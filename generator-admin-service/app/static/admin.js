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
  row.append(activityCell(job.llm_model || "Modèle historique inconnu"));
  row.append(activityCell(job.created_at));
  row.append(activityCell(job.started_at));
  row.append(
    activityCell(
      job.cancelled_at
        ? `Annulée le ${job.cancelled_at}`
        : job.completed_at
          ? `Terminée le ${job.completed_at}`
          : null,
    ),
  );
  row.append(
    activityCell(
      Number.isFinite(job.duration_seconds)
        ? `${job.duration_seconds.toFixed(1)} s`
        : null,
    ),
  );

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

document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-models-root]");
  if (!root) return;
  const primaryRoot = root.querySelector("[data-primary-model]");
  const otherRoot = root.querySelector("[data-other-models]");
  const empty = root.querySelector("[data-models-empty]");
  const errorBox = document.querySelector("[data-models-error]");
  const refreshState = document.querySelector("[data-models-refresh]");
  let timer;
  let inFlight = false;
  let stopped = false;

  function clearScheduledRefresh() {
    if (timer) window.clearTimeout(timer);
    timer = undefined;
  }

  function scheduleRefresh(delay) {
    clearScheduledRefresh();
    if (!stopped && document.visibilityState === "visible") {
      timer = window.setTimeout(refresh, delay);
    }
  }

  function actionForm(action, model, label, className) {
    const form = document.createElement("form");
    form.method = "post";
    form.action = `/llm-models/${action}`;
    form.dataset.modelAction = "";
    for (const [name, value] of Object.entries({
      csrf_token: root.dataset.csrfToken,
      model,
    })) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      form.append(input);
    }
    const button = document.createElement("button");
    button.type = "submit";
    button.className = `button ${className} compact`;
    button.textContent = label;
    form.append(button);
    return form;
  }

  function modelFacts(model) {
    const facts = document.createElement("dl");
    facts.className = "model-facts";
    for (const [term, value] of [
      ["Quantification", model.quantization || "Non renseignée"],
      ["SSD", model.size_label],
      ["VRAM estimée (indicative)", model.vram_estimate_label],
    ]) {
      const item = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = term;
      dd.textContent = value;
      item.append(dt, dd);
      facts.append(item);
    }
    return facts;
  }

  function modelCard(model, primary = false) {
    const card = document.createElement("article");
    card.className = `model-card${primary ? " model-card-primary" : ""}`;
    const heading = document.createElement("div");
    heading.className = "model-card-heading";
    const identity = document.createElement("div");
    const name = document.createElement("h3");
    const reference = document.createElement("code");
    name.textContent = model.name;
    reference.textContent = model.id;
    reference.title = model.id;
    identity.append(name, reference);
    const badge = document.createElement("span");
    badge.className = `badge status-${model.status}`;
    badge.textContent = model.status_label;
    heading.append(identity, badge);
    card.append(heading, modelFacts(model));

    if (["downloading", "incomplete"].includes(model.status)) {
      const download = document.createElement("div");
      download.className = "download-progress";
      const progress = document.createElement("progress");
      const label = document.createElement("span");
      if (model.progress_total) {
        progress.max = model.progress_total;
        progress.value = model.progress_done || 0;
        label.textContent = `${model.progress_percentage} % · ${model.progress_done_label} / ${model.progress_total_label}`;
      } else {
        label.textContent = "Volume total inconnu";
      }
      download.append(progress, label);
      card.append(download);
    }
    const footer = document.createElement("div");
    footer.className = "model-card-footer";
    const description = document.createElement("p");
    description.textContent = primary && model.loaded
      ? "Prêt pour la génération."
      : primary && model.status === "unloaded"
        ? "Il sera rechargé automatiquement à la prochaine génération."
        : model.status_label;
    const actions = document.createElement("div");
    actions.className = "model-actions";
    if (primary && ["loaded", "sleeping"].includes(model.status)) {
      actions.append(actionForm("unload", model.id, "Décharger de la VRAM", "secondary"));
    } else if (primary && model.status === "unloaded") {
      actions.append(actionForm("activate", model.id, "Charger en VRAM", "primary"));
    } else if (!primary && model.status === "unloaded") {
      actions.append(actionForm("activate", model.id, "Utiliser", "primary"));
    } else if (!primary && model.status === "incomplete") {
      actions.append(actionForm("download", model.id, "Reprendre", "secondary"));
    }
    footer.append(description, actions);
    card.append(footer);
    return card;
  }

  function render(payload) {
    const primary = payload.models.find((model) => model.selected);
    primaryRoot.replaceChildren();
    if (primary) primaryRoot.append(modelCard(primary, true));
    else {
      const missing = document.createElement("div");
      missing.className = "empty compact-empty";
      missing.textContent = `Le modèle sélectionné ${payload.selected_model} n’est pas visible dans le cache.`;
      primaryRoot.append(missing);
    }
    const others = payload.models.filter((model) => !model.selected);
    otherRoot.replaceChildren(...others.map((model) => modelCard(model)));
    empty.hidden = others.length !== 0;
    const busy = payload.models.some((model) =>
      ["downloading", "loading"].includes(model.status),
    );
    scheduleRefresh(busy ? 3000 : 30000);
  }

  async function refresh() {
    clearScheduledRefresh();
    if (stopped || inFlight || document.visibilityState !== "visible") return;
    inFlight = true;
    root.setAttribute("aria-busy", "true");
    try {
      const response = await fetch("/llm-models/data", {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (response.status === 401) {
        stopped = true;
        window.location.assign("/login?next=%2Fllm-models&expired=1");
        return;
      }
      if (!response.ok) throw new Error("models-refresh-failed");
      render(await response.json());
      errorBox.hidden = true;
      refreshState.textContent = "État actualisé.";
    } catch {
      errorBox.textContent = "Serveur LLM indisponible — nouvelle tentative automatique.";
      errorBox.hidden = false;
      scheduleRefresh(10000);
    } finally {
      inFlight = false;
      root.setAttribute("aria-busy", "false");
    }
  }
  root.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-model-action]");
    if (!form || form.dataset.submitted === "true") {
      if (form) event.preventDefault();
      return;
    }
    form.dataset.submitted = "true";
    form.querySelector("button").disabled = true;
  });
  document.addEventListener("visibilitychange", () => {
    clearScheduledRefresh();
    if (document.visibilityState === "visible") refresh();
  });
  window.addEventListener("pagehide", () => {
    stopped = true;
    clearScheduledRefresh();
  });
  scheduleRefresh(5000);
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
