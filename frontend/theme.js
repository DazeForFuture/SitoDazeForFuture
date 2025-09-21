function applyTheme(theme) {
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  } else if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme'); // qui si applica prefers-color-scheme
  }
}

const savedTheme = localStorage.getItem('theme-preference');
if (savedTheme) {
  applyTheme(savedTheme);
}
