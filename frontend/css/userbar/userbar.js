// Funzione per generare l'iniziale dall'email
function getInitialFromEmail(email) {
  return email.charAt(0).toUpperCase();
}

// Funzione per mostrare/nascondere la userbar in base allo stato di login
function toggleUserbar() {
  const utente = localStorage.getItem('utente');
  const ruolo = localStorage.getItem('utente_ruolo');
  const userbar = document.getElementById('userbar');
  const useremail = document.getElementById('useremail');
  const userAvatar = document.getElementById('userAvatar');

  let userLabel = utente || '';
  if (ruolo === 'admin') {
    userLabel += ' (admin)';
  }

  if (utente && userbar && useremail && userAvatar) {
    useremail.innerText = userLabel;
    userAvatar.innerText = getInitialFromEmail(utente);
    userbar.style.display = 'flex';
  } else if (userbar) {
    userbar.style.display = 'none';
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