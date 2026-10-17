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
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.themeValue === theme),
    );
  });
  const activeTheme =
    theme === "system" && systemTheme.matches ? "dark" : theme;
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

const CSRF_RENEWAL_MARGIN_MS = 5 * 60 * 1000;
let loginCsrfRenewal;

async function renewLoginCsrf(form, force = false) {
  const expiresAt = Date.parse(form.dataset.csrfExpiresAt || "");
  if (
    !force &&
    Number.isFinite(expiresAt) &&
    expiresAt - Date.now() > CSRF_RENEWAL_MARGIN_MS
  ) {
    return true;
  }
  if (!loginCsrfRenewal) {
    loginCsrfRenewal = fetch("/login/csrf", {
      credentials: "same-origin",
      cache: "no-store",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (response.status === 409) {
          window.location.assign(form.elements.next.value || "/");
          return false;
        }
        if (!response.ok) throw new Error("csrf-renewal-failed");
        const payload = await response.json();
        form.elements.csrf_token.value = payload.csrf_token;
        form.dataset.csrfExpiresAt = payload.expires_at;
        return true;
      })
      .finally(() => {
        loginCsrfRenewal = undefined;
      });
  }
  return loginCsrfRenewal;
}

function showLoginRenewalError(form) {
  const alert = document.querySelector("[data-login-error]");
  if (alert) {
    alert.textContent =
      "Impossible de sécuriser la connexion. Vérifiez votre réseau puis réessayez ; vos champs ont été conservés.";
    alert.hidden = false;
  }
  const button = form.querySelector("button[type='submit']");
  if (button) button.disabled = false;
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-login-form]");
  if (!form) return;
  const submitButton = form.querySelector("button[type='submit']");
  let loginSubmissionInProgress = false;

  form.addEventListener("submit", async (event) => {
    if (form.dataset.csrfReady === "true") {
      delete form.dataset.csrfReady;
      return;
    }
    event.preventDefault();
    if (loginSubmissionInProgress) return;

    loginSubmissionInProgress = true;
    if (submitButton) submitButton.disabled = true;
    try {
      if (await renewLoginCsrf(form, true)) {
        form.dataset.csrfReady = "true";
        form.requestSubmit(event.submitter || undefined);
      }
    } catch {
      loginSubmissionInProgress = false;
      showLoginRenewalError(form);
    }
  });

  const renewIfNeeded = () =>
    renewLoginCsrf(form).catch(() => showLoginRenewalError(form));
  window.addEventListener("pageshow", renewIfNeeded);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") renewIfNeeded();
  });
});
