# 🧪 SECURITY TESTING COMMANDS

Comandi per testare tutte le implementazioni di sicurezza.

---

## 📋 Prerequisiti

```bash
# Python 3.8+
python --version

# Install dependencies
pip install -r requirements.txt

# Set environment variables (Linux/macOS)
export FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export ADMIN_PASSWORD=TestAdmin123!
export API_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export FLASK_ENV=development

# Set environment variables (PowerShell)
$env:FLASK_SECRET_KEY = python -c \"import secrets; print(secrets.token_hex(32))\"
$env:ADMIN_PASSWORD = \"TestAdmin123!\"
$env:API_KEY = python -c \"import secrets; print(secrets.token_hex(32))\"
```

---

## 🚀 Start Server

### Terminal 1: Main Server
```bash
cd Backend
python server.py
# Output: Running on http://0.0.0.0:5000
```

### Terminal 2: Centrale (Sensori)
```bash
cd Backend
python centrale.py
# Output: Running on http://0.0.0.0:5005
```

### Terminal 3: Documenti
```bash
cd Backend
python documenti_server.py
# Output: Running on http://0.0.0.0:5010
```

### Terminal 4: Forum
```bash
cd Backend
python forum.py
# Output: Running on http://0.0.0.0:5015
```

---

## ✅ Test 1: CSRF Token Protection

### 1.1 Ottieni Token
```bash
curl -v http://localhost:5000/csrf-token
# Output include: {"csrf_token": "abc123..."}
```

### 1.2 POST con Token Valido ✅
```bash
TOKEN=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')

curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{
    "email": "testcsrf@test.com",
    "password": "Pass123!",
    "nome": "John",
    "cognome": "Doe",
    "ruolo": "user"
  }'
# Risultato: 200 OK
```

### 1.3 POST senza Token ❌
```bash
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@test.com",
    "password": "Pass123!",
    "nome": "John",
    "cognome": "Doe",
    "ruolo": "user"
  }'
# Risultato: 403 Forbidden - CSRF token not found
```

### 1.4 POST con Token Invalido ❌
```bash
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: invalid_token_123" \
  -d '{
    "email": "test@test.com",
    "password": "Pass123!",
    "nome": "John",
    "cognome": "Doe",
    "ruolo": "user"
  }'
# Risultato: 403 Forbidden - Invalid CSRF token
```

---

## ⏱️ Test 2: Rate Limiting

### 2.1 Login Rate Limiting (5 per ora)
```bash
# Genera 6 richieste rapid-fire
for i in {1..6}; do
  echo "Richiesta $i:"
  curl -s -w "HTTP %{http_code}\n" -X POST http://localhost:5000/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"wrong"}'
done

# Output:
# Richiesta 1: HTTP 401
# Richiesta 2: HTTP 401
# Richiesta 3: HTTP 401
# Richiesta 4: HTTP 401
# Richiesta 5: HTTP 401
# Richiesta 6: HTTP 429  ← Rate limited!
```

### 2.2 Register Rate Limiting (5 per ora)
```bash
for i in {1..6}; do
  echo "Registro $i:"
  TOKEN=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')
  curl -s -w "HTTP %{http_code}\n" -X POST http://localhost:5000/register \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $TOKEN" \
    -d "{\"email\":\"reg$i@test.com\",\"password\":\"Pass123!\",\"nome\":\"Test\",\"cognome\":\"User\",\"ruolo\":\"user\"}"
done

# Ultime richieste: HTTP 429
```

### 2.3 Sensor Update Rate Limiting (30 per ora)
```bash
API_KEY=$(echo $API_KEY)  # Already set

# 10 richieste rapid-fire
for i in {1..10}; do
  echo "Update $i:"
  curl -s -w "HTTP %{http_code}\n" -X GET "http://localhost:5005/update?t=22.5&h=60&source=test" \
    -H "X-API-Key: $API_KEY"
done

# Dovrebbe completare 30 prima di limitare
```

---

## 🚫 Test 3: Path Traversal Protection

### 3.1 Tentativo Traversal - Bloccato ❌
```bash
# Prova accedere a file fuori della cartella frontend
curl -v http://localhost:5000/../../../../etc/passwd
# Risultato: 403 Forbidden

curl -v http://localhost:5000/../../../Backend/config.py
# Risultato: 403 Forbidden
```

### 3.2 CSS Traversal - Bloccato ❌
```bash
curl -v http://localhost:5000/css/../../../../etc/passwd
# Risultato: 403 Forbidden
```

### 3.3 CSS Valido - OK ✅
```bash
curl -v http://localhost:5000/css/style.css
# Risultato: 200 OK (o 404 se file non esiste, ma non 403)
```

---

## 📤 Test 4: Content-Type Validation

### 4.1 POST con Content-Type Sbagliato ❌
```bash
# text/plain instead of application/json
curl -X POST http://localhost:5000/login \
  -H "Content-Type: text/plain" \
  -d 'email=test@test.com&password=test123'
# Risultato: 400 Bad Request - Content-Type deve essere application/json
```

### 4.2 POST senza Content-Type ❌
```bash
curl -X POST http://localhost:5000/login \
  -d '{"email":"test@test.com","password":"test123"}'
# Risultato: 400 Bad Request
```

### 4.3 POST con Content-Type Corretto ✅
```bash
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test123"}'
# Risultato: 401 Unauthorized (credenziali wrong, ma request accettato)
```

---

## 🔑 Test 5: API Key Security

### 5.1 Senza API Key ❌
```bash
curl http://localhost:5005/update?t=22.5&h=60
# Risultato: 401 Unauthorized
```

### 5.2 Con API Key Sbagliata ❌
```bash
curl -H "X-API-Key: wrong_key" http://localhost:5005/update?t=22.5&h=60
# Risultato: 401 Unauthorized
```

### 5.3 Con API Key Corretta ✅
```bash
curl -H "X-API-Key: $API_KEY" http://localhost:5005/update?t=22.5&h=60
# Risultato: 200 OK
```

### 5.4 API Key in Query String ❌ (Prevenzione)
```bash
# Anche se metti key in query, non funziona (deve essere header)
curl "http://localhost:5005/update?t=22.5&h=60&X-API-Key=$API_KEY"
# Risultato: 401 Unauthorized
```

---

## 🔐 Test 6: Security Headers

### 6.1 Check Headers di Sicurezza
```bash
curl -v http://localhost:5000/ 2>&1 | grep -i "strict-transport\|x-frame\|x-content-type\|content-security"

# Output atteso:
# Strict-Transport-Security: max-age=31536000
# X-Frame-Options: SAMEORIGIN
# X-Content-Type-Options: nosniff
# Content-Security-Policy: default-src 'self'
```

### 6.2 Check su tutti i server
```bash
echo "=== Server (5000) ==="
curl -s -D - http://localhost:5000 -o /dev/null | grep -i "strict\|x-frame\|x-content"

echo "=== Centrale (5005) ==="
curl -s -D - http://localhost:5005 -o /dev/null | grep -i "strict\|x-frame\|x-content"

echo "=== Documenti (5010) ==="
curl -s -D - http://localhost:5010 -o /dev/null | grep -i "strict\|x-frame\|x-content"

echo "=== Forum (5015) ==="
curl -s -D - http://localhost:5015 -o /dev/null | grep -i "strict\|x-frame\|x-content"
```

---

## 🔒 Test 7: Input Validation

### 7.1 Email Invalid
```bash
TOKEN=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')

curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{
    "email": "not-an-email",
    "password": "Pass123!",
    "nome": "John",
    "cognome": "Doe",
    "ruolo": "user"
  }'
# Risultato: 400 - Email non valida
```

### 7.2 Password Weak
```bash
TOKEN=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')

curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{
    "email": "test@test.com",
    "password": "weak",
    "nome": "John",
    "cognome": "Doe",
    "ruolo": "user"
  }'
# Risultato: 400 - Password non sicura
```

### 7.3 Sensor Range Invalid
```bash
API_KEY=$(echo $API_KEY)

# Temperature fuori range (-50 a 80)
curl -H "X-API-Key: $API_KEY" "http://localhost:5005/update?t=200&h=60"
# Risultato: 400 - Reading out of plausible range

# Humidity fuori range (0 a 100)
curl -H "X-API-Key: $API_KEY" "http://localhost:5005/update?t=22.5&h=150"
# Risultato: 400 - Reading out of plausible range
```

---

## 📊 Test 8: Error Messages (Anti-Enumeration)

### 8.1 Registrazione con Email Existente
```bash
# Prima registrazione
TOKEN1=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')
curl -s -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN1" \
  -d '{"email":"unique@test.com","password":"Pass123!","nome":"John","cognome":"Doe","ruolo":"user"}' | jq

# Seconda registrazione con stessa email
TOKEN2=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')
curl -s -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN2" \
  -d '{"email":"unique@test.com","password":"Pass123!","nome":"Jane","cognome":"Doe","ruolo":"user"}' | jq

# Risultato: Messaggio generico, non rivela se email esiste
# {"success": false, "message": "Registrazione non possibile. Email potrebbe già essere registrata"}
```

---

## 🧬 Test 9: Complete Flow - Registration + Login

```bash
#!/bin/bash

# 1. Get CSRF Token
echo "1. Ottengo CSRF token..."
TOKEN=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')
echo "Token: $TOKEN"

# 2. Register
echo -e "\n2. Registro nuovo utente..."
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{
    "email": "fulltest@test.com",
    "password": "SecurePass123!",
    "nome": "Full",
    "cognome": "Test",
    "ruolo": "user"
  }')
echo $REGISTER_RESPONSE | jq

# 3. Get new CSRF token for login
echo -e "\n3. Ottengo nuovo token per login..."
TOKEN2=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')

# 4. Login
echo -e "\n4. Faccio login..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN2" \
  -d '{
    "email": "fulltest@test.com",
    "password": "SecurePass123!"
  }')
echo $LOGIN_RESPONSE | jq

# 5. Try login con password sbagliata 5 volte
echo -e "\n5. Provo login con password sbagliata 5 volte..."
for i in {1..5}; do
  TOKEN3=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')
  RESULT=$(curl -s -w "\nHTTP %{http_code}" -X POST http://localhost:5000/login \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $TOKEN3" \
    -d '{"email":"fulltest@test.com","password":"wrong"}')
  echo "Tentativo $i: $RESULT"
done

# 6. 6ª richiesta sarà rate limited
echo -e "\n6. Sesto tentativo (rate limited)..."
TOKEN4=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')
curl -s -w "HTTP %{http_code}\n" -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN4" \
  -d '{"email":"fulltest@test.com","password":"wrong"}'
```

---

## 📊 Test 10: Load Test (Optional)

```bash
# Installa Apache Bench
sudo apt-get install apache2-utils  # Linux
brew install httpd                   # macOS

# Test rate limiting con 100 concurrent requests
ab -n 100 -c 10 http://localhost:5000/

# Vedrai rate limiting attivo dopo N richieste
```

---

## 🔧 Troubleshooting

### Problem: jq not found
```bash
# Install jq
sudo apt-get install jq          # Linux
brew install jq                   # macOS
choco install jq                 # Windows
```

### Problem: curl timeout
```bash
# Aumenta timeout
curl --max-time 10 http://localhost:5000/
```

### Problem: CSRF token expired
```bash
# Token session scade, richiedi nuovo token
TOKEN=$(curl -s http://localhost:5000/csrf-token | jq -r '.csrf_token')
```

### Problem: Port already in use
```bash
# Trova processo su port
lsof -i :5000

# Uccidi processo
kill -9 <PID>

# O usa porta diversa
FLASK_PORT=5001 python server.py
```

---

## 📝 Test Report Template

Dopo completare tutti i test, compila:

```markdown
# Security Test Report - SitoDazeForFuture

Date: 2025-11-30
Tester: [Your Name]
Environment: [Dev/Staging/Prod]

## Test Results

| Test | Status | Notes |
|------|--------|-------|
| CSRF Protection | ✅ PASS | Token validation works |
| Rate Limiting | ✅ PASS | 429 after limit |
| Path Traversal | ✅ PASS | ../.. blocked |
| Content-Type | ✅ PASS | Non-JSON rejected |
| API Key | ✅ PASS | Header-only |
| Security Headers | ✅ PASS | All headers present |
| Input Validation | ✅ PASS | Invalid data rejected |
| Error Messages | ✅ PASS | Generic messages |
| Full Flow | ✅ PASS | Register + Login works |
| Load Test | ✅ PASS | Rate limit under load |

## Summary
All security tests passed successfully. Application is ready for deployment.

## Issues Found
None.

## Recommendations
None at this time.
```

---

**Versione**: 1.0  
**Data**: 2025-11-30  
**Tipo**: QA/Security Testing
