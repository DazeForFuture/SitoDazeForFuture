from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from flask_cors import CORS
import os
import base64
import uuid
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='.', static_folder='.')
# CORREZIONE CORS: Configurazione completa
CORS(app, 
     supports_credentials=True, 
     origins=["http://localhost:5000", "http://127.0.0.1:5000", "http://0.0.0.0:5000",
              "http://localhost:5001", "http://127.0.0.1:5001", "http://0.0.0.0:5001"])

app.secret_key = 'daze_for_future_secret_key_2025'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Cambiato da 'None'
app.config['SESSION_COOKIE_SECURE'] = False    # Disabilitato per sviluppo HTTP
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Configurazione
UPLOAD_FOLDER = 'documenti'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png', 'gif'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Creazione cartella uploads
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# PERCORSI DATABASE CORRETTI - due livelli sopra
current_dir = os.path.dirname(os.path.abspath(__file__))
database_dir = os.path.abspath(os.path.join(current_dir, '../../database'))

# Assicurati che la cartella database esista
os.makedirs(database_dir, exist_ok=True)

users_db = os.path.join(database_dir, 'utenti.db')
documents_db = os.path.join(database_dir, 'documenti.db')

print(f"Percorso corrente: {current_dir}")
print(f"Percorso database: {database_dir}")
print(f"Percorso database utenti: {users_db}")
print(f"Percorso database documenti: {documents_db}")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection(db_path):
    """Crea una connessione al database SQLite"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Errore connessione database {db_path}: {e}")
        raise

def get_user_documents(user_email):
    """Restituisce i documenti dell'utente dal database"""
    try:
        conn = get_db_connection(documents_db)
        cursor = conn.cursor()
        
        # Verifica se la tabella esiste
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("Tabella documents non esiste, creazione...")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    user_email TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    filepath TEXT NOT NULL
                )
            ''')
            conn.commit()
            return []
        
        cursor.execute('''
            SELECT id, filename, uploaded_at, filepath 
            FROM documents 
            WHERE user_email = ?
            ORDER BY uploaded_at DESC
        ''', (user_email,))
        
        documents = cursor.fetchall()
        conn.close()
        
        user_docs = []
        for doc in documents:
            user_docs.append({
                'id': doc['id'],
                'filename': doc['filename'],
                'uploaded_at': doc['uploaded_at'],
                'filepath': doc['filepath']
            })
        
        return user_docs
    except Exception as e:
        print(f"Errore nel recupero documenti: {e}")
        return []

def init_databases():
    """Inizializza le tabelle se non esistono"""
    try:
        # Database utenti - solo creazione tabella se non esiste
        conn_users = get_db_connection(users_db)
        conn_users.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn_users.commit()
        conn_users.close()
        
        # Database documenti
        conn_docs = get_db_connection(documents_db)
        conn_docs.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                user_email TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                filepath TEXT NOT NULL
            )
        ''')
        conn_docs.commit()
        conn_docs.close()
        print("Database inizializzati con successo")
    except Exception as e:
        print(f"Errore nell'inizializzazione database: {e}")

# Inizializza i database all'avvio
init_databases()

# Middleware per verificare l'autenticazione
@app.before_request
def check_authentication():
    # Route pubbliche che non richiedono autenticazione
    public_routes = ['login', 'static', 'check_auth']
    
    if request.endpoint and not any(route in request.endpoint for route in public_routes):
        if 'user' not in session:
            return jsonify({'success': False, 'message': 'Non autenticato'}), 401

# Route principali
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            # Gestisci sia JSON che form-data
            if request.is_json:
                data = request.get_json()
                email = data.get('email')
                password = data.get('password')
            else:
                email = request.form.get('email')
                password = request.form.get('password')
            
            if not email or not password:
                return jsonify({'success': False, 'message': 'Email e password richiesti'}), 400
            
            # Verifica credenziali nel database
            conn = get_db_connection(users_db)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                session['user'] = email
                session.permanent = True
                response = jsonify({
                    'success': True, 
                    'message': 'Login effettuato',
                    'redirect': '/documenti.html'
                })
                return response
            else:
                return jsonify({'success': False, 'message': 'Credenziali non valide'}), 401
                
        except Exception as e:
            return jsonify({'success': False, 'message': f'Errore server: {str(e)}'}), 500
    
    # Se GET, servi la pagina HTML
    try:
        return render_template('login.html')
    except:
        return """
        <html>
            <body>
                <h1>Pagina di Login</h1>
                <p>Usa il frontend per accedere</p>
            </body>
        </html>
        """

@app.route('/check_auth')
def check_auth():
    """Endpoint per verificare lo stato dell'autenticazione"""
    print(f"Check auth - Session: {dict(session)}")
    if 'user' in session:
        return jsonify({'authenticated': True, 'user': session['user']})
    return jsonify({'authenticated': False}), 200

@app.route('/logout')
def logout():
    session.pop('user', None)
    response = jsonify({'success': True, 'message': 'Logout effettuato'})
    return response

@app.route('/documenti.html')
def documenti():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        return render_template('documenti.html')
    except:
        return """
        <html>
            <body>
                <h1>Gestione Documenti</h1>
                <p>Utente: {}</p>
                <p>Usa il frontend per la gestione documenti</p>
            </body>
        </html>
        """.format(session['user'])

# API per i documenti
@app.route('/api/upload_document', methods=['POST'])
def upload_document():
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 401
    
    try:
        data = request.get_json()
        if not data or 'filedata' not in data or 'filename' not in data:
            return jsonify({'success': False, 'message': 'Dati mancanti'}), 400
        
        # Decodifica il file base64
        file_data = base64.b64decode(data['filedata'])
        filename = secure_filename(data['filename'])
        
        # Genera ID univoco
        doc_id = str(uuid.uuid4())
        
        # Salva il file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{doc_id}_{filename}")
        with open(filepath, 'wb') as f:
            f.write(file_data)
        
        # Salva nei documenti nel database
        conn = get_db_connection(documents_db)
        conn.execute('''
            INSERT INTO documents (id, filename, user_email, uploaded_at, filepath)
            VALUES (?, ?, ?, ?, ?)
        ''', (doc_id, filename, session['user'], datetime.now().isoformat(), filepath))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'id': doc_id})
        
    except Exception as e:
        print(f"Errore upload documento: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/list_documents')
def list_documents():
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 401
    
    try:
        user_docs = get_user_documents(session['user'])
        return jsonify(user_docs)
    except Exception as e:
        print(f"Errore list_documents: {e}")
        return jsonify([])

@app.route('/api/view_document/<doc_id>')
def view_document(doc_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 401
    
    try:
        conn = get_db_connection(documents_db)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ? AND user_email = ?', (doc_id, session['user']))
        document = cursor.fetchone()
        conn.close()
        
        if not document:
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        return send_file(document['filepath'], as_attachment=False)
    except Exception as e:
        print(f"Errore view_document: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/download_document/<doc_id>')
def download_document(doc_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 401
    
    try:
        conn = get_db_connection(documents_db)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ? AND user_email = ?', (doc_id, session['user']))
        document = cursor.fetchone()
        conn.close()
        
        if not document:
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        return send_file(document['filepath'], as_attachment=True, 
                        download_name=document['filename'])
    except Exception as e:
        print(f"Errore download_document: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete_document/<doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 401
    
    try:
        conn = get_db_connection(documents_db)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ? AND user_email = ?', (doc_id, session['user']))
        document = cursor.fetchone()
        
        if not document:
            conn.close()
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        # Rimuovi il file fisico
        if os.path.exists(document['filepath']):
            os.remove(document['filepath'])
        
        # Rimuovi dal database
        cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"Errore delete_document: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("Server in avvio su http://localhost:5001")
    print("Percorso database utenti:", users_db)
    print("Percorso database documenti:", documents_db)
    app.run(debug=True, port=5001, host='0.0.0.0')