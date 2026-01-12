from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
import time
from datetime import datetime, timedelta
import random

app = Flask(__name__)
CORS(app)  # Permette richieste dal frontend

# Database in memoria per i dati storici
sensor_readings = []
ultima_temperatura = 22.5  # Valore iniziale
ultima_umidita = 65.0  # Valore iniziale

@app.route('/sensor', methods=['GET'])
def get_sensor_data():
    """Restituisce l'ultima lettura del sensore"""
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
    """Endpoint per ricevere dati dal sensore fisico"""
    global ultima_temperatura, ultima_umidita

    # Legge i parametri GET
    temp = request.args.get('temp')
    hum = request.args.get('hum')

    if temp is None or hum is None:
        return "Parametri mancanti", 400

    try:
        # Salva valori globali
        ultima_temperatura = float(temp)
        ultima_umidita = float(hum)

        # Aggiungi alla cronologia
        reading = {
            "temperature": ultima_temperatura,
            "humidity": ultima_umidita,
            "timestamp": datetime.now().isoformat()
        }
        sensor_readings.append(reading)

        # Mantieni solo le ultime 1000 letture
        if len(sensor_readings) > 1000:
            sensor_readings.pop(0)

        # Stampa sul terminale
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Temperatura: {ultima_temperatura} °C | Umidità: {ultima_umidita} %")

        return "Dati ricevuti", 200
    except ValueError:
        return "Valori non validi", 400

@app.route('/history', methods=['GET'])
def get_history():
    """Restituisce i dati storici per un certo periodo"""
    try:
        hours = int(request.args.get('hours', 24))
        
        # Calcola la data limite
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filtra le letture recenti
        recent_readings = [
            reading for reading in sensor_readings
            if datetime.fromisoformat(reading['timestamp']) >= cutoff_time
        ]
        
        # Se non ci sono letture reali, genera dati di esempio
        if not recent_readings:
            recent_readings = generate_mock_data(hours)
        
        return jsonify({
            "readings": recent_readings,
            "count": len(recent_readings)
        })
    except Exception as e:
        print(f"Errore in /history: {e}")
        return jsonify({"readings": [], "count": 0})

def generate_mock_data(hours=24):
    """Genera dati di esempio per il grafico"""
    data = []
    now = datetime.now()
    
    for i in range(hours * 2):  # Un punto ogni 30 minuti
        timestamp = now - timedelta(hours=hours) + timedelta(minutes=30 * i)
        
        # Variazioni realistiche di temperatura e umidità
        base_temp = 22.0 + random.uniform(-1, 1)
        base_hum = 65.0 + random.uniform(-5, 5)
        
        # Simula variazioni giornaliere
        hour = timestamp.hour
        if 14 <= hour <= 16:  # Pomeriggio più caldo
            temp_variation = random.uniform(2, 4)
            hum_variation = random.uniform(-10, -5)
        elif 2 <= hour <= 4:  # Notte più fresca
            temp_variation = random.uniform(-3, -1)
            hum_variation = random.uniform(5, 10)
        else:
            temp_variation = random.uniform(-1, 1)
            hum_variation = random.uniform(-2, 2)
        
        data.append({
            "temperature": round(base_temp + temp_variation, 1),
            "humidity": round(base_hum + hum_variation, 1),
            "timestamp": timestamp.isoformat()
        })
    
    return data

@app.route('/stream')
def stream():
    """Server-Sent Events per aggiornamenti in tempo reale"""
    def event_stream():
        last_id = 0
        while True:
            # Invia dati ogni 30 secondi
            time.sleep(30)
            
            # Crea evento SSE
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
    """Pagina principale dell'API"""
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
            "temperature": ultima_temperatura,
            "humidity": ultima_umidita,
            "last_update": datetime.now().isoformat() if sensor_readings else None,
            "readings_count": len(sensor_readings)
        }
    })

@app.route('/status', methods=['GET'])
def status():
    """Compatibilità con vecchio endpoint"""
    return jsonify({
        "temperatura": ultima_temperatura,
        "umidita": ultima_umidita
    })

if __name__ == '__main__':
    print("=" * 50)
    print("Centrale Meteorologica API")
    print("=" * 50)
    print(f"Server in esecuzione su: http://localhost:8888")
    print(f"Endpoint disponibili:")
    print(f"  GET /                - Informazioni API")
    print(f"  GET /sensor          - Ultima lettura")
    print(f"  GET /update?temp=X&hum=Y - Invia nuovi dati")
    print(f"  GET /history?hours=N - Dati storici")
    print(f"  GET /stream          - Streaming live (SSE)")
    print(f"  GET /status          - Status compatibilità")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=8888, debug=True)