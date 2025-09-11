from flask import Flask, send_from_directory
import os

# Percorso assoluto alla cartella frontend
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(__name__, static_folder=None)

@app.route('/')
def index():
    # Serve index.html dalla cartella frontend
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_page(filename):
    # Serve qualsiasi altro file HTML dalla cartella frontend
    return send_from_directory(frontend_dir, filename)

if __name__ == '__main__':
    app.run(debug=True)
