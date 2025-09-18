import os
import sqlite3
import base64
from flask import Flask, request, jsonify, send_file
from io import BytesIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
db_path = os.path.join(os.path.dirname(__file__), 'documenti.db')

def init_doc_db():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content BLOB NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/upload_document', methods=['POST'])
def upload_document():
    data = request.json
    filename = data.get('filename')
    filedata = data.get('filedata')  # base64 string
    if not filename or not filedata:
        return jsonify({'success': False, 'message': 'File mancante'}), 400
    try:
        filebytes = base64.b64decode(filedata)
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO documents (filename, content, uploaded_at)
            VALUES (?, ?, datetime('now'))
        ''', (filename, filebytes))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Documento salvato'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/list_documents', methods=['GET'])
def list_documents():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, filename, uploaded_at FROM documents ORDER BY uploaded_at DESC')
    docs = [{'id': row[0], 'filename': row[1], 'uploaded_at': row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(docs)

@app.route('/download_document/<int:doc_id>', methods=['GET'])
def download_document(doc_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT filename, content FROM documents WHERE id=?', (doc_id,))
    row = c.fetchone()
    conn.close()
    if row:
        filename, content = row
        return send_file(BytesIO(content), download_name=filename, as_attachment=True)
    else:
        return "Documento non trovato", 404

@app.route('/view_document/<int:doc_id>', methods=['GET'])
def view_document(doc_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT filename, content FROM documents WHERE id=?', (doc_id,))
    row = c.fetchone()
    conn.close()
    if row:
        filename, content = row
        return send_file(BytesIO(content), download_name=filename)
    else:
        return "Documento non trovato", 404

if __name__ == '__main__':
    init_doc_db()
    app.run(debug=True, host='0.0.0.0', port=5050)