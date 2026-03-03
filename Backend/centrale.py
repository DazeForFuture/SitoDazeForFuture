from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
import time
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

sensor_readings = []
ultima_temperatura = None  
ultima_umidita = None

def aggiorna_file():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(base_dir, '..', '..', 'database')
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, 'centrale.dat')
    
    lines = ["=== DATI CENTRALE METEOROLOGICA ===\n"]
    lines.append(f"Totale letture: {len(sensor_readings)}")
    lines.append(f"Ultimo aggiornamento: {sensor_readings[-1]['timestamp'] if sensor_readings else 'Nessun dato'}\n")
    lines.append("-" * 50)
    lines.append(f"{'TIMESTAMP':<25} {'TEMPERATURA':<12} {'UMIDITA':<10}")
    lines.append("-" * 50)
    
    for reading in sensor_readings:
        timestamp = reading['timestamp']
        temperatura = f"{reading['temperature']} °C"
        umidita = f"{reading['humidity']} %"
        lines.append(f"{timestamp:<25} {temperatura:<12} {umidita:<10}")
    
    lines.append("-" * 50)
    lines.append(f"Fine report - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    content = "\n".join(lines)
    f = open(file_path, 'w', encoding='utf-8')
    f.write(content)
    f.close()

@app.route('/sensor', methods=['GET'])
def get_sensor_data():
    if ultima_temperatura is None or ultima_umidita is None:
        return jsonify({
            "error": "Nessun dato disponibile",
            "method": "none"
        }), 404
    
    return jsonify({
        "reading": {
            "temperature": ultima_temperatura,
            "humidity": ultima_umidita,
            "timestamp": datetime.now().isoformat()
        },
        "method": "latest"
    })

@app.route('/update', methods=['GET'])
def update_sensor():
    global ultima_temperatura, ultima_umidita

    temp = request.args.get('temp')
    hum = request.args.get('hum')

    if temp is None or hum is None:
        return "Parametri mancanti", 400

    ultima_temperatura = float(temp)
    ultima_umidita = float(hum)

    reading = {
        "temperature": ultima_temperatura,
        "humidity": ultima_umidita,
        "timestamp": datetime.now().isoformat()
    }
    sensor_readings.append(reading)

    if len(sensor_readings) > 1000:
        sensor_readings.pop(0)

    aggiorna_file()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Temperatura: {ultima_temperatura} °C | Umidità: {ultima_umidita} %")

    return "Dati ricevuti", 200

@app.route('/history', methods=['GET'])
def get_history():
    hours = int(request.args.get('hours', 24))
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    recent_readings = [
        reading for reading in sensor_readings
        if datetime.fromisoformat(reading['timestamp']) >= cutoff_time
    ]
    
    return jsonify({
        "readings": recent_readings,
        "count": len(recent_readings)
    })

@app.route('/stream')
def stream():
    def event_stream():
        last_id = 0
        while True:
            if ultima_temperatura is not None and ultima_umidita is not None:
                data = {
                    "id": last_id,
                    "type": "reading",
                    "payload": {
                        "temperature": ultima_temperatura,
                        "humidity": ultima_umidita,
                        "timestamp": datetime.now().isoformat(),
                        "source": "sse"
                    }
                }
                
                yield f"data: {json.dumps(data)}\n\n"
                last_id += 1
            
            time.sleep(30)
    
    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
    )

@app.route('/')
def index():
    return jsonify({
        "name": "Centrale Meteorologica API",
        "version": "1.0",
        "endpoints": {
            "/sensor": "Ultima lettura",
            "/update": "Ricevi nuovi dati (GET con param temp, hum)",
            "/history": "Dati storici (param hours)",
            "/stream": "Streaming dati in tempo reale (SSE)"
        },
        "status": {
            "has_data": ultima_temperatura is not None and ultima_umidita is not None,
            "temperature": ultima_temperatura,
            "humidity": ultima_umidita,
            "last_update": sensor_readings[-1]['timestamp'] if sensor_readings else None,
            "total_readings": len(sensor_readings)
        }
    })

@app.route('/status', methods=['GET'])
def status():
    if ultima_temperatura is None or ultima_umidita is None:
        return jsonify({
            "error": "Nessun dato ricevuto ancora"
        }), 404
    
    return jsonify({
        "temperatura": ultima_temperatura,
        "umidita": ultima_umidita
    })

@app.route('/visualizza', methods=['GET'])
def visualizza_dati():
    lines = ["=== DATI CENTRALE METEOROLOGICA ===\n"]
    lines.append(f"Totale letture: {len(sensor_readings)}")
    lines.append(f"Ultimo aggiornamento: {sensor_readings[-1]['timestamp'] if sensor_readings else 'Nessun dato'}\n")
    lines.append("-" * 50)
    lines.append(f"{'TIMESTAMP':<25} {'TEMPERATURA':<12} {'UMIDITA':<10}")
    lines.append("-" * 50)
    
    for reading in sensor_readings:
        timestamp = reading['timestamp']
        temperatura = f"{reading['temperature']} °C"
        umidita = f"{reading['humidity']} %"
        lines.append(f"{timestamp:<25} {temperatura:<12} {umidita:<10}")
    
    lines.append("-" * 50)
    lines.append(f"Fine report - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    content = "\n".join(lines)
    
    return Response(
        content,
        mimetype="text/plain",
        headers={
            "Content-Type": "text/plain; charset=utf-8"
        }
    )

@app.route('/salva', methods=['GET'])
def salva_dati():
    aggiorna_file()
    return Response("File aggiornato", mimetype="text/plain")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=True)