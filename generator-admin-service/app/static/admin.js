const THEME_STORAGE_KEY = "cv-generator.theme";
const THEMES = new Set(["light", "dark", "system"]);
const THEME_COLORS = { light: "#f7f9fc", dark: "#111827" };
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");

function storedTheme() {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return THEMES.has(value) ? value : "system";
  } catch {
    return "system";
  }
}

function applyTheme(theme) {
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.dataset.theme = theme;
  }
  document.querySelectorAll("[data-theme-value]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeValue === theme));
  });
  const activeTheme = theme === "system" && systemTheme.matches ? "dark" : theme;
  const themeColor = document.querySelector("meta[data-theme-color]");
  if (themeColor) {
    themeColor.setAttribute(
      "content",
      THEME_COLORS[activeTheme === "system" ? "light" : activeTheme],
    );
  }
}

applyTheme(storedTheme());
systemTheme.addEventListener("change", () => {
  if (storedTheme() === "system") applyTheme("system");
});

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(storedTheme());

  document.querySelectorAll("[data-theme-value]").forEach((button) => {
    button.addEventListener("click", () => {
      const theme = button.dataset.themeValue;
      if (!THEMES.has(theme)) return;
      applyTheme(theme);
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, theme);
      } catch {
        // Le choix reste appliqué jusqu'à la fin de cette navigation.
      }
    });
  });
});

document.addEventListener("click", async (event) => {
  const toggle = event.target.closest("[data-toggle-secret]");
  if (toggle) {
    const input = document.getElementById(toggle.dataset.toggleSecret);
    input.type = input.type === "password" ? "text" : "password";
    toggle.textContent = input.type === "password" ? "Afficher" : "Masquer";
  }
  const copy = event.target.closest("[data-copy-secret]");
  if (copy) {
    const input = document.getElementById(copy.dataset.copySecret);
    await navigator.clipboard.writeText(input.value);
    copy.textContent = "Clé copiée";
  }
});

document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
    return;
  }
  if (event.target.hasAttribute("data-single-submit")) {
    const button = event.target.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "Création…";
  }
});
