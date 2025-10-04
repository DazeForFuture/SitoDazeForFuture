# app.py
import os
import sqlite3
import base64
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_file, session, make_response
from flask_cors import CORS
import bcrypt
import logging
from werkzeug.security import generate_password_hash, check_password_hash

# Configurazione logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# CORS configuration
CORS(app, supports_credentials=True, origins=["http://localhost:5000", "http://127.0.0.1:5000","http://0.0.0.0:5000"])

# Percorsi database
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
static_dir = os.path.join(frontend_dir, 'css')
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/utenti.db'))
documents_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/documenti.db'))
ADMIN_PASSWORD = "deidopas0810!"

# Crea directory se non esiste
os.makedirs(os.path.dirname(db_path), exist_ok=True)
os.makedirs(os.path.dirname(documents_db_path), exist_ok=True)

# Database setup
def init_databases():
    """Inizializza il database documenti"""    
    # Database documenti
    conn = sqlite3.connect(documents_db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_data BLOB NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_documents_user_id 
        ON documents(user_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_documents_uploaded_at 
        ON documents(uploaded_at DESC)
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database documenti inizializzato")

def get_users_db_connection():
    """Connessione al database utenti"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Errore connessione database utenti: {str(e)}")
        raise

def get_documents_db_connection():
    """Connessione al database documenti"""
    try:
        conn = sqlite3.connect(documents_db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Errore connessione database documenti: {str(e)}")
        raise

# Helper functions
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    mime_types = {
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'txt': 'text/plain',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif'
    }
    return mime_types.get(ext, 'application/octet-stream')

# Authentication routes (dal tuo codice esistente)
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
        if admin_password != ADMIN_PASSWORD:
            return jsonify({'success': False, 'message': 'Password admin errata'}), 403
        ruolo = 'admin'
    
    if not all([nome, cognome, email, ruolo, password]):
        return jsonify({'success': False, 'message': 'Tutti i campi obbligatori tranne la motivazione'}), 400
    
    hashed_pw = generate_password_hash(password)
    
    try:
        conn = get_users_db_connection()
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
    
    conn = get_users_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, password, ruolo, nome, cognome FROM users WHERE email = ?', (email,))
    row = c.fetchone()
    conn.close()
    
    if row and check_password_hash(row[1], password):
        # Imposta la sessione
        session['user_id'] = row[0]
        session['user_email'] = email
        session['user_role'] = row[2]
        session['user_name'] = f"{row[3]} {row[4]}"
        
        response = jsonify({
            'success': True, 
            'message': 'Accesso riuscito', 
            'ruolo': row[2], 
            'email': email,
            'user': {
                'id': row[0],
                'nome': row[3],
                'cognome': row[4],
                'email': email,
                'ruolo': row[2]
            }
        })
        
        response.set_cookie(
            'session_id', 
            value=str(row[0]),
            httponly=True,
            secure=False,
            samesite='Lax'
        )
        
        logger.info(f"Login riuscito per: {email}")
        return response
    else:
        logger.warning(f"Login fallito per: {email}")
        return jsonify({'success': False, 'message': 'Credenziali non valide'}), 401

@app.route('/check_auth', methods=['GET'])
def check_auth():
    try:
        user_id = session.get('user_id')
        
        if user_id:
            conn = get_users_db_connection()
            user = conn.execute(
                'SELECT id, email, ruolo, nome, cognome FROM users WHERE id = ?', (user_id,)
            ).fetchone()
            conn.close()
            
            if user:
                logger.info(f"Utente autenticato: {user['email']}")
                return jsonify({
                    'authenticated': True,
                    'user': {
                        'id': user['id'],
                        'email': user['email'],
                        'ruolo': user['ruolo'],
                        'nome': user['nome'],
                        'cognome': user['cognome']
                    }
                })
        
        logger.info("Utente non autenticato")
        return jsonify({'authenticated': False}), 401
        
    except Exception as e:
        logger.error(f"Errore durante check auth: {str(e)}")
        return jsonify({'authenticated': False}), 401

@app.route('/logout', methods=['POST'])
def logout():
    try:
        session.clear()
        response = jsonify({'success': True, 'message': 'Logout effettuato'})
        response.set_cookie('session_id', '', expires=0)
        logger.info("Logout effettuato")
        return response
    except Exception as e:
        logger.error(f"Errore durante logout: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore durante il logout'}), 500

# Document routes (nuove funzionalità)
@app.route('/api/upload_document', methods=['POST'])
def upload_document():
    try:
        # Verifica autenticazione
        user_id = session.get('user_id')
        if not user_id:
            logger.warning("Tentativo upload senza autenticazione")
            return jsonify({'success': False, 'message': 'Non autenticato'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Nessun dato ricevuto'}), 400
        
        filename = data.get('filename')
        filedata = data.get('filedata')
        
        if not filename or not filedata:
            return jsonify({'success': False, 'message': 'Nome file e dati richiesti'}), 400
        
        if not allowed_file(filename):
            return jsonify({'success': False, 'message': 'Tipo di file non supportato'}), 400
        
        # Decodifica base64
        try:
            file_bytes = base64.b64decode(filedata)
        except Exception as e:
            logger.error(f"Errore decodifica base64: {str(e)}")
            return jsonify({'success': False, 'message': 'Dati file non validi'}), 400
        
        file_size = len(file_bytes)
        file_type = get_file_type(filename)
        
        # Salva nel database documenti
        conn = get_documents_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO documents (user_id, filename, file_data, file_size, file_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, filename, file_bytes, file_size, file_type))
        
        document_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Documento caricato: {filename} (ID: {document_id}) per utente {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Documento caricato con successo',
            'document_id': document_id
        })
        
    except Exception as e:
        logger.error(f"Errore durante l'upload: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore interno del server'}), 500

@app.route('/api/list_documents', methods=['GET'])
def list_documents():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Non autenticato'}), 401
        
        conn = get_documents_db_connection()
        documents = conn.execute('''
            SELECT id, filename, file_size, file_type, uploaded_at 
            FROM documents 
            WHERE user_id = ? 
            ORDER BY uploaded_at DESC
        ''', (user_id,)).fetchall()
        conn.close()
        
        docs_list = []
        for doc in documents:
            docs_list.append({
                'id': doc['id'],
                'filename': doc['filename'],
                'file_size': doc['file_size'],
                'file_type': doc['file_type'],
                'uploaded_at': doc['uploaded_at']
            })
        
        logger.info(f"Listati {len(docs_list)} documenti per utente {user_id}")
        return jsonify(docs_list)
        
    except Exception as e:
        logger.error(f"Errore durante il listing documenti: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore interno del server'}), 500

@app.route('/api/view_document/<int:doc_id>', methods=['GET'])
def view_document(doc_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Non autenticato'}), 401
        
        conn = get_documents_db_connection()
        document = conn.execute('''
            SELECT filename, file_data, file_type 
            FROM documents 
            WHERE id = ? AND user_id = ?
        ''', (doc_id, user_id)).fetchone()
        conn.close()
        
        if not document:
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        # Crea una risposta con il file
        response = make_response(document['file_data'])
        response.headers.set('Content-Type', document['file_type'])
        response.headers.set('Content-Disposition', 'inline', filename=document['filename'])
        
        logger.info(f"Documento visualizzato: {document['filename']} (ID: {doc_id})")
        return response
        
    except Exception as e:
        logger.error(f"Errore durante la visualizzazione documento: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore interno del server'}), 500

@app.route('/api/download_document/<int:doc_id>', methods=['GET'])
def download_document(doc_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Non autenticato'}), 401
        
        conn = get_documents_db_connection()
        document = conn.execute('''
            SELECT filename, file_data, file_type 
            FROM documents 
            WHERE id = ? AND user_id = ?
        ''', (doc_id, user_id)).fetchone()
        conn.close()
        
        if not document:
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        # Crea una risposta con il file per il download
        response = make_response(document['file_data'])
        response.headers.set('Content-Type', document['file_type'])
        response.headers.set('Content-Disposition', 'attachment', filename=document['filename'])
        
        logger.info(f"Documento scaricato: {document['filename']} (ID: {doc_id})")
        return response
        
    except Exception as e:
        logger.error(f"Errore durante il download documento: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore interno del server'}), 500

@app.route('/api/delete_document/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Non autenticato'}), 401
        
        conn = get_documents_db_connection()
        
        # Prima verifica che il documento appartenga all'utente
        document = conn.execute('''
            SELECT filename FROM documents WHERE id = ? AND user_id = ?
        ''', (doc_id, user_id)).fetchone()
        
        if not document:
            conn.close()
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        # Elimina il documento
        conn.execute('DELETE FROM documents WHERE id = ? AND user_id = ?', (doc_id, user_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Documento eliminato: {document['filename']} (ID: {doc_id})")
        return jsonify({'success': True, 'message': 'Documento eliminato con successo'})
        
    except Exception as e:
        logger.error(f"Errore durante l'eliminazione documento: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore interno del server'}), 500

# Routes per servire le pagine (dal tuo codice esistente)
@app.route('/')
def index():
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_page(filename):
    return send_from_directory(frontend_dir, filename)

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(static_dir, filename)

# Health check
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'databases': {
            'users': 'ok',
            'documents': 'ok'
        }
    })

# Aggiungi questa route per gestire le richieste proxy dal frontend
@app.route('/api/<path:api_path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_proxy(api_path):
    """Proxy per le API chiamate dal frontend sulla stessa porta"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': 'Non autenticato'}), 401
        
        # Gestisci le varie API qui
        if api_path == 'list_documents':
            return list_documents()
        elif api_path.startswith('view_document/'):
            doc_id = int(api_path.split('/')[1])
            return view_document(doc_id)
        elif api_path.startswith('download_document/'):
            doc_id = int(api_path.split('/')[1])
            return download_document(doc_id)
        elif api_path.startswith('delete_document/'):
            doc_id = int(api_path.split('/')[1])
            return delete_document(doc_id)
        elif api_path == 'upload_document':
            return upload_document()
        else:
            return jsonify({'success': False, 'message': 'API non trovata'}), 404
            
    except Exception as e:
        logger.error(f"Errore API proxy: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore interno del server'}), 500

if __name__ == '__main__':
    init_databases()
    print("=== Sistema di Gestione Documenti ===")
    print(f"Database utenti: {db_path}")
    print(f"Database documenti: {documents_db_path}")
    print("Server in esecuzione su http://localhost:5001")
    app.run(debug=True, port=5001, host='0.0.0.0')