import os
import sqlite3
import logging
from datetime import datetime, timedelta
from flask import Flask, send_from_directory, request, jsonify, redirect, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv
load_dotenv()

# SECURITY
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', None)
JWT_SECRET = os.environ.get('JWT_SECRET', os.environ.get('SECRET_KEY', None))


# --- Configurazione frontend e DB ---
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
static_dir = os.path.join(frontend_dir, 'css')
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
cors_origins = os.environ.get('CORS_ORIGINS', '*')
CORS(app, supports_credentials=True, resources={r"/*": {"origins": cors_origins}})

app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.environ.get('SECRET_KEY', os.urandom(32)))
logging.basicConfig(level=logging.INFO)

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/utenti.db'))

if JWT_SECRET is None:
    JWT_SECRET = os.urandom(32)
    logging.warning('JWT_SECRET not set in env; using ephemeral secret - do not use in production')

if ADMIN_PASSWORD is None:
    logging.warning('ADMIN_PASSWORD not set in env; admin creation protected via absence of secret')

# Configurazione OAuth Google 
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', None)
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', None)
AUTHORIZATION_BASE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
USER_INFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'
REDIRECT_URI = 'http://localhost:5000/google/callback'
SCOPE = ['https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

if GOOGLE_CLIENT_ID is None:
    logging.warning('GOOGLE_CLIENT_ID not set in env; admin creation protected via absence of secret')

if GOOGLE_CLIENT_SECRET is None:
    logging.warning('GOOGLE_CLIENT_SECRET not set in env; admin creation protected via absence of secret')


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

# --- Errori ---
@app.errorhandler(403)
def forbidden_error(error):
    return send_from_directory(frontend_dir, 'errori/403.html'), 403

@app.errorhandler(404)
def not_found_error(error):
    return send_from_directory(frontend_dir, 'errori/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return send_from_directory(frontend_dir, 'errori/500.html'), 500

# --- Registrazione standard ---
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

# --- Login standard ---
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

# Google Login
@app.route('/google/login')
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logging.error("Google OAuth credenziali mancanti.")
        return "Google OAuth non configurato", 500

    try:
        google = OAuth2Session(client_id=GOOGLE_CLIENT_ID, scope=SCOPE + ['openid'], redirect_uri=REDIRECT_URI)
        authorization_url, state = google.authorization_url(
            AUTHORIZATION_BASE_URL,
            access_type='offline',
            prompt='select_account'
        )
        session['oauth_state'] = state
        session.modified = True
        logging.debug("Generato authorization_url con state %s", state)
        return redirect(authorization_url)
    except Exception as e:
        logging.exception("Errore in google_login: %s", e)
        return "Errore durante l'accesso con Google", 500


# Google Callback (login/registrazione)
@app.route('/google/callback')
def google_callback():
    # Verifica stato sessione
    if 'oauth_state' not in session:
        logging.error("oauth_state non trovato nella sessione.")
        return "Errore: sessione OAuth scaduta o mancante.", 400

    try:
        google = OAuth2Session(client_id=GOOGLE_CLIENT_ID, state=session['oauth_state'], redirect_uri=REDIRECT_URI)

        # Scambia il code per il token (includi client_id per compatibilità)
        token = google.fetch_token(
            TOKEN_URL,
            client_secret=GOOGLE_CLIENT_SECRET,
            client_id=GOOGLE_CLIENT_ID,
            authorization_response=request.url
        )
        logging.debug("Token ottenuto (access_token presente? %s)", bool(token.get('access_token')))
    except Exception as e:
        logging.exception("Errore durante fetch_token: %s", e)
        return ("Errore nello scambio del token con Google. Controlla CLIENT_ID/SECRET "
                "e redirect URI nella Console Google. Dettaglio: " + str(e)), 500

    # Recupera userinfo e controlla codice di risposta
    try:
        resp = google.get(USER_INFO_URL)
        logging.debug("Userinfo status code: %s", resp.status_code)
        resp.raise_for_status()
        user_info = resp.json()
    except Exception as e:
        logging.exception("Errore durante richiesta userinfo: %s", e)
        return "Errore durante la richiesta delle informazioni utente da Google.", 500

    email = user_info.get('email')
    if not email:
        logging.error("Google non ha fornito email. user_info: %s", user_info)
        return "Errore: Google non ha fornito l'email (controlla gli scope).", 400

    # Normalizza nome/cognome
    nome_completo = user_info.get('name', 'GoogleUser').strip()
    if ' ' in nome_completo:
        parti = nome_completo.split(' ', 1)
        nome = parti[0]
        cognome = parti[1]
    else:
        nome = nome_completo
        cognome = 'GoogleUser'

    # Interazione sicura col DB
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT id, ruolo, motivazione FROM users WHERE email = ?', (email,))
        row = c.fetchone()

        if not row:
            c.execute('''
                INSERT INTO users (nome, cognome, email, ruolo, motivazione, password)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome, cognome, email, 'user', 'REGISTRAZIONE_DA_COMPLETARE',
                  generate_password_hash(os.urandom(16).hex())))
            conn.commit()
            conn.close()

            session['google_pending_email'] = email
            session['google_pending_nome'] = nome
            session['google_pending_cognome'] = cognome
            return redirect(f'/completa_registrazione.html?email={email}&nome={nome}+{cognome}')
        else:
            user_id, ruolo, motivazione = row
            conn.close()
            if motivazione == 'REGISTRAZIONE_DA_COMPLETARE':
                session['google_pending_email'] = email
                session['google_pending_nome'] = nome
                session['google_pending_cognome'] = cognome
                return redirect(f'/completa_registrazione.html?email={email}&nome={nome}+{cognome}')
            else:
                session['user_email'] = email
                session['user_nome'] = nome
                session['user_cognome'] = cognome
                session['user_ruolo'] = ruolo
                session['logged_in'] = True
                session['login_method'] = 'google'
                return f'''
                <!DOCTYPE html>
                <html>
                <head><title>Login con Google - Successo</title></head>
                <body>
                    <script>
                        localStorage.setItem('utente', '{email}');
                        localStorage.setItem('utente_ruolo', '{ruolo}');
                        localStorage.setItem('login_method', 'google');
                        window.location.href = '/';
                    </script>
                    <p>Login effettuato con successo! Reindirizzamento...</p>
                </body>
                </html>
                '''
    except Exception as e:
        logging.exception("Errore DB dopo userinfo: %s", e)
        try:
            conn.close()
        except:
            pass
        return "Errore interno durante la gestione dell'utente.", 500

# Route per completare la registrazione Google
@app.route('/complete-google-registration', methods=['POST'])
def complete_google_registration():
    data = request.json
    
    email = data.get('email')
    nome = data.get('nome')
    cognome = data.get('cognome')
    ruolo = data.get('ruolo')
    motivazione = data.get('motivazione')
    is_admin = data.get('is_admin', False)
    admin_password = data.get('admin_password', '')
    anno = data.get('anno')
    sezione = data.get('sezione')
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Verifica che l'utente esista
    c.execute('SELECT id, motivazione FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return jsonify({'success': False, 'message': 'Utente non trovato'}), 404
    
    user_id, current_motivazione = user
    
    # Verifica che la registrazione non sia già completata
    if current_motivazione != 'REGISTRAZIONE_DA_COMPLETARE':
        conn.close()
        return jsonify({'success': False, 'message': 'Registrazione già completata'}), 400
    
    # Se richiesto admin, verifica la password
    if is_admin:
        if admin_password != ADMIN_PASSWORD:
            conn.close()
            return jsonify({'success': False, 'message': 'Password admin errata'}), 403
        ruolo_finale = 'admin'
    else:
        ruolo_finale = ruolo
    
    # Se l'utente non inserisce una motivazione, usa una di default
    if not motivazione or motivazione.strip() == '':
        motivazione_finale = f"Registrato via Google - {ruolo_finale}"
    else:
        motivazione_finale = motivazione
    
    # Aggiorna l'utente con i dati completi
    try:
        c.execute('''
            UPDATE users 
            SET nome = ?, cognome = ?, ruolo = ?, motivazione = ?, anno = ?, sezione = ?
            WHERE email = ?
        ''', (nome, cognome, ruolo_finale, motivazione_finale, anno, sezione, email))
        conn.commit()
        conn.close()
        
        # Imposta la sessione di login
        session['user_email'] = email
        session['user_nome'] = nome
        session['user_cognome'] = cognome
        session['user_ruolo'] = ruolo_finale
        session['logged_in'] = True
        session['login_method'] = 'google'
        
        # Pulisci i dati pendenti dalla sessione
        session.pop('google_pending_email', None)
        session.pop('google_pending_nome', None)
        session.pop('google_pending_cognome', None)
        
        return jsonify({'success': True, 'message': 'Registrazione completata con successo', 'ruolo': ruolo_finale})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'Errore durante l\'aggiornamento: {str(e)}'}), 500

# --- Pagine ---
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

# --- Avvio app ---
if __name__ == '__main__':
    init_db()
    # SECURITY: disable debug mode for production
    app.run(debug=False, port=5000, host='0.0.0.0')