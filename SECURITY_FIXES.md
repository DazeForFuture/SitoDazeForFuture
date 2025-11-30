# 🔒 Security Fixes Implementation Guide

## Overview
Questo documento riassume tutti i fix di sicurezza implementati nel progetto SitoDazeForFuture Backend.

---

## ✅ Fix Implementati

### 1. **Input Validation e Sanitizzazione** ✓

#### File: `Backend/security.py` (Nuovo)
Creato modulo centralizzato con utility di sicurezza riutilizzabili.

**Funzioni disponibili:**
- `sanitize_text()` – Escape HTML + length validation
- `sanitize_html_aggressive()` – Rimozione tag HTML
- `validate_iso_date()` – Validazione date ISO format
- `validate_time_format()` – Validazione HH:MM
- `is_valid_email()` – RFC 5322 compliant email validation
- `validate_range()` – Range check per numeri (es. temperatura)
- `is_strong_password()` – Password strength validation
- `is_valid_username()` – Username format validation

**Esempio uso:**
```python
from security import sanitize_text, is_valid_email

# In endpoint
titolo = sanitize_text(request.json.get('titolo'), max_length=200)
email = request.json.get('email')

if not titolo or not is_valid_email(email):
    return jsonify({'error': 'Input non valido'}), 400
```

#### File: `Backend/post.py`
**Aggiornamenti:**
- Import funzioni da `security`
- `crea_post()` → Input validation su titolo, contenuto, data, orario
- `modifica_post()` → Stesse validazioni

**Protezione contro:**
- XSS (HTML escape su text fields)
- Invalid data format
- SQL Injection (già protetto da prepared statements)

---

### 2. **Password Hashing Sicuro** ✓

#### File: `Backend/server.py`
**Cambio:**
- ❌ `generate_password_hash(password)` (default: sha1)
- ✅ `generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)`

**Protezione contro:**
- Rainbow table attacks
- GPU brute-force attacks
- Usa PBKDF2 con 16 byte di salt

#### File: `Backend/forum.py`
**Rimosso:**
- Vecchia funzione `hash_password()` che usava SHA256 crudo (insicuro)
- Importa ora `security.is_valid_email` centralizzato

---

### 3. **API Key Validation Sicura** ✓

#### File: `Backend/centrale.py`
**Prima:**
```python
# ❌ Insicuro
key = request.headers.get('X-API-KEY') or request.args.get('api_key')
return key == API_KEY  # Vulnerable a timing attacks
```

**Dopo:**
```python
# ✅ Sicuro
from security import secure_compare_api_keys

def require_api_key():
    if not API_KEY:
        return False  # Nega se non configurato
    
    key = request.headers.get('X-API-Key')  # Solo header!
    if not key:
        return False
    
    return secure_compare_api_keys(key, API_KEY)  # Timing-safe
```

**Protezione contro:**
- Timing attacks su API key
- API key in log (query params → header only)
- API key optional quando dovrebbe essere obbligatorio

---

### 4. **CORS Whitelist** ✓

#### Tutti i file Flask (`server.py`, `post.py`, `forum.py`, `documenti_server.py`)

**Prima:**
```python
# ❌ Permette qualsiasi dominio
CORS(app)
```

**Dopo:**
```python
# ✅ Whitelist solo domini autorizzati
allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app,
    origins=allowed_origins,
    supports_credentials=True,
    methods=['GET', 'POST', 'DELETE', 'PUT', 'OPTIONS'],
    allow_headers=['Content-Type', 'X-API-Key', 'X-User-Email']
)
```

**Configurazione via `.env`:**
```bash
ALLOWED_ORIGINS=http://localhost:3000,https://example.com
```

**Protezione contro:**
- CSRF attacks
- Cross-origin data theft
- Unauthorized API consumption

---

### 5. **Email Validation Centralizzata** ✓

#### File: `Backend/security.py`
Funzione `is_valid_email()` RFC 5322 compliant.

**Usata in:**
- `server.py` → Registrazione utenti
- `forum.py` → Check-auth endpoint
- `documenti_server.py` → Validazione email utente

**Esempio:**
```python
from security import is_valid_email

email = request.json.get('email', '').strip()
if not is_valid_email(email):
    return jsonify({'error': 'Email non valida'}), 400
```

---

### 6. **Dipendenze Aggiornate** ✓

#### File: `requirements.txt`
**Aggiornamenti:**
- Flask: 2.3.3 → 3.0.3
- Werkzeug: 2.3.7 → 3.0.3
- **Nuove dipendenze di sicurezza:**
  - `Flask-Talisman==1.1.0` (Security headers)
  - `email-validator==2.1.0` (Email validation)
  - `bleach==6.1.0` (HTML sanitization)

**Benefici:**
- Patch di sicurezza recenti
- Miglior protezione da vulnerabilità note
- Support per Python 3.10+

---

## 🚀 Come Usare

### 1. Installare Dipendenze
```bash
pip install -r requirements.txt
```

### 2. Configurare Variabili d'Ambiente
```bash
# Copiare il file di esempio
cp .env.example .env

# Editare e impostare i valori
# Generare SECRET_KEY e API_KEY sicuri:
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Eseguire i Server
```bash
# Terminal 1
python Backend/server.py

# Terminal 2
python Backend/forum.py

# Terminal 3
python Backend/post.py

# Terminal 4
python Backend/centrale.py

# Terminal 5 (documenti)
python Backend/documenti_server.py
```

---

## 📋 Checklist di Deployment

Prima di mettere in produzione:

- [ ] Generare e impostare `FLASK_SECRET_KEY` (min 32 chars)
- [ ] Generare e impostare `API_KEY` (min 32 chars)
- [ ] Impostare `ADMIN_PASSWORD` sicura
- [ ] Configurare `ALLOWED_ORIGINS` con domini reali
- [ ] Disabilitare `DEBUG=False` (già configurato)
- [ ] Usare HTTPS in produzione
- [ ] Impostare `SESSION_COOKIE_SECURE=True` in produzione
- [ ] Configurare rate limiting se necessario
- [ ] Eseguire security audit con bandit:
  ```bash
  pip install bandit
  bandit -r Backend/
  ```
- [ ] Testare CORS con curl:
  ```bash
  curl -H "Origin: https://example.com" http://localhost:5000/
  ```

---

## 🛡️ Best Practices per la Manutenzione

### 1. **Aggiornare Dipendenze Regolarmente**
```bash
pip list --outdated
pip install --upgrade -r requirements.txt
```

### 2. **Controllare CVE Periodicamente**
```bash
pip install pip-audit
pip-audit
```

### 3. **Review Log per Attività Anomale**
```bash
tail -f server.log | grep -i "error\|failed\|unauthorized"
```

### 4. **Monitorare Accessi Admin**
```bash
grep -i "admin" server.log
```

---

## 🔍 Testing della Sicurezza

### Test 1: API Key Validation
```bash
# Senza API key → 401
curl http://localhost:5005/update

# Con API key errata → 401
curl -H "X-API-Key: wrong" http://localhost:5005/update

# Con API key corretta → 200
curl -H "X-API-Key: $YOUR_API_KEY" \
  "http://localhost:5005/update?t=25.5&h=60"
```

### Test 2: CORS
```bash
# Dominio non autorizzato
curl -H "Origin: https://malicious.com" http://localhost:3000/

# Dominio autorizzato
curl -H "Origin: https://example.com" http://localhost:3000/
```

### Test 3: Input Validation
```bash
# Email non valida
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"invalid"}'

# Password debole
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"password":"weak"}'
```

### Test 4: XSS Prevention
```bash
# Tentare di iniettare script
curl -X POST http://localhost:5002/api/post \
  -H "Content-Type: application/json" \
  -d '{"titolo":"<script>alert(1)</script>","contenuto":"test"}'
```

---

## 📚 Risorse Aggiuntive

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Werkzeug Security](https://werkzeug.palletsprojects.com/security/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/security/)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/)

---

## 🐛 Segnalazione Bug di Sicurezza

Se scopri una vulnerabilità, **non** aprire un issue pubblico. Contatta i maintainer privatamente.

---

**Ultima aggiornamento:** Novembre 2025  
**Versione:** 1.0 - Security Hardening Edition
