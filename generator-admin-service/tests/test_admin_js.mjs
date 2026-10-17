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
      documentListeners.set(type, listener);
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
      windowListeners.set(type, listener);
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
  documentListeners.get("DOMContentLoaded")();

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
