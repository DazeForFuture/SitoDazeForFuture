// userbar.js

/**
 * Gestione della Userbar - Mostra informazioni utente e badge ruolo
 */

// Funzione per ottenere il nome utente dal localStorage
function getUserName() {
    // Cerca il nome in diverse chiavi per compatibilità
    return localStorage.getItem('userName') || 
           localStorage.getItem('utente_nome') || 
           localStorage.getItem('nome_utente') || 
           'Utente';
}

// Funzione per generare l'iniziale dal nome
function getInitialFromName(name) {
    return name.charAt(0).toUpperCase();
}

// Funzione per ottenere il ruolo dell'utente
function getUserRole() {
    return localStorage.getItem('utente_ruolo') || 
           localStorage.getItem('userRole') || 
           'user';
}

// Funzione per ottenere il testo del badge in base al ruolo
function getBadgeText(role) {
    const roleMap = {
        'admin': 'Admin',
        'moderator': 'Mod',
        'user': 'User'
    };
    return roleMap[role] || 'User';
}

// Funzione per ottenere la classe CSS del badge in base al ruolo
function getBadgeClass(role) {
    const classMap = {
        'admin': 'badge-admin',
        'moderator': 'badge-moderator',
        'user': 'badge-user'
    };
    return classMap[role] || 'badge-user';
}

// Funzione principale per mostrare/nascondere la userbar
function toggleUserbar() {
    const utente = localStorage.getItem('utente');
    const userName = getUserName();
    const ruolo = getUserRole();
    
    console.log('Toggle Userbar - Nome:', userName, 'Ruolo:', ruolo); // Debug
    
    const userbar = document.getElementById('userbar');
    const loginLink = document.getElementById('loginLink');
    const sidebarLoginLink = document.getElementById('sidebarLoginLink');
    const mobileUserInfo = document.getElementById('mobileUserInfo');

    if (utente && userbar) {
        // Utente loggato - Nascondi link login e mostra userbar
        if (loginLink) loginLink.style.display = 'none';
        if (sidebarLoginLink) sidebarLoginLink.style.display = 'none';
        
        // Mostra userbar desktop
        userbar.style.display = 'flex';
        
        // Aggiorna contenuti userbar desktop
        updateUserbarElements(
            userName,
            ruolo,
            'userName',
            'userBadge',
            'userAvatar'
        );
        
        // Mostra e aggiorna user info mobile
        if (mobileUserInfo) {
            mobileUserInfo.style.display = 'block';
            updateUserbarElements(
                userName,
                ruolo,
                'mobileUserName',
                'mobileUserBadge',
                'mobileUserAvatar'
            );
        }
    } else {
        // Utente non loggato - Nascondi userbar e mostra link login
        if (userbar) userbar.style.display = 'none';
        if (mobileUserInfo) mobileUserInfo.style.display = 'none';
        if (loginLink) loginLink.style.display = 'block';
        if (sidebarLoginLink) sidebarLoginLink.style.display = 'block';
    }
}

// Funzione helper per aggiornare gli elementi della userbar
function updateUserbarElements(userName, ruolo, nameId, badgeId, avatarId) {
    const nameElement = document.getElementById(nameId);
    const badgeElement = document.getElementById(badgeId);
    const avatarElement = document.getElementById(avatarId);
    
    if (nameElement) {
        nameElement.innerText = userName;
        console.log('Aggiornato elemento', nameId, 'con:', userName); // Debug
    }
    if (badgeElement) {
        badgeElement.innerText = getBadgeText(ruolo);
        badgeElement.className = `user-badge ${getBadgeClass(ruolo)}`;
        // Per mobile usa classe specifica
        if (badgeId === 'mobileUserBadge') {
            badgeElement.className = `mobile-user-badge ${getBadgeClass(ruolo)}`;
        }
    }
    if (avatarElement) avatarElement.innerText = getInitialFromName(userName);
}

// Funzione per il logout
function logout() {
    // Rimuovi tutti i dati utente dal localStorage
    const keysToRemove = [
        'utente',
        'utente_ruolo',
        'userName',
        'utente_nome',
        'nome_utente',
        'userRole'
    ];
    
    keysToRemove.forEach(key => localStorage.removeItem(key));
    
    // Aggiorna l'interfaccia
    toggleUserbar();
    
    // Reindirizza alla pagina di login
    window.location.href = "login.html";
}

// Funzione per aggiornare la userbar quando l'utente effettua il login
function updateUserbarOnLogin(userData) {
    // Salva i dati dell'utente nel localStorage
    if (userData.email) localStorage.setItem('utente', userData.email);
    if (userData.nome) {
        localStorage.setItem('userName', userData.nome);
        localStorage.setItem('utente_nome', userData.nome);
    }
    if (userData.ruolo) {
        localStorage.setItem('utente_ruolo', userData.ruolo);
        localStorage.setItem('userRole', userData.ruolo);
    }
    
    console.log('Dati salvati nel localStorage:', userData); // Debug
    
    // Aggiorna la userbar
    toggleUserbar();
}

// Funzione per verificare se l'utente è loggato
function isUserLoggedIn() {
    return !!localStorage.getItem('utente');
}

// Funzione per ottenere i dati dell'utente corrente
function getCurrentUser() {
    return {
        email: localStorage.getItem('utente'),
        nome: getUserName(),
        ruolo: getUserRole()
    };
}

  function getUserName() {
    const nome = localStorage.getItem('userName') || 
                 localStorage.getItem('utente_nome') || 
                 localStorage.getItem('nome_utente');
    
    if (nome && nome !== 'Utente') {
        return nome;
    }
    
    // Se non c'è un nome specifico, usa l'email o un default
    const email = localStorage.getItem('utente');
    if (email) {
        return email.split('@')[0]; // Prende la parte prima della @
    }
    
    return 'Utente';
}
// Inizializzazione
document.addEventListener('DOMContentLoaded', function() {
    toggleUserbar();
    
    // Ascolta cambiamenti nel localStorage (utile per più tab)
    window.addEventListener('storage', function(e) {
        if (e.key === 'utente' || e.key === 'userName' || e.key === 'utente_ruolo') {
            toggleUserbar();
        }
    });
});


// Esponi le funzioni globalmente per l'uso in altri script
window.userbar = {
    toggleUserbar,
    logout,
    updateUserbarOnLogin,
    isUserLoggedIn,
    getCurrentUser
};