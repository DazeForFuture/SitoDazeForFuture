document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector(".sidebar");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const sidebarClose = document.querySelector(".sidebar-close");

  // Apri sidebar
  sidebarToggle?.addEventListener("click", () => {
    sidebar.classList.add("active");
  });

  // Chiudi sidebar
  sidebarClose?.addEventListener("click", () => {
    sidebar.classList.remove("active");
  });

  // Chiudi se clicchi fuori
  document.addEventListener("click", (e) => {
    if (
      sidebar.classList.contains("active") &&
      !sidebar.contains(e.target) &&
      !sidebarToggle.contains(e.target)
    ) {
      sidebar.classList.remove("active");
    }
  });

  // Evidenzia il link attivo
  const currentPage = location.pathname.split("/").pop();
  document.querySelectorAll(".sidebar-menu a").forEach(link => {
    if (link.getAttribute("href") === currentPage) {
      link.classList.add("active");
    }
  });
});
