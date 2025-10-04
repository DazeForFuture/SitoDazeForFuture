from flask import Flask, request, jsonify 
from flask_cors import CORS
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000"], supports_credentials=True)

# Percorso database
db_path = '../../database/post.db'

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
            indirizzo TEXT,
            link TEXT,
            tipo TEXT DEFAULT 'evento',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
init_db()

@app.route('/api/post', methods=['POST'])
def crea_post():
    try:
        data = request.get_json()
        print("Dati ricevuti:", data)  # Debug
        
        if not data:
            return jsonify({'success': False, 'message': 'Nessun dato JSON ricevuto'}), 400
            
        titolo = data.get('titolo')
        contenuto = data.get('contenuto')
        immagine = data.get('immagine', '')
        data_evento = data.get('data', '')
        orario = data.get('orario', '')
        durata = data.get('durata', '')
        luogo = data.get('luogo', '')
        indirizzo = data.get('indirizzo', '')
        link = data.get('link', '')
        tipo = data.get('tipo', 'evento')

        if not titolo or not contenuto:
            return jsonify({'success': False, 'message': 'Titolo e contenuto obbligatori'}), 400

        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            INSERT INTO posts (titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo, link, tipo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (titolo, contenuto, immagine, data_evento, orario, durata, luogo, indirizzo, link, tipo))
        conn.commit()
        post_id = c.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'message': 'Post pubblicato', 'id': post_id})
    
    except Exception as e:
        print("Errore:", str(e))
        return jsonify({'success': False, 'message': f'Errore del server: {str(e)}'}), 500

@app.route('/api/post', methods=['GET'])
def leggi_post():
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            SELECT id, titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo, link, tipo 
            FROM posts 
            ORDER BY created_at DESC
        """)
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
                'indirizzo': row[8],
                'link': row[9],
                'tipo': row[10]
            }
            for row in c.fetchall()
        ]
        conn.close()
        print(f"Trovati {len(posts)} post")  # Debug
        return jsonify(posts)
    
    except Exception as e:
        print("Errore nel caricamento post:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'OK', 'message': 'Server funzionante'})

if __name__ == '__main__':
    print(f"Percorso del datbase: {db_path}")
    print("Server in esecuzione su http://localhost:5002")
    app.run(host='0.0.0.0', port=5002, debug=True)