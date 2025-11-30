# 🔐 Security Improvements - SitoDazeForFuture

Questo documento descrive tutti i miglioramenti di sicurezza implementati nel progetto.

---

## ✅ **Implementazioni Completate**

### 1. **Rate Limiting (Flask-Limiter)**
- **Stato**: ✅ Implementato
- **File modificati**: `server.py`, `centrale.py`, `documenti_server.py`, `forum.py`
- **Cosa fa**: Limita il numero di richieste per prevenire:
  - Brute force su login/registrazione (5 per ora)
  - Enumerazione di utenti
  - Attacchi DoS

**Limiti applicati**:
- `/register`, `/login`: **5 per ora**
- `/update`, `/latest`: **30-60 per ora**
- `/api/threads`, `/api/create_publication`: **10-20 per ora**
- `/api/posts/<id>/vote`: **60 per ora**

---

### 2. **Path Traversal Protection**
- **Stato**: ✅ Implementato
- **File modificati**: `server.py`, `security.py`
- **Cosa fa**: 
  - Funzione `safe_path_join()` che valida i path relativi
  - Previene accesso a file al di fuori delle directory autorizzate
  - Blocca pattern come `../../../etc/passwd`

**Endpoint protetti**:
```
GET / /<path:filename>
GET /css/<path:filename>
```

---

### 3. **Protezione CSRF Token**
- **Stato**: ✅ Implementato
- **File modificati**: `security.py`, `server.py`
- **Cosa fa**:
  - Token generato casualmente (32 bytes, timing-safe)
  - Stored in session, transmitted in header `X-CSRF-Token`
  - Decorator `@require_csrf_token()` su POST/PUT/DELETE

**Funzioni aggiunte**:
```python
generate_csrf_token()     # Crea token random
verify_csrf_token()       # Verifica con hmac.compare_digest
require_csrf_token()      # Decorator
```

**Flow client**:
1. Client chiama `GET /csrf-token` → riceve token
2. Client aggiunge header `X-CSRF-Token` su POST/PUT/DELETE
3. Server valida token prima di processare

---

### 4. **Content-Type Validation**
- **Stato**: ✅ Implementato
- **File modificati**: `server.py`
- **Cosa fa**:
  - Endpoint `/register` e `/login` accettano SOLO `application/json`
  - Previene content confusion attacks
  - Risponde con 400 se Content-Type invalido

```python
if not request.is_json:
    return jsonify({'success': False, 'message': 'Content-Type deve essere application/json'}), 400
```

---

### 5. **Prevenzione Enumeration di Utenti**
- **Stato**: ✅ Implementato
- **File modificati**: `server.py`
- **Cosa fa**:
  - Non rivela se email esiste già nel sistema
  - Messaggio generico: "Email già registrata (potrebbe essere registrata)"
  - Log interno per audit

**Prima** (vulnerabile):
```python
except sqlite3.IntegrityError:
    return jsonify({'success': False, 'message': 'Email già registrata'}), 409
```

**Dopo** (sicuro):
```python
except sqlite3.IntegrityError:
    app.logger.warning(f"Registration attempt with duplicate email: {email}")
    return jsonify({'success': False, 'message': 'Registrazione non possibile...'}), 400
```

---

### 6. **Security Headers (Flask-Talisman)**
- **Stato**: ✅ Implementato
- **File modificati**: `server.py`, `centrale.py`, `documenti_server.py`, `forum.py`
- **Cosa fa**: Aggiunge header di sicurezza HTTP automaticamente

**Headers applicati**:
```
Strict-Transport-Security: max-age=31536000 (HSTS 1 year)
X-Frame-Options: SAMEORIGIN (no clickjacking)
X-Content-Type-Options: nosniff (no MIME sniffing)
Content-Security-Policy: default-src 'self' (CSP)
```

**Configurazione**:
```python
Talisman(
    app,
    force_https=True,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    content_security_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'"],
    }
)
```

---

### 7. **Logging Sicuro**
- **Stato**: ✅ Implementato
- **File modificati**: `server.py`, `security.py`
- **Cosa fa**:
  - Funzione `sanitize_for_logging()` che redatta dati sensibili
  - Maschere: password, token, api_key, secret, creditcard, ssn
  - Non loga email su admin password failure

**Esempio**:
```python
app.logger.error(f"Error: {sanitize_for_logging({'password': 'secret123'})}")
# Output: "Error: {'password': '***REDACTED***'}"
```

---

### 8. **Validazione Input Robusto**
- **Stato**: ✅ Già presente, confermato
- **File**: `security.py`
- **Funzioni**:
  - `is_valid_email()` - RFC 5322 compliant
  - `is_strong_password()` - 8+ char, 3/4 requisiti
  - `sanitize_text()` - HTML escape, length check
  - `validate_range()` - Numeric validation
  - `safe_path_join()` - Path traversal prevention

---

### 9. **Password Hashing Sicuro**
- **Stato**: ✅ Già presente, confermato
- **File**: `server.py`
- **Configurazione**:
```python
hashed_pw = generate_password_hash(
    password, 
    method='pbkdf2:sha256', 
    salt_length=16
)
```

---

### 10. **Session Security**
- **Stato**: ✅ Implementato in `config.py`
- **Settings**:
```python
SESSION_COOKIE_SECURE = True        # HTTPS only
SESSION_COOKIE_HTTPONLY = True      # No JS access
SESSION_COOKIE_SAMESITE = "Lax"     # CSRF protection
PERMANENT_SESSION_LIFETIME = 3600   # 1 hour timeout
```

---

## 📋 **Checklist di Sicurezza**

| # | Feature | Stato | Note |
|---|---------|-------|------|
| 1 | Rate Limiting | ✅ | Flask-Limiter attivo su tutti i server |
| 2 | Path Traversal | ✅ | safe_path_join() applicato |
| 3 | CSRF Token | ✅ | Decorator applicato su POST/PUT/DELETE |
| 4 | Content-Type | ✅ | Validazione su login/register |
| 5 | Anti-Enumeration | ✅ | Messaggi generici per errori |
| 6 | Security Headers | ✅ | Talisman su tutti i server |
| 7 | Logging Sicuro | ✅ | Redazione di dati sensibili |
| 8 | Input Validation | ✅ | Email, password, text sanitization |
| 9 | Password Hash | ✅ | pbkdf2:sha256 con salt 16 byte |
| 10 | Session Security | ✅ | Secure, HttpOnly, SameSite |
| 11 | API Key | ✅ | Header-only, timing-safe comparison |
| 12 | SQL Injection | ✅ | Prepared statements su tutti i DB |

---

## 🚀 **Come Testare**

### Test Rate Limiting
```bash
# Fare 6 richieste di login in rapida successione
for i in {1..6}; do
  curl -X POST http://localhost:5000/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"test123","csrf_token":"token"}'
done
# 6ª richiesta riceve: HTTP 429 Too Many Requests
```

### Test Path Traversal
```bash
# Tentare accesso a file fuori dalla cartella frontend
curl http://localhost:5000/../../../etc/passwd
# Riceve: 403 Forbidden
```

### Test CSRF
```bash
# Senza token
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"Pass123!"}'
# Riceve: 403 CSRF token missing

# Con token
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{"email":"test@test.com","password":"Pass123!"}'
# Processa la richiesta
```

### Test Content-Type
```bash
# Wrong content-type
curl -X POST http://localhost:5000/login \
  -H "Content-Type: text/plain" \
  -d 'email=test@test.com&password=test123'
# Riceve: 400 Content-Type deve essere application/json

# Correct
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123"}'
# Funziona
```

---

## 📦 **Dipendenze Utilizzate**

Tutte le seguenti sono in `requirements.txt`:

```
Flask==3.0.3
Flask-Limiter==3.5.0          # Rate limiting
Flask-Talisman==1.1.0         # Security headers
Werkzeug==3.0.3               # Password hashing
flask-cors==4.0.0             # CORS
```

---

## ⚠️ **Prossimi Passi (Opzionali)**

1. **WAF (Web Application Firewall)**
   - Implementare ModSecurity in nginx
   - Protezione da SQL injection, XSS, command injection

2. **Monitoring**
   - ELK Stack (Elasticsearch, Logstash, Kibana)
   - Monitoring realtime di tentativi di attacco

3. **Secrets Rotation**
   - Implementare rotation automatica di API keys
   - Usare Vault per secrets management

4. **Penetration Testing**
   - Commissare pentest professionale
   - Fuzzing automatico su tutti gli endpoint

5. ** 2FA (Two-Factor Authentication)**
   - Aggiungere TOTP (Time-based OTP)
   - Login più sicuro con SMS o authenticator app

---

## 🔗 **Riferimenti Sicurezza**

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Rate Limiting](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#throttle-login-attempts)
- [Flask Security](https://flask.palletsprojects.com/security/)
- [Flask-Talisman](https://github.com/wntrblm/flask-talisman)
- [Flask-Limiter](https://flask-limiter.readthedocs.io/)

---

## ✍️ **Changelog**

| Data | Versione | Cambiamenti |
|------|----------|-----------|
| 2025-11-30 | 1.0 | Implementazione completa di tutti i miglioramenti di sicurezza |

---

**Documento creato**: 2025-11-30  
**Ultimo aggiornamento**: 2025-11-30  
**Autore**: Security Review
