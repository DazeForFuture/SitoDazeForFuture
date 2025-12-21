from flask import Flask, request, jsonify 
from flask_cors import CORS
import os
import sqlite3
import logging
import jwt
from functools import wraps
from datetime import datetime

app = Flask(__name__)
cors_origins = os.environ.get('CORS_ORIGINS', '*')
CORS(app, supports_credentials=True, resources={r"/*": {"origins": cors_origins}})
logging.basicConfig(level=logging.INFO)

# Configurazione JWT
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.environ.get('SECRET_KEY', os.urandom(32)))
JWT_SECRET = os.environ.get('JWT_SECRET', None)
if JWT_SECRET is None:
    logging.warning('JWT_SECRET not set in env for post.py; using ephemeral secret for local dev')
    JWT_SECRET = os.urandom(32)

# Percorso database
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../database/post.db'))

def init_db():
    """Inizializza il database per gli eventi"""
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
            indirizzo TEXT,
            creato_il TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def decode_jwt(token: str):
    """Decodifica un token JWT"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return {'email': payload.get('email'), 'role': payload.get('ruolo')}
    except jwt.ExpiredSignatureError:
        logging.error("Token JWT scaduto")
        return None
    except jwt.InvalidTokenError as e:
        logging.error(f"Token JWT non valido: {e}")
        return None
    except Exception as e:
        logging.error(f"Errore decodifica JWT: {e}")
        return None

def require_auth(f):
    """Decorator per richiedere autenticazione (JWT o headers legacy)"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # DEBUG: Log degli headers per troubleshooting
        auth_header = request.headers.get('Authorization', '')
        email_header = request.headers.get('X-User-Email', '')
        role_header = request.headers.get('X-User-Role', '')
        
        logging.info(f"Auth headers - Authorization: {auth_header[:50] if auth_header else 'None'}, "
                    f"X-User-Email: {email_header}, X-User-Role: {role_header}")
        
        # PRIMA: prova con JWT token
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            user = decode_jwt(token)
            if user:
                request.user = user
                logging.info(f"Autenticato via JWT: email={user.get('email')}, role={user.get('role')}")
                return f(*args, **kwargs)
            else:
                logging.warning("Token JWT non valido o scaduto")
        
        # SECONDA: fallback a headers legacy per compatibilità
        if email_header and role_header:
            request.user = {'email': email_header, 'role': role_header}
            logging.info(f"Autenticato via legacy headers: email={email_header}, role={role_header}")
            return f(*args, **kwargs)
        
        # Nessuna autenticazione valida trovata
        logging.warning("Nessuna autenticazione valida trovata")
        return jsonify({
            'success': False, 
            'message': 'Autenticazione richiesta. Effettua il login.',
            'details': 'Mancano token JWT o headers di autenticazione'
        }), 401
    return wrapper

@app.route('/api/post', methods=['POST'])
@require_auth
def crea_post():
    """Crea un nuovo evento"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'message': 'Content-Type deve essere application/json'}), 400
        
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({'success': False, 'message': 'JSON non valido'}), 400
        
        logging.info(f"Dati ricevuti per creazione post: {data}")
        
        # Estrai i campi
        titolo = data.get('titolo', '').strip()
        contenuto = data.get('contenuto', '').strip()
        immagine = data.get('immagine', '').strip()
        data_evento = data.get('data', '').strip()
        orario = data.get('orario', '').strip()
        durata = data.get('durata', '').strip()
        luogo = data.get('luogo', '').strip()
        indirizzo = data.get('indirizzo', '').strip()
        
        # Validazioni
        if not titolo:
            return jsonify({'success': False, 'message': 'Titolo obbligatorio'}), 400
        if not contenuto:
            return jsonify({'success': False, 'message': 'Contenuto obbligatorio'}), 400
        
        if len(titolo) > 200:
            return jsonify({'success': False, 'message': 'Titolo troppo lungo (max 200 caratteri)'}), 400
        if len(contenuto) > 10000:
            return jsonify({'success': False, 'message': 'Contenuto troppo lungo (max 10000 caratteri)'}), 400
        
        # Converti durata in stringa se è numerica
        if durata and isinstance(durata, (int, float)):
            durata = str(durata)
        
        conn = sqlite3.connect(db_path, check_same_thread=False)
        c = conn.cursor()
        c.execute("""
            INSERT INTO posts (titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (titolo, contenuto, immagine, data_evento, orario, durata, luogo, indirizzo))
        
        post_id = c.lastrowid
        conn.commit()
        conn.close()
        
        logging.info(f"✅ Post creato con ID: {post_id}")
        return jsonify({
            'success': True, 
            'message': 'Evento pubblicato con successo', 
            'id': post_id
        })
        
    except Exception as e:
        logging.error(f"❌ Errore nella creazione del post: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore interno del server: {str(e)}'
        }), 500

@app.route('/api/post', methods=['GET'])
def leggi_post():
    """Legge tutti gli eventi"""
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        c = conn.cursor()
        c.execute("""
            SELECT id, titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo 
            FROM posts 
            ORDER BY data DESC, id DESC
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
                'indirizzo': row[8]
            }
            for row in c.fetchall()
        ]
        
        conn.close()
        
        logging.info(f"📊 Recuperati {len(posts)} eventi")
        return jsonify(posts)
        
    except Exception as e:
        logging.error(f"❌ Errore nella lettura dei post: {e}")
        return jsonify({
            'success': False, 
            'message': 'Errore nel recupero degli eventi'
        }), 500

@app.route('/api/post/<int:post_id>', methods=['GET'])
def get_post(post_id):
    """Recupera un evento specifico"""
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        c = conn.cursor()
        c.execute("""
            SELECT id, titolo, contenuto, immagine, data, orario, durata, luogo, indirizzo 
            FROM posts 
            WHERE id = ?
        """, (post_id,))
        
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
            return jsonify({
                'success': False, 
                'message': 'Evento non trovato'
            }), 404
            
    except Exception as e:
        logging.error(f"❌ Errore nel recupero del post: {e}")
        return jsonify({
            'success': False, 
            'message': 'Errore interno del server'
        }), 500

@app.route('/api/post/<int:post_id>', methods=['DELETE'])
@require_auth
def elimina_post(post_id):
    """Elimina un evento"""
    try:
        # Verifica che l'utente sia admin
        if not hasattr(request, 'user'):
            return jsonify({
                'success': False, 
                'message': 'Utente non autenticato'
            }), 401
            
        user_role = request.user.get('role')
        if user_role != 'admin':
            logging.warning(f"❌ Tentativo di eliminazione da utente non admin: role={user_role}")
            return jsonify({
                'success': False, 
                'message': 'Solo gli amministratori possono eliminare eventi'
            }), 403
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Prima verifica che l'evento esista
        c.execute("SELECT id, titolo FROM posts WHERE id = ?", (post_id,))
        post = c.fetchone()
        
        if not post:
            conn.close()
            return jsonify({
                'success': False, 
                'message': 'Evento non trovato'
            }), 404
        
        # Elimina l'evento
        c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()
        
        logging.info(f"🗑️ Evento eliminato: ID={post_id}, Titolo={post[1]}")
        return jsonify({
            'success': True, 
            'message': 'Evento eliminato con successo'
        })
        
    except Exception as e:
        logging.error(f"❌ Errore nell'eliminazione del post: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore interno del server: {str(e)}'
        }), 500

@app.route('/api/post/<int:post_id>', methods=['PUT'])
@require_auth
def modifica_post(post_id):
    """Modifica un evento esistente"""
    try:
        # Verifica che l'utente sia admin
        if not hasattr(request, 'user'):
            return jsonify({
                'success': False, 
                'message': 'Utente non autenticato'
            }), 401
            
        user_role = request.user.get('role')
        if user_role != 'admin':
            return jsonify({
                'success': False, 
                'message': 'Solo gli amministratori possono modificare eventi'
            }), 403
        
        if not request.is_json:
            return jsonify({
                'success': False, 
                'message': 'Content-Type deve essere application/json'
            }), 400
        
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({
                'success': False, 
                'message': 'JSON non valido'
            }), 400
        
        # Estrai i campi
        titolo = data.get('titolo', '').strip()
        contenuto = data.get('contenuto', '').strip()
        immagine = data.get('immagine', '').strip()
        data_evento = data.get('data', '').strip()
        orario = data.get('orario', '').strip()
        durata = data.get('durata', '').strip()
        luogo = data.get('luogo', '').strip()
        indirizzo = data.get('indirizzo', '').strip()
        
        # Validazioni
        if not titolo:
            return jsonify({'success': False, 'message': 'Titolo obbligatorio'}), 400
        if not contenuto:
            return jsonify({'success': False, 'message': 'Contenuto obbligatorio'}), 400
        
        if len(titolo) > 200:
            return jsonify({'success': False, 'message': 'Titolo troppo lungo (max 200 caratteri)'}), 400
        if len(contenuto) > 10000:
            return jsonify({'success': False, 'message': 'Contenuto troppo lungo (max 10000 caratteri)'}), 400
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Verifica che l'evento esista
        c.execute("SELECT id FROM posts WHERE id = ?", (post_id,))
        if not c.fetchone():
            conn.close()
            return jsonify({
                'success': False, 
                'message': 'Evento non trovato'
            }), 404
        
        # Aggiorna l'evento
        c.execute("""
            UPDATE posts 
            SET titolo=?, contenuto=?, immagine=?, data=?, orario=?, durata=?, luogo=?, indirizzo=?
            WHERE id=?
        """, (titolo, contenuto, immagine, data_evento, orario, durata, luogo, indirizzo, post_id))
        
        conn.commit()
        conn.close()
        
        logging.info(f"✏️ Evento modificato: ID={post_id}")
        return jsonify({
            'success': True, 
            'message': 'Evento modificato con successo'
        })
        
    except Exception as e:
        logging.error(f"❌ Errore nella modifica del post: {e}")
        return jsonify({
            'success': False, 
            'message': f'Errore interno del server: {str(e)}'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint per health check"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
        tables = c.fetchall()
        
        c.execute("SELECT COUNT(*) FROM posts")
        count = c.fetchone()[0]
        
        conn.close()
        
        if tables:
            return jsonify({
                'status': 'healthy', 
                'message': 'Server eventi operativo',
                'database': 'connected',
                'tables': len(tables),
                'total_events': count,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'degraded', 
                'message': 'Server operativo ma tabelle non trovate',
                'database': 'connected'
            }), 503
            
    except Exception as e:
        logging.error(f"❌ Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy', 
            'message': f'Errore del server: {str(e)}',
            'database': 'disconnected'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False, 
        'message': 'Endpoint non trovato'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logging.error(f"❌ Errore interno del server: {error}")
    return jsonify({
        'success': False, 
        'message': 'Errore interno del server'
    }), 500

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    logging.info("=" * 50)
    logging.info("🚀 Avvio Server Eventi Daze for Future")
    logging.info(f"📡 Porta: 5002")
    logging.info(f"🗄️ Database: {db_path}")
    logging.info(f"🔧 Debug: {debug_mode}")
    logging.info("=" * 50)
    
    # Verifica che il database esista
    if not os.path.exists(db_path):
        logging.warning(f"⚠️ Database non trovato a {db_path}, inizializzazione...")
        init_db()
        logging.info("✅ Database inizializzato")
    
    # Controlla i permessi del database
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.close()
            logging.info("✅ Connessione al database verificata")
        except Exception as e:
            logging.error(f"❌ Errore connessione database: {e}")
    
    app.run(host='0.0.0.0', port=5002, debug=debug_mode)