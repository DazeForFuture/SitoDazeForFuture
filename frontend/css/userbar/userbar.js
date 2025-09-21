// Funzione per generare l'iniziale dall'email
function getInitialFromEmail(email) {
  return email.charAt(0).toUpperCase();
}

// Funzione per mostrare/nascondere la userbar in base allo stato di login
function toggleUserbar() {
  const utente = localStorage.getItem('utente');
  const loginLink = document.getElementById('loginLink');
  const sidebarLoginLink = document.getElementById('sidebarLoginLink');
  const userbar = document.getElementById('userbar');
  const mobileUserInfo = document.getElementById('mobileUserInfo');
  
  if(utente) {
    // Nascondi link login
    if (loginLink) loginLink.style.display = 'none';
    if (sidebarLoginLink) sidebarLoginLink.style.display = 'none';
    
    // Mostra userbar al posto di "Accedi"
    if (userbar) {
      userbar.style.display = 'flex';
      document.getElementById('useremail').innerText = utente;
      document.getElementById('userAvatar').innerText = getInitialFromEmail(utente);
    }
    
    // Mostra user info mobile nella sidebar
    if (mobileUserInfo) {
      mobileUserInfo.style.display = 'block';
      document.getElementById('mobileUseremail').innerText = utente;
      document.getElementById('mobileUserAvatar').innerText = getInitialFromEmail(utente);
    }
  } else {
    // Nascondi userbar se non loggato
    if (userbar) userbar.style.display = 'none';
    if (mobileUserInfo) mobileUserInfo.style.display = 'none';
    
    // Mostra link login
    if (loginLink) loginLink.style.display = 'block';
    if (sidebarLoginLink) sidebarLoginLink.style.display = 'block';
  }
}

// Funzione per il logout
function logout() {
  localStorage.removeItem('utente');
  toggleUserbar(); // Aggiorna l'interfaccia
  window.location.href = "login.html";
}

// Inizializza la userbar al caricamento della pagina
document.addEventListener('DOMContentLoaded', function() {
  toggleUserbar();
  
  // Aggiungi listener per cambiamenti nello storage (utile per più tab)
  window.addEventListener('storage', function(e) {
    if (e.key === 'utente') {
      toggleUserbar();
    }
  });
});