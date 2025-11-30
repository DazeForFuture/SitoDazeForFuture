# 🚀 Deployment Security Guide - SitoDazeForFuture

Guida completa per deployare l'applicazione in modo sicuro in produzione.

---

## ⚙️ **Configurazione Pre-Deployment**

### 1. **Variabili d'Ambiente (.env)**

Crea un file `.env` **FUORI dal repository** (aggiunto a `.gitignore`):

```bash
# Core Flask
FLASK_ENV=production
FLASK_SECRET_KEY=<random_32_bytes_hex>  # Generare con: python -c "import secrets; print(secrets.token_hex(32))"

# Admin
ADMIN_PASSWORD=<strong_admin_password>

# Database
DB_FILE=../../database/daticentrale.db

# API Keys
API_KEY=<random_api_key_32_bytes>

# Sensor Config
ENABLE_SERIAL=false
SERIAL_PATH=
SERIAL_BAUD=115200
WIFI_FRESH_MS=60000

# Server Config
HOST=0.0.0.0
PORT=5000
MAX_CONTENT_LENGTH=8388608  # 8MB

# CORS - In production usa il dominio reale
ALLOWED_ORIGINS=https://example.com,https://www.example.com

# Security
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
PERMANENT_SESSION_LIFETIME=3600
```

### 2. **Generare Secret Key Sicura**

```bash
python -c "import secrets; print(f'FLASK_SECRET_KEY={secrets.token_hex(32)}')"
python -c "import secrets; print(f'API_KEY={secrets.token_hex(32)}')"
python -c "import secrets; print(f'ADMIN_PASSWORD={secrets.token_urlsafe(32)}')"
```

### 3. **Installare Dipendenze**

```bash
pip install -r requirements.txt
```

---

## 🏢 **Deployment con Gunicorn (Recommended)**

### Step 1: Installa Gunicorn

```bash
pip install gunicorn[gevent]
```

### Step 2: Crea Script di Startup

**`start_servers.sh`** (Linux/macOS):
```bash
#!/bin/bash
set -e

export FLASK_ENV=production
source /path/to/.env

cd /path/to/Backend

# Server.py (port 5000)
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 30 --access-logfile /var/log/server.log server:app &
PIDS="$PIDS $!"

# Centrale.py (port 5005)
gunicorn -w 2 -b 0.0.0.0:5005 --timeout 30 --access-logfile /var/log/centrale.log centrale:app &
PIDS="$PIDS $!"

# Documenti.py (port 5010)
gunicorn -w 2 -b 0.0.0.0:5010 --timeout 60 --access-logfile /var/log/documenti.log documenti_server:app &
PIDS="$PIDS $!"

# Forum.py (port 5015)
gunicorn -w 2 -b 0.0.0.0:5015 --timeout 30 --access-logfile /var/log/forum.log forum:app &
PIDS="$PIDS $!"

echo "All servers started with PIDs: $PIDS"

# Graceful shutdown
trap "kill $PIDS" SIGINT SIGTERM
wait
```

**`start_servers.ps1`** (PowerShell/Windows):
```powershell
$env:FLASK_ENV = "production"
Get-Content .env | ForEach-Object {
    if ($_ -match '(.+)=(.+)') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
    }
}

cd Backend

# Server.py
Start-Process -NoNewWindow -FilePath python -ArgumentList "-m gunicorn -w 4 -b 0.0.0.0:5000 server:app"

# Centrale.py
Start-Process -NoNewWindow -FilePath python -ArgumentList "-m gunicorn -w 2 -b 0.0.0.0:5005 centrale:app"

# Documenti.py
Start-Process -NoNewWindow -FilePath python -ArgumentList "-m gunicorn -w 2 -b 0.0.0.0:5010 documenti_server:app"

# Forum.py
Start-Process -NoNewWindow -FilePath python -ArgumentList "-m gunicorn -w 2 -b 0.0.0.0:5015 forum:app"

Write-Host "All servers started"
```

### Step 3: Parametri Gunicorn Spiegati

```
-w 4                    # 4 worker process (regola in base a CPU cores)
-b 0.0.0.0:5000         # Bind all interfaces, port 5000
--timeout 30            # Timeout 30 secondi per richiesta
--access-logfile        # Log accessi HTTP
--reload                # NON usare in produzione (per dev only)
--worker-class gevent   # Async worker (opzionale)
```

---

## 🔒 **Configurazione Nginx (Reverse Proxy)**

### nginx.conf (Produzione Sicura)

```nginx
# Rate limit zone
limit_req_zone $binary_remote_addr zone=general:10m rate=20r/s;
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;

upstream server_app {
    server localhost:5000;
}

upstream centrale_app {
    server localhost:5005;
}

upstream documenti_app {
    server localhost:5010;
}

upstream forum_app {
    server localhost:5015;
}

# HTTPS Redirect
server {
    listen 80;
    server_name example.com www.example.com;
    
    location / {
        return 301 https://$server_name$request_uri;
    }
    
    # ACME challenge per Let's Encrypt
    location /.well-known/acme-challenge/ {
        alias /var/www/certbot/.well-known/acme-challenge/;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    server_name example.com www.example.com;
    
    # SSL Certificate
    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
    
    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;" always;
    
    # Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;
    
    # Rate Limiting
    limit_req zone=general burst=40 nodelay;
    
    # Main API
    location / {
        limit_req zone=general burst=40 nodelay;
        proxy_pass http://server_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
    
    # Auth Endpoints (Stricter rate limiting)
    location ~ ^/(login|register|csrf-token)$ {
        limit_req zone=auth burst=5 nodelay;
        proxy_pass http://server_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Sensori
    location ~ ^/api/sensor|^/stream|^/latest|^/history$ {
        limit_req zone=general burst=60 nodelay;
        proxy_pass http://centrale_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;  # For SSE
        proxy_cache_bypass $http_upgrade;
    }
    
    # Documenti
    location ~ ^/api/|^/files/ {
        limit_req zone=general burst=30 nodelay;
        proxy_pass http://documenti_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_request_buffering off;  # For file upload
        client_max_body_size 50M;
    }
    
    # Forum
    location ~ ^/api/threads|^/api/posts {
        limit_req zone=general burst=30 nodelay;
        proxy_pass http://forum_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Deny access to sensitive files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
    
    location ~ ~$ {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

---

## 📝 **Checklist Pre-Produzione**

- [ ] Secret Key generata e aggiunta a `.env`
- [ ] API Key generata e configurata
- [ ] Admin password forte impostata
- [ ] `.env` aggiunto a `.gitignore`
- [ ] Gunicorn installato
- [ ] Nginx configurato per HTTPS
- [ ] SSL Certificate (Let's Encrypt)
- [ ] Rate limiting attivo in nginx
- [ ] Log directory exists: `/var/log/`
- [ ] Database directory writable: `../../database/`
- [ ] Firewall configurato (porta 80, 443 aperte; 5000-5015 chiuse)
- [ ] Monitoring attivo (cpu, memory, disk)
- [ ] Backup database setup
- [ ] Error logging configurato

---

## 🔐 **Hardening Security**

### 1. **Firewall (UFW - Linux)**

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing

sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS

sudo ufw enable

# Blocca porte Flask
sudo ufw deny 5000:5015/tcp
```

### 2. **Backup Automatico Database**

```bash
# backup.sh
#!/bin/bash
BACKUP_DIR="/backups/sitodaze"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup databases
sqlite3 /var/local/database/utenti.db ".backup $BACKUP_DIR/utenti_$TIMESTAMP.db"
sqlite3 /var/local/database/daticentrale.db ".backup $BACKUP_DIR/daticentrale_$TIMESTAMP.db"
sqlite3 /var/local/database/documenti.db ".backup $BACKUP_DIR/documenti_$TIMESTAMP.db"
sqlite3 /var/local/database/forum.db ".backup $BACKUP_DIR/forum_$TIMESTAMP.db"

# Compress
tar -czf $BACKUP_DIR/backup_$TIMESTAMP.tar.gz $BACKUP_DIR/*_$TIMESTAMP.db

# Remove old backups (keep 30 days)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
```

### 3. **Crontab per Backup**

```bash
# Backup ogni giorno alle 2:00 AM
0 2 * * * /path/to/backup.sh >> /var/log/backup.log 2>&1
```

---

## 📊 **Monitoring**

### Health Check Endpoint

```python
@app.route('/health')
def health():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0'
    }), 200
```

### Monitoraggio con Prometheus (Opzionale)

```bash
pip install prometheus-client
```

---

## 🚨 **Incident Response**

Se noti attività sospetta:

1. **Check Logs**
   ```bash
   tail -f /var/log/server.log
   tail -f /var/log/access.log
   ```

2. **Rate Limiting Attacchi**
   ```bash
   grep "429 Too Many Requests" /var/log/access.log | tail -20
   ```

3. **Block IP Address**
   ```bash
   sudo ufw deny from <attacker_ip>
   ```

4. **Restart Service**
   ```bash
   systemctl restart sitodaze
   ```

---

## ✨ **Produzione - Final Checklist**

```
✅ SSL/TLS HTTPS configurato
✅ Rate limiting attivo (nginx + Flask-Limiter)
✅ CSRF protection attivo
✅ Path traversal prevention attivo
✅ Secrets in environment variables
✅ Debug mode OFF
✅ Logging configurato
✅ Backup automatico
✅ Firewall configurato
✅ Monitoring attivo
✅ Error pages personalizzate
```

---

**Versione**: 1.0  
**Data**: 2025-11-30  
**Autore**: Security Team
