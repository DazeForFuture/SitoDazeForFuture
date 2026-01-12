from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json
import time
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Permette richieste dal frontend

# Database in memoria per i dati storici
sensor_readings = []
ultima_temperatura = None  # Nessun valore iniziale
ultima_umidita = None

@app.route('/sensor', methods=['GET'])
def get_sensor_data():
    """Restituisce l'ultima lettura del sensore"""
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
        
        # Se non ci sono letture, restituisci array vuoto
        if not recent_readings:
            print(f"Nessun dato disponibile per le ultime {hours} ore")
        
        return jsonify({
            "readings": recent_readings,
            "count": len(recent_readings)
        })
    except Exception as e:
        print(f"Errore in /history: {e}")
        return jsonify({"readings": [], "count": 0})

@app.route('/stream')
def stream():
    """Server-Sent Events per aggiornamenti in tempo reale"""
    def event_stream():
        last_id = 0
        while True:
            # Invia dati solo se disponibili
            if ultima_temperatura is not None and ultima_umidita is not None:
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
            
            # Aspetta 30 secondi prima del prossimo invio
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
            "has_data": ultima_temperatura is not None and ultima_umidita is not None,
            "temperature": ultima_temperatura,
            "humidity": ultima_umidita,
            "last_update": sensor_readings[-1]['timestamp'] if sensor_readings else None,
            "total_readings": len(sensor_readings)
        }
    })

@app.route('/status', methods=['GET'])
def status():
    """Compatibilità con vecchio endpoint"""
    if ultima_temperatura is None or ultima_umidita is None:
        return jsonify({
            "error": "Nessun dato ricevuto ancora"
        }), 404
    
    return jsonify({
        "temperatura": ultima_temperatura,
        "umidita": ultima_umidita
    })

if __name__ == '__main__':
    print("=" * 50)
    print("Centrale Meteorologica API")
    print("=" * 50)
    print("Server in esecuzione su: http://localhost:8888")
    print("Endpoint disponibili:")
    print("  GET /                - Informazioni API")
    print("  GET /sensor          - Ultima lettura")
    print("  GET /update?temp=X&hum=Y - Invia nuovi dati")
    print("  GET /history?hours=N - Dati storici")
    print("  GET /stream          - Streaming live (SSE)")
    print("  GET /status          - Status compatibilità")
    print("=" * 50)
    print("NOTA: Nessun dato mock generato. Aspettando dati dal sensore...")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=8888, debug=True)