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
