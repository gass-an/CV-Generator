import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const script = await readFile(
  new URL("../app/static/admin.js", import.meta.url),
  "utf8",
);

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function settle() {
  await new Promise((resolve) => setImmediate(resolve));
}

function createThemeHarness(storedTheme = "system") {
  const documentListeners = new Map();
  const storage = new Map([["cv-generator.theme", storedTheme]]);
  const buttons = ["light", "dark", "system"].map((themeValue) => ({
    attributes: {},
    dataset: { themeValue },
    listeners: new Map(),
    addEventListener(type, listener) {
      this.listeners.set(type, listener);
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  }));
  const themeColor = {
    attributes: {},
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
  const documentElement = {
    dataset: {},
    removeAttribute(name) {
      if (name === "data-theme") delete this.dataset.theme;
    },
  };
  const systemTheme = { matches: false, addEventListener() {} };
  const document = {
    documentElement,
    addEventListener(type, listener) {
      documentListeners.set(type, [
        ...(documentListeners.get(type) || []),
        listener,
      ]);
    },
    querySelector(selector) {
      return selector === "meta[data-theme-color]" ? themeColor : null;
    },
    querySelectorAll(selector) {
      return selector === "[data-theme-value]" ? buttons : [];
    },
  };
  const window = {
    document,
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
    },
    matchMedia: () => systemTheme,
    addEventListener() {},
    location: { assign() {} },
    confirm: () => true,
  };
  vm.runInContext(script, vm.createContext({ console, document, Set, window }), {
    filename: "admin.js",
  });
  documentListeners.get("DOMContentLoaded").forEach((listener) => listener());
  return { buttons, documentElement, storage, themeColor };
}

test("le sélecteur de thème applique et mémorise le choix accessible", () => {
  const harness = createThemeHarness("dark");
  const [light, dark] = harness.buttons;

  assert.equal(harness.documentElement.dataset.theme, "dark");
  assert.equal(dark.attributes["aria-pressed"], "true");
  assert.equal(harness.themeColor.attributes.content, "#111827");

  light.listeners.get("click")();
  assert.equal(harness.storage.get("cv-generator.theme"), "light");
  assert.equal(harness.documentElement.dataset.theme, "light");
  assert.equal(light.attributes["aria-pressed"], "true");
  assert.equal(dark.attributes["aria-pressed"], "false");
  assert.equal(harness.themeColor.attributes.content, "#f7f9fc");
});

function createHarness(fetchImplementation) {
  const documentListeners = new Map();
  const windowListeners = new Map();
  const formListeners = new Map();
  const button = { disabled: false };
  const alert = { hidden: true, textContent: "" };
  let nativeSubmissions = 0;

  const form = {
    dataset: { csrfExpiresAt: new Date(Date.now() + 3_600_000).toISOString() },
    elements: {
      csrf_token: { value: "csrf-initial" },
      next: { value: "/clients" },
      password: { value: "mot-de-passe-saisi" },
      username: { value: "administrateur" },
    },
    addEventListener(type, listener) {
      formListeners.set(type, listener);
    },
    querySelector(selector) {
      return selector === "button[type='submit']" ? button : null;
    },
    requestSubmit(submitter) {
      const event = {
        submitter,
        defaultPrevented: false,
        preventDefault() {
          this.defaultPrevented = true;
        },
      };
      formListeners.get("submit")(event);
      if (!event.defaultPrevented) nativeSubmissions += 1;
    },
  };

  const document = {
    documentElement: {
      dataset: {},
      removeAttribute() {},
    },
    visibilityState: "visible",
    addEventListener(type, listener) {
      documentListeners.set(type, [
        ...(documentListeners.get(type) || []),
        listener,
      ]);
    },
    querySelector(selector) {
      if (selector === "[data-login-form]") return form;
      if (selector === "[data-login-error]") return alert;
      return null;
    },
    querySelectorAll() {
      return [];
    },
  };

  const window = {
    document,
    localStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    addEventListener(type, listener) {
      windowListeners.set(type, [
        ...(windowListeners.get(type) || []),
        listener,
      ]);
    },
    location: { assign() {} },
    confirm: () => true,
  };

  const context = vm.createContext({
    console,
    Date,
    document,
    fetch: fetchImplementation,
    Promise,
    Set,
    window,
  });
  vm.runInContext(script, context, { filename: "admin.js" });
  documentListeners.get("DOMContentLoaded").forEach((listener) => listener());

  function submit() {
    const event = {
      submitter: button,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
    };
    formListeners.get("submit")(event);
    if (!event.defaultPrevented) nativeSubmissions += 1;
  }

  return {
    alert,
    button,
    form,
    nativeSubmissions: () => nativeSubmissions,
    submit,
  };
}

function successfulResponse(token = "csrf-renouvele") {
  return {
    ok: true,
    status: 200,
    async json() {
      return {
        csrf_token: token,
        expires_at: new Date(Date.now() + 3_600_000).toISOString(),
      };
    },
  };
}

test("un double clic pendant le renouvellement ne produit qu'une soumission", async () => {
  const renewal = deferred();
  let fetchCount = 0;
  const harness = createHarness(() => {
    fetchCount += 1;
    return renewal.promise;
  });

  harness.submit();
  harness.submit();
  assert.equal(fetchCount, 1);
  assert.equal(harness.button.disabled, true);

  renewal.resolve(successfulResponse());
  await settle();
  assert.equal(harness.nativeSubmissions(), 1);

  harness.submit();
  assert.equal(fetchCount, 1);
  assert.equal(harness.nativeSubmissions(), 1);
});

test("un renouvellement réussi met à jour le jeton avant la soumission native", async () => {
  const harness = createHarness(async () => successfulResponse("csrf-nouveau"));

  harness.submit();
  await settle();

  assert.equal(harness.form.elements.csrf_token.value, "csrf-nouveau");
  assert.equal(harness.nativeSubmissions(), 1);
});

test("un échec réseau réarme le formulaire pour une nouvelle tentative", async () => {
  let fetchCount = 0;
  const harness = createHarness(async () => {
    fetchCount += 1;
    if (fetchCount === 1) throw new Error("network unavailable");
    return successfulResponse("csrf-apres-reprise");
  });

  harness.submit();
  await settle();
  assert.equal(harness.nativeSubmissions(), 0);
  assert.equal(harness.button.disabled, false);
  assert.equal(harness.alert.hidden, false);
  assert.equal(harness.form.elements.csrf_token.value, "csrf-initial");
  assert.equal(harness.form.elements.username.value, "administrateur");
  assert.equal(harness.form.elements.password.value, "mot-de-passe-saisi");

  harness.submit();
  await settle();
  assert.equal(fetchCount, 2);
  assert.equal(harness.form.elements.csrf_token.value, "csrf-apres-reprise");
  assert.equal(harness.nativeSubmissions(), 1);
});

test("la soumission interne ne relance pas un renouvellement en boucle", async () => {
  let fetchCount = 0;
  const harness = createHarness(async () => {
    fetchCount += 1;
    return successfulResponse();
  });

  harness.submit();
  await settle();
  await settle();

  assert.equal(fetchCount, 1);
  assert.equal(harness.nativeSubmissions(), 1);
});

function activityPayload(pending = 2) {
  return {
    counters: {
      pending,
      processing: 1,
      completed_today: 3,
      failed_today: 1,
    },
    recent: [],
    history: [],
    pagination: { page: 1, page_count: 1, page_size: 25, total: 0 },
    refreshed_at: "17/10/2026 12:00",
  };
}

function createActivityHarness(fetchImplementation) {
  const documentListeners = new Map();
  const windowListeners = new Map();
  const timers = new Map();
  let timerId = 0;
  const redirects = [];
  const root = {
    attributes: {},
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
  const error = { hidden: true };
  const counter = { textContent: "0" };
  function activityBody() {
    return {
      hasOpenDetails: false,
      replacementCount: 0,
      contains(element) {
        return element?.activityBody === this;
      },
      querySelector(selector) {
        return selector === "details[open]" && this.hasOpenDetails ? {} : null;
      },
      replaceChildren() {
        this.replacementCount += 1;
      },
    };
  }
  const recentBody = activityBody();
  const historyBody = activityBody();
  const recentEmpty = { hidden: true };
  const historyEmpty = { hidden: true };
  const simpleElement = { hidden: false, textContent: "", href: "" };
  const selectors = new Map([
    ["[data-activity-root]", root],
    ["[data-activity-error]", error],
    ['[data-counter="pending"]', counter],
    ["[data-activity-recent]", recentBody],
    ["[data-activity-history]", historyBody],
    ["[data-activity-recent-empty]", recentEmpty],
    ["[data-activity-history-empty]", historyEmpty],
    ["[data-history-total]", { ...simpleElement }],
    ["[data-page-current]", { ...simpleElement }],
    ["[data-page-count]", { ...simpleElement }],
    ["[data-page-previous]", { ...simpleElement }],
    ["[data-page-next]", { ...simpleElement }],
    ["[data-activity-refreshed]", { ...simpleElement }],
  ]);
  const document = {
    activeElement: null,
    documentElement: { dataset: {}, removeAttribute() {} },
    visibilityState: "visible",
    addEventListener(type, listener) {
      documentListeners.set(type, [
        ...(documentListeners.get(type) || []),
        listener,
      ]);
    },
    querySelector: (selector) => selectors.get(selector) || null,
    querySelectorAll: () => [],
  };
  const window = {
    document,
    localStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    addEventListener(type, listener) {
      windowListeners.set(type, [
        ...(windowListeners.get(type) || []),
        listener,
      ]);
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    setTimeout(callback, delay) {
      timerId += 1;
      timers.set(timerId, { callback, delay });
      return timerId;
    },
    location: {
      pathname: "/activity",
      search: "?status=processing",
      assign(value) {
        redirects.push(value);
      },
    },
    confirm: () => true,
  };
  const context = vm.createContext({
    AbortController,
    console,
    Date,
    document,
    encodeURIComponent,
    fetch: fetchImplementation,
    Promise,
    Set,
    URLSearchParams,
    window,
  });
  vm.runInContext(script, context, { filename: "admin.js" });
  documentListeners.get("DOMContentLoaded").forEach((listener) => listener());

  return {
    counter,
    document,
    error,
    historyBody,
    next: selectors.get("[data-page-next]"),
    previous: selectors.get("[data-page-previous]"),
    recentBody,
    redirects,
    root,
    timers,
    async runTimer() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      timer.callback();
      await settle();
    },
    visibility(value) {
      document.visibilityState = value;
      documentListeners
        .get("visibilitychange")
        .forEach((listener) => listener());
    },
  };
}

test("l’activité est renouvelée et ne lance jamais deux requêtes concurrentes", async () => {
  const response = deferred();
  let fetchCount = 0;
  const harness = createActivityHarness(() => {
    fetchCount += 1;
    return response.promise;
  });

  assert.equal([...harness.timers.values()][0].delay, 5000);
  await harness.runTimer();
  harness.visibility("hidden");
  harness.visibility("visible");
  assert.equal(fetchCount, 1);

  response.resolve({
    ok: true,
    status: 200,
    json: async () => activityPayload(7),
  });
  await settle();
  assert.equal(harness.counter.textContent, "7");
  assert.equal(harness.root.attributes["aria-busy"], "false");
});

test("le polling est suspendu lorsque l’onglet est masqué et reprend immédiatement", async () => {
  let fetchCount = 0;
  const harness = createActivityHarness(async () => {
    fetchCount += 1;
    return { ok: true, status: 200, json: async () => activityPayload() };
  });

  harness.visibility("hidden");
  assert.equal(harness.timers.size, 0);
  harness.visibility("visible");
  await settle();
  assert.equal(fetchCount, 1);
  assert.equal(harness.timers.size, 1);
});

test("une erreur réseau est signalée puis retentée", async () => {
  let fetchCount = 0;
  const harness = createActivityHarness(async () => {
    fetchCount += 1;
    if (fetchCount === 1) throw new Error("network unavailable");
    return { ok: true, status: 200, json: async () => activityPayload() };
  });

  await harness.runTimer();
  assert.equal(harness.error.hidden, false);
  assert.equal(harness.timers.size, 1);
  await harness.runTimer();
  assert.equal(harness.error.hidden, true);
  assert.equal(fetchCount, 2);
});

test("une session expirée arrête le polling et redirige vers la connexion", async () => {
  const harness = createActivityHarness(async () => ({
    ok: false,
    status: 401,
  }));

  await harness.runTimer();
  assert.deepEqual(harness.redirects, [
    "/login?next=%2Factivity%3Fstatus%3Dprocessing&expired=1",
  ]);
  assert.equal(harness.timers.size, 0);
});

test("les liens de pagination inutiles sont marqués comme masqués", async () => {
  const payload = activityPayload();
  payload.pagination.page_count = 2;
  const harness = createActivityHarness(async () => ({
    ok: true,
    status: 200,
    json: async () => payload,
  }));

  await harness.runTimer();
  assert.equal(harness.previous.hidden, true);
  assert.equal(harness.next.hidden, false);
});

test("un identifiant déplié empêche le remplacement de sa table", async () => {
  const payload = activityPayload();
  payload.history = [{ id: "job-modifie" }];
  const harness = createActivityHarness(async () => ({
    ok: true,
    status: 200,
    json: async () => payload,
  }));
  harness.historyBody.hasOpenDetails = true;

  await harness.runTimer();
  assert.equal(harness.historyBody.replacementCount, 0);
});

test("le polling ne remplace pas une table contenant le focus clavier", async () => {
  const payload = activityPayload();
  payload.history = [{ id: "job-modifie" }];
  const harness = createActivityHarness(async () => ({
    ok: true,
    status: 200,
    json: async () => payload,
  }));
  harness.document.activeElement = { activityBody: harness.historyBody };

  await harness.runTimer();
  assert.equal(harness.historyBody.replacementCount, 0);
});

class ModelElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.attributes = {};
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.disabled = false;
    this.hidden = false;
    this.listeners = new Map();
    this.textContent = "";
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  append(...children) {
    this.children.push(...children);
  }

  closest(selector) {
    return selector === "[data-model-action]" && "modelAction" in this.dataset
      ? this
      : null;
  }

  querySelector(selector) {
    if (selector === "button" || selector === "button[type='submit']") {
      return this.children.find((child) => child?.tagName === "BUTTON") || null;
    }
    return null;
  }

  replaceChildren(...children) {
    this.children = children;
  }

  setAttribute(name, value) {
    this.attributes[name] = value;
  }
}

function modelPayload(models = []) {
  return {
    selected_model: "org/selected-GGUF:Q4_K_M",
    loaded_model: "org/loaded-GGUF:Q5_K_M",
    models,
  };
}

function modelState(id, status, overrides = {}) {
  return {
    id,
    name: id.split("/").at(-1).split(":")[0].replace(/-GGUF$/, ""),
    loaded: false,
    progress_done: null,
    progress_percentage: null,
    progress_total: null,
    quantization: "Q4_K_M",
    selected: false,
    size: 2048,
    size_label: "2 Mio",
    vram_estimate_label: "3 Gio",
    progress_done_label: "1 Mio",
    progress_total_label: "4 Mio",
    status,
    status_label: status,
    ...overrides,
  };
}

function createModelsHarness(fetchImplementation) {
  const documentListeners = new Map();
  const windowListeners = new Map();
  const timers = new Map();
  let timerId = 0;
  const redirects = [];
  const body = new ModelElement("div");
  const primary = new ModelElement("div");
  const empty = new ModelElement("p");
  const error = new ModelElement("p");
  error.hidden = true;
  const refreshed = new ModelElement("span");
  const root = new ModelElement("section");
  root.dataset.csrfToken = "csrf-test";
  root.querySelector = (selector) => {
    if (selector === "[data-primary-model]") return primary;
    if (selector === "[data-other-models]") return body;
    if (selector === "[data-models-empty]") return empty;
    return null;
  };
  const selectors = new Map([
    ["[data-models-root]", root],
    ["[data-models-error]", error],
    ["[data-models-refresh]", refreshed],
  ]);
  const document = {
    documentElement: { dataset: {}, removeAttribute() {} },
    visibilityState: "visible",
    addEventListener(type, listener) {
      documentListeners.set(type, [
        ...(documentListeners.get(type) || []),
        listener,
      ]);
    },
    createElement: (tagName) => new ModelElement(tagName),
    querySelector: (selector) => selectors.get(selector) || null,
    querySelectorAll: () => [],
  };
  const window = {
    document,
    localStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    addEventListener(type, listener) {
      windowListeners.set(type, [
        ...(windowListeners.get(type) || []),
        listener,
      ]);
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    setTimeout(callback, delay) {
      timerId += 1;
      timers.set(timerId, { callback, delay });
      return timerId;
    },
    location: { assign: (value) => redirects.push(value) },
    confirm: () => true,
  };
  vm.runInContext(
    script,
    vm.createContext({
      console,
      Date,
      document,
      fetch: fetchImplementation,
      Promise,
      Set,
      window,
    }),
    { filename: "admin.js" },
  );
  documentListeners.get("DOMContentLoaded").forEach((listener) => listener());

  return {
    body,
    document,
    empty,
    error,
    primary,
    redirects,
    refreshed,
    root,
    timers,
    async runTimer() {
      const entry = timers.entries().next().value;
      assert.ok(entry, "un rafraîchissement devait être planifié");
      const [id, timer] = entry;
      timers.delete(id);
      await timer.callback();
      await settle();
    },
    pagehide() {
      windowListeners.get("pagehide").forEach((listener) => listener());
    },
    visibility(value) {
      document.visibilityState = value;
      documentListeners
        .get("visibilitychange")
        .forEach((listener) => listener());
    },
  };
}

function jsonResponse(payload) {
  return { ok: true, status: 200, json: async () => payload };
}

test("les modèles et tous leurs états Router sont affichés", async () => {
  const states = ["loaded", "loading", "downloading", "incomplete", "error"];
  const payload = modelPayload(
    states.map((state) =>
      modelState(`org/${state}-GGUF:Q4_K_M`, state, {
        status_label: `Libellé ${state}`,
      }),
    ),
  );
  const harness = createModelsHarness(async () => jsonResponse(payload));

  await harness.runTimer();

  assert.equal(harness.body.children.length, states.length);
  assert.deepEqual(harness.body.children.map((card) => card.children[0].children[1].className), states.map((state) => `badge status-${state}`));
  assert.equal(
    harness.body.children[0].children[1].children[2].children[0].textContent,
    "VRAM estimée (indicative)",
  );
  assert.equal(harness.empty.hidden, true);
});

test("le modèle principal reste distinct du modèle réellement chargé", async () => {
  const payload = modelPayload([
    modelState("org/selected-GGUF:Q4_K_M", "downloading", {
      progress_done: 1024,
      progress_total: 4096,
      progress_percentage: 25,
      selected: true,
    }),
    modelState("org/loaded-GGUF:Q5_K_M", "loaded", {
      loaded: true,
      quantization: "Q5_K_M",
    }),
  ]);
  const harness = createModelsHarness(async () => jsonResponse(payload));

  await harness.runTimer();

  assert.equal(harness.primary.children.length, 1);
  assert.equal(harness.primary.children[0].children[0].children[1].textContent, "downloading");
  assert.equal(harness.body.children.length, 1);
  assert.equal(harness.body.children[0].children[0].children[1].textContent, "loaded");
});

test("les formulaires d’activation et de reprise contiennent modèle et CSRF", async () => {
  const payload = modelPayload([
    modelState("org/available-GGUF:Q4_K_M", "unloaded"),
    modelState("org/partial-GGUF:Q4_K_M", "incomplete"),
  ]);
  const harness = createModelsHarness(async () => jsonResponse(payload));
  await harness.runTimer();

  const activateLayout = harness.body.children[0].children.at(-1).children[1];
  const resumeLayout = harness.body.children[1].children.at(-1).children[1];
  assert.equal(activateLayout.className, "model-actions");
  assert.equal(resumeLayout.className, "model-actions");
  const activate = activateLayout.children[0];
  const resume = resumeLayout.children[0];
  assert.equal(activate.action, "/llm-models/activate");
  assert.equal(resume.action, "/llm-models/download");
  for (const form of [activate, resume]) {
    assert.deepEqual(form.children.slice(0, 2).map((input) => input.value), [
      "csrf-test",
      form === activate
        ? "org/available-GGUF:Q4_K_M"
        : "org/partial-GGUF:Q4_K_M",
    ]);
  }
});

test("une double soumission d’action est bloquée", async () => {
  const harness = createModelsHarness(async () =>
    jsonResponse(modelPayload([modelState("org/model-GGUF:Q4_K_M", "unloaded")])),
  );
  await harness.runTimer();
  const form = harness.body.children[0].children.at(-1).children[1].children[0];
  const submit = harness.root.listeners.get("submit");
  const first = { target: form, preventDefault() { this.prevented = true; } };
  const second = { target: form, preventDefault() { this.prevented = true; } };

  submit(first);
  submit(second);

  assert.equal(first.prevented, undefined);
  assert.equal(second.prevented, true);
  assert.equal(form.children[2].disabled, true);
});

test("le polling des modèles est adaptatif et ne se duplique pas", async () => {
  let payload = modelPayload([modelState("org/model-GGUF:Q4_K_M", "loading")]);
  const harness = createModelsHarness(async () => jsonResponse(payload));
  assert.equal([...harness.timers.values()][0].delay, 5000);

  await harness.runTimer();
  assert.equal(harness.timers.size, 1);
  assert.equal([...harness.timers.values()][0].delay, 3000);

  payload = modelPayload([modelState("org/model-GGUF:Q4_K_M", "loaded")]);
  harness.visibility("hidden");
  assert.equal(harness.timers.size, 0);
  harness.visibility("visible");
  await settle();
  assert.equal(harness.timers.size, 1);
  assert.equal([...harness.timers.values()][0].delay, 30000);
});

test("l’interface récupère après une indisponibilité du Router", async () => {
  let callCount = 0;
  const harness = createModelsHarness(async () => {
    callCount += 1;
    if (callCount === 1) throw new Error("internal network detail");
    return jsonResponse(modelPayload([modelState("org/model-GGUF:Q4_K_M", "loaded")]));
  });

  await harness.runTimer();
  assert.equal(harness.error.hidden, false);
  assert.equal(harness.error.textContent.includes("nouvelle tentative"), true);
  assert.equal([...harness.timers.values()][0].delay, 10000);

  await harness.runTimer();
  assert.equal(harness.error.hidden, true);
  assert.equal(harness.body.children.length, 1);
  assert.equal(harness.refreshed.textContent, "État actualisé.");
});

test("quitter la page arrête le polling des modèles", async () => {
  let fetchCount = 0;
  const harness = createModelsHarness(async () => {
    fetchCount += 1;
    return jsonResponse(modelPayload());
  });
  harness.pagehide();
  assert.equal(harness.timers.size, 0);
  harness.visibility("visible");
  await settle();
  assert.equal(fetchCount, 0);
  assert.equal(harness.timers.size, 0);
});

test("une session expirée arrête le polling des modèles", async () => {
  const harness = createModelsHarness(async () => ({ ok: false, status: 401 }));
  await harness.runTimer();
  assert.deepEqual(harness.redirects, [
    "/login?next=%2Fllm-models&expired=1",
  ]);
  assert.equal(harness.timers.size, 0);
});
