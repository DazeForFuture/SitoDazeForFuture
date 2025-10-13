import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_file, g
from werkzeug.utils import secure_filename
from flask_cors import CORS  # Per gestire CORS

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'documenti'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 16MB max file size
app.config['DATABASE'] = '../../database/documenti.db'

# Abilita CORS per tutte le origini
CORS(app)

# Estensioni permesse
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip'}

# Funzione per inizializzare il database
def init_db():
    """Inizializza il database con le tabelle necessarie"""
    db = get_db()
    
    # Crea tabella documents
    db.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            size INTEGER NOT NULL,
            upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT NOT NULL
        )
    ''')
    
    # Crea tabella document_requests
    db.execute('''
        CREATE TABLE IF NOT EXISTS document_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            requested_by TEXT NOT NULL,
            request_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    # Crea tabella users per gestire autenticazione
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Inserisce utenti di default
    try:
        db.execute(
            'INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)',
            ('admin@dazefuture.com', 'pbkdf2:sha256:260000$abc123$def456', 'admin')
        )
        print("Admin user created: admin@dazefuture.com")
    except sqlite3.IntegrityError:
        pass  # L'utente admin esiste già
    
    try:
        db.execute(
            'INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)',
            ('user@dazefuture.com', 'pbkdf2:sha256:260000$xyz789$uvw000', 'user')
        )
        print("User created: user@dazefuture.com")
    except sqlite3.IntegrityError:
        pass  # L'utente user esiste già
    
    db.commit()
    print("Database initialized successfully!")

def get_db():
    """Ottiene la connessione al database"""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Chiude la connessione al database"""
    if hasattr(g, 'db'):
        g.db.close()

def allowed_file(filename):
    """Verifica se il tipo di file è permesso"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Sistema di autenticazione semplificato
def get_current_user():
    """Funzione semplificata per ottenere l'utente corrente"""
    # In un'app reale, questa funzione verificherebbe il token JWT o la sessione
    # Per ora simuliamo con header personalizzati
    user_email = request.headers.get('X-User-Email', 'user@dazefuture.com')
    user_role = request.headers.get('X-User-Role', 'user')
    
    return {
        'email': user_email,
        'role': user_role
    }

# API Routes
@app.route('/')
def home():
    return jsonify({
        'message': 'Daze for Future API',
        'version': '1.0',
        'port': 5001,
        'endpoints': {
            'documents': '/api/documents',
            'upload': '/api/upload',
            'download': '/api/download/<id>',
            'delete': '/api/delete/<id>',
            'request': '/api/request',
            'requests': '/api/requests'
        }
    })

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Restituisce tutti i documenti disponibili"""
    try:
        db = get_db()
        cursor = db.execute('SELECT * FROM documents ORDER BY upload_date DESC')
        documents = cursor.fetchall()
        
        result = []
        for doc in documents:
            result.append({
                'id': doc['id'],
                'name': doc['name'],
                'file_type': doc['file_type'],
                'size': doc['size'],
                'upload_date': doc['upload_date'],
                'uploaded_by': doc['uploaded_by']
            })
        
        return jsonify({'success': True, 'documents': result})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel recupero documenti: {str(e)}'}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Carica uno o più documenti (solo admin)"""
    try:
        # Verifica autenticazione e ruolo admin
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono caricare documenti'}), 403
        
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': 'Nessun file selezionato'}), 400
        
        files = request.files.getlist('files')
        uploaded_files = []
        
        for file in files:
            if file.filename == '':
                continue
                
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # Crea la cartella uploads se non esiste
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])
                
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Gestisci file con lo stesso nome
                counter = 1
                original_filename = filename
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_filename)
                    filename = f"{name}_{counter}{ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    counter += 1
                
                file.save(file_path)
                
                # Salva informazioni nel database
                db = get_db()
                db.execute(
                    'INSERT INTO documents (name, file_path, file_type, size, uploaded_by) VALUES (?, ?, ?, ?, ?)',
                    (filename, file_path, filename.rsplit('.', 1)[1].lower(), 
                     os.path.getsize(file_path), user['email'])
                )
                db.commit()
                
                uploaded_files.append(filename)
            else:
                return jsonify({'success': False, 'message': f'Tipo file non supportato: {file.filename}'}), 400
        
        return jsonify({
            'success': True, 
            'message': f'{len(uploaded_files)} file caricati con successo',
            'files': uploaded_files
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel caricamento: {str(e)}'}), 500

@app.route('/api/download/<int:document_id>')
def download_document(document_id):
    """Scarica un documento specifico"""
    try:
        db = get_db()
        cursor = db.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
        document = cursor.fetchone()
        
        if document is None:
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        if not os.path.exists(document['file_path']):
            return jsonify({'success': False, 'message': 'File non trovato sul server'}), 404
        
        return send_file(
            document['file_path'], 
            as_attachment=True, 
            download_name=document['name']
        )
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel download: {str(e)}'}), 500

@app.route('/api/delete/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Elimina un documento (solo admin)"""
    try:
        # Verifica autenticazione e ruolo admin
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono eliminare documenti'}), 403
        
        db = get_db()
        
        # Recupera informazioni sul file
        cursor = db.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
        document = cursor.fetchone()
        
        if document is None:
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        # Elimina il file fisico
        try:
            if os.path.exists(document['file_path']):
                os.remove(document['file_path'])
        except OSError as e:
            print(f"Errore nell'eliminazione del file: {e}")
        
        # Elimina record dal database
        db.execute('DELETE FROM documents WHERE id = ?', (document_id,))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Documento eliminato con successo'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nell\'eliminazione: {str(e)}'}), 500

@app.route('/api/request', methods=['POST'])
def request_document():
    """Invia una richiesta per un nuovo documento"""
    try:
        # Verifica autenticazione
        user = get_current_user()
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Dati non validi'}), 400
        
        document_name = data.get('name')
        document_description = data.get('description', '')
        
        if not document_name:
            return jsonify({'success': False, 'message': 'Nome documento richiesto'}), 400
        
        # Salva richiesta nel database
        db = get_db()
        db.execute(
            'INSERT INTO document_requests (name, description, requested_by) VALUES (?, ?, ?)',
            (document_name, document_description, user['email'])
        )
        db.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Richiesta inviata con successo. Gli admin la prenderanno in considerazione.'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nell\'invio della richiesta: {str(e)}'}), 500

@app.route('/api/requests', methods=['GET'])
def get_requests():
    """Restituisce tutte le richieste (solo admin)"""
    try:
        # Verifica autenticazione e ruolo admin
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono vedere le richieste'}), 403
        
        db = get_db()
        cursor = db.execute('SELECT * FROM document_requests ORDER BY request_date DESC')
        requests = cursor.fetchall()
        
        result = []
        for req in requests:
            result.append({
                'id': req['id'],
                'name': req['name'],
                'description': req['description'],
                'requested_by': req['requested_by'],
                'request_date': req['request_date'],
                'status': req['status']
            })
        
        return jsonify({'success': True, 'requests': result})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel recupero richieste: {str(e)}'}), 500

# API per simulare login
@app.route('/api/login', methods=['POST'])
def login():
    """Endpoint per simulare il login"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

# Gestione errori
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Endpoint non trovato'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'Errore interno del server'}), 500

# Inizializzazione dell'app
if __name__ == '__main__':
    with app.app_context():
        init_db()
    
    print("=" * 60)
    print("Daze for Future Document Management System")
    print("Server in esecuzione su porta 5001")
    print("Database creato automaticamente: documents.db")
    print("Cartella uploads creata automaticamente")
    print("Accesso: http://localhost:5001")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5001)