from flask import Flask, request, jsonify 
from flask_cors import CORS
import os
import sqlite3
import logging
import jwt
from functools import wraps
from werkzeug.utils import secure_filename

app = Flask(__name__)
cors_origins = os.environ.get('CORS_ORIGINS', '*')
CORS(app, supports_credentials=True, resources={r"/*": {"origins": cors_origins}})
logging.basicConfig(level=logging.INFO)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.environ.get('SECRET_KEY', os.urandom(32)))
JWT_SECRET = os.environ.get('JWT_SECRET', None)
if JWT_SECRET is None:
    logging.warning('JWT_SECRET not set in env for post.py; using ephemeral secret for local dev')
    JWT_SECRET = os.urandom(32)
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/post.db'))

def init_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
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

def decode_jwt(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return {'email': payload.get('email'), 'role': payload.get('ruolo')}
    except Exception:
        return None

def require_jwt(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'success': False, 'message': 'Autenticazione richiesta'}), 401
        token = auth.split(' ', 1)[1]
        user = decode_jwt(token)
        if not user:
            return jsonify({'success': False, 'message': 'Token non valido'}), 401
        return f(*args, **kwargs)
    return wrapper

@app.route('/api/post', methods=['POST'])
@require_jwt
def crea_post():
    data = request.json
    titolo = data.get('titolo')
    contenuto = data.get('contenuto')
    immagine = data.get('immagine')
    data_evento = data.get('data')
    orario = data.get('orario')
    durata = data.get('durata')
    luogo = data.get('luogo')
    indirizzo = data.get('indirizzo')

    if not titolo or not contenuto:
        return jsonify({'success': False, 'message': 'Titolo e contenuto obbligatori'}), 400
    if len(titolo) > 200 or len(contenuto) > 10000:
        return jsonify({'success': False, 'message': 'Titolo o contenuto troppo lunghi'}), 400

    conn = sqlite3.connect(db_path, check_same_thread=False)
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
    conn = sqlite3.connect(db_path, check_same_thread=False)
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
    conn = sqlite3.connect(db_path, check_same_thread=False)
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
@require_jwt
def elimina_post(post_id):
    # SECURITY: only admin can delete posts
    auth = request.headers.get('Authorization', '')
    token = auth.split(' ', 1)[1] if auth.startswith('Bearer ') else None
    user = decode_jwt(token) if token else None
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Solo admin può eliminare post'}), 403
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Post eliminato'})

# PUT modifica post
@app.route('/api/post/<int:post_id>', methods=['PUT'])
@require_jwt
def modifica_post(post_id):
    data = request.json
    titolo = data.get('titolo')
    contenuto = data.get('contenuto')
    immagine = data.get('immagine')
    data_evento = data.get('data')
    orario = data.get('orario')
    durata = data.get('durata')
    luogo = data.get('luogo')
    indirizzo = data.get('indirizzo')
    if not titolo or not contenuto:
        return jsonify({'success': False, 'message': 'Titolo e contenuto obbligatori'}), 400
    if len(titolo) > 200 or len(contenuto) > 10000:
        return jsonify({'success': False, 'message': 'Titolo o contenuto troppo lunghi'}), 400
    # SECURITY: only admin can modify posts
    auth = request.headers.get('Authorization', '')
    token = auth.split(' ', 1)[1] if auth.startswith('Bearer ') else None
    user = decode_jwt(token) if token else None
    if not user or user.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Solo admin può modificare post'}), 403
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
    # SECURITY: disable debug for production
    app.run(host='0.0.0.0', port=5002, debug=False)
    