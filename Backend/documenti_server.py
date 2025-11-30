import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from werkzeug.utils import secure_filename
from config import BaseConfig, require_secrets
from file_utils import allowed_file, save_uploaded_file, safe_send_file, validate_file_ownership
from logging.handlers import RotatingFileHandler
from security import sanitize_text, is_valid_email

app = Flask(__name__)
app.config.from_object(BaseConfig)

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
)

# Configure CORS with whitelist
allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app,
    origins=allowed_origins,
    supports_credentials=True,
    methods=['GET', 'POST', 'DELETE', 'PUT', 'OPTIONS'],
    allow_headers=['Content-Type', 'X-User-Email', 'X-User-Role']
)

# Setup logging
if not app.debug:
    handler = RotatingFileHandler('documenti.log', maxBytes=10*1024*1024, backupCount=5)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['DATABASE'] = os.path.join('../../database', 'documenti.db')

# Directory di storage dei PDF (assolute)
DB_DIR = os.path.abspath(os.path.join(BASE_DIR, os.path.dirname(app.config['DATABASE'])))
STORAGE_ROOT = os.path.join(DB_DIR, 'documenti_server')
DRAFTS_FOLDER = 'bozze'
PUBLISHED_FOLDER = 'pubblicazioni'

def init_db():
    """Inizializza il database con la tabella articles e le cartelle file"""
    try:
        os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
        # crea cartelle per i file
        os.makedirs(STORAGE_ROOT, exist_ok=True)
        os.makedirs(os.path.join(STORAGE_ROOT, DRAFTS_FOLDER), exist_ok=True)
        os.makedirs(os.path.join(STORAGE_ROOT, PUBLISHED_FOLDER), exist_ok=True)

        db = get_db()
        
        db.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL, 
                publication_date DATETIME NOT NULL,
                drive_link TEXT NOT NULL,
                description TEXT,
                file_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_published INTEGER DEFAULT 0,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.commit()

        # Migrazione minima: aggiungi la colonna review_notes se manca (usata per rifiuti)
        cur = db.execute("PRAGMA table_info(articles)")
        cols = [row['name'] for row in cur.fetchall()]
        if 'review_notes' not in cols:
            try:
                db.execute("ALTER TABLE articles ADD COLUMN review_notes TEXT DEFAULT ''")
                db.commit()
            except Exception:
                # ignore se non possibile (compatibilità)
                pass
        
        print("Database initialized successfully!")
        print(f"Database path: {app.config['DATABASE']}")
        print(f"Storage root: {STORAGE_ROOT}")
        
    except Exception as e:
        print(f"Errore nell'inizializzazione del database: {str(e)}")

def get_db():
    """Ottiene la connessione al database"""
    if 'db' not in g:
        db_path = os.path.abspath(os.path.join(BASE_DIR, app.config['DATABASE']))
        # se il path era già assoluto nella config, os.path.abspath lo lascia intatto
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Chiude la connessione al database"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_current_user():
    """Funzione semplificata per ottenere l'utente corrente"""
    return {
        'email': request.headers.get('X-User-Email', ''),
        'role': request.headers.get('X-User-Role', 'user')
    }

@app.route('/api/articles', methods=['GET'])
def get_articles():
    """Restituisce gli articoli in base al ruolo dell'utente"""
    try:
        user = get_current_user()
        db = get_db()
        
        if user['role'] == 'admin':
            # Admin vede tutto
            cursor = db.execute('''
                SELECT * FROM articles 
                ORDER BY publication_date DESC
            ''')
        else:
            # Altri utenti vedono solo articoli pubblicati
            cursor = db.execute('''
                SELECT * FROM articles 
                WHERE is_published = 1
                ORDER BY publication_date DESC
            ''')
            
        articles = cursor.fetchall()
        
        result = []
        for article in articles:
            is_pub = bool(article['is_published'])
            folder = PUBLISHED_FOLDER if is_pub else DRAFTS_FOLDER
            file_url = None
            if article['file_name']:
                file_url = f"/files/{folder}/{article['file_name']}"
            result.append({
                'id': article['id'],
                'title': article['title'],
                'author': article['author'],
                'publication_date': article['publication_date'],
                'drive_link': article['drive_link'],
                'description': article['description'],
                'is_published': is_pub,
                'file_name': article['file_name'],
                'file_url': file_url
            })
        
        # Fornisco both 'articles' e 'documents' per compatibilità col frontend
        return jsonify({'success': True, 'articles': result, 'documents': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/articles', methods=['POST'])
@limiter.limit("10 per hour")
def create_article():
    """Crea un nuovo articolo (solo admin)"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono creare articoli'}), 403
        
        data = request.get_json() or {}
        required = ['title', 'author', 'publication_date', 'drive_link']
        
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Campo {field} richiesto'}), 400
        
        file_name = data.get('file_name')  # nome con cui il PDF è salvato nel filesystem (opzionale)
        # Se viene fornito file_name, verifico che esista nella cartella corretta in base a is_published
        is_published = bool(data.get('is_published', False))
        if file_name:
            expected_folder = PUBLISHED_FOLDER if is_published else DRAFTS_FOLDER
            expected_path = os.path.join(STORAGE_ROOT, expected_folder, file_name)
            if not os.path.isfile(expected_path):
                return jsonify({'success': False, 'message': f'File non trovato in {expected_folder} con nome {file_name}'}), 400
        
        db = get_db()
        db.execute('''
            INSERT INTO articles (
                title, author, publication_date, drive_link, 
                description, file_name, is_published
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['title'],
            data['author'],
            data['publication_date'], 
            data['drive_link'],
            data.get('description', ''),
            file_name,
            1 if is_published else 0
        ))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Articolo creato con successo'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/articles/<int:article_id>/publish', methods=['POST'])
@limiter.limit("20 per hour")
def toggle_publish(article_id):
    """Pubblica o mette in revisione un articolo (solo admin) e sposta il file se presente"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono pubblicare articoli'}), 403
        
        data = request.get_json() or {}
        is_published = bool(data.get('is_published', True))
        
        db = get_db()
        # leggo lo stato e il nome file corrente
        cur = db.execute('SELECT file_name, is_published FROM articles WHERE id = ?', (article_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Articolo non trovato'}), 404
        
        old_is_published = bool(row['is_published'])
        file_name = row['file_name']
        # se c'è un file e lo stato cambia, sposto il file tra le cartelle
        if file_name and (old_is_published != is_published):
            src_folder = PUBLISHED_FOLDER if old_is_published else DRAFTS_FOLDER
            dst_folder = PUBLISHED_FOLDER if is_published else DRAFTS_FOLDER
            src = os.path.join(STORAGE_ROOT, src_folder, file_name)
            dst_dir = os.path.join(STORAGE_ROOT, dst_folder)
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, file_name)
            if os.path.isfile(src):
                try:
                    os.replace(src, dst)
                except Exception as e:
                    return jsonify({'success': False, 'message': f'Errore nello spostamento file: {str(e)}'}), 500
        
        db.execute('''
            UPDATE articles 
            SET is_published = ?, 
                last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (1 if is_published else 0, article_id))
        db.commit()
        
        status = "pubblicato" if is_published else "messo in revisione"
        return jsonify({
            'success': True, 
            'message': f'Articolo {status} con successo'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/articles/<int:article_id>', methods=['DELETE'])
def delete_article(article_id):
    """Elimina un articolo (solo admin) e il relativo file se presente"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono eliminare articoli'}), 403
        
        db = get_db()
        cur = db.execute('SELECT file_name, is_published FROM articles WHERE id = ?', (article_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Articolo non trovato'}), 404
        
        file_name = row['file_name']
        folder = PUBLISHED_FOLDER if row['is_published'] else DRAFTS_FOLDER
        if file_name:
            file_path = os.path.join(STORAGE_ROOT, folder, file_name)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                return jsonify({'success': False, 'message': f'Errore eliminazione file: {str(e)}'}), 500
        
        db.execute('DELETE FROM articles WHERE id = ?', (article_id,))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Articolo eliminato con successo'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/files/<folder>/<path:filename>', methods=['GET'])
def serve_file(folder, filename):
    """Serve i PDF con protezione contro path traversal."""
    try:
        if folder not in (PUBLISHED_FOLDER, DRAFTS_FOLDER):
            return jsonify({'success': False, 'message': 'Folder non valido'}), 400
        
        user = get_current_user()
        
        # Accesso a bozze solo per admin
        if folder == DRAFTS_FOLDER and user['role'] != 'admin':
            app.logger.warning(f"Unauthorized draft access attempt by {user['email']}")
            return jsonify({'success': False, 'message': 'Accesso negato'}), 403
        
        directory = os.path.join(STORAGE_ROOT, folder)
        app.logger.info(f"File serve request: {user['email']} -> {folder}/{filename}")
        return safe_send_file(directory, filename)
    
    except Exception as e:
        app.logger.error(f"File serve error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/documents', methods=['GET'])
def get_documents_wrapper():
    # wrapper compatibile -> riusa get_articles
    return get_articles()

@app.route('/api/create_publication', methods=['POST', 'OPTIONS'])
@limiter.limit("20 per hour")
def create_publication():
    """Create a new publication with file upload (admin only)."""
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono creare pubblicazioni'}), 403

        # Extract form fields
        title = request.form.get('title', '').strip()
        author = request.form.get('author', user.get('email', ''))
        publication_date = request.form.get('publication_date') or datetime.utcnow().isoformat()
        drive_link = request.form.get('drive_link', '').strip()
        description = request.form.get('description', '').strip()
        is_published = request.form.get('is_published', '0') in ('1', 'true', 'True', 'on')

        if not title or not author or not publication_date:
            return jsonify({'success': False, 'message': 'Campi title, author e publication_date richiesti'}), 400

        file_name = None
        file = request.files.get('file')
        
        if file and file.filename:
            try:
                dest_folder = PUBLISHED_FOLDER if is_published else DRAFTS_FOLDER
                dest_dir = os.path.join(STORAGE_ROOT, dest_folder)
                file_name = save_uploaded_file(file, dest_dir, app.config['ALLOWED_EXTENSIONS'], max_size_mb=8)
                app.logger.info(f"File uploaded by {user['email']}: {file_name}")
            except ValueError as ve:
                app.logger.warning(f"File upload validation failed: {str(ve)}")
                return jsonify({'success': False, 'message': f"File upload error: {str(ve)}"}), 400

        db = get_db()
        db.execute('''
            INSERT INTO articles (
                title, author, publication_date, drive_link,
                description, file_name, is_published
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            title,
            author,
            publication_date,
            drive_link,
            description,
            file_name,
            1 if is_published else 0
        ))
        db.commit()

        app.logger.info(f"Publication created by {user['email']}: {title}")
        return jsonify({'success': True, 'message': 'Pubblicazione creata con successo'})

    except Exception as e:
        app.logger.error(f"Publication creation error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Compatibilità API frontend -- START ---
@app.route('/api/drafts', methods=['GET'])
def api_get_drafts():
    """Lista bozze (admin sees all, others none)"""
    try:
        user = get_current_user()
        db = get_db()
        cursor = db.execute("SELECT * FROM articles WHERE is_published = 0 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        drafts = []
        for r in rows:
            file_name = r['file_name']
            _, ext = os.path.splitext(file_name or '')
            file_type = ext.lstrip('.').lower() if ext else None
            file_url = None
            if file_name:
                file_url = f"/files/{DRAFTS_FOLDER}/{file_name}"
            review_notes = r['review_notes'] if 'review_notes' in r.keys() else ''
            drafts.append({
                'id': r['id'],
                'title': r['title'],
                'description': r['description'],
                'author': r['author'],
                'created_at': r['created_at'],
                'status': 'pending',
                'type': None,
                'file_type': file_type,
                'original_name': file_name,
                'file_url': file_url,
                'review_notes': review_notes
            })
        return jsonify({'success': True, 'drafts': drafts})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/my_drafts', methods=['GET'])
def api_my_drafts():
    """Bozze dell'utente corrente"""
    try:
        user = get_current_user()
        email = user.get('email', '')
        if not email:
            return jsonify({'success': False, 'message': 'Utente non autenticato'}), 401
        db = get_db()
        cursor = db.execute("SELECT * FROM articles WHERE is_published = 0 AND author = ? ORDER BY created_at DESC", (email,))
        rows = cursor.fetchall()
        drafts = []
        for r in rows:
            file_name = r['file_name']
            _, ext = os.path.splitext(file_name or '')
            file_type = ext.lstrip('.').lower() if ext else None
            file_url = f"/files/{DRAFTS_FOLDER}/{file_name}" if file_name else None
            review_notes = r['review_notes'] if 'review_notes' in r.keys() else ''
            drafts.append({
                'id': r['id'],
                'title': r['title'],
                'description': r['description'],
                'author': r['author'],
                'created_at': r['created_at'],
                'status': 'pending',
                'type': None,
                'file_type': file_type,
                'original_name': file_name,
                'file_url': file_url,
                'review_notes': review_notes
            })
        return jsonify({'success': True, 'drafts': drafts})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/all_publications', methods=['GET'])
def api_all_publications():
    """Ritorna tutte le pubblicazioni/record (admin expected)"""
    try:
        user = get_current_user()
        db = get_db()
        cursor = db.execute("SELECT * FROM articles ORDER BY created_at DESC")
        rows = cursor.fetchall()
        pubs = []
        for r in rows:
            status = 'published' if r['is_published'] else 'pending'
            file_name = r['file_name']
            _, ext = os.path.splitext(file_name or '')
            file_type = ext.lstrip('.').lower() if ext else None
            file_url = None
            if file_name:
                folder = PUBLISHED_FOLDER if r['is_published'] else DRAFTS_FOLDER
                file_url = f"/files/{folder}/{file_name}"
            review_notes = r['review_notes'] if 'review_notes' in r.keys() else ''
            pubs.append({
                'id': r['id'],
                'title': r['title'],
                'description': r['description'],
                'author': r['author'],
                'created_at': r['created_at'],
                'status': status,
                'type': None,
                'file_type': file_type,
                'original_name': file_name,
                'file_url': file_url,
                'review_notes': review_notes
            })
        return jsonify({'success': True, 'publications': pubs})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/view_draft/<int:article_id>', methods=['GET'])
def api_view_draft(article_id):
    """Serve la bozza (solo admin o autore). Se l'articolo è pubblicato serve dalla cartella pubblicazioni."""
    try:
        user = get_current_user()
        db = get_db()
        cur = db.execute("SELECT file_name, author, is_published FROM articles WHERE id = ?", (article_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Articolo non trovato'}), 404

        file_name = row['file_name']
        is_pub = bool(row['is_published'])
        if not file_name:
            return jsonify({'success': False, 'message': 'File non presente'}), 404

        # Se è bozza: solo admin o autore
        if not is_pub:
            if user['role'] != 'admin' and user.get('email') != row['author']:
                return jsonify({'success': False, 'message': 'Accesso negato'}), 403
            directory = os.path.join(STORAGE_ROOT, DRAFTS_FOLDER)
        else:
            # pubblicato: può essere visualizzato da tutti, prendi dalla cartella pubblicazioni
            directory = os.path.join(STORAGE_ROOT, PUBLISHED_FOLDER)

        file_path = os.path.join(directory, file_name)
        if not os.path.isfile(file_path):
            return jsonify({'success': False, 'message': 'File non trovato nel filesystem'}), 404

        # Serve inline per permettere preview nel browser (non forzare download)
        return send_from_directory(directory, file_name, as_attachment=False)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/download/<int:article_id>', methods=['GET'])
def api_download(article_id):
    """Download pubblico per file pubblicati"""
    try:
        db = get_db()
        cur = db.execute("SELECT file_name, is_published FROM articles WHERE id = ?", (article_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Articolo non trovato'}), 404
        if not row['file_name']:
            return jsonify({'success': False, 'message': 'File non presente'}), 404
        if not row['is_published']:
            # non pubblicato: richiedi autenticazione (o blocca)
            return jsonify({'success': False, 'message': 'File non pubblicato'}), 403
        directory = os.path.join(STORAGE_ROOT, PUBLISHED_FOLDER)
        return send_from_directory(directory, row['file_name'], as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/review_draft/<int:article_id>', methods=['POST'])
def api_review_draft(article_id):
    """Approva o rifiuta una bozza (admin)"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo admin può rivedere bozze'}), 403
        data = request.get_json() or {}
        action = data.get('action')
        review_notes = data.get('review_notes', '')
        if action not in ('approved', 'rejected'):
            return jsonify({'success': False, 'message': 'Action non valida'}), 400
        db = get_db()
        cur = db.execute("SELECT file_name, is_published FROM articles WHERE id = ?", (article_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Articolo non trovato'}), 404

        if action == 'approved':
            # sposta file in pubblicazioni se presente
            if row['file_name']:
                src = os.path.join(STORAGE_ROOT, DRAFTS_FOLDER, row['file_name'])
                dst_dir = os.path.join(STORAGE_ROOT, PUBLISHED_FOLDER)
                os.makedirs(dst_dir, exist_ok=True)
                dst = os.path.join(dst_dir, row['file_name'])
                if os.path.isfile(src):
                    try:
                        os.replace(src, dst)
                    except Exception as e:
                        return jsonify({'success': False, 'message': f'Errore spostamento file: {str(e)}'}), 500
            db.execute("UPDATE articles SET is_published = 1, review_notes = ?, last_modified = CURRENT_TIMESTAMP WHERE id = ?", (review_notes, article_id))
        else:
            # rejected: salva note e mantiene come bozza
            db.execute("UPDATE articles SET review_notes = ?, last_modified = CURRENT_TIMESTAMP WHERE id = ?", (review_notes, article_id))
        db.commit()
        return jsonify({'success': True, 'message': 'Operazione completata'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# wrapper di compatibilità per delete chiamate dal frontend
@app.route('/api/delete/<int:article_id>', methods=['DELETE'])
def api_delete_article(article_id):
    return delete_article(article_id)

@app.route('/api/delete_draft/<int:article_id>', methods=['DELETE'])
def api_delete_draft(article_id):
    return delete_article(article_id)
# --- Compatibilità API frontend -- END ---

if __name__ == '__main__':
    try:
        require_secrets(app)
    except RuntimeError as e:
        app.logger.error(str(e))
        print(f"ERROR: {str(e)}")
        exit(1)
    
    with app.app_context():
        init_db()
    
    # IMPORTANT: debug=False for security. Use Gunicorn in production.
    app.run(debug=False, host='0.0.0.0', port=5001)