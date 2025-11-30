# Sito di Daze For Future
Il sito è attualmente hostato su un Raspberry Pi 400.
## Specifiche Raspberry Pi 400

| Caratteristica        | Specifica                                                                 |
|------------------------|---------------------------------------------------------------------------|
| Processore             | Broadcom BCM2711 quad-core Cortex-A72 (ARM v8) 64-bit SoC a 1,8 GHz       |
| GPU                    | VideoCore VI                                                             |
| RAM                    | 4 GB LPDDR4-3200                                                         |
| Archiviazione          | microSD 128GB                                                         |
| Connettività wireless  | Wi-Fi 802.11b/g/n/ac (2,4 e 5 GHz), Bluetooth 5.0, BLE                   |
| Ethernet               | Gigabit Ethernet                                                         |
| Porte USB              | 2 × USB 3.0, 1 × USB 2.0                                                 |
| Uscite video           | 2 × micro HDMI (fino a 4Kp60 supportato)                                 |
| Uscita audio           | Via HDMI e GPIO (non presente jack 3,5 mm)                               |
| GPIO                   | Header GPIO a 40 pin (attraverso connettore dedicato)                    |
| Alimentazione          | USB-C (5V/3A consigliati)                                                |
| Tastiera integrata     | Layout completo a 78/79 tasti (dipende dal mercato)                      |
| Dimensioni             | 286 × 122 × 23 mm                                                        |
| Sistema operativo      | Ubuntu Server 24.04.03 LTS                        |

## Fatto da:
- Davide Albanese 
    <p>
    <a href="https://github.com/DocCiaoBimbi" target="_blank" style="text-decoration: none;">
        <img src="https://img.shields.io/badge/Account-GitHub-grey?style=flat-square&logo=github" alt="Account GitHub" />
    </a>
    </p>
- Michele Antonio Portulano  
    <p> <a href="https://github.com/MichyPortu08" target="_blank" style="text-decoration: none;">
        <img src="https://img.shields.io/badge/Account-GitHub-grey?style=flat-square&logo=github" alt="Account GitHub" />
    </a>
    </p>
- Achenio Sogno 
    <p> <a href="https://github.com/achenio" target="_blank" style="text-decoration: none;">
        <img src="https://img.shields.io/badge/Account-GitHub-grey?style=flat-square&logo=github" alt="Account GitHub" />
    </a>
    </p>


---

##  Security & Setup Guide

### Quick Start

1. **Installa le dipendenze:**
   \\\ash
   pip install -r requirements.txt
   \\\

2. **Configura le variabili d'ambiente:**
   \\\ash
   cp .env.example .env
   # Edita .env e genera secret keys sicure:
   python -c "import secrets; print('FLASK_SECRET_KEY=' + secrets.token_hex(32))"
   python -c "import secrets; print('API_KEY=' + secrets.token_urlsafe(32))"
   \\\

3. **Avvia i server:**
   \\\ash
   # Terminal 1
   python Backend/server.py

   # Terminal 2
   python Backend/forum.py

   # Terminal 3
   python Backend/post.py

   # Terminal 4
   python Backend/centrale.py

   # Terminal 5
   python Backend/documenti_server.py
   \\\

###  Security Features Implemented

| Feature | Status | Details |
|---------|--------|---------|
| Input Validation & Sanitization |  | Email, password, text validation |
| Secure Password Hashing |  | PBKDF2 with 16-byte salt |
| API Key Security |  | Timing-safe comparison, header-only |
| CORS Protection |  | Whitelist-based with environment config |
| XSS Prevention |  | HTML entity escaping |
| SQL Injection Prevention |  | Parametrized queries (all endpoints) |
| Dependencies Updated |  | Flask 3.0.3, Werkzeug 3.0.3 |

###  Documentation

See \SECURITY_FIXES.md\ for detailed security implementation guide and testing procedures.

###  Testing Security

\\\ash
python Backend/test_security.py http://localhost:5000
\\\

###  Production Deployment Checklist

- [ ] Enable HTTPS with valid certificate
- [ ] Set all environment variables in \.env\
- [ ] Use Gunicorn instead of Flask dev server
- [ ] Configure database backups
- [ ] Setup monitoring and alerting
- [ ] Run \pip-audit\ to check for vulnerabilities
- [ ] Configure firewall rules
- [ ] Review logs for suspicious activity
