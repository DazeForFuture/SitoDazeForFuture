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
      !sidebarToggle.contains(e.target)
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
});

// Funzione per gestire il login/logout dell'utente
function updateUserInterface() {
  const utente = localStorage.getItem('utente');
  const ruolo = localStorage.getItem('utente_ruolo') || 'user';
  
  if(utente) {
    // Nascondi link login
    document.getElementById('loginLink').style.display = 'none';
    document.getElementById('sidebarLoginLink').style.display = 'none';
    
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
    document.getElementById('loginLink').style.display = 'block';
    document.getElementById('sidebarLoginLink').style.display = 'block';
    
    const userbar = document.getElementById('userbar');
    if (userbar) userbar.style.display = 'none';
    
    const mobileUserInfo = document.getElementById('mobileUserInfo');
    if (mobileUserInfo) mobileUserInfo.style.display = 'none';
  }
}

// Esegui l'aggiornamento dell'interfaccia utente al caricamento
document.addEventListener('DOMContentLoaded', updateUserInterface);