#!/usr/bin/env python3
"""
Backend Flask per letture DHT11 (Arduino R4).
- Crea automaticamente il DB SQLite (e la cartella se necessario).
- Endpoint /update (GET/POST) per ricevere dati via WiFi (o qualsiasi producer HTTP).
- Lettura seriale opzionale (USB) in thread separato.
- Endpoint /sensor preferisce WiFi se recente (WIFI_FRESH_MS), altrimenti usa USB o DB.
- SSE su /stream per aggiornamenti in tempo reale.
"""
import os
import json
import time
import queue
import threading
import sqlite3
import logging
import hmac
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from config import BaseConfig, require_secrets
from logging.handlers import RotatingFileHandler
from security import validate_range, secure_compare_api_keys
from serial import Serial
from serial.tools.list_ports import comports
from html import escape
import re

# --- Config (modificabili via env) ---
DB_FILE = os.environ.get('DB_FILE', '../../database/daticentrale.db')
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '5005'))

SERIAL_ENABLE = os.environ.get('ENABLE_SERIAL', 'true').lower() not in ('0', 'false', 'no')
SERIAL_PATH = os.environ.get('SERIAL_PATH', '')  # se vuoto, prova autodetect
SERIAL_BAUD = int(os.environ.get('SERIAL_BAUD', '115200'))

WIFI_FRESH_MS = int(os.environ.get('WIFI_FRESH_MS', str(60 * 1000)))  # prefer WiFi se entro questo ms
API_KEY = os.environ.get('API_KEY')  # opzionale

# --- Optional pyserial import (non obbligatorio) ---
try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

# --- App setup ---
app = Flask(__name__, static_folder='static', static_url_path='')
app.config.from_object(BaseConfig)
CORS(app)

# Rate Limiter setup
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Security Headers with Talisman
Talisman(
    app,
    force_https=True,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    content_security_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'"],
    }
)

# Setup logging
if not app.debug:
    handler = RotatingFileHandler('centrale.log', maxBytes=10*1024*1024, backupCount=5)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

# --- In-memory latest caches e SSE clients ---
latestWiFi = None
latestUSB = None
clients = set()
clients_lock = threading.Lock()

# --- Utility: assicurati che la cartella DB esista e crea DB e tabella ---
def ensure_db_and_dirs(db_path: str):
    p = Path(db_path)
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    # Create DB file and table if not exists
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            source TEXT,
            raw TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_conn():
    # ogni chiamata apre una nuova connessione: pattern sicuro per multi-thread con sqlite
    return sqlite3.connect(DB_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

# --- DB helpers ---
def insert_reading(temperature, humidity, ts=None, source=None, raw=None):
    ts = ts or datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT INTO readings (timestamp, temperature, humidity, source, raw) VALUES (?, ?, ?, ?, ?)',
                (ts, temperature, humidity, source, json.dumps(raw) if raw is not None else None))
    conn.commit()
    conn.close()
    return {'timestamp': ts, 'temperature': temperature, 'humidity': humidity, 'source': source, 'raw': raw}

def get_latest_reading_from_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT timestamp, temperature, humidity, source, raw FROM readings ORDER BY id DESC LIMIT 1')
    row = cur.fetchone()
    conn.close()
    if row:
        raw = None
        try:
            raw = json.loads(row[4]) if row[4] else None
        except Exception:
            raw = row[4]
        return {'timestamp': row[0], 'temperature': row[1], 'humidity': row[2], 'source': row[3], 'raw': raw}
    return None

def get_history(limit=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT timestamp, temperature, humidity, source FROM readings ORDER BY id DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{'timestamp': r[0], 'temperature': r[1], 'humidity': r[2], 'source': r[3]} for r in rows]

# --- SSE pubsub ---
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
            clients.discard(d)

@app.route('/stream')
def stream():
    def gen(q: queue.Queue):
        try:
            latest = get_latest_reading_from_db()
            if latest:
                q.put_nowait('data: ' + json.dumps({'type': 'initial', 'payload': latest}) + '\n\n')
            while True:
                msg = q.get()
                yield msg
        except GeneratorExit:
            pass

    q = queue.Queue()
    with clients_lock:
        clients.add(q)
    return Response(gen(q), mimetype='text/event-stream')

# --- Helpers for validation and API key ---
def require_api_key():
    """Valida API key in modo sicuro"""
    if not API_KEY:
        return False  # Nega se non configurato
    
    # Solo da header, mai da query string
    key = request.headers.get('X-API-Key')
    if not key:
        return False
    
    # Confronto sicuro (timing-safe)
    return secure_compare_api_keys(key, API_KEY)


def is_valid_range(temp: float, hum: float) -> bool:
    """
    Valida che temperatura e umidità siano in range plausibili.
    Temperatura: -50 a 80°C (per DHT11 e ambienti)
    Umidità: 0 a 100%
    """
    try:
        temp_f = float(temp)
        hum_f = float(hum)
        return (-50 <= temp_f <= 80) and (0 <= hum_f <= 100)
    except (TypeError, ValueError):
        return False

# Usa il decorator
from functools import wraps

def require_valid_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not require_api_key():
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/update', methods=['GET', 'POST'])
@limiter.limit("30 per hour")
@require_valid_api_key
def update_sensor():
    # Accept both GET (querystring) and POST (json/form)
    if request.method == 'GET':
        t = request.args.get('t')
        h = request.args.get('h')
        ts = request.args.get('ts')
        source = request.args.get('source', 'wifi')
        raw = dict(request.args)
    else:
        data = request.get_json(silent=True) or {}
        t = data.get('t') or data.get('temp') or request.form.get('t')
        h = data.get('h') or data.get('hum') or request.form.get('h')
        ts = data.get('ts') or request.form.get('ts')
        source = data.get('source') or request.form.get('source') or 'wifi'
        raw = data if isinstance(data, dict) and data else request.form.to_dict()

    if t is None or h is None:
        return jsonify({'error': 'Missing parameters t (temperature) and h (humidity)'}), 400

    try:
        temp = float(t)
        hum = float(h)
    except ValueError:
        return jsonify({'error': 'Invalid numeric format for t or h'}), 400

    if not is_valid_range(temp, hum):
        return jsonify({'error': 'Reading out of plausible range'}), 400

    rec = insert_reading(temp, hum, ts, source=source, raw=raw)

    # Update in-memory latest
    global latestWiFi, latestUSB
    if source and 'usb' in source.lower():
        latestUSB = rec
    else:
        latestWiFi = rec

    # Notify SSE clients
    push_event({'type': 'reading', 'payload': rec})

    return jsonify({'status': 'ok', 'reading': rec})

@app.route('/sensor', methods=['GET'])
def sensor():
    """
    Prefer WiFi if recent (WIFI_FRESH_MS), else USB, else DB latest.
    """
    now_ms = int(time.time() * 1000)
    chosen = None
    method = None

    if latestWiFi:
        try:
            ts = int(datetime.fromisoformat(latestWiFi['timestamp']).replace(tzinfo=timezone.utc).timestamp() * 1000)
        except Exception:
            ts = now_ms
        if now_ms - ts <= WIFI_FRESH_MS:
            chosen = latestWiFi
            method = 'wifi'

    if not chosen and latestUSB:
        chosen = latestUSB
        method = 'usb'

    if not chosen:
        db_latest = get_latest_reading_from_db()
        if db_latest:
            chosen = db_latest
            method = db_latest.get('source') or 'db'

    if not chosen:
        return jsonify({'error': 'no data available'}), 404

    return jsonify({'method': method, 'reading': chosen})

@app.route('/latest', methods=['GET'])
@limiter.limit("60 per hour")
def latest():
    r = get_latest_reading_from_db()
    if not r:
        return jsonify({'error': 'no data yet'}), 404
    return jsonify(r)

@app.route('/history', methods=['GET'])
@limiter.limit("30 per hour")
def history():
    try:
        limit = int(request.args.get('limit', 100))
    except Exception:
        limit = 100
    return jsonify({'count': len(get_history(limit)), 'readings': get_history(limit)})

# Serve frontend static if exists
@app.route('/')
def index():
    try:
        return send_from_directory(app.static_folder, 'centrale_meteo.html')
    except Exception:
        try:
            return send_from_directory(app.static_folder, 'index.html')
        except Exception:
            return "Static files not found. Put your frontend files in the ./static folder.", 404

# --- Serial reader (optional) ---
def auto_detect_serial_port():
    if not list_ports:
        return None
    ports = list_ports.comports()
    # try common Arduino-ish names first
    candidates = []
    for p in ports:
        dev = p.device or ''
        desc = p.description or ''
        if 'Arduino' in desc or 'ttyACM' in dev or 'ttyUSB' in dev or 'USB Serial' in desc or 'COM' in dev:
            candidates.append(dev)
    if candidates:
        return candidates[0]
    if ports:
        return ports[0].device
    return None

def start_serial_thread(path: str, baud: int):
    if not serial:
        app.logger.warning('pyserial non installato: lettura serial disabilitata')
        return None

    def reader_loop(path, baud):
        global latestUSB
        while True:
            try:
                ser = serial.Serial(path, baud, timeout=1)
                app.logger.info(f'Seriale aperta {path} @ {baud}')
                buf = ''
                while True:
                    chunk = ser.read(ser.in_waiting or 1)
                    if not chunk:
                        time.sleep(0.05)
                        continue
                    try:
                        s = chunk.decode('utf-8', errors='replace')
                    except Exception:
                        s = str(chunk)
                    buf += s
                    while '\n' in buf:
                        line, buf = buf.split('\n', 1)
                        line = line.strip()
                        if not line:
                            continue
                        parsed = None
                        try:
                            parsed = json.loads(line)
                        except Exception:
                            txt = line.replace('TEMP:', '').replace('temp:', '').replace('HUM:', '').replace('hum:', '')
                            parts = [p.strip() for p in txt.replace(';', ',').split(',') if p.strip()]
                            if len(parts) >= 2:
                                try:
                                    parsed = {'t': float(parts[0]), 'h': float(parts[1])}
                                except Exception:
                                    parsed = None
                        if parsed:
                            t = parsed.get('t') or parsed.get('temp') or parsed.get('temperature')
                            h = parsed.get('h') or parsed.get('hum') or parsed.get('humidity')
                            if t is None or h is None:
                                app.logger.warning(f'Linea serial parsata ma mancano t/h: {parsed}')
                                continue
                            try:
                                temp = float(t); hum = float(h)
                            except Exception:
                                app.logger.warning(f'Numerico invalido da serial: {line}')
                                continue
                            if not is_valid_range(temp, hum):
                                app.logger.warning(f'Valori serial fuori range: {temp},{hum}')
                                continue
                            rec = insert_reading(temp, hum, source='usb', raw=line)
                            latestUSB = rec
                            push_event({'type': 'reading', 'payload': rec})
                            app.logger.info(f'[USB] {temp}C {hum}%')
                        else:
                            app.logger.debug(f'Linea serial non parsata: {line}')
            except Exception as e:
                app.logger.error(f'Errore serial reader: {e}')
                time.sleep(2)
                # riprova

    th = threading.Thread(target=reader_loop, args=(path, baud), daemon=True)
    th.start()
    return th

# --- Avvio app ---
if __name__ == '__main__':
    ensure_db_and_dirs(DB_FILE)

    # Inizializza eventuale lettura serial
    if SERIAL_ENABLE:
        if SERIAL_PATH:
            ser_path = SERIAL_PATH
        else:
            ser_path = auto_detect_serial_port()
        if ser_path:
            start_serial_thread(ser_path, SERIAL_BAUD)
        else:
            app.logger.warning('Serial enabled ma nessuna porta trovata. Imposta SERIAL_PATH per forzare una porta.')

    # IMPORTANT: debug=False for security. Use Gunicorn in production.
    app.run(host=HOST, port=PORT, threaded=True, debug=False)

# Valida formato data
def validate_date(date_str):
    try:
        datetime.fromisoformat(date_str)
        return True
    except:
        return False

# Sanitizza input
def sanitize_text(text, max_length=1000):
    if not isinstance(text, str):
        return None
    text = text.strip()
    if len(text) > max_length:
        return None
    # Escape HTML per evitare XSS
    return escape(text)

@app.route('/api/post', methods=['POST'])
def crea_post():
    data = request.json
    
    # Validazione e sanitizzazione
    titolo = sanitize_text(data.get('titolo'), 200)
    contenuto = sanitize_text(data.get('contenuto'), 5000)
    
    if not titolo or not contenuto:
        return jsonify({'success': False, 'message': 'Input non valido'}), 400
    
    # Valida data se presente
    data_evento = data.get('data')
    if data_evento and not validate_date(data_evento):
        return jsonify({'success': False, 'message': 'Data non valida'}), 400
    
    # ... rest della logica
