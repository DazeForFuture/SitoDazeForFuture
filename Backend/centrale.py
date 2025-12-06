# backend.py
import serial
import serial.tools.list_ports
import time
import threading
import json
import sqlite3
import re
from datetime import datetime
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import queue

app = Flask(__name__)
CORS(app)  # Abilita CORS per tutte le rotte

# Configurazione
SERIAL_PORT = None
BAUD_RATE = 9600
ser = None
data_queue = queue.Queue()
latest_data = {"temperature": None, "humidity": None, "timestamp": None, "source": "usb"}
db_lock = threading.Lock()
arduino_connected = False

# Database per memorizzare le letture
def init_db():
    with db_lock:
        conn = sqlite3.connect('../../database/sensor_data.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS readings
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      temperature REAL,
                      humidity REAL,
                      source TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()

def save_to_db(temp, hum, source="usb"):
    with db_lock:
        conn = sqlite3.connect('../../database/sensor_data.db')
        c = conn.cursor()
        c.execute("INSERT INTO readings (temperature, humidity, source) VALUES (?, ?, ?)",
                  (temp, hum, source))
        conn.commit()
        conn.close()

def get_recent_readings(limit=50):
    with db_lock:
        conn = sqlite3.connect('../../database/sensor_data.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT temperature, humidity, source, timestamp FROM readings ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        
        readings = []
        for row in rows:
            readings.append({
                "temperature": row["temperature"],
                "humidity": row["humidity"],
                "source": row["source"],
                "timestamp": row["timestamp"]
            })
        return readings[::-1]

# Funzione per trovare Arduino
def find_arduino():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if ("Arduino" in port.description or 
            "ttyACM" in port.device or 
            "ttyUSB" in port.device or
            "CH340" in port.description or
            "USB Serial" in port.description):
            print(f"Trovata porta: {port.device} - {port.description}")
            return port.device
    return None

# Funzione per processare la linea ricevuta
def process_serial_line(line):
    """Processa una linea ricevuta dalla seriale e estrae temperatura e umidità."""
    line = line.strip()
    
    # Se è un messaggio di stato, ignoralo ma stampalo
    if "Connesso" in line or "connesso" in line.lower():
        print(f"Messaggio Arduino: {line}")
        return None, None, line
    
    # Se è un messaggio di errore
    if "errore" in line.lower():
        print(f"Errore Arduino: {line}")
        return None, None, line
    
    # Prova a estrarre numeri dalla stringa usando regex
    # Cerca pattern come: 22.5,45.0 oppure Temp:22.5,Hum:45.0
    numbers = re.findall(r'[-+]?\d*\.\d+|\d+', line)
    
    if len(numbers) >= 2:
        try:
            temp = float(numbers[0])
            hum = float(numbers[1])
            return temp, hum, None
        except ValueError:
            print(f"Non posso convertire i numeri: {numbers}")
            return None, None, line
    else:
        print(f"Stringa non riconosciuta: {line}")
        return None, None, line

# Funzione per leggere dalla seriale
def read_serial():
    global ser, latest_data, arduino_connected
    
    while True:
        try:
            if ser and ser.is_open:
                line = ser.readline().decode('utf-8', errors='ignore')
                if line:
                    # Processa la linea
                    temp, hum, message = process_serial_line(line)
                    
                    if temp is not None and hum is not None:
                        # Dati validi ricevuti
                        latest_data = {
                            "temperature": temp,
                            "humidity": hum,
                            "timestamp": datetime.now().isoformat(),
                            "source": "usb"
                        }
                        
                        # Salva nel database
                        save_to_db(temp, hum, "usb")
                        
                        # Metti in coda per gli eventi SSE
                        data_queue.put({
                            "type": "reading",
                            "payload": latest_data
                        })
                        
                        print(f"Dati ricevuti: Temperatura: {temp}°C, Umidità: {hum}%")
                    
                    elif message:
                        # Messaggio di stato o errore
                        if "errore" in message.lower():
                            data_queue.put({
                                "type": "error",
                                "payload": {"message": message}
                            })
                        else:
                            # Invia anche i messaggi di stato via SSE
                            data_queue.put({
                                "type": "status",
                                "payload": {"message": message}
                            })
            else:
                time.sleep(5)
                try_connect_arduino()
                
        except serial.SerialException as e:
            print(f"Errore di comunicazione seriale: {e}")
            arduino_connected = False
            if ser:
                try:
                    ser.close()
                except:
                    pass
            time.sleep(5)
            try_connect_arduino()
            
        except Exception as e:
            print(f"Errore generico nella lettura seriale: {e}")
            time.sleep(2)

# Funzione per connettersi ad Arduino
def try_connect_arduino():
    global ser, SERIAL_PORT, arduino_connected
    
    if not SERIAL_PORT:
        SERIAL_PORT = find_arduino()
    
    if SERIAL_PORT:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            arduino_connected = True
            
            # Pulisci il buffer seriale
            ser.reset_input_buffer()
            
            print(f"✓ Connesso a Arduino su porta: {SERIAL_PORT}")
            
            data_queue.put({
                "type": "connection",
                "payload": {"connected": True, "port": SERIAL_PORT, "message": "Arduino connesso"}
            })
            
            return True
        except Exception as e:
            print(f"✗ Errore connessione: {e}")
            arduino_connected = False
            data_queue.put({
                "type": "connection",
                "payload": {"connected": False, "message": f"Errore: {e}"}
            })
            return False
    else:
        print("✗ Arduino non trovato")
        arduino_connected = False
        return False

# Funzione per gestire eventi SSE
def event_stream():
    while True:
        try:
            try:
                data = data_queue.get(timeout=30)
                yield f"data: {json.dumps(data)}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"
        except Exception as e:
            print(f"Errore SSE: {e}")
            time.sleep(1)

# API endpoints
@app.route('/sensor')
def get_sensor_data():
    if latest_data["temperature"] is not None:
        return jsonify({
            "reading": latest_data,
            "method": "usb",
            "arduino_connected": arduino_connected,
            "status": "ok"
        })
    else:
        recent = get_recent_readings(limit=1)
        if recent:
            return jsonify({
                "reading": recent[0],
                "method": "db",
                "arduino_connected": arduino_connected,
                "status": "historical"
            })
        return jsonify({
            "error": "In attesa di dati dal sensore...",
            "arduino_connected": arduino_connected,
            "status": "waiting"
        })

@app.route('/history')
def get_history():
    limit = request.args.get('limit', default=50, type=int)
    readings = get_recent_readings(limit)
    return jsonify({
        "readings": readings,
        "arduino_connected": arduino_connected,
        "count": len(readings)
    })

@app.route('/stream')
def stream():
    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/status')
def system_status():
    status = {
        "arduino_connected": arduino_connected,
        "serial_port": SERIAL_PORT if arduino_connected else None,
        "latest_data": latest_data,
        "queue_size": data_queue.qsize(),
        "timestamp": datetime.now().isoformat(),
        "status": "connected" if arduino_connected else "disconnected"
    }
    return jsonify(status)

@app.route('/')
def index():
    return jsonify({
        "name": "Centrale Meteorologica Backend",
        "version": "1.0",
        "endpoints": {
            "/sensor": "Dati correnti sensore",
            "/history": "Dati storici (?limit=N)",
            "/stream": "Stream in tempo reale (SSE)",
            "/status": "Stato sistema"
        },
        "arduino_connected": arduino_connected
    })

if __name__ == '__main__':
    # Inizializzazione
    print("="*60)
    print("BACKEND CENTRALE METEOROLOGICA")
    print("="*60)
    
    init_db()
    
    recent = get_recent_readings(limit=1)
    if recent:
        latest_data.update(recent[0])
        print(f"Caricati dati storici: {latest_data}")
    
    print("\nRicerca Arduino...")
    if try_connect_arduino():
        serial_thread = threading.Thread(target=read_serial, daemon=True)
        serial_thread.start()
        print("✓ Lettura seriale attiva")
    else:
        print("⚠  Arduino non trovato - Modalità solo storico")
    
    print("\n" + "="*60)
    print("SERVER IN ASCOLTO SU http://localhost:5005")
    print(f"Arduino: {'✓ CONNESSO' if arduino_connected else '✗ NON CONNESSO'}")
    print(f"Porta: {SERIAL_PORT or 'N/A'}")
    print("="*60 + "\n")
    
    try:
        app.run(host='0.0.0.0', port=5005, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nChiusura in corso...")
        if ser and ser.is_open:
            ser.close()
