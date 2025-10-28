import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['DATABASE'] = os.path.join('../../database', 'documenti.db')

def init_db():
    """Inizializza il database con la tabella articles"""
    try:
        os.makedirs(os.path.dirname(app.config['DATABASE']), exist_ok=True)
        db = get_db()
        
        db.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL, 
                publication_date DATETIME NOT NULL,
                drive_link TEXT NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_published BOOLEAN DEFAULT FALSE,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        db.commit()
        print("✅ Database initialized successfully!")
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
                WHERE is_published = TRUE
                ORDER BY publication_date DESC
            ''')
            
        articles = cursor.fetchall()
        
        result = []
        for article in articles:
            result.append({
                'id': article['id'],
                'title': article['title'],
                'author': article['author'],
                'publication_date': article['publication_date'],
                'drive_link': article['drive_link'],
                'description': article['description'],
                'is_published': bool(article['is_published'])
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
        
        data = request.get_json()
        required = ['title', 'author', 'publication_date', 'drive_link']
        
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Campo {field} richiesto'}), 400
        
        db = get_db()
        db.execute('''
            INSERT INTO articles (
                title, author, publication_date, drive_link, 
                description, is_published
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['title'],
            data['author'],
            data['publication_date'], 
            data['drive_link'],
            data.get('description', ''),
            data.get('is_published', False)  # Default a False se non specificato
        ))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Articolo creato con successo'})
        
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
    """Elimina un articolo (solo admin)"""
    try:
        user = get_current_user()
        if user['role'] != 'admin':
            return jsonify({'success': False, 'message': 'Solo gli admin possono eliminare articoli'}), 403
        
        db = get_db()
        db.execute('DELETE FROM articles WHERE id = ?', (article_id,))
        db.commit()
        
        return jsonify({'success': True, 'message': 'Articolo eliminato con successo'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    
    print("=" * 60)
    print("Server Articoli Avviato")
    print(f"Database: {app.config['DATABASE']}")
    print("Su: http://localhost:5001")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5001)