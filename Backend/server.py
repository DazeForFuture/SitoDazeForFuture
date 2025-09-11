from flask import Flask, send_from_directory
import os

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(__name__, static_folder=None)

@app.route('/')
def index():
    
    return send_from_directory(frontend_dir, 'index.html')

@app.route('/<path:filename>')
def serve_page(filename):
    
    return send_from_directory(frontend_dir, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
