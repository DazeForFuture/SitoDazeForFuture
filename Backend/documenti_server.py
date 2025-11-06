import os
import sqlite3
from datetime import datetime
from flask import (
    Flask, 
    request, 
    jsonify, 
    g, 
    send_from_directory
)
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# --- CORREZIONE CONFIGURAZIONE PATH ---

# 1. BASE_DIR è la directory dove si trova app.py (e.g., .../sitoDFF/SitoDazeForFuture/Backend)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. Risaliamo di due livelli per trovare la root del progetto (e.g., .../sitoDFF)
# BASE_DIR è .../Backend
# os.path.dirname(BASE_DIR) è .../SitoDazeForFuture
# os.path.dirname(os.path.dirname(BASE_DIR)) è .../sitoDFF (PROJECT_ROOT)
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

# Definisce la cartella di upload: /sitoDFF/ServerDocumenti
# La directory ServerDocumenti è a livello di PROJECT_ROOT
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'ServerDocumenti')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configurazione database: /sitoDFF/database/documenti.db
app.config['DATABASE'] = os.path.join(PROJECT_ROOT, 'database', 'documenti.db') 

# Limita i tipi di file accettati (mantenuto)
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}

# --- FINE CORREZIONE CONFIGURAZIONE PATH ---

def allowed_file(filename):
    """Controlla l'estensione del file"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- FUNZIONI DATABASE ---

def init_db():
    """Inizializza il database e crea la directory di upload"""
    try:
        # 1. Crea la directory di upload se non esiste
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        print(f"📁 Directory di upload creata: {app.config['UPLOAD_FOLDER']}")

        # 2. Crea la directory del database se non esiste
        os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
        db = get_db()
        
        # 3. Crea la tabella aggiornata (con file_path)
        db.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL, 
                publication_date DATETIME NOT NULL,
                file_path TEXT NOT NULL,  
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_published BOOLEAN DEFAULT FALSE,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db.commit()
        print("✅ Database e schema aggiornati (file_path) con successo!")
        print(f"📁 Database path: {app.config['DATABASE']}")
        
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

# --- FUNZIONI UTILITY (INVARIATE) ---

def get_current_user():
    """Funzione semplificata per ottenere l'utente corrente"""
    return {
        'email': request.headers.get('X-User-Email', ''),
        'role': request.headers.get('X-User-Role', 'user')
    }

# --- ENDPOINT API (INVARIANTI NELLA LOGICA) ---

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
                WHERE is_published = TRUE
                ORDER BY publication_date DESC
            ''')
            
        articles = cursor.fetchall()
        
        result = []
        for article in articles:
            # Ritorna il file_path
            result.append({
                'id': article['id'],
                'title': article['title'],
                'author': article['author'],
                'publication_date': article['publication_date'],
                'file_path': article['file_path'], # Restituisce il nome del file
                'download_link': f'/documents/{article["file_path"]}', # Nuovo link di download
                'description': article['description'],
                'is_published': bool(article['is_published'])
            })
        
        return jsonify({'success': True, 'articles': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/articles', methods=['POST'])
def create_article():
    """Crea un nuovo articolo gestendo l'upload del file (solo admin)"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono creare articoli'}), 403
        
        if 'document_file' not in request.files:
            return jsonify({'success': False, 'message': 'Nessun file inviato con la chiave "document_file"'}), 400
        
        file = request.files['document_file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'File non selezionato'}), 400
        
        if file and allowed_file(file.filename):
            # 1. Salva il file
            filename = secure_filename(file.filename)
            file_save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_save_path)

            # 2. Ottieni gli altri dati
            data = request.form
            required = ['title', 'author', 'publication_date']
            
            for field in required:
                if not data.get(field):
                    # Se i dati testuali mancano, il file è già stato salvato, bisognerebbe gestirlo con attenzione
                    return jsonify({'success': False, 'message': f'Campo {field} richiesto'}), 400
            
            # 3. Inserisci i dati nel database
            db = get_db()
            db.execute('''
                INSERT INTO articles (
                    title, author, publication_date, file_path, 
                    description, is_published
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data['title'],
                data['author'],
                data['publication_date'], 
                filename, 
                data.get('description', ''),
                data.get('is_published', False)
            ))
            db.commit()
            
            return jsonify({
                'success': True, 
                'message': 'Articolo e file caricati con successo',
                'file_name': filename,
                'download_link': f'/documents/{filename}'
            })
            
        return jsonify({'success': False, 'message': 'Tipo di file non ammesso'}), 400
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Errore nel caricamento: {str(e)}'}), 500

# --- ENDPOINT PER SCARICARE I DOCUMENTI (INVARIANTE) ---

@app.route('/documents/<filename>', methods=['GET'])
def download_file(filename):
    """Serve i file dalla directory ServerDocumenti"""
    try:
        return send_from_directory(
            app.config['UPLOAD_FOLDER'], 
            filename,
            as_attachment=True 
        )
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'File non trovato'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/articles/<int:article_id>/publish', methods=['POST'])
def toggle_publish(article_id):
    """Pubblica o mette in revisione un articolo (solo admin)"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono pubblicare articoli'}), 403
        
        data = request.get_json()
        is_published = data.get('is_published', True)
        
        db = get_db()
        db.execute('''
            UPDATE articles 
            SET is_published = ?, 
                last_modified = CURRENT_TIMESTAMP 
            WHERE id = ?
        ''', (is_published, article_id))
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
    """Elimina un articolo (solo admin) e il file associato"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono eliminare articoli'}), 403
        
        db = get_db()
        
        # 1. Recupera il nome del file
        cursor = db.execute('SELECT file_path FROM articles WHERE id = ?', (article_id,))
        article = cursor.fetchone()
        
        if not article:
            return jsonify({'success': False, 'message': 'Articolo non trovato'}), 404

        file_to_delete = article['file_path']
        
        # 2. Elimina l'articolo dal DB
        db.execute('DELETE FROM articles WHERE id = ?', (article_id,))
        db.commit()
        
        # 3. Elimina il file dal file system
        if file_to_delete:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_to_delete)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"File eliminato: {file_path}")
            else:
                print(f"Attenzione: File non trovato sul disco: {file_path}")
        
        return jsonify({'success': True, 'message': 'Articolo e file eliminati con successo'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    
    print("=" * 60)
    print("Server Documenti Avviato (Gestione File Locali)")
    print(f"Database: {app.config['DATABASE']}")
    print(f"Cartella Documenti: {app.config['UPLOAD_FOLDER']}")
    print("Su: http://localhost:5001")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5001)