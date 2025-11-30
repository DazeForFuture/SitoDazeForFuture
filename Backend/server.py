import os
import sqlite3
import logging
from flask import Flask, send_from_directory, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from config import BaseConfig, require_secrets
from logging.handlers import RotatingFileHandler
from security import is_valid_email, is_strong_password, sanitize_text, sanitize_for_logging, safe_path_join, generate_csrf_token, require_csrf_token

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
static_dir = os.path.join(frontend_dir, 'css')
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
app.config.from_object(BaseConfig)

# Rate Limiter setup
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Configure CORS with whitelist
allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, 
    origins=allowed_origins,
    supports_credentials=True,
    methods=['GET', 'POST', 'DELETE', 'PUT', 'OPTIONS'],
    allow_headers=['Content-Type', 'X-User-Email']
)

# Security Headers with Talisman
Talisman(
    app,
    force_https=True,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,  # 1 year
    content_security_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'"],  # Adjust as needed
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", 'data:', 'https:'],
        'font-src': ["'self'"],
        'connect-src': ["'self'"],
    },
    content_security_policy_nonce_in=['script-src', 'style-src']
)

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/utenti.db'))

# Setup logging
if not app.debug:
    handler = RotatingFileHandler('server.log', maxBytes=10*1024*1024, backupCount=5)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)


def init_db():
    conn = sqlite3.connect(db_path)
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


@app.route('/csrf-token', methods=['GET'])
@limiter.limit("60 per hour")
def get_csrf_token():
    """Get CSRF token for client to use in subsequent POST requests."""
    from flask import session
    token = generate_csrf_token()
    session['csrf_token'] = token
    return jsonify({'csrf_token': token})


@app.route('/register', methods=['POST'])
@limiter.limit("5 per hour")
@require_csrf_token()
def register():
    # Validate Content-Type
    if request.method == 'POST':
        if request.is_json:
            data = request.json
        else:
            return jsonify({'success': False, 'message': 'Content-Type deve essere application/json'}), 400
    else:
        data = request.json
    
    nome = sanitize_text(data.get('nome'), max_length=100) if data.get('nome') else None
    cognome = sanitize_text(data.get('cognome'), max_length=100) if data.get('cognome') else None
    email = data.get('email', '').strip() if data.get('email') else None
    ruolo = data.get('ruolo', '').strip() if data.get('ruolo') else None
    motivazione = sanitize_text(data.get('motivazione'), max_length=500) if data.get('motivazione') else None
    password = data.get('password', '').strip() if data.get('password') else None
    anno = data.get('anno')
    sezione = data.get('sezione', '').strip() if data.get('sezione') else None
    is_admin = data.get('is_admin', False)
    admin_password = data.get('admin_password', '')
    
    # Validazione email
    if not email or not is_valid_email(email):
        return jsonify({'success': False, 'message': 'Email non valida'}), 400
    
    # Validazione password
    if not password:
        return jsonify({'success': False, 'message': 'Password richiesta'}), 400
    
    is_strong, reason = is_strong_password(password)
    if not is_strong:
        return jsonify({'success': False, 'message': f'Password non sicura: {reason}'}), 400
    
    # Verificazione admin password se richiesto
    if is_admin:
        expected_admin_pw = app.config.get('ADMIN_PASSWORD')
        if not expected_admin_pw or admin_password != expected_admin_pw:
            # Log without exposing email for security
            app.logger.warning("Failed admin registration attempt - incorrect admin password")
            return jsonify({'success': False, 'message': 'Password admin errata'}), 403
        ruolo = 'admin'
    
    if not all([nome, cognome, email, ruolo, password]):
        return jsonify({'success': False, 'message': 'Campi obbligatori mancanti o non validi'}), 400
    
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO users (nome, cognome, email, ruolo, motivazione, password, anno, sezione)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome, cognome, email, ruolo, motivazione, hashed_pw, anno, sezione))
        conn.commit()
        conn.close()
        app.logger.info(f"User registered: {email} with role {ruolo}")
        return jsonify({'success': True, 'message': 'Registrazione avvenuta con successo'})
    except sqlite3.IntegrityError:
        # Log internally but respond generically to prevent enumeration
        app.logger.warning(f"Registration attempt with duplicate email: {email}")
        return jsonify({'success': False, 'message': 'Registrazione non possibile. Email potrebbe già essere registrata'}), 400
    except Exception as e:
        app.logger.error(f"Registration error: {sanitize_for_logging({'error': str(e)})}")
        return jsonify({'success': False, 'message': 'Errore nella registrazione'}), 500

@app.route('/login', methods=['POST'])
@limiter.limit("5 per hour")
@require_csrf_token()
def login():
    # Validate Content-Type
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Content-Type deve essere application/json'}), 400
    
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email e password richiesti'}), 400
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT password, ruolo FROM users WHERE email = ?', (email,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[0], password):
        return jsonify({'success': True, 'message': 'Accesso riuscito', 'ruolo': row[1], 'email': email})
    else:
        return jsonify({'success': False, 'message': 'Credenziali non valide'}), 401

@app.route('/')
def index():
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_page(filename):
    # Prevent path traversal attacks
    is_safe, resolved_path = safe_path_join(frontend_dir, filename)
    if not is_safe:
        app.logger.warning(f"Path traversal attempt detected: {filename}")
        return send_from_directory(frontend_dir, 'errori/403.html'), 403
    
    try:
        return send_from_directory(frontend_dir, filename)
    except Exception:
        return send_from_directory(frontend_dir, 'errori/404.html'), 404

@app.route('/css/<path:filename>')
def serve_css(filename):
    # Prevent path traversal attacks
    is_safe, resolved_path = safe_path_join(static_dir, filename)
    if not is_safe:
        app.logger.warning(f"Path traversal attempt detected in /css: {filename}")
        return send_from_directory(frontend_dir, 'errori/403.html'), 403
    
    try:
        return send_from_directory(static_dir, filename)
    except Exception:
        return send_from_directory(frontend_dir, 'errori/404.html'), 404

if __name__ == '__main__':
    try:
        require_secrets(app)
    except RuntimeError as e:
        app.logger.error(str(e))
        print(f"ERROR: {str(e)}")
        exit(1)
    
    init_db()
    # IMPORTANT: debug=False for security. Use Gunicorn in production.
    app.run(debug=False, port=5000, host='0.0.0.0')