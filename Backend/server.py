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

# Configurazione sicurezza
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', None)
JWT_SECRET = os.environ.get('JWT_SECRET', os.environ.get('SECRET_KEY', None))

# Configurazione frontend e database
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
static_dir = os.path.join(frontend_dir, 'css')
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
cors_origins = os.environ.get('CORS_ORIGINS', '*')
CORS(app, supports_credentials=True, resources={r"/*": {"origins": cors_origins}})

app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.environ.get('SECRET_KEY', os.urandom(32)))
logging.basicConfig(level=logging.INFO)

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/utenti.db'))

# Inizializzazione JWT
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
    logging.warning('GOOGLE_CLIENT_ID not set in env; Google OAuth disabilitato')

if GOOGLE_CLIENT_SECRET is None:
    logging.warning('GOOGLE_CLIENT_SECRET not set in env; Google OAuth disabilitato')

def init_db():
    """Inizializza il database degli utenti"""
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
            sezione TEXT,
            creato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Crea un admin di default se non esiste
    c.execute("SELECT COUNT(*) FROM users WHERE email = 'admin@dazeforfuture.it'")
    if c.fetchone()[0] == 0 and ADMIN_PASSWORD:
        hashed_pw = generate_password_hash(ADMIN_PASSWORD)
        c.execute('''
            INSERT INTO users (nome, cognome, email, ruolo, motivazione, password)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Admin', 'System', 'admin@dazeforfuture.it', 'admin', 'Amministratore di sistema', hashed_pw))
        logging.info("👑 Creato admin di default")
    
    conn.commit()
    conn.close()

# --- Gestione errori ---
@app.errorhandler(403)
def forbidden_error(error):
    return send_from_directory(frontend_dir, 'errori/403.html'), 403

@app.errorhandler(404)
def not_found_error(error):
    return send_from_directory(frontend_dir, 'errori/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logging.error(f"Errore 500: {error}")
    return send_from_directory(frontend_dir, 'errori/500.html'), 500

# --- API Registrazione ---
@app.route('/register', methods=['POST'])
def register():
    """Registra un nuovo utente"""
    try:
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
        
        # Validazioni
        if not all([nome, cognome, email, ruolo, password]):
            return jsonify({
                'success': False, 
                'message': 'Tutti i campi obbligatori sono richiesti'
            }), 400
        
        if is_admin:
            if not ADMIN_PASSWORD or admin_password != ADMIN_PASSWORD:
                return jsonify({
                    'success': False, 
                    'message': 'Password amministratore errata o disabilitata'
                }), 403
            ruolo = 'admin'
        
        hashed_pw = generate_password_hash(password)
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT INTO users (nome, cognome, email, ruolo, motivazione, password, anno, sezione)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nome, cognome, email, ruolo, motivazione, hashed_pw, anno, sezione))
            conn.commit()
            
            logging.info(f"✅ Nuovo utente registrato: {email} ({ruolo})")
            
            return jsonify({
                'success': True, 
                'message': 'Registrazione avvenuta con successo',
                'email': email,
                'ruolo': ruolo
            })
            
        except sqlite3.IntegrityError:
            return jsonify({
                'success': False, 
                'message': 'Email già registrata'
            }), 409
        finally:
            conn.close()
            
    except Exception as e:
        logging.error(f"❌ Errore nella registrazione: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore interno del server: {str(e)}'
        }), 500

# --- API Login ---
@app.route('/login', methods=['POST'])
def login():
    """Autentica un utente"""
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({
                'success': False, 
                'message': 'Email e password sono obbligatori'
            }), 400
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT password, ruolo, nome, cognome FROM users WHERE email = ?', (email,))
        row = c.fetchone()
        conn.close()
        
        if row and check_password_hash(row[0], password):
            # Genera token JWT
            payload = {
                'email': email,
                'ruolo': row[1],
                'nome': row[2],
                'cognome': row[3],
                'exp': datetime.utcnow() + timedelta(hours=24)
            }
            token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
            
            logging.info(f"✅ Login riuscito: {email} ({row[1]})")
            
            return jsonify({
                'success': True, 
                'message': 'Accesso riuscito',
                'ruolo': row[1],
                'email': email,
                'nome': row[2],
                'cognome': row[3],
                'token': token
            })
        else:
            logging.warning(f"❌ Tentativo di login fallito per: {email}")
            return jsonify({
                'success': False, 
                'message': 'Credenziali non valide'
            }), 401
            
    except Exception as e:
        logging.error(f"❌ Errore nel login: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore interno del server: {str(e)}'
        }), 500

# --- API Verifica Token ---
@app.route('/api/verify-token', methods=['POST'])
def verify_token():
    """Verifica la validità di un token JWT"""
    try:
        data = request.json
        token = data.get('token')
        
        if not token:
            return jsonify({'success': False, 'message': 'Token mancante'}), 400
        
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            return jsonify({
                'success': True,
                'valid': True,
                'user': {
                    'email': payload.get('email'),
                    'ruolo': payload.get('ruolo'),
                    'nome': payload.get('nome'),
                    'cognome': payload.get('cognome')
                }
            })
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'valid': False, 'message': 'Token scaduto'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'valid': False, 'message': 'Token non valido'}), 401
            
    except Exception as e:
        logging.error(f"❌ Errore nella verifica del token: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore interno del server: {str(e)}'
        }), 500

# --- Google OAuth ---
@app.route('/google/login')
def google_login():
    """Avvia il processo di login con Google"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logging.error("Google OAuth non configurato")
        return jsonify({
            'success': False, 
            'message': 'Login con Google non disponibile'
        }), 500
    
    try:
        google = OAuth2Session(
            client_id=GOOGLE_CLIENT_ID, 
            scope=SCOPE + ['openid'], 
            redirect_uri=REDIRECT_URI
        )
        authorization_url, state = google.authorization_url(
            AUTHORIZATION_BASE_URL,
            access_type='offline',
            prompt='select_account'
        )
        
        session['oauth_state'] = state
        session.modified = True
        
        logging.debug(f"Google OAuth: URL generato con state {state}")
        return redirect(authorization_url)
        
    except Exception as e:
        logging.exception(f"❌ Errore in google_login: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore durante l\'accesso con Google: {str(e)}'
        }), 500

@app.route('/google/callback')
def google_callback():
    """Callback per Google OAuth"""
    if 'oauth_state' not in session:
        logging.error("State OAuth non trovato nella sessione")
        return "Errore: sessione OAuth scaduta o mancante.", 400
    
    try:
        google = OAuth2Session(
            client_id=GOOGLE_CLIENT_ID, 
            state=session['oauth_state'], 
            redirect_uri=REDIRECT_URI
        )
        
        token = google.fetch_token(
            TOKEN_URL,
            client_secret=GOOGLE_CLIENT_SECRET,
            client_id=GOOGLE_CLIENT_ID,
            authorization_response=request.url
        )
        
        resp = google.get(USER_INFO_URL)
        resp.raise_for_status()
        user_info = resp.json()
        
        email = user_info.get('email')
        if not email:
            logging.error("Google non ha fornito email")
            return "Errore: Google non ha fornito l'email.", 400
        
        nome_completo = user_info.get('name', 'GoogleUser').strip()
        if ' ' in nome_completo:
            parti = nome_completo.split(' ', 1)
            nome = parti[0]
            cognome = parti[1]
        else:
            nome = nome_completo
            cognome = 'GoogleUser'
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT id, ruolo, motivazione FROM users WHERE email = ?', (email,))
        row = c.fetchone()
        
        if not row:
            # Nuovo utente
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
                # Genera token JWT per l'utente Google
                payload = {
                    'email': email,
                    'ruolo': ruolo,
                    'nome': nome,
                    'cognome': cognome,
                    'exp': datetime.utcnow() + timedelta(hours=24)
                }
                token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
                
                return f'''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Login con Google - Successo</title>
                    <style>
                        body {{
                            font-family: 'Inter', sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }}
                        .message {{
                            background: white;
                            padding: 2rem;
                            border-radius: 12px;
                            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                            text-align: center;
                        }}
                        h1 {{ color: #4CAF50; }}
                    </style>
                </head>
                <body>
                    <div class="message">
                        <h1>✅ Login Effettuato!</h1>
                        <p>Reindirizzamento in corso...</p>
                    </div>
                    <script>
                        localStorage.setItem('utente', '{email}');
                        localStorage.setItem('utente_ruolo', '{ruolo}');
                        localStorage.setItem('jwt_token', '{token}');
                        localStorage.setItem('login_method', 'google');
                        setTimeout(() => {{
                            window.location.href = '/';
                        }}, 1500);
                    </script>
                </body>
                </html>
                '''
                
    except Exception as e:
        logging.exception(f"❌ Errore in google_callback: {e}")
        return f"Errore durante il login con Google: {str(e)}", 500

@app.route('/complete-google-registration', methods=['POST'])
def complete_google_registration():
    """Completa la registrazione per utenti Google"""
    try:
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
        c.execute('SELECT id, motivazione FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        
        if not user:
            conn.close()
            return jsonify({
                'success': False, 
                'message': 'Utente non trovato'
            }), 404
        
        user_id, current_motivazione = user
        
        if current_motivazione != 'REGISTRAZIONE_DA_COMPLETARE':
            conn.close()
            return jsonify({
                'success': False, 
                'message': 'Registrazione già completata'
            }), 400
        
        if is_admin:
            if admin_password != ADMIN_PASSWORD:
                conn.close()
                return jsonify({
                    'success': False, 
                    'message': 'Password amministratore errata'
                }), 403
            ruolo_finale = 'admin'
        else:
            ruolo_finale = ruolo
        
        if not motivazione or motivazione.strip() == '':
            motivazione_finale = f"Registrato via Google - {ruolo_finale}"
        else:
            motivazione_finale = motivazione
        
        c.execute('''
            UPDATE users 
            SET nome = ?, cognome = ?, ruolo = ?, motivazione = ?, anno = ?, sezione = ?
            WHERE email = ?
        ''', (nome, cognome, ruolo_finale, motivazione_finale, anno, sezione, email))
        conn.commit()
        conn.close()
        
        # Genera token JWT
        payload = {
            'email': email,
            'ruolo': ruolo_finale,
            'nome': nome,
            'cognome': cognome,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
        
        return jsonify({
            'success': True, 
            'message': 'Registrazione completata con successo', 
            'ruolo': ruolo_finale,
            'email': email,
            'token': token
        })
        
    except Exception as e:
        logging.error(f"❌ Errore nel completamento registrazione Google: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore durante l\'aggiornamento: {str(e)}'
        }), 500

# --- API Utenti ---
@app.route('/api/users', methods=['GET'])
def get_users():
    """Ottiene la lista degli utenti (solo admin)"""
    try:
        # Verifica token
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({
                'success': False, 
                'message': 'Token mancante'
            }), 401
        
        token = auth.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            if payload.get('ruolo') != 'admin':
                return jsonify({
                    'success': False, 
                    'message': 'Solo gli amministratori possono accedere a questa risorsa'
                }), 403
        except:
            return jsonify({
                'success': False, 
                'message': 'Token non valido'
            }), 401
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        c = conn.cursor()
        c.execute('''
            SELECT id, nome, cognome, email, ruolo, motivazione, anno, sezione, creato_il
            FROM users 
            ORDER BY creato_il DESC
        ''')
        
        users = [
            {
                'id': row[0],
                'nome': row[1],
                'cognome': row[2],
                'email': row[3],
                'ruolo': row[4],
                'motivazione': row[5],
                'anno': row[6],
                'sezione': row[7],
                'creato_il': row[8]
            }
            for row in c.fetchall()
        ]
        
        conn.close()
        return jsonify({
            'success': True, 
            'users': users, 
            'count': len(users)
        })
        
    except Exception as e:
        logging.error(f"❌ Errore nel recupero utenti: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore interno del server: {str(e)}'
        }), 500

# --- Health Check ---
@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint per health check"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        tables = c.fetchall()
        
        c.execute("SELECT COUNT(*) FROM users")
        count = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'healthy', 
            'service': 'main_server',
            'database': 'connected',
            'total_users': count,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"❌ Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy', 
            'service': 'main_server',
            'message': f'Errore: {str(e)}'
        }), 500

# --- Servizio file statici ---
@app.route('/')
def index():
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_page(filename):
    requested = os.path.abspath(os.path.join(frontend_dir, filename))
    if not requested.startswith(os.path.abspath(frontend_dir)):
        return jsonify({'success': False, 'message': 'Percorso non valido'}), 400
    return send_from_directory(frontend_dir, filename)

@app.route('/css/<path:filename>')
def serve_css(filename):
    requested = os.path.abspath(os.path.join(static_dir, filename))
    if not requested.startswith(os.path.abspath(static_dir)):
        return jsonify({'success': False, 'message': 'Percorso non valido'}), 400
    return send_from_directory(static_dir, filename)

# --- Avvio applicazione ---
if __name__ == '__main__':
    init_db()
    
    logging.info("=" * 50)
    logging.info("🚀 Avvio Server Principale Daze for Future")
    logging.info(f"📡 Porta: 5000")
    logging.info(f"🌐 Frontend: {frontend_dir}")
    logging.info(f"🗄️ Database utenti: {db_path}")
    logging.info(f"🔐 Google OAuth: {'Abilitato' if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET else 'Disabilitato'}")
    logging.info("=" * 50)
    
    app.run(debug=False, port=5000, host='0.0.0.0')