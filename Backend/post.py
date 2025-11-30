from flask import Flask, request, jsonify 
from flask_cors import CORS
import os
import sqlite3
import logging
from config import BaseConfig, require_secrets
from logging.handlers import RotatingFileHandler
from security import sanitize_text, validate_iso_date

app = Flask(__name__)
app.config.from_object(BaseConfig)
CORS(app,supports_credentials=True)

# Setup logging
if not app.debug:
    handler = RotatingFileHandler('post.log', maxBytes=10*1024*1024, backupCount=5)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/post.db'))

def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo TEXT NOT NULL,
            contenuto TEXT NOT NULL,
            immagine TEXT,
            data TEXT,
            orario TEXT,
            durata TEXT,
            luogo TEXT,
            indirizzo TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route('/api/post', methods=['POST'])
def crea_post():
    data = request.json
    
    # Validazione e sanitizzazione input
    titolo = sanitize_text(data.get('titolo'), max_length=200) if data.get('titolo') else None
    contenuto = sanitize_text(data.get('contenuto'), max_length=5000, allow_newlines=True) if data.get('contenuto') else None
    
    if not titolo or not contenuto:
        return jsonify({'success': False, 'message': 'Titolo e contenuto obbligatori e validi'}), 400
    
    # Opzionali - validazione base
    immagine = data.get('immagine')
    data_evento = data.get('data')
    orario = data.get('orario')
    durata = data.get('durata')
    luogo = sanitize_text(data.get('luogo'), max_length=200) if data.get('luogo') else None
    indirizzo = sanitize_text(data.get('indirizzo'), max_length=300) if data.get('indirizzo') else None
    
    # Valida data se presente
    if data_evento and not validate_iso_date(data_evento):
        return jsonify({'success': False, 'message': 'Data non valida (formato: YYYY-MM-DD)'}), 400
    
    # Valida orario se presente (semplice check HH:MM)
    if orario:
        import re
        if not re.match(r'^([0-1][0-9]|2[0-3]):([0-5][0-9])$', orario):
            return jsonify({'success': False, 'message': 'Orario non valido (formato: HH:MM)'}), 400
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        INSERT INTO posts (titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (titolo, contenuto, immagine, data_evento, orario, durata, luogo, indirizzo))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Post pubblicato'})

@app.route('/api/post', methods=['GET'])
def leggi_post():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo FROM posts ORDER BY id DESC")
    posts = [
        {
            'id': row[0],
            'titolo': row[1],
            'contenuto': row[2],
            'immagine': row[3],
            'data': row[4],
            'orario': row[5],
            'durata': row[6],
            'luogo': row[7],
            'indirizzo': row[8]
        }
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify(posts)

# GET singolo post
@app.route('/api/post/<int:post_id>', methods=['GET'])
def get_post(post_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo FROM posts WHERE id = ?", (post_id,))
    row = c.fetchone()
    conn.close()
    if row:
        post = {
            'id': row[0],
            'titolo': row[1],
            'contenuto': row[2],
            'immagine': row[3],
            'data': row[4],
            'orario': row[5],
            'durata': row[6],
            'luogo': row[7],
            'indirizzo': row[8]
        }
        return jsonify(post)
    else:
        return jsonify({'success': False, 'message': 'Post non trovato'}), 404

# DELETE post
@app.route('/api/post/<int:post_id>', methods=['DELETE'])
def elimina_post(post_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Post eliminato'})

# PUT modifica post
@app.route('/api/post/<int:post_id>', methods=['PUT'])
def modifica_post(post_id):
    data = request.json
    
    # Validazione e sanitizzazione
    titolo = sanitize_text(data.get('titolo'), max_length=200) if data.get('titolo') else None
    contenuto = sanitize_text(data.get('contenuto'), max_length=5000, allow_newlines=True) if data.get('contenuto') else None
    
    if not titolo or not contenuto:
        return jsonify({'success': False, 'message': 'Titolo e contenuto obbligatori e validi'}), 400
    
    immagine = data.get('immagine')
    data_evento = data.get('data')
    orario = data.get('orario')
    durata = data.get('durata')
    luogo = sanitize_text(data.get('luogo'), max_length=200) if data.get('luogo') else None
    indirizzo = sanitize_text(data.get('indirizzo'), max_length=300) if data.get('indirizzo') else None
    
    # Valida data se presente
    if data_evento and not validate_iso_date(data_evento):
        return jsonify({'success': False, 'message': 'Data non valida (formato: YYYY-MM-DD)'}), 400
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        UPDATE posts SET titolo=?, contenuto=?, immagine=?, data=?, orario=?, durata=?, luogo=?, indirizzo=? WHERE id=?
    """, (titolo, contenuto, immagine, data_evento, orario, durata, luogo, indirizzo, post_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Post modificato'})

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Server is running'})


if __name__ == '__main__':
    try:
        require_secrets(app)
    except RuntimeError as e:
        app.logger.error(str(e))
        print(f"ERROR: {str(e)}")
        exit(1)
    
    # IMPORTANT: debug=False for security. Use Gunicorn in production.
    app.run(host='0.0.0.0', port=5002, debug=False)
    