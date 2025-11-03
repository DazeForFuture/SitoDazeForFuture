// Funzioni di utilità per la gestione utente
function getNameFromEmail(email) {
  if (!email) return 'Utente';
  return email.split('@')[0].charAt(0).toUpperCase() + email.split('@')[0].slice(1);
}

function getInitialFromEmail(email) {
  if (!email) return 'U';
  return email.charAt(0).toUpperCase();
}

function getBadgeText(ruolo) {
  const badges = {
    'admin': 'ADMIN',
    'user': 'USER',
    'moderator': 'MOD',
    'premium': 'PREMIUM'
  };
  return badges[ruolo] || 'USER';
}

function getBadgeClass(ruolo) {
  const classes = {
    'admin': 'badge-admin',
    'user': 'badge-user',
    'moderator': 'badge-admin',
    'premium': 'badge-premium'
  };
  return classes[ruolo] || 'badge-user';
}

// Funzione per gestire il login/logout dell'utente
function updateUserInterface() {
  const utente = localStorage.getItem('utente');
  const ruolo = localStorage.getItem('utente_ruolo') || 'user';
  
  if(utente) {
    // Nascondi link login
    const loginLink = document.getElementById('loginLink');
    const sidebarLoginLink = document.getElementById('sidebarLoginLink');
    
    if (loginLink) loginLink.style.display = 'none';
    if (sidebarLoginLink) sidebarLoginLink.style.display = 'none';
    
    // Mostra userbar
    const userbar = document.getElementById('userbar');
    if (userbar) userbar.style.display = 'flex';
    
    // Aggiorna userbar desktop
    const userName = document.getElementById('userName');
    const userBadge = document.getElementById('userBadge');
    const userAvatar = document.getElementById('userAvatar');
    
    if (userName) userName.innerText = getNameFromEmail(utente);
    if (userBadge) {
      userBadge.innerText = getBadgeText(ruolo);
      userBadge.className = `user-badge ${getBadgeClass(ruolo)}`;
    }
    if (userAvatar) userAvatar.innerText = getInitialFromEmail(utente);
    
    // Aggiorna sezione utente mobile nella sidebar
    const mobileUserInfo = document.getElementById('mobileUserInfo');
    if (mobileUserInfo) {
      mobileUserInfo.style.display = 'block';
      
      const mobileUserName = document.getElementById('mobileUserName');
      const mobileUserBadge = document.getElementById('mobileUserBadge');
      const mobileUserAvatar = document.getElementById('mobileUserAvatar');
      
      if (mobileUserName) mobileUserName.innerText = getNameFromEmail(utente);
      if (mobileUserBadge) {
        mobileUserBadge.innerText = getBadgeText(ruolo);
        mobileUserBadge.className = `mobile-user-badge ${getBadgeClass(ruolo)}`;
      }
      if (mobileUserAvatar) mobileUserAvatar.innerText = getInitialFromEmail(utente);
    }
  } else {
    // Mostra link login e nascondi userbar
    const loginLink = document.getElementById('loginLink');
    const sidebarLoginLink = document.getElementById('sidebarLoginLink');
    
    if (loginLink) loginLink.style.display = 'block';
    if (sidebarLoginLink) sidebarLoginLink.style.display = 'block';
    
    const userbar = document.getElementById('userbar');
    if (userbar) userbar.style.display = 'none';
    
    const mobileUserInfo = document.getElementById('mobileUserInfo');
    if (mobileUserInfo) mobileUserInfo.style.display = 'none';
  }
}

// Funzione per il logout
function handleLogout() {
  localStorage.removeItem('utente');
  localStorage.removeItem('utente_ruolo');
  updateUserInterface();
  
  // Reindirizza alla homepage se non ci siamo già
  if (window.location.pathname !== '/' && !window.location.pathname.includes('index.html')) {
    window.location.href = 'index.html';
  }
}

// Inizializzazione della sidebar
document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector(".sidebar");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebarClose = document.querySelector(".sidebar-close");

  // Apri sidebar con animazione
  sidebarToggle?.addEventListener("click", (e) => {
    e.stopPropagation();
    sidebar.classList.add("active");
    document.body.style.overflow = "hidden"; // Previene lo scroll del body
  });

  // Chiudi sidebar
  sidebarClose?.addEventListener("click", () => {
    sidebar.classList.remove("active");
    document.body.style.overflow = ""; // Riabilita lo scroll
  });

  // Chiudi se clicchi fuori
  document.addEventListener("click", (e) => {
    if (
      sidebar.classList.contains("active") &&
      !sidebar.contains(e.target) &&
      (!sidebarToggle || !sidebarToggle.contains(e.target))
    ) {
      sidebar.classList.remove("active");
      document.body.style.overflow = "";
    }
  });

  // Chiudi con ESC
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && sidebar.classList.contains("active")) {
      sidebar.classList.remove("active");
      document.body.style.overflow = "";
    }
  });

  // Evidenzia il link attivo nella sidebar
  const currentPage = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".sidebar-menu a").forEach(link => {
    const linkHref = link.getAttribute("href");
    if (linkHref === currentPage || 
        (currentPage === "" && linkHref === "index.html") ||
        (currentPage === "/" && linkHref === "index.html")) {
      link.classList.add("active");
    }
  });

  // Chiudi sidebar dopo il click su un link (per mobile)
  document.querySelectorAll(".sidebar-menu a").forEach(link => {
    link.addEventListener("click", () => {
      sidebar.classList.remove("active");
      document.body.style.overflow = "";
    });
  });

  // Gestione dropdown nella sidebar
  const dropdownToggles = document.querySelectorAll('.sidebar-dropdown-toggle');
  
  dropdownToggles.forEach(toggle => {
    toggle.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      const dropdown = this.closest('.sidebar-dropdown');
      const menu = dropdown.querySelector('.sidebar-dropdown-menu');
      
      // Chiudi altri dropdown aperti
      dropdownToggles.forEach(otherToggle => {
        if (otherToggle !== this) {
          const otherDropdown = otherToggle.closest('.sidebar-dropdown');
          const otherMenu = otherDropdown.querySelector('.sidebar-dropdown-menu');
          otherMenu.classList.remove('active');
          otherToggle.classList.remove('active');
        }
      });
      
      // Apri/chiudi dropdown corrente
      menu.classList.toggle('active');
      this.classList.toggle('active');
    });
  });
  
  // Chiudi dropdown quando si clicca fuori
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.sidebar-dropdown')) {
      dropdownToggles.forEach(toggle => {
        const dropdown = toggle.closest('.sidebar-dropdown');
        const menu = dropdown.querySelector('.sidebar-dropdown-menu');
        menu.classList.remove('active');
        toggle.classList.remove('active');
      });
    }
  });
  
  // Evidenzia link attivi nei dropdown
  document.querySelectorAll('.sidebar-dropdown-menu a').forEach(link => {
    const linkHref = link.getAttribute("href");
    if (linkHref === currentPage || 
        (currentPage === "" && linkHref === "index.html") ||
        (currentPage === "/" && linkHref === "index.html")) {
      link.classList.add("active");
      
      // Apri automaticamente il dropdown che contiene il link attivo
      const dropdown = link.closest('.sidebar-dropdown');
      if (dropdown) {
        const toggle = dropdown.querySelector('.sidebar-dropdown-toggle');
        const menu = dropdown.querySelector('.sidebar-dropdown-menu');
        menu.classList.add('active');
        toggle.classList.add('active');
      }
    }
  });

  // Gestione logout
  const logoutButtons = document.querySelectorAll('.logout-btn');
  logoutButtons.forEach(button => {
    button.addEventListener('click', handleLogout);
  });

  // Aggiorna l'interfaccia utente
  updateUserInterface();
});

// Espone le funzioni per l'uso globale
window.handleLogout = handleLogout;
window.updateUserInterface = updateUserInterface;