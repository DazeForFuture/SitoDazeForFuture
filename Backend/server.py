import os
import sqlite3
from flask import Flask, send_from_directory, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(__name__, static_folder=None)
db_path = os.path.join(os.path.dirname(__file__), 'utenti.db')

def init_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cognome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            ruolo TEXT NOT NULL,
            motivazione TEXT,
            password TEXT NOT NULL,
            anno INTEGER,
            sezione TEXT
        )
    ''')
    conn.commit()
    conn.close()

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
    if not all([nome, cognome, email, ruolo, password]):
        return jsonify({'success': False, 'message': 'Tutti i campi obbligatori tranne la motivazione'}), 400
    hashed_pw = generate_password_hash(password)
    try:
        conn = sqlite3.connect(db_path)
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
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT password FROM users WHERE email = ?', (email,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[0], password):
        return jsonify({'success': True, 'message': 'Accesso riuscito'})
    else:
        return jsonify({'success': False, 'message': 'Credenziali non valide'}), 401

@app.route('/')
def index():
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_page(filename):
    return send_from_directory(frontend_dir, filename)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')