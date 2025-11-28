"""
app.py
Flask backend to receive data from Arduino and provide realtime updates to the frontend.
Features:
 - /update?t=<temp>&h=<hum>   -> Arduino (GET) sends measurements here
 - /latest                    -> returns the most recent reading as JSON
 - /history?limit=N           -> returns last N readings as JSON
 - /stream                    -> Server-Sent Events (SSE) stream for realtime updates to the frontend
 - Serves static files from ./static (so you can drop your HTML/CSS/JS there)

Server defaults to host=0.0.0.0 port=8080 to match your Arduino sketch.
Stores data in a lightweight SQLite DB (file: readings.db) and keeps an in-memory notify system
for SSE clients.
"""

from flask import Flask, request, jsonify, Response, send_from_directory, abort
from flask_cors import CORS
import sqlite3
import threading
import time
import json
from datetime import datetime
import queue

DB_FILE = 'readings.db'

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # allow frontend to fetch API from different origin if needed

# --- Database helpers ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def insert_reading(temperature, humidity, ts=None):
    ts = ts or datetime.utcnow().isoformat() + 'Z'
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('INSERT INTO readings (timestamp, temperature, humidity) VALUES (?, ?, ?)', (ts, temperature, humidity))
    conn.commit()
    conn.close()
    return {'timestamp': ts, 'temperature': temperature, 'humidity': humidity}

def get_latest_reading():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('SELECT timestamp, temperature, humidity FROM readings ORDER BY id DESC LIMIT 1')
    row = cur.fetchone()
    conn.close()
    if row:
        return {'timestamp': row[0], 'temperature': row[1], 'humidity': row[2]}
    return None

def get_history(limit=100):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('SELECT timestamp, temperature, humidity FROM readings ORDER BY id DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{'timestamp': r[0], 'temperature': r[1], 'humidity': r[2]} for r in rows]

# --- SSE / notifier ---
# Simple pub-sub: each connected SSE client gets its own Queue
clients = set()
clients_lock = threading.Lock()

def push_event(data: dict):
    text = 'data: ' + json.dumps(data) + '\n\n'
    with clients_lock:
        dead = []
        for q in list(clients):
            try:
                q.put_nowait(text)
            except Exception:
                dead.append(q)
        for d in dead:
            try:
                clients.remove(d)
            except KeyError:
                pass

@app.route('/stream')
def stream():
    def gen(q: queue.Queue):
        try:
            # on connect, send the latest reading immediately
            latest = get_latest_reading()
            if latest:
                q.put_nowait('data: ' + json.dumps({'type': 'initial', 'payload': latest}) + '\n\n')

            while True:
                # block until next item is available
                msg = q.get()
                yield msg
        except GeneratorExit:
            # client disconnected
            pass

    q = queue.Queue()
    with clients_lock:
        clients.add(q)
    return Response(gen(q), mimetype='text/event-stream')

# --- API endpoints ---
@app.route('/update', methods=['GET', 'POST'])
def update():
    # Accept both GET (from your Arduino) and POST (from other producers)
    # Query params: t, h (temperature, humidity). Accept also 'ts' optional ISO timestamp.
    if request.method == 'GET':
        t = request.args.get('t')
        h = request.args.get('h')
        ts = request.args.get('ts')
    else:
        data = request.get_json(silent=True) or {}
        t = data.get('t') or request.form.get('t')
        h = data.get('h') or request.form.get('h')
        ts = data.get('ts') or request.form.get('ts')

    if t is None or h is None:
        return jsonify({'error': 'Missing parameters t (temperature) and h (humidity)'}), 400

    try:
        temp = float(t)
        hum = float(h)
    except ValueError:
        return jsonify({'error': 'Invalid numeric format for t or h'}), 400

    record = insert_reading(temp, hum, ts)

    # notify SSE clients
    push_event({'type': 'reading', 'payload': record})

    return jsonify({'status': 'ok', 'reading': record})

@app.route('/latest', methods=['GET'])
def latest():
    r = get_latest_reading()
    if not r:
        return jsonify({'error': 'no data yet'}), 404
    return jsonify(r)

@app.route('/history', methods=['GET'])
def history():
    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        limit = 100
    data = get_history(limit)
    return jsonify({'count': len(data), 'readings': data})

# Serve frontend static files
# Place your provided HTML/CSS/JS files inside a directory named 'static'.
@app.route('/')
def index():
    try:
        return send_from_directory(app.static_folder, 'centrale_meteo.html')
    except Exception:
        # fallback to any index if present
        try:
            return send_from_directory(app.static_folder, 'index.html')
        except Exception:
            return "Static files not found. Put your frontend files in the ./static folder.", 404

# Allow downloading DB for debugging (optional)
@app.route('/download-db')
def download_db():
    # remove or protect this endpoint in production!
    try:
        return send_from_directory('.', DB_FILE, as_attachment=True)
    except Exception:
        abort(404)

if __name__ == '__main__':
    init_db()
    # Default host and port match your Arduino configuration (server=192.168.50.1 ; port=8080)
    # Run with: python app.py
    app.run(host='0.0.0.0', port=8080, threaded=True)


# requirements.txt
# ----------------
# Flask
# flask-cors


# README.md
# ---------
# Quick setup:
# 1) Put your frontend files (the HTML you shared) in a folder named `static` and rename the main file to `centrale_meteo.html` or `index.html`.
# 2) Create a Python virtualenv and install requirements:
#    python -m venv venv
#    source venv/bin/activate   # on Windows: venv\Scripts\activate
#    pip install Flask flask-cors
# 3) Run the server:
#    python app.py
# 4) Configure your Arduino sketch: change `server = "192.168.50.1"` to the server IP of the machine running this Flask app (or keep 192.168.50.1 if you assign that IP to the host).
#    Keep `port = 8080` (or adjust app.run port accordingly).
# 5) Frontend realtime update options:
#    - Polling: your frontend can periodically GET /latest or /history
#    - SSE: connect to `/stream` as an EventSource to receive new readings in real time.

# Example SSE usage in the browser (JS):
# const es = new EventSource('/stream');
# es.onmessage = (e) => { const d = JSON.parse(e.data); console.log('sse', d); }

# Security notes:
# - This example is intentionally simple for local network use. Do not expose it to the public internet without adding auth and HTTPS.
# - Consider adding an API key or basic auth to /update if you want to prevent unauthorized data injection.
