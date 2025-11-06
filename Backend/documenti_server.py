import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
# limiti upload
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

# CORS configurabile via env FRONTEND_ORIGINS (comma-separated).
# Se usi credenziali (cookie/session) assicurati di elencare le origini e supports_credentials=True.
FRONTEND_ORIGINS = os.environ.get("FRONTEND_ORIGINS")
if FRONTEND_ORIGINS:
    origins = [o.strip() for o in FRONTEND_ORIGINS.split(",") if o.strip()]
else:
    origins = ["http://localhost:5000", "http://192.168.0.137:5000", "http://100.108.96.23:5000"]

CORS(app, origins=origins, supports_credentials=True)


HERE = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.environ.get("SITO_ROOT") or os.path.abspath(os.path.join(HERE, "..", ".."))
PROJECT_ROOT = os.path.normpath(PROJECT_ROOT)


BASE_DIR = os.path.join(PROJECT_ROOT, "SitoDazeForFuture", "Backend")
if not os.path.isdir(BASE_DIR):

    BASE_DIR = os.path.abspath(HERE)

UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "ServerDocumenti")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["DATABASE"] = os.path.join(PROJECT_ROOT, "database", "documenti.db")
os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)

        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                publication_date DATETIME NOT NULL,
                file_path TEXT NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_published BOOLEAN DEFAULT FALSE,
                last_modified DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()
        print("✅ DB pronto:", app.config["DATABASE"])
        print("✅ Cartella upload:", app.config["UPLOAD_FOLDER"])
    except Exception as e:
        print(f"❌ Errore init_db: {e}")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, "db"):
        g.db.close()

def get_current_user():
    return {
        "email": request.headers.get("X-User-Email", ""),
        "role": request.headers.get("X-User-Role", "user"),
    }

@app.route("/api/articles", methods=["GET"])
def get_articles():
    try:
        user = get_current_user()
        db = get_db()
        if user["role"] == "admin":
            cursor = db.execute("SELECT * FROM articles ORDER BY publication_date DESC")
        else:
            cursor = db.execute("""
                SELECT * FROM articles
                WHERE is_published = TRUE
                ORDER BY publication_date DESC
            """)
        rows = cursor.fetchall()
        articles = [{
            "id": r["id"],
            "title": r["title"],
            "author": r["author"],
            "publication_date": r["publication_date"],
            "file_path": r["file_path"],
            "download_link": f"/documents/{r['file_path']}",
            "description": r["description"],
            "is_published": bool(r["is_published"]),
        } for r in rows]
        return jsonify({"success": True, "articles": articles})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/articles", methods=["POST"])
def create_article():
    try:
        user = get_current_user()
        if user["role"] != "admin":
            return jsonify({"success": False, "message": "Solo gli admin possono creare articoli"}), 403

        if "document_file" not in request.files:
            return jsonify({"success": False, "message": 'Nessun file inviato con la chiave "document_file"'}), 400

        file = request.files["document_file"]
        if file.filename == "":
            return jsonify({"success": False, "message": "File non selezionato"}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # evita sovrascritture: aggiungi timestamp se esiste
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            if os.path.exists(save_path):
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{int(datetime.utcnow().timestamp())}{ext}"
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            data = request.form
            for field in ["title", "author", "publication_date"]:
                if not data.get(field):
                    return jsonify({"success": False, "message": f"Campo {field} richiesto"}), 400

            db = get_db()
            db.execute("""
                INSERT INTO articles (title, author, publication_date, file_path, description, is_published)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data["title"],
                data["author"],
                data["publication_date"],
                filename,
                data.get("description", ""),
                int(str(data.get("is_published", "0")).lower() in ("1", "true", "on")),
             ))
            db.commit()

            return jsonify({
                "success": True,
                "message": "Articolo e file caricati con successo",
                "file_name": filename,
                "download_link": f"/documents/{filename}"
            })

        return jsonify({"success": False, "message": "Tipo di file non ammesso"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Errore nel caricamento: {str(e)}"}), 500

@app.route("/documents/<filename>", methods=["GET"])
def download_file(filename):
    try:
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"success": False, "message": "File non trovato"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/articles/<int:article_id>/publish", methods=["POST"])
def toggle_publish(article_id):
    try:
        user = get_current_user()
        if user["role"] != "admin":
            return jsonify({"success": False, "message": "Solo gli admin possono pubblicare articoli"}), 403

        data = request.get_json()
        is_published = data.get("is_published", True)

        db = get_db()
        db.execute("""
            UPDATE articles
            SET is_published = ?, last_modified = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (is_published, article_id))
        db.commit()

        status = "pubblicato" if is_published else "messo in revisione"
        return jsonify({"success": True, "message": f"Articolo {status} con successo"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/articles/<int:article_id>", methods=["DELETE"])
def delete_article(article_id):
    try:
        user = get_current_user()
        if user["role"] != "admin":
            return jsonify({"success": False, "message": "Solo gli admin possono eliminare articoli"}), 403

        db = get_db()
        cur = db.execute("SELECT file_path FROM articles WHERE id = ?", (article_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Articolo non trovato"}), 404

        filename = row["file_path"]
        db.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        db.commit()

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if filename and os.path.exists(file_path):
            os.remove(file_path)
            print("🗑️ Eliminato:", file_path)
        else:
            print("⚠️ File non presente sul disco:", file_path)

        return jsonify({"success": True, "message": "Articolo e file eliminati con successo"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    with app.app_context():
        init_db()

    print("=" * 60)
    print("Server Documenti Avviato (Ubuntu)")
    print("Database:", app.config["DATABASE"])
    print("Cartella Documenti:", app.config["UPLOAD_FOLDER"])
    print("Su: http://0.0.0.0:5001")
    print("=" * 60)

    app.run(debug=True, host="0.0.0.0", port=5001)
