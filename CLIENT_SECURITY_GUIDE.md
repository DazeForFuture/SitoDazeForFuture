# 🛡️ Client-Side Security Implementation Guide

Guida per integrare i nuovi controlli di sicurezza dal lato client/frontend.

---

## 📋 **Indice**

1. [CSRF Token](#csrf-token)
2. [Rate Limiting Handling](#rate-limiting-handling)
3. [Content-Type Headers](#content-type-headers)
4. [Path Traversal Protection](#path-traversal-protection)
5. [Error Handling](#error-handling)
6. [Example Requests](#example-requests)

---

## 🔐 **CSRF Token**

### Flusso di Utilizzo

#### Passo 1: Ottieni il Token

**JavaScript (Vanilla)**:
```javascript
async function getCsrfToken() {
    const response = await fetch('/csrf-token', {
        method: 'GET',
        credentials: 'include'  // Importante: per cookie di sessione
    });
    
    const data = await response.json();
    return data.csrf_token;
}

// Esecuzione
const token = await getCsrfToken();
console.log('CSRF Token:', token);
```

**jQuery**:
```javascript
function getCsrfToken() {
    return $.ajax({
        url: '/csrf-token',
        method: 'GET',
        dataType: 'json',
        xhrFields: {
            withCredentials: true
        }
    }).then(data => data.csrf_token);
}
```

**Axios**:
```javascript
import axios from 'axios';

// Configure axios to include credentials
axios.defaults.withCredentials = true;

async function getCsrfToken() {
    const { data } = await axios.get('/csrf-token');
    return data.csrf_token;
}
```

#### Passo 2: Usa il Token nei POST

**Vanilla Fetch**:
```javascript
async function registerUser(email, password) {
    const token = await getCsrfToken();
    
    const response = await fetch('/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': token  // ⚠️ Importante: Header CSRF
        },
        credentials: 'include',
        body: JSON.stringify({
            email: email,
            password: password,
            nome: 'John',
            cognome: 'Doe',
            ruolo: 'user',
            csrf_token: token  // Opzionale: anche in body
        })
    });
    
    return await response.json();
}
```

**jQuery**:
```javascript
function registerUser(email, password) {
    return $.ajax({
        url: '/register',
        method: 'POST',
        contentType: 'application/json',
        headers: {
            'X-CSRF-Token': getCsrfToken()
        },
        data: JSON.stringify({
            email: email,
            password: password,
            nome: 'John',
            cognome: 'Doe',
            ruolo: 'user'
        }),
        dataType: 'json',
        xhrFields: {
            withCredentials: true
        }
    });
}
```

**Axios**:
```javascript
async function registerUser(email, password) {
    const token = await getCsrfToken();
    
    const response = await axios.post('/register', {
        email: email,
        password: password,
        nome: 'John',
        cognome: 'Doe',
        ruolo: 'user'
    }, {
        headers: {
            'X-CSRF-Token': token
        }
    });
    
    return response.data;
}
```

#### Passo 3: Store Token Localmente (Opzionale)

```javascript
// Store in sessionStorage (esiste solo per la sessione del browser)
sessionStorage.setItem('csrf_token', token);

// Recupera
const storedToken = sessionStorage.getItem('csrf_token');
```

---

## ⏱️ **Rate Limiting Handling**

### Cosa Succede

- **429 Too Many Requests**: Troppi tentativi
- **Retry-After header**: Specifica quando riprovare

### Gestione Client

```javascript
async function handleRateLimit(response) {
    if (response.status === 429) {
        // Optionally, read Retry-After header
        const retryAfter = response.headers.get('Retry-After') || 60;
        
        console.warn(`Rate limited. Retry after ${retryAfter} seconds`);
        
        // Notifica utente
        showError(`Troppi tentativi. Riprova tra ${retryAfter} secondi`);
        
        // Disabilita bottone per N secondi
        disableButtonFor(parseInt(retryAfter));
        
        return false;
    }
    return true;
}

// Usage
const response = await fetch('/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
});

if (!handleRateLimit(response)) {
    return;
}

const data = await response.json();
```

### Exponential Backoff

```javascript
async function fetchWithRetry(url, options, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const response = await fetch(url, options);
            
            if (response.status === 429) {
                const delay = Math.pow(2, i) * 1000; // 1s, 2s, 4s...
                console.log(`Retry ${i + 1}/${maxRetries} after ${delay}ms`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }
            
            return response;
        } catch (error) {
            if (i === maxRetries - 1) throw error;
        }
    }
}

// Usage
const response = await fetchWithRetry('/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
});
```

---

## 📤 **Content-Type Headers**

### Importante: Content-Type DEVE essere `application/json`

```javascript
// ✅ CORRETTO
fetch('/login', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'  // ⚠️ Obbligatorio
    },
    body: JSON.stringify({ email, password })
});

// ❌ SBAGLIATO - Riceve 400 Error
fetch('/login', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: 'email=test@test.com&password=test123'
});

// ❌ SBAGLIATO - Se no headers, è text/plain
fetch('/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
});
```

### Form Data (Se Supportato)

Per endpoint che accettano `multipart/form-data` (upload file):

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('title', 'My Document');

fetch('/api/create_publication', {
    method: 'POST',
    // NON specificare Content-Type - il browser lo farà automaticamente
    body: formData
});
```

---

## 🚫 **Path Traversal Protection**

### Cosa Non Fare

```javascript
// ❌ BLOCCATO - Path traversal attempt
fetch('/../../../../etc/passwd');
// Response: 403 Forbidden

// ❌ BLOCCATO - Anche codificato
fetch('/%2e%2e/%2e%2e/etc/passwd');
// Response: 403 Forbidden
```

### Safe Patterns

```javascript
// ✅ OK - File legittimi nella cartella
fetch('/css/style.css');
fetch('/immagini/logo.png');
fetch('/login.html');

// ✅ OK - Scarica documento
fetch('/files/pubblicazioni/documento.pdf');
```

---

## ⚠️ **Error Handling**

### Tipi di Errori di Sicurezza

```javascript
const handleSecurityError = (response) => {
    switch (response.status) {
        case 400:
            // Bad Request (validation failed)
            return { error: 'Dati non validi. Controlla i campi.' };
        
        case 401:
            // Unauthorized (invalid credentials)
            return { error: 'Credenziali non valide.' };
        
        case 403:
            // Forbidden (no permission / CSRF fail / path traversal)
            return { error: 'Accesso negato. Riprova.' };
        
        case 409:
            // Conflict (resource exists)
            return { error: 'Risorsa già esiste.' };
        
        case 429:
            // Too Many Requests (rate limited)
            return { error: 'Troppi tentativi. Riprova più tardi.' };
        
        case 500:
            // Server Error
            return { error: 'Errore del server. Contatta support.' };
        
        default:
            return { error: 'Errore sconosciuto.' };
    }
};

// Usage
try {
    const response = await fetch('/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': token
        },
        body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
        const { error } = handleSecurityError(response);
        showError(error);
        return;
    }
    
    const data = await response.json();
    handleLoginSuccess(data);
    
} catch (error) {
    console.error('Network error:', error);
    showError('Errore di connessione. Controlla la rete.');
}
```

---

## 📝 **Example Requests**

### Login Completo

```javascript
// 1. Get CSRF Token
const tokenResponse = await fetch('/csrf-token', {
    credentials: 'include'
});
const { csrf_token } = await tokenResponse.json();

// 2. Login con token
const loginResponse = await fetch('/login', {
    method: 'POST',
    credentials: 'include',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrf_token
    },
    body: JSON.stringify({
        email: 'user@example.com',
        password: 'SecurePass123!'
    })
});

// 3. Check response
if (loginResponse.status === 429) {
    alert('Troppi tentativi. Riprova più tardi.');
} else if (!loginResponse.ok) {
    const data = await loginResponse.json();
    alert(data.message);
} else {
    const data = await loginResponse.json();
    if (data.success) {
        // Store session info
        localStorage.setItem('email', data.email);
        localStorage.setItem('ruolo', data.ruolo);
        // Redirect
        window.location.href = '/dashboard';
    }
}
```

### Registration Completo

```javascript
async function completeRegistration(formData) {
    try {
        // 1. Get CSRF Token
        const tokenRes = await fetch('/csrf-token', {
            credentials: 'include'
        });
        const { csrf_token } = await tokenRes.json();
        
        // 2. Register
        const registerRes = await fetch('/register', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrf_token
            },
            body: JSON.stringify({
                email: formData.email,
                password: formData.password,
                nome: formData.nome,
                cognome: formData.cognome,
                ruolo: formData.ruolo,
                motivazione: formData.motivazione,
                anno: parseInt(formData.anno),
                sezione: formData.sezione
            })
        });
        
        // 3. Handle response
        if (registerRes.status === 429) {
            return { success: false, message: 'Troppi registri. Riprova dopo.' };
        } else if (!registerRes.ok) {
            const data = await registerRes.json();
            return { success: false, message: data.message };
        } else {
            const data = await registerRes.json();
            return { success: true, message: data.message };
        }
    } catch (error) {
        return { success: false, message: 'Errore rete: ' + error.message };
    }
}
```

### Upload Document

```javascript
async function uploadDocument(file, title) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('title', title);
        formData.append('email', localStorage.getItem('email'));
        
        const response = await fetch('/api/create_publication', {
            method: 'POST',
            credentials: 'include',
            body: formData  // FormData auto-set Content-Type
        });
        
        if (response.status === 429) {
            alert('Troppi upload. Riprova dopo.');
            return false;
        }
        
        if (!response.ok) {
            const data = await response.json();
            alert(data.message);
            return false;
        }
        
        alert('Documento caricato con successo!');
        return true;
        
    } catch (error) {
        alert('Errore upload: ' + error.message);
        return false;
    }
}
```

---

## 🧪 **Testing da Browser Console**

### Test CSRF

```javascript
// 1. Prendi token
const token = await fetch('/csrf-token').then(r => r.json()).then(d => d.csrf_token);

// 2. Prova login
fetch('/login', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': token
    },
    body: JSON.stringify({
        email: 'test@test.com',
        password: 'test123'
    })
}).then(r => r.json()).then(console.log);
```

### Test Rate Limiting

```javascript
// Rapid-fire 6 requests
for (let i = 0; i < 6; i++) {
    fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@test.com', password: 'test' })
    }).then(r => console.log(`Request ${i}: ${r.status}`));
}
// Ultimo avrà 429 Too Many Requests
```

---

## 📚 **Risorse Esterne**

- [MDN: Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [OWASP: CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Content-Type Header](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type)
- [HTTP Status Codes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)

---

**Versione**: 1.0  
**Data**: 2025-11-30  
**Autore**: Frontend Security Team
