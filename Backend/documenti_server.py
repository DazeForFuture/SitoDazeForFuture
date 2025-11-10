import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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
        
        return jsonify({'success': True, 'articles': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/articles', methods=['POST'])
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
    """Serve i PDF. Le bozze sono accessibili solo agli admin."""
    try:
        if folder not in (PUBLISHED_FOLDER, DRAFTS_FOLDER):
            return jsonify({'success': False, 'message': 'Folder non valido'}), 400
        user = get_current_user()
        if folder == DRAFTS_FOLDER and user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Accesso negato'}), 403
        directory = os.path.join(STORAGE_ROOT, folder)
        file_path = os.path.join(directory, filename)
        if not os.path.isfile(file_path):
            return jsonify({'success': False, 'message': 'File non trovato'}), 404
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, host='0.0.0.0', port=5001)