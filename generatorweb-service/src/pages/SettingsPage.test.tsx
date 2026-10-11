import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "@/App";
import { THEME_STORAGE_KEY } from "@/app/ThemeProvider";

const SESSION_KEY = "cv-generator.api-key.session";
const LOCAL_KEY = "cv-generator.api-key.local";

function response(status = 200) {
  return new Response(
    status === 200
      ? JSON.stringify({ items: [], total: 0, limit: 1, offset: 0 })
      : JSON.stringify({
          detail: { code: "invalid_api_key", message: "Clé API invalide" },
        }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function renderSettings() {
  return render(
    <MemoryRouter initialEntries={["/parametres"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("configuration de la clé API", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => vi.unstubAllGlobals());

  it("permet de saisir, afficher et masquer la clé", async () => {
    const user = userEvent.setup();
    renderSettings();
    const input = screen.getByLabelText("Clé API");

    await user.type(input, "cle-test-secrete");
    expect(input).toHaveAttribute("type", "password");
    await user.click(
      screen.getByRole("button", { name: "Afficher la clé API" }),
    );
    expect(input).toHaveAttribute("type", "text");
    await user.click(
      screen.getByRole("button", { name: "Masquer la clé API" }),
    );
    expect(input).toHaveAttribute("type", "password");
  });

  it("valide une clé et la conserve par défaut dans sessionStorage", async () => {
    const fetchMock = vi.mocked(fetch).mockResolvedValue(response());
    const user = userEvent.setup();
    renderSettings();

    await user.type(screen.getByLabelText("Clé API"), "cle-session");
    await user.click(
      screen.getByRole("button", { name: "Vérifier et enregistrer" }),
    );

    expect(await screen.findByText("Connecté")).toBeInTheDocument();
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe("cle-session");
    expect(window.localStorage.getItem(LOCAL_KEY)).toBeNull();
    const requestOptions = fetchMock.mock.calls[0]?.[1];
    expect(new Headers(requestOptions?.headers).get("X-API-Key")).toBe(
      "cle-session",
    );
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/documents?limit=1&offset=0",
    );
  });

  it("mémorise facultativement la clé dans localStorage", async () => {
    vi.mocked(fetch).mockResolvedValue(response());
    const user = userEvent.setup();
    renderSettings();

    await user.type(screen.getByLabelText("Clé API"), "cle-locale");
    await user.click(
      screen.getByRole("checkbox", {
        name: /Mémoriser la clé sur cet appareil/,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Vérifier et enregistrer" }),
    );

    await screen.findByText("Connecté");
    expect(window.localStorage.getItem(LOCAL_KEY)).toBe("cle-locale");
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("déplace une clé valide lorsque la préférence change", async () => {
    vi.mocked(fetch).mockResolvedValue(response());
    const user = userEvent.setup();
    renderSettings();

    await user.type(screen.getByLabelText("Clé API"), "cle-a-deplacer");
    await user.click(
      screen.getByRole("button", { name: "Vérifier et enregistrer" }),
    );
    await screen.findByText("Connecté");
    await user.click(
      screen.getByRole("checkbox", {
        name: /Mémoriser la clé sur cet appareil/,
      }),
    );

    expect(window.localStorage.getItem(LOCAL_KEY)).toBe("cle-a-deplacer");
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull();
  });

  it("revalide une clé chargée avant d'afficher l'état connecté", async () => {
    window.sessionStorage.setItem(SESSION_KEY, "cle-existante");
    const fetchMock = vi.mocked(fetch).mockResolvedValue(response());

    renderSettings();

    expect(screen.getByText("Vérification…")).toBeInTheDocument();
    expect(await screen.findByText("Connecté")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("distingue un refus, une erreur réseau et une erreur serveur", async () => {
    const fetchMock = vi
      .mocked(fetch)
      .mockResolvedValueOnce(response(401))
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: { message: "Interne" } }), {
          status: 500,
        }),
      );
    const user = userEvent.setup();
    renderSettings();
    const input = screen.getByLabelText("Clé API");
    const submit = screen.getByRole("button", {
      name: "Vérifier et enregistrer",
    });

    await user.type(input, "secret-refuse");
    await user.click(submit);
    expect(await screen.findByText(/La clé a été refusée/)).toBeInTheDocument();
    expect(screen.queryByText("secret-refuse")).not.toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "secret-reseau");
    await user.click(submit);
    expect(
      await screen.findByText(/Impossible de joindre le service/),
    ).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, "secret-serveur");
    await user.click(submit);
    expect(
      await screen.findByText(/Le service ne peut pas vérifier la clé/),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("préserve l'ancienne clé si son remplacement est refusé", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(response())
      .mockResolvedValueOnce(response(401));
    const user = userEvent.setup();
    renderSettings();
    const input = screen.getByLabelText("Clé API");

    await user.type(input, "ancienne-cle");
    await user.click(
      screen.getByRole("button", { name: "Vérifier et enregistrer" }),
    );
    await screen.findByText("Connecté");
    await user.clear(input);
    await user.type(input, "nouvelle-cle-refusee");
    await user.click(
      screen.getByRole("button", { name: "Vérifier et remplacer" }),
    );

    expect(await screen.findByText(/La clé a été refusée/)).toBeInTheDocument();
    expect(screen.getByText("Connecté")).toBeInTheDocument();
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBe("ancienne-cle");
  });

  it("supprime la clé des deux stockages", async () => {
    window.localStorage.setItem(LOCAL_KEY, "cle-a-supprimer");
    vi.mocked(fetch).mockResolvedValue(response());
    const user = userEvent.setup();
    renderSettings();
    await screen.findByText("Connecté");

    await user.click(screen.getByRole("button", { name: "Supprimer la clé" }));

    await waitFor(() =>
      expect(screen.getByText("Non configurée")).toBeInTheDocument(),
    );
    expect(window.localStorage.getItem(LOCAL_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(SESSION_KEY)).toBeNull();
    expect(screen.getByLabelText("Clé API")).toHaveValue("");
  });

  it("ne réactive pas une clé supprimée pendant sa revalidation initiale", async () => {
    window.sessionStorage.setItem(SESSION_KEY, "ancienne-cle");
    let resolveRequest: ((value: Response) => void) | undefined;
    vi.mocked(fetch).mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveRequest = resolve;
      }),
    );
    const user = userEvent.setup();
    renderSettings();

    expect(screen.getByText("Vérification…")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Supprimer la clé" }));
    expect(screen.getByText("Non configurée")).toBeInTheDocument();

    resolveRequest?.(response());
    await waitFor(() =>
      expect(screen.getByText("Non configurée")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Connecté")).not.toBeInTheDocument();
  });
});

describe("apparence", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    document.documentElement.classList.remove("dark");
    document.documentElement.style.colorScheme = "";
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => vi.unstubAllGlobals());

  it.each([null, "invalide"])(
    "utilise le thème clair sans préférence valide (%s)",
    (storedTheme) => {
      if (storedTheme) {
        window.localStorage.setItem(THEME_STORAGE_KEY, storedTheme);
      }
      renderSettings();

      expect(
        screen.getByRole("switch", { name: "Activer le mode sombre" }),
      ).not.toBeChecked();
      expect(document.documentElement).not.toHaveClass("dark");
      expect(document.documentElement.style.colorScheme).toBe("light");
    },
  );

  it("active immédiatement le mode sombre et conserve le choix", async () => {
    const user = userEvent.setup();
    const { unmount } = renderSettings();
    const themeSwitch = screen.getByRole("switch", {
      name: "Activer le mode sombre",
    });

    expect(themeSwitch).toHaveClass("h-11", "w-14");

    await user.click(themeSwitch);

    expect(themeSwitch).toBeChecked();
    expect(document.documentElement).toHaveClass("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");

    unmount();
    renderSettings();
    expect(
      screen.getByRole("switch", { name: "Activer le mode sombre" }),
    ).toBeChecked();
    expect(document.documentElement).toHaveClass("dark");
  });

  it("reste actif pendant la navigation puis permet le retour au clair", async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    const user = userEvent.setup();
    renderSettings();

    await user.click(screen.getByRole("link", { name: /Générer/ }));
    expect(document.documentElement).toHaveClass("dark");
    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    const themeSwitch = screen.getByRole("switch", {
      name: "Activer le mode sombre",
    });
    await user.keyboard("{Tab}");
    themeSwitch.focus();
    await user.keyboard("{Enter}");

    expect(themeSwitch).not.toBeChecked();
    expect(document.documentElement).not.toHaveClass("dark");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("bascule le thème avec Espace", async () => {
    const user = userEvent.setup();
    renderSettings();
    const themeSwitch = screen.getByRole("switch", {
      name: "Activer le mode sombre",
    });

    themeSwitch.focus();
    await user.keyboard(" ");

    expect(themeSwitch).toBeChecked();
    expect(document.documentElement).toHaveClass("dark");
  });
});
