import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_file, g
from werkzeug.utils import secure_filename
from flask_cors import CORS 

app = Flask(__name__)

# Configurazione corretta dei percorsi
app.config['UPLOAD_FOLDER'] = os.path.join('documenti')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size
app.config['DATABASE'] = os.path.join('../../database/documenti.db')

# Abilita CORS per tutte le origini
CORS(app)

# Estensioni permesse
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip'}

# Funzione per inizializzare il database
def init_db():
    """Inizializza il database con le tabelle necessarie"""
    try:
        # Crea la cartella per il database se non esiste
        os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
        
        db = get_db()
        
        # Crea tabella documents (documenti pubblicati)
        db.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                uploaded_by TEXT NOT NULL,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'published'
            )
        ''')
        
        # Crea tabella publications (bozze e pubblicazioni)
        db.execute('''
            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                author TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending', -- pending, approved, rejected, published
                reviewed_by TEXT,
                reviewed_at DATETIME,
                review_notes TEXT,
                original_filename TEXT,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
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
        
        db.commit()
        print("✅ Database initialized successfully!")
        print(f"📁 Database path: {app.config['DATABASE']}")
        
        # Verifica che le tabelle siano state create
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📊 Tabelle create: {[table[0] for table in tables]}")
        
    except Exception as e:
        print(f"❌ Errore nell'inizializzazione del database: {str(e)}")

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
    user_email = request.headers.get('X-User-Email', '')
    user_role = request.headers.get('X-User-Role', 'user')
    
    return {
        'email': user_email,
        'role': user_role
    }

# API Routes
@app.route('/')
def home():
    return jsonify({
        'message': 'Daze for Future API - Sistema Documenti',
        'version': '2.4',
        'port': 5001,
        'features': ['bozze_persistenti', 'cloud_sync', 'admin_dashboard'],
        'endpoints': {
            'documents': '/api/documents',
            'upload': '/api/upload',
            'download': '/api/download/<id>',
            'delete': '/api/delete/<id>',
            'request': '/api/request',
            'requests': '/api/requests',
            'create_publication': '/api/create_publication',
            'drafts': '/api/drafts',
            'my_drafts': '/api/my_drafts',
            'review_draft': '/api/review_draft/<id>',
            'view_draft': '/api/view_draft/<id>',
            'delete_draft': '/api/delete_draft/<id>',
            'all_publications': '/api/all_publications'
        }
    })

@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Restituisce tutti i documenti pubblicati"""
    try:
        db = get_db()
        cursor = db.execute('''
            SELECT * FROM documents 
            WHERE status = 'published'
            ORDER BY upload_date DESC
        ''')
        documents = cursor.fetchall()
        
        result = []
        for doc in documents:
            result.append({
                'id': doc['id'],
                'name': doc['name'],  # Nome file originale per download
                'title': doc['title'] or doc['name'],  # Titolo per visualizzazione
                'description': doc['description'],
                'file_type': doc['file_type'],
                'size': doc['size'],
                'upload_date': doc['upload_date'],
                'uploaded_by': doc['uploaded_by'],
                'status': 'published'  # Fisso per documenti pubblicati
            })
        
        return jsonify({'success': True, 'documents': result})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel recupero documenti: {str(e)}'}), 500

@app.route('/api/all_publications', methods=['GET'])
def get_all_publications():
    """Restituisce tutte le pubblicazioni (bozze e documenti) per admin"""
    try:
        # Verifica autenticazione e ruolo admin
        user = get_current_user()
        print(f"🔍 Debug all_publications - User: {user}")
        
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono vedere tutte le pubblicazioni'}), 403
        
        db = get_db()
        
        # Recupera documenti pubblicati con più debug
        print("📋 Recupero documenti pubblicati...")
        cursor = db.execute('''
            SELECT id, name as title, description, file_type, size, 
                   uploaded_by as author, upload_date as created_at, 
                   'published' as status, NULL as reviewed_by, NULL as reviewed_at,
                   name as original_filename
            FROM documents 
            WHERE status = 'published'
            ORDER BY upload_date DESC
        ''')
        documents = cursor.fetchall()
        print(f"✅ Documenti trovati: {len(documents)}")
        
        # Recupera bozze con più debug
        print("📋 Recupero bozze...")
        cursor = db.execute('''
            SELECT id, title, description, file_type, size, author, 
                   created_at, status, reviewed_by, reviewed_at, original_filename
            FROM publications 
            ORDER BY created_at DESC
        ''')
        publications = cursor.fetchall()
        print(f"✅ Bozze trovate: {len(publications)}")
        
        result = []
        
        # Aggiungi documenti pubblicati
        for doc in documents:
            print(f"📄 Elaborazione documento: {doc['title']}")
            result.append({
                'id': f"doc_{doc['id']}",
                'title': doc['title'],
                'description': doc['description'],
                'file_type': doc['file_type'],
                'size': doc['size'],
                'author': doc['author'],
                'created_at': doc['created_at'],
                'status': 'published',
                'type': 'document',
                'reviewed_by': doc['reviewed_by'],
                'reviewed_at': doc['reviewed_at'],
                'original_filename': doc['original_filename']
            })
        
        # Aggiungi bozze
        for pub in publications:
            print(f"📝 Elaborazione bozza: {pub['title']}")
            result.append({
                'id': f"pub_{pub['id']}",
                'title': pub['title'],
                'description': pub['description'],
                'file_type': pub['file_type'],
                'size': pub['size'],
                'author': pub['author'],
                'created_at': pub['created_at'],
                'status': pub['status'],
                'type': 'publication',
                'reviewed_by': pub['reviewed_by'],
                'reviewed_at': pub['reviewed_at'],
                'original_filename': pub['original_filename']
            })
        
        # Ordina per data di creazione
        print("🔄 Ordinamento risultati...")
        result.sort(key=lambda x: x['created_at'], reverse=True)
        
        print(f"✅ Totale pubblicazioni: {len(result)}")
        return jsonify({'success': True, 'publications': result})
    
    except Exception as e:
        print(f"❌ Errore critico in get_all_publications: {str(e)}")
        import traceback
        print(f"🔍 Traceback completo: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Errore nel recupero pubblicazioni: {str(e)}'}), 500
    
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Carica uno o più documenti (solo admin) - metodo diretto"""
    try:
        # Verifica autenticazione e ruolo admin
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono caricare documenti'}), 403
        
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': 'Nessun file selezionato'}), 400
        
        files = request.files.getlist('files')
        uploaded_files = []
        
        # Crea la cartella uploads se non esiste
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        for file in files:
            if file.filename == '':
                continue
                
            if file and allowed_file(file.filename):
                original_filename = secure_filename(file.filename)
                filename = original_filename  # Usa il nome originale come punto di partenza
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Gestisci file con lo stesso nome
                counter = 1
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_filename)
                    filename = f"{name}_{counter}{ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    counter += 1
                
                file.save(file_path)
                file_size = os.path.getsize(file_path)
                file_type = filename.rsplit('.', 1)[1].lower()
                
                # Salva informazioni nel database - usa il nome ORIGINALE per il download
                db = get_db()
                db.execute(
                    'INSERT INTO documents (name, file_path, file_type, size, uploaded_by, status) VALUES (?, ?, ?, ?, ?, ?)',
                    (original_filename, file_path, file_type, file_size, user['email'], 'published')  # Salva original_filename come name
                )
                db.commit()
                
                uploaded_files.append(original_filename)
            else:
                return jsonify({'success': False, 'message': f'Tipo file non supportato: {file.filename}'}), 400
        
        return jsonify({
            'success': True, 
            'message': f'{len(uploaded_files)} file caricati con successo',
            'files': uploaded_files
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel caricamento: {str(e)}'}), 500
    
@app.route('/api/create_publication', methods=['POST'])
def create_publication():
    """Crea una nuova pubblicazione (sia user che admin) - VERSIONE PERSISTENTE"""
    try:
        # Verifica autenticazione
        user = get_current_user()
        if not user['email']:
            return jsonify({'success': False, 'message': 'Autenticazione richiesta'}), 401
        
        # Verifica se è un file upload
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Nessun file selezionato'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Nessun file selezionato'}), 400
        
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        
        if not title:
            return jsonify({'success': False, 'message': 'Titolo richiesto'}), 400
        
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            filename = original_filename
            
            # Crea la cartella uploads se non esiste
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            
            # Se è admin, pubblica direttamente
            if user['role'] == 'admin':
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Gestisci file con lo stesso nome
                counter = 1
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_filename)
                    filename = f"{name}_{counter}{ext}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    counter += 1
                
                file.save(file_path)
                file_type = filename.rsplit('.', 1)[1].lower()
                file_size = os.path.getsize(file_path)
                
                # Salva direttamente come documento pubblicato - usa nome originale per download
                db = get_db()
                db.execute(
                    'INSERT INTO documents (name, file_path, file_type, size, uploaded_by, title, description, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (original_filename, file_path, file_type, file_size, user['email'], title, description, 'published')
                )
                db.commit()
                
                return jsonify({
                    'success': True, 
                    'message': 'Documento pubblicato con successo!'
                })
            
            else:
                # Se è user, crea bozza PERSISTENTE nel database
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                draft_filename = f"draft_{timestamp}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], draft_filename)
                
                file.save(file_path)
                file_type = filename.rsplit('.', 1)[1].lower()
                file_size = os.path.getsize(file_path)
                
                # Salva come bozza PERSISTENTE nel database - salva nome originale
                db = get_db()
                db.execute(
                    '''INSERT INTO publications 
                    (title, description, file_path, file_type, size, author, status, original_filename, last_modified) 
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)''',
                    (title, description, file_path, file_type, file_size, user['email'], original_filename)
                )
                db.commit()
                
                # Ottieni l'ID della bozza appena creata
                cursor = db.execute('SELECT last_insert_rowid() as id')
                draft_id = cursor.fetchone()['id']
                
                return jsonify({
                    'success': True, 
                    'message': 'Bozza creata con successo! In attesa di revisione da parte degli admin.',
                    'draft_id': draft_id,
                    'cloud_saved': True
                })
        else:
            return jsonify({'success': False, 'message': 'Tipo file non supportato'}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nella creazione della pubblicazione: {str(e)}'}), 500

@app.route('/api/drafts', methods=['GET'])
def get_drafts():
    """Restituisce tutte le bozze da revisionare (solo admin)"""
    try:
        # Verifica autenticazione e ruolo admin
        user = get_current_user()
        print(f"🔍 Debug get_drafts - User: {user}")  # Debug
        
        if user['role'] != 'admin':
            print(f"❌ Accesso negato - Ruolo: {user['role']}")  # Debug
            return jsonify({'success': False, 'message': 'Solo gli admin possono vedere le bozze'}), 403
        
        db = get_db()
        cursor = db.execute('''
            SELECT * FROM publications 
            WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        drafts = cursor.fetchall()
        
        print(f"📋 Bozze trovate: {len(drafts)}")  # Debug
        
        result = []
        for draft in drafts:
            result.append({
                'id': draft['id'],
                'title': draft['title'],  # Titolo della pubblicazione
                'description': draft['description'],
                'file_type': draft['file_type'],
                'size': draft['size'],
                'author': draft['author'],
                'created_at': draft['created_at'],
                'status': draft['status'],
                'original_filename': draft['original_filename'],  # Nome file originale
                'last_modified': draft['last_modified']
            })
        
        return jsonify({'success': True, 'drafts': result})
    
    except Exception as e:
        print(f"❌ Errore nel recupero bozze: {str(e)}")  # Debug
        return jsonify({'success': False, 'message': f'Errore nel recupero bozze: {str(e)}'}), 500
    
@app.route('/api/my_drafts', methods=['GET'])
def get_my_drafts():
    """Restituisce le bozze PERSISTENTI dell'utente corrente"""
    try:
        user = get_current_user()
        if not user['email']:
            return jsonify({'success': False, 'message': 'Autenticazione richiesta'}), 401
        
        db = get_db()
        cursor = db.execute('''
            SELECT * FROM publications 
            WHERE author = ?
            ORDER BY created_at DESC
        ''', (user['email'],))
        drafts = cursor.fetchall()
        
        result = []
        for draft in drafts:
            result.append({
                'id': draft['id'],
                'title': draft['title'],  # Titolo della pubblicazione
                'description': draft['description'],
                'file_type': draft['file_type'],
                'size': draft['size'],
                'author': draft['author'],
                'created_at': draft['created_at'],
                'status': draft['status'],
                'review_notes': draft['review_notes'],
                'reviewed_by': draft['reviewed_by'],
                'reviewed_at': draft['reviewed_at'],
                'original_filename': draft['original_filename'],  # Nome file originale
                'last_modified': draft['last_modified'],
                'cloud_saved': True
            })
        
        return jsonify({'success': True, 'drafts': result})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel recupero bozze: {str(e)}'}), 500

@app.route('/api/review_draft/<int:draft_id>', methods=['POST'])
def review_draft(draft_id):
    """Revisiona una bozza (solo admin)"""
    try:
        # Verifica autenticazione e ruolo admin
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono revisionare bozze'}), 403
        
        data = request.get_json()
        action = data.get('action')  # 'approved' o 'rejected'
        review_notes = data.get('review_notes', '')
        
        if action not in ['approved', 'rejected']:
            return jsonify({'success': False, 'message': 'Azione non valida'}), 400
        
        db = get_db()
        
        # Recupera la bozza
        cursor = db.execute('SELECT * FROM publications WHERE id = ?', (draft_id,))
        draft = cursor.fetchone()
        
        if not draft:
            return jsonify({'success': False, 'message': 'Bozza non trovata'}), 404
        
        if action == 'approved':
            # Sposta il file dalla cartella bozze a documenti pubblicati
            original_path = draft['file_path']
            
            # Usa SEMPRE il nome file originale per il file pubblicato
            if draft['original_filename']:
                filename = draft['original_filename']
            else:
                # Fallback: estrai dal path
                original_name = os.path.basename(original_path)
                if original_name.startswith('draft_'):
                    parts = original_name.split('_', 2)
                    if len(parts) >= 3:
                        filename = parts[2]
                    else:
                        filename = original_name[6:]
                else:
                    filename = original_name
            
            new_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Gestisci file con lo stesso nome
            counter = 1
            name, ext = os.path.splitext(filename)
            while os.path.exists(new_path):
                new_filename = f"{name}_{counter}{ext}"
                new_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                counter += 1
            
            # Rinomina il file
            os.rename(original_path, new_path)
            
            # Aggiungi ai documenti pubblicati - usa nome originale per download
            db.execute(
                '''INSERT INTO documents (name, file_path, file_type, size, uploaded_by, title, description, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (draft['original_filename'], new_path, draft['file_type'], 
                 draft['size'], draft['author'], draft['title'], draft['description'], 'published')
            )
            
            # Aggiorna lo stato della bozza
            db.execute(
                '''UPDATE publications SET status = 'published', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_notes = ?, last_modified = CURRENT_TIMESTAMP
                WHERE id = ?''',
                (user['email'], review_notes, draft_id)
            )
            
            message = 'Bozza approvata e pubblicata con successo'
        
        else:  # rejected
            # Aggiorna solo lo stato
            db.execute(
                '''UPDATE publications SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP, review_notes = ?, last_modified = CURRENT_TIMESTAMP
                WHERE id = ?''',
                (user['email'], review_notes, draft_id)
            )
            
            message = 'Bozza rifiutata'
        
        db.commit()
        return jsonify({'success': True, 'message': message})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nella revisione: {str(e)}'}), 500

@app.route('/api/view_draft/<int:draft_id>')
def view_draft(draft_id):
    """Visualizza una bozza PERSISTENTE con il nome originale e mimetype corretto"""
    try:
        user = get_current_user()
        if not user['email']:
            return jsonify({'success': False, 'message': 'Autenticazione richiesta'}), 401
        
        db = get_db()
        cursor = db.execute('SELECT * FROM publications WHERE id = ?', (draft_id,))
        draft = cursor.fetchone()
        
        if draft is None:
            return jsonify({'success': False, 'message': 'Bozza non trovata'}), 404
        
        # Verifica permessi: solo admin o autore possono visualizzare
        if user['role'] != 'admin' and draft['author'] != user['email']:
            return jsonify({'success': False, 'message': 'Non hai i permessi per visualizzare questa bozza'}), 403
        
        if not os.path.exists(draft['file_path']):
            return jsonify({'success': False, 'message': 'File non trovato sul server'}), 404
        
        # Usa SEMPRE il nome file originale per il download
        download_name = draft['original_filename'] or f"{draft['title']}.{draft['file_type']}"
        
        # Determina il mimetype corretto in base all'estensione
        mimetype = None
        file_extension = download_name.lower().split('.')[-1]
        
        # Mappa delle estensioni ai mimetype comuni
        mimetype_map = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'txt': 'text/plain',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'zip': 'application/zip'
        }
        
        mimetype = mimetype_map.get(file_extension, 'application/octet-stream')
        
        return send_file(
            draft['file_path'], 
            as_attachment=True, 
            download_name=download_name,
            mimetype=mimetype  # Usa il mimetype corretto
        )
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel download: {str(e)}'}), 500

@app.route('/api/download/<int:document_id>')
def download_document(document_id):
    """Scarica un documento specifico con il nome originale e mimetype corretto"""
    try:
        db = get_db()
        cursor = db.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
        document = cursor.fetchone()
        
        if document is None:
            return jsonify({'success': False, 'message': 'Documento non trovato'}), 404
        
        if not os.path.exists(document['file_path']):
            return jsonify({'success': False, 'message': 'File non trovato sul server'}), 404
        
        # Usa SEMPRE il nome originale dal database per il download
        original_filename = document['name']
        
        # Determina il mimetype corretto in base all'estensione
        mimetype = None
        file_extension = original_filename.lower().split('.')[-1]
        
        # Mappa delle estensioni ai mimetype comuni
        mimetype_map = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'txt': 'text/plain',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'zip': 'application/zip'
        }
        
        mimetype = mimetype_map.get(file_extension, 'application/octet-stream')
        
        return send_file(
            document['file_path'], 
            as_attachment=True, 
            download_name=original_filename,
            mimetype=mimetype  # Usa il mimetype corretto
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

@app.route('/api/delete_draft/<int:draft_id>', methods=['DELETE'])
def delete_draft(draft_id):
    """Elimina una bozza (solo admin o autore)"""
    try:
        user = get_current_user()
        if not user['email']:
            return jsonify({'success': False, 'message': 'Autenticazione richiesta'}), 401
        
        db = get_db()
        
        # Recupera informazioni sulla bozza
        cursor = db.execute('SELECT * FROM publications WHERE id = ?', (draft_id,))
        draft = cursor.fetchone()
        
        if draft is None:
            return jsonify({'success': False, 'message': 'Bozza non trovata'}), 404
        
        # Verifica permessi: solo admin o autore possono eliminare
        if user['role'] != 'admin' and draft['author'] != user['email']:
            return jsonify({'success': False, 'message': 'Non hai i permessi per eliminare questa bozza'}), 403
        
        # Elimina il file fisico
        try:
            if os.path.exists(draft['file_path']):
                os.remove(draft['file_path'])
        except OSError as e:
            print(f"Errore nell'eliminazione del file: {e}")
        
        # Elimina record dal database
        db.execute('DELETE FROM publications WHERE id = ?', (draft_id,))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Bozza eliminata con successo'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nell\'eliminazione: {str(e)}'}), 500

@app.route('/api/debug/database')
def debug_database():
    """Endpoint di debug per verificare lo stato del database"""
    try:
        db = get_db()
        
        # Conta record nelle tabelle
        cursor = db.execute("SELECT COUNT(*) as count FROM publications")
        publications_count = cursor.fetchone()['count']
        
        cursor = db.execute("SELECT COUNT(*) as count FROM documents")
        documents_count = cursor.fetchone()['count']
        
        # Verifica struttura tabelle
        cursor = db.execute("PRAGMA table_info(publications)")
        publications_columns = [dict(row) for row in cursor.fetchall()]
        
        cursor = db.execute("PRAGMA table_info(documents)")
        documents_columns = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({
            'success': True,
            'database_path': app.config['DATABASE'],
            'tables': {
                'publications': {
                    'count': publications_count,
                    'columns': publications_columns
                },
                'documents': {
                    'count': documents_count,
                    'columns': documents_columns
                }
            },
            'upload_folder': {
                'path': app.config['UPLOAD_FOLDER'],
                'exists': os.path.exists(app.config['UPLOAD_FOLDER'])
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
    print("🚀 Server Documenti")
    print(f"📁 Database: {app.config['DATABASE']}")
    print(f"📁 Cartella documenti: {app.config['UPLOAD_FOLDER']}")
    print("🌐 Su: http://localhost:5001")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5001)