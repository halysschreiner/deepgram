// Runs before the stylesheet so saved preferences apply before the first paint.
(() => {
  const storageKey = 'transcritor.appearance';
  const themes = ['light', 'dark', 'system'];
  const accents = { blue: 'Azul', purple: 'Roxo', pink: 'Rosa', red: 'Vermelho', orange: 'Laranja', yellow: 'Amarelo', green: 'Verde', graphite: 'Grafite' };
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let theme = 'system', accent = 'green', storageAvailable = true;

  function readPreferences(value) {
    let saved;
    try { saved = JSON.parse(value); } catch { /* Ignore invalid saved preferences. */ }
    theme = themes.includes(saved?.theme) ? saved.theme : 'system';
    accent = Object.hasOwn(accents, saved?.accent) ? saved.accent : 'green';
  }

  try { readPreferences(localStorage.getItem(storageKey)); }
  catch { storageAvailable = false; }

  function apply() {
    document.documentElement.dataset.theme = theme === 'system' ? (system.matches ? 'dark' : 'light') : theme;
    document.documentElement.dataset.accent = accent;
  }

  apply();
  system.addEventListener('change', apply);

  document.addEventListener('DOMContentLoaded', () => {
    const menu = document.getElementById('appearance');
    const trigger = menu.querySelector('summary');

    function syncControls() {
      menu.querySelector(`input[name="theme"][value="${theme}"]`).checked = true;
      menu.querySelector(`input[name="accent"][value="${accent}"]`).checked = true;
      document.getElementById('accent-name').textContent = accents[accent];
      document.getElementById('appearance-storage').textContent = storageAvailable
        ? 'Preferências salvas neste navegador.'
        : 'Preferências válidas nesta aba; o navegador bloqueou o salvamento.';
    }

    syncControls();
    menu.addEventListener('change', event => {
      const { name, value } = event.target;
      if (name === 'theme' && themes.includes(value)) theme = value;
      else if (name === 'accent' && Object.hasOwn(accents, value)) accent = value;
      else return;
      apply();
      try {
        localStorage.setItem(storageKey, JSON.stringify({ theme, accent }));
        storageAvailable = true;
      } catch { storageAvailable = false; }
      syncControls();
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open) {
        menu.open = false;
        trigger.focus();
      }
    });
    document.addEventListener('click', event => {
      if (!menu.contains(event.target)) menu.open = false;
    });
    menu.addEventListener('focusout', event => {
      if (event.relatedTarget && !menu.contains(event.relatedTarget)) menu.open = false;
    });
    window.addEventListener('storage', event => {
      if (event.key === storageKey || event.key === null) {
        readPreferences(event.newValue);
        apply();
        syncControls();
      }
    });
  });
})();
