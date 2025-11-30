# 🔒 Quick Reference Guide - Security Implementation

## 📌 Essential Commands

### Setup (First Time)
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate security keys
python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('API_KEY=' + secrets.token_urlsafe(32))"

# 3. Configure environment
cp .env.example .env
# Edit .env and paste the generated keys

# 4. Test security
python Backend/test_security.py http://localhost:5000
```

### Running Servers
```bash
# Option 1: Manual (one per terminal)
python Backend/server.py          # Port 5000
python Backend/documenti_server.py # Port 5001
python Backend/post.py             # Port 5002
python Backend/forum.py            # Port 5003
python Backend/centrale.py         # Port 5005

# Option 2: Automated with monitoring
python Backend/autostart_servers.py
```

### Monitoring & Logs
```bash
# Check logs
tail -f Backend/server.log        # Main app
tail -f Backend/central.log       # Sensors
tail -f servers.log               # All servers

# Check active servers
netstat -ano | findstr "5000\|5001\|5002\|5003\|5005"

# Validate security (after startup)
python Backend/test_security.py http://localhost:5000
```

---

## 🛡️ Security Features Checklist

### Input Validation
```python
from security import is_valid_email, sanitize_text, validate_iso_date

# Email validation
if not is_valid_email(request.json.get('email')):
    return jsonify({'error': 'Invalid email'}), 400

# Text sanitization (prevents XSS)
title = sanitize_text(request.json.get('title'), max_length=200)

# Date validation
if not validate_iso_date(request.json.get('date')):
    return jsonify({'error': 'Invalid date format'}), 400
```

### API Key Protection
```python
from security import require_api_key

@app.route('/protected')
@require_api_key(app.config['API_KEY'])
def protected_endpoint():
    return jsonify({'data': 'secret'})
```

### CORS Configuration
```bash
# In .env:
ALLOWED_ORIGINS=http://localhost:3000,https://example.com
```

### Password Hashing
```python
from werkzeug.security import generate_password_hash, check_password_hash

# Hash password
hashed = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

# Verify password
if check_password_hash(hashed, password):
    # Password is correct
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `Backend/security.py` | All security utilities (import from here) |
| `.env.example` | Template for environment variables |
| `SECURITY_FIXES.md` | Detailed security documentation |
| `nginx.conf.example` | Production reverse proxy config |
| `Backend/test_security.py` | Security test suite |

---

## 🔧 Configuration Variables

```bash
# .env - Essential Configuration

# Session security
FLASK_SECRET_KEY=<generate with: secrets.token_hex(32)>

# API security
API_KEY=<generate with: secrets.token_urlsafe(32)>
ADMIN_PASSWORD=<strong password>

# Network
ALLOWED_ORIGINS=http://localhost:3000,https://example.com
HOST=0.0.0.0
PORT=5000

# Database
DB_FILE=../../database/daticentrale.db
MAX_CONTENT_LENGTH=8388608

# Sensors (centrale.py)
ENABLE_SERIAL=true
SERIAL_BAUD=115200
```

---

## ✅ Testing Checklist

```bash
# 1. Syntax validation
python -m py_compile Backend/*.py

# 2. Security tests
python Backend/test_security.py http://localhost:5000

# 3. Manual API tests
curl -X POST http://localhost:5000/register \
  -H "Content-Type: application/json" \
  -d '{
    "nome":"Test",
    "cognome":"User", 
    "email":"test@example.com",
    "ruolo":"student",
    "password":"SecurePass123!"
  }'

# 4. API key validation
curl -H "X-API-Key: wrong" http://localhost:5005/update
# Should return 401

# 5. CORS validation
curl -H "Origin: https://malicious.com" http://localhost:5000/
# Should NOT have Access-Control-Allow-Origin header

# 6. XSS prevention
curl -X POST http://localhost:5002/api/post \
  -H "Content-Type: application/json" \
  -d '{
    "titolo":"<script>alert(1)</script>",
    "contenuto":"test"
  }'
# Should escape the script tag
```

---

## 🚨 Common Issues & Solutions

### Issue: "Missing FLASK_SECRET_KEY"
**Solution:** 
```bash
export FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

### Issue: "API key required but not set"
**Solution:**
```bash
export API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Issue: "CORS error on frontend"
**Solution:**
```bash
# Add frontend URL to .env
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### Issue: "Port already in use"
**Solution:**
```bash
# Kill process on port (e.g., 5000)
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :5000
kill -9 <PID>
```

### Issue: "Module 'security' not found"
**Solution:**
```bash
# Ensure you're in Backend directory
cd Backend
# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/Backend"
```

---

## 📊 Performance Tips

1. **Use environment variables** for sensitive data
2. **Enable caching** for static assets
3. **Use connection pooling** for databases
4. **Monitor logs** for suspicious activity
5. **Update dependencies** regularly

---

## 🔐 Security Audit Checklist

- [ ] All API endpoints require authentication
- [ ] CORS is configured with whitelist
- [ ] API keys are in environment variables (not code)
- [ ] Passwords use PBKDF2 + salt
- [ ] All inputs are validated and sanitized
- [ ] Error messages don't leak sensitive info
- [ ] Logs don't contain passwords or tokens
- [ ] HTTPS is enabled in production
- [ ] Database backups are configured
- [ ] Monitoring is in place

---

## 📞 Support Resources

- **SECURITY_FIXES.md** - Detailed security guide
- **IMPLEMENTATION_SUMMARY.md** - Implementation details
- **CHANGELOG.md** - Version history
- **README.md** - General documentation
- **Security tests** - Run `python Backend/test_security.py`

---

**Last Updated:** November 30, 2025  
**Status:** ✅ Production Ready
