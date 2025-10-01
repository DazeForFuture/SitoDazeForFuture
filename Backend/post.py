from flask import Flask, request, jsonify
import os
import sqlite3

app = Flask(__name__)

DB_PATH = "c:/Users/rober/Documents/GitHub/database/post.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo TEXT NOT NULL,
            contenuto TEXT NOT NULL,
            immagine TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route('/api/post', methods=['POST'])
def crea_post():
    data = request.json
    titolo = data.get('titolo')
    contenuto = data.get('contenuto')
    immagine = data.get('immagine')  

    if not titolo or not contenuto:
        return jsonify({'success': False, 'message': 'Titolo e contenuto obbligatori'}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO posts (titolo, contenuto, immagine) VALUES (?, ?, ?)", (titolo, contenuto, immagine))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Post pubblicato'})

@app.route('/api/post', methods=['GET'])
def leggi_post():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, titolo, contenuto, immagine FROM posts ORDER BY id DESC")
    posts = [
        {'id': row[0], 'titolo': row[1], 'contenuto': row[2], 'immagine': row[3]}
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify(posts)

if __name__ == '__main__':
    app.run(port=5002, debug=True)