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

function activityCell(value, className) {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  cell.textContent = value || "—";
  return cell;
}

function activityRow(job) {
  const row = document.createElement("tr");
  const owner = document.createElement("td");
  const ownerName = document.createElement("strong");
  ownerName.textContent = job.owner_name || "Propriétaire inconnu";
  owner.append(ownerName);
  if (job.owner_active === false) {
    const note = document.createElement("small");
    note.className = "table-note";
    note.textContent = "Désactivé";
    owner.append(note);
  }
  row.append(owner);
  row.append(activityCell(job.document_type_label));
  row.append(activityCell(job.avp_number));
  row.append(activityCell(job.candidate_name));

  const status = document.createElement("td");
  const badge = document.createElement("span");
  badge.className = `badge status-${job.status}`;
  badge.textContent = job.status_label;
  status.append(badge);
  row.append(status);
  row.append(activityCell(job.created_at));
  row.append(activityCell(job.started_at));
  row.append(activityCell(job.completed_at));

  const identifier = document.createElement("td");
  const details = document.createElement("details");
  details.className = "job-id";
  const summary = document.createElement("summary");
  const shortCode = document.createElement("code");
  shortCode.textContent = `${job.id.slice(0, 12)}…`;
  summary.append(shortCode);
  const fullCode = document.createElement("code");
  fullCode.textContent = job.id;
  details.append(summary, fullCode);
  identifier.append(details);
  row.append(identifier);
  return row;
}

function replaceActivityRows(selector, emptySelector, jobs) {
  const body = document.querySelector(selector);
  const empty = document.querySelector(emptySelector);
  if (!body || !empty) return;
  const focusedElement = document.activeElement;
  const isBeingUsed =
    (focusedElement && body.contains(focusedElement)) ||
    body.querySelector("details[open]");
  if (isBeingUsed) return;
  body.replaceChildren(...jobs.map(activityRow));
  empty.hidden = jobs.length !== 0;
}

function activityPageUrl(page) {
  const parameters = new URLSearchParams(window.location.search);
  parameters.set("page", String(page));
  return `/activity?${parameters.toString()}`;
}

function updateActivity(payload) {
  Object.entries(payload.counters).forEach(([name, value]) => {
    const counter = document.querySelector(`[data-counter="${name}"]`);
    if (counter) counter.textContent = String(value);
  });
  replaceActivityRows(
    "[data-activity-recent]",
    "[data-activity-recent-empty]",
    payload.recent,
  );
  replaceActivityRows(
    "[data-activity-history]",
    "[data-activity-history-empty]",
    payload.history,
  );
  const total = document.querySelector("[data-history-total]");
  const currentPage = document.querySelector("[data-page-current]");
  const pageCount = document.querySelector("[data-page-count]");
  const previous = document.querySelector("[data-page-previous]");
  const next = document.querySelector("[data-page-next]");
  const refreshed = document.querySelector("[data-activity-refreshed]");
  if (total) total.textContent = String(payload.pagination.total);
  if (currentPage) currentPage.textContent = String(payload.pagination.page);
  if (pageCount) pageCount.textContent = String(payload.pagination.page_count);
  if (refreshed) refreshed.textContent = payload.refreshed_at;
  if (previous) {
    previous.hidden = payload.pagination.page <= 1;
    previous.href = activityPageUrl(payload.pagination.page - 1);
  }
  if (next) {
    next.hidden = payload.pagination.page >= payload.pagination.page_count;
    next.href = activityPageUrl(payload.pagination.page + 1);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-activity-root]");
  if (!root) return;
  const errorMessage = document.querySelector("[data-activity-error]");
  let timer;
  let controller;
  let inFlight = false;
  let stopped = false;

  const clearScheduledRefresh = () => {
    if (timer) window.clearTimeout(timer);
    timer = undefined;
  };

  const scheduleRefresh = () => {
    clearScheduledRefresh();
    if (!stopped && document.visibilityState === "visible") {
      timer = window.setTimeout(refresh, 5000);
    }
  };

  async function refresh() {
    clearScheduledRefresh();
    if (stopped || document.visibilityState !== "visible" || inFlight) return;
    inFlight = true;
    controller = new AbortController();
    root.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(`/activity/data${window.location.search}`, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (response.status === 401) {
        const destination = `${window.location.pathname}${window.location.search}`;
        window.location.assign(
          `/login?next=${encodeURIComponent(destination)}&expired=1`,
        );
        stopped = true;
        return;
      }
      if (!response.ok) throw new Error("activity-refresh-failed");
      updateActivity(await response.json());
      if (errorMessage) errorMessage.hidden = true;
    } catch (error) {
      if (error.name !== "AbortError" && errorMessage) {
        errorMessage.hidden = false;
      }
    } finally {
      inFlight = false;
      controller = undefined;
      root.setAttribute("aria-busy", "false");
      scheduleRefresh();
    }
  }

  document.addEventListener("visibilitychange", () => {
    clearScheduledRefresh();
    if (document.visibilityState === "visible") refresh();
  });
  window.addEventListener("pagehide", () => {
    stopped = true;
    clearScheduledRefresh();
    if (controller) controller.abort();
  });
  scheduleRefresh();
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
