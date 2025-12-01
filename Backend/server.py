import os
import sqlite3
import logging
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt  # PyJWT

# SECURITY: use environment variables for secrets
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', None)
JWT_SECRET = os.environ.get('JWT_SECRET', os.environ.get('SECRET_KEY', None))

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
static_dir = os.path.join(frontend_dir, 'css')
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
cors_origins = os.environ.get('CORS_ORIGINS', '*')
CORS(app, supports_credentials=True, resources={r"/*": {"origins": cors_origins}})
# SECURITY: flask secret from env
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.environ.get('SECRET_KEY', os.urandom(32)))
logging.basicConfig(level=logging.INFO)

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/utenti.db'))

# SECURITY: environment based secret. Fail fast if not set for JWT and admin flows
if JWT_SECRET is None:
    # fallback to a random one at runtime, but warn. In production, always set JWT_SECRET.
    JWT_SECRET = os.urandom(32)
    logging.warning('JWT_SECRET not set in env; using ephemeral secret - do not use in production')

if ADMIN_PASSWORD is None:
    logging.warning('ADMIN_PASSWORD not set in env; admin creation protected via absence of secret')


def init_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cognome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            ruolo TEXT NOT NULL,
            motivazione TEXT,
            password TEXT NOT NULL,
            anno INTEGER,
            sezione TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Errori con pagine personalizzate
@app.errorhandler(403)
def forbidden_error(error):
    return send_from_directory(frontend_dir, 'errori/403.html'), 403

@app.errorhandler(404)
def not_found_error(error):
    return send_from_directory(frontend_dir, 'errori/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return send_from_directory(frontend_dir, 'errori/500.html'), 500


@app.route('/register', methods=['POST'])
def register():
    data = request.json
    nome = data.get('nome')
    cognome = data.get('cognome')
    email = data.get('email')
    ruolo = data.get('ruolo')
    motivazione = data.get('motivazione')
    password = data.get('password')
    anno = data.get('anno')
    sezione = data.get('sezione')
    is_admin = data.get('is_admin', False)
    admin_password = data.get('admin_password', '')
    if is_admin:
        # SECURITY: require correct ADMIN_PASSWORD from env
        if not ADMIN_PASSWORD or admin_password != ADMIN_PASSWORD:
            return jsonify({'success': False, 'message': 'Password admin errata or admin disabled'}), 403
        ruolo = 'admin'
    if not all([nome, cognome, email, ruolo, password]):
        return jsonify({'success': False, 'message': 'Tutti i campi obbligatori tranne la motivazione'}), 400
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO users (nome, cognome, email, ruolo, motivazione, password, anno, sezione)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome, cognome, email, ruolo, motivazione, hashed_pw, anno, sezione))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Registrazione avvenuta con successo'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Email già registrata'}), 409

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email e password richiesti'}), 400
    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT password, ruolo FROM users WHERE email = ?', (email,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[0], password):
        # SECURITY: generate JWT token instead of relying on client-supplied headers
        payload = {
            'email': email,
            'ruolo': row[1],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
        return jsonify({'success': True, 'message': 'Accesso riuscito', 'ruolo': row[1], 'email': email, 'token': token})
    else:
        return jsonify({'success': False, 'message': 'Credenziali non valide'}), 401

@app.route('/')
def index():
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_page(filename):
    # SECURITY: ensure path is within the frontend dir to prevent path traversal
    requested = os.path.abspath(os.path.join(frontend_dir, filename))
    if not requested.startswith(os.path.abspath(frontend_dir)):
        return jsonify({'success': False, 'message': 'Invalid path'}), 400
    return send_from_directory(frontend_dir, filename)

@app.route('/css/<path:filename>')
def serve_css(filename):
    # SECURITY: validate static path
    requested = os.path.abspath(os.path.join(static_dir, filename))
    if not requested.startswith(os.path.abspath(static_dir)):
        return jsonify({'success': False, 'message': 'Invalid path'}), 400
    return send_from_directory(static_dir, filename)

if __name__ == '__main__':
    init_db()
    # SECURITY: disable debug mode for production
    app.run(debug=False, port=int(os.environ.get('PORT', 5000)), host='0.0.0.0')