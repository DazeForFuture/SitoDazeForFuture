from flask import Flask, request, jsonify, session
from flask_cors import CORS
import sqlite3
import datetime
import hashlib
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Usa la stessa secret_key di server.py
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Database paths
db_path = app.config['DATABASE'] = os.path.join('../../database', 'forum.db')
users_db_path = app.config['DATABASE'] = os.path.join('../../database', 'utenti.db')

# Database initialization
def init_db():
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Forum users table (links to main users)
    c.execute('''
        CREATE TABLE IF NOT EXISTS forum_users (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Categories table
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
    ''')
    
    # Threads table
    c.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            user_id INTEGER,
            category_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    # Posts table
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            user_id INTEGER,
            thread_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (thread_id) REFERENCES threads (id)
        )
    ''')
    
    # Insert default categories
    c.execute('''
        INSERT OR IGNORE INTO categories (name, description) VALUES 
        ('Generale', 'Discussioni generali'),
        ('Python', 'Discussioni su Python'),
        ('Web Development', 'Sviluppo web'),
        ('Aiuto', 'Richiesta di aiuto')
    ''')
    
    conn.commit()
    conn.close()

# Utility functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Authentication routes
@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    email = request.args.get('email')
    if not email:
        return jsonify({'authenticated': False, 'error': 'Email richiesta'}), 400
        
    conn = sqlite3.connect(users_db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id, nome, cognome, email FROM users WHERE email = ?', (email,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user['id'],
                'username': f"{user['nome']} {user['cognome']}",
                'email': user['email']
            }
        })
    return jsonify({'authenticated': False})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logout successful'})

# Forum routes
@app.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT c.*, COUNT(t.id) as thread_count 
        FROM categories c 
        LEFT JOIN threads t ON c.id = t.category_id 
        GROUP BY c.id
    ''')
    categories = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(categories)

@app.route('/api/threads', methods=['GET'])
def get_threads():
    category_id = request.args.get('category_id')
    conn = get_db_connection()
    c = conn.cursor()
    
    conn_users = sqlite3.connect(users_db_path)
    conn_users.row_factory = sqlite3.Row
    
    if category_id:
        c.execute('''
            SELECT t.*, COUNT(p.id) as post_count
            FROM threads t 
            LEFT JOIN posts p ON t.id = p.thread_id
            WHERE t.category_id = ?
            GROUP BY t.id
            ORDER BY t.created_at DESC
        ''', (category_id,))
    else:
        c.execute('''
            SELECT t.*, COUNT(p.id) as post_count
            FROM threads t 
            LEFT JOIN posts p ON t.id = p.thread_id
            GROUP BY t.id
            ORDER BY t.created_at DESC
        ''')
    
    threads = []
    for row in c.fetchall():
        thread_dict = dict(row)
        # Get user info from utenti.db
        cu = conn_users.cursor()
        cu.execute('SELECT nome, cognome FROM users WHERE id = ?', (thread_dict['user_id'],))
        user = cu.fetchone()
        if user:
            thread_dict['username'] = f"{user['nome']} {user['cognome']}"
        else:
            thread_dict['username'] = "Utente sconosciuto"
        threads.append(thread_dict)
    
    conn_users.close()
    
    threads = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(threads)

@app.route('/api/threads', methods=['POST'])
def create_thread():
    data = request.json
    email = data.get('email')
    title = data.get('title')
    content = data.get('content')
    category_id = data.get('category_id')
    
    if not all([email, title, content, category_id]):
        return jsonify({'error': 'Email, titolo e contenuto sono richiesti'}), 400
    
    # Get user from utenti.db
    conn_users = sqlite3.connect(users_db_path)
    conn_users.row_factory = sqlite3.Row
    c_users = conn_users.cursor()
    c_users.execute('SELECT id FROM users WHERE email = ?', (email,))
    user = c_users.fetchone()
    conn_users.close()
    
    if not user:
        return jsonify({'error': 'Utente non autorizzato'}), 401
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO threads (title, content, user_id, category_id)
        VALUES (?, ?, ?, ?)
    ''', (title, content, user['id'], category_id))
    conn.commit()
    thread_id = c.lastrowid
    conn.close()
    
    return jsonify({'message': 'Thread creato', 'thread_id': thread_id}), 201

@app.route('/api/threads/<int:thread_id>', methods=['GET'])
def get_thread(thread_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get thread details
    c.execute('''
        SELECT t.*, c.name as category_name
        FROM threads t 
        JOIN categories c ON t.category_id = c.id
        WHERE t.id = ?
    ''', (thread_id,))
    thread = dict(c.fetchone())
    
    # Get user info from utenti.db
    conn_users = sqlite3.connect(users_db_path)
    conn_users.row_factory = sqlite3.Row
    cu = conn_users.cursor()
    cu.execute('SELECT nome, cognome FROM users WHERE id = ?', (thread['user_id'],))
    user = cu.fetchone()
    if user:
        thread['username'] = f"{user['nome']} {user['cognome']}"
    else:
        thread['username'] = "Utente sconosciuto"
    conn_users.close()
    
    # Get posts for this thread
    c.execute('''
        SELECT p.* 
        FROM posts p 
        WHERE p.thread_id = ? 
        ORDER BY p.created_at ASC
    ''', (thread_id,))
    posts = []
    
    # Get user info for each post
    conn_users = sqlite3.connect(users_db_path)
    conn_users.row_factory = sqlite3.Row
    cu = conn_users.cursor()
    
    for row in c.fetchall():
        post_dict = dict(row)
        cu.execute('SELECT nome, cognome FROM users WHERE id = ?', (post_dict['user_id'],))
        user = cu.fetchone()
        if user:
            post_dict['username'] = f"{user['nome']} {user['cognome']}"
        else:
            post_dict['username'] = "Utente sconosciuto"
        posts.append(post_dict)
    
    conn_users.close()
    
    conn.close()
    
    thread['posts'] = posts
    return jsonify(thread)

@app.route('/api/threads/<int:thread_id>/posts', methods=['POST'])
def create_post(thread_id):
    data = request.json
    email = data.get('email')
    content = data.get('content')
    
    if not all([email, content]):
        return jsonify({'error': 'Email e contenuto sono richiesti'}), 400
    
    # Get user from utenti.db
    conn_users = sqlite3.connect(users_db_path)
    conn_users.row_factory = sqlite3.Row
    c_users = conn_users.cursor()
    c_users.execute('SELECT id FROM users WHERE email = ?', (email,))
    user = c_users.fetchone()
    conn_users.close()
    
    if not user:
        return jsonify({'error': 'Utente non autorizzato'}), 401
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO posts (content, user_id, thread_id)
        VALUES (?, ?, ?)
    ''', (content, user['id'], thread_id))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Post creato'}), 201

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5003)