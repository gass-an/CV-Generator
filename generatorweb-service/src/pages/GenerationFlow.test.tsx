import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "@/App";
import { useDocumentPolling } from "@/hooks/useDocumentPolling";
import { ApiError } from "@/services/apiClient";
import {
  createDocumentJob,
  getDocumentAvpNumbers,
  getDocumentHistory,
  getDocumentPdf,
  getDocumentExport,
} from "@/services/documentService";

vi.mock("@/hooks/useDocumentPolling", () => ({
  useDocumentPolling: vi.fn(),
}));
vi.mock("@/services/documentService", () => ({
  createDocumentJob: vi.fn(),
  getDocumentJobStatus: vi.fn(),
  getDocumentHistory: vi.fn(),
  getDocumentAvpNumbers: vi.fn(),
  getDocumentPdf: vi.fn(),
  getDocumentExport: vi.fn(),
}));

const SESSION_KEY = "cv-generator.api-key.session";
const resume = {
  basics: { name: "Camille Exemple" },
  work: [],
  education: [],
  skills: [],
  extension_personnalisee: { disponibilite: "Immédiate" },
};

function authResponse() {
  return new Response(
    JSON.stringify({ items: [], total: 0, limit: 1, offset: 0 }),
    { status: 200, headers: { "Content-Type": "application/json" } },
  );
}

function renderGeneration() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
}

async function prepareGeneration(user: ReturnType<typeof userEvent.setup>) {
  const rendered = renderGeneration();
  await waitFor(() =>
    expect(screen.getByText("Clé API vérifiée")).toHaveClass("text-primary"),
  );
  await user.upload(
    screen.getByLabelText("Choisir un fichier"),
    new File([JSON.stringify(resume)], "camille.json", {
      type: "application/json",
    }),
  );
  await user.type(screen.getByLabelText("Numéro AVP"), "3134-26-1382/SR");
  await user.click(
    screen.getByRole("radio", { name: /Préparation à l'entretien/ }),
  );
  return rendered;
}

function latestPollingOptions() {
  const calls = vi.mocked(useDocumentPolling).mock.calls;
  const options = calls.at(-1)?.[0];
  if (!options) {
    throw new Error("Le hook de polling n'a pas été appelé.");
  }
  return options;
}

describe("génération et suivi d'un document", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
    window.sessionStorage.setItem(SESSION_KEY, "cle-valide");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(authResponse()));
    vi.mocked(useDocumentPolling).mockReset();
    vi.mocked(createDocumentJob).mockReset();
    vi.mocked(getDocumentHistory).mockResolvedValue({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });
    vi.mocked(getDocumentAvpNumbers).mockResolvedValue([]);
    vi.mocked(getDocumentPdf).mockResolvedValue(
      new Blob(["%PDF-1.4"], { type: "application/pdf" }),
    );
    vi.mocked(getDocumentExport).mockResolvedValue(
      new Blob(["document"], { type: "application/octet-stream" }),
    );
    let downloadUrl = 0;
    vi.spyOn(URL, "createObjectURL").mockImplementation((source) =>
      source instanceof Blob && source.type === "application/pdf"
        ? "blob:preview"
        : `blob:download-${++downloadUrl}`,
    );
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("crée le job puis affiche les transitions jusqu'à completed", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-123",
      status: "pending",
    });
    const user = userEvent.setup();
    await prepareGeneration(user);

    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    expect(
      await screen.findByText("Votre document est en attente de traitement."),
    ).toBeInTheDocument();
    expect(createDocumentJob).toHaveBeenCalledWith(
      "interview_prep",
      { avp_number: "3134-26-1382/SR", resume },
      "cle-valide",
      expect.any(AbortSignal),
    );

    await act(async () =>
      latestPollingOptions().onStatus({
        id: "job-123",
        status: "processing",
        created_at: "2026-10-11T08:00:00+11:00",
        started_at: "2026-10-11T08:00:03+11:00",
        completed_at: null,
      }),
    );
    expect(
      screen.getByText("L'IA prépare votre document…"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Télécharger au format/ }),
    ).not.toBeInTheDocument();
    expect(
      screen
        .getByText("L'IA prépare votre document…")
        .parentElement?.querySelector("svg"),
    ).toHaveClass("generation-spinner");

    await user.click(screen.getByRole("link", { name: /Historique/ }));
    await user.click(screen.getByRole("link", { name: /Générer/ }));
    expect(
      screen.getByText("L'IA prépare votre document…"),
    ).toBeInTheDocument();

    await act(async () =>
      latestPollingOptions().onStatus({
        id: "job-123",
        status: "completed",
        created_at: "2026-10-11T08:00:00+11:00",
        started_at: "2026-10-11T08:00:03+11:00",
        completed_at: "2026-10-11T08:01:00+11:00",
      }),
    );
    expect(screen.getByText("Votre document est prêt !")).toBeInTheDocument();
    expect(document.querySelector(".generation-spinner")).toBeNull();
    expect(latestPollingOptions().enabled).toBe(false);
    for (const format of ["PDF", "DOCX", "ADOC", "MD"]) {
      expect(
        screen.getByRole("button", {
          name: `Télécharger au format ${format}`,
        }),
      ).toBeInTheDocument();
    }
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    for (const format of ["ADOC", "MD"] as const) {
      await user.click(
        screen.getByRole("button", {
          name: `Télécharger au format ${format}`,
        }),
      );
      await waitFor(() =>
        expect(getDocumentExport).toHaveBeenCalledWith(
          "job-123",
          "cle-valide",
          format.toLowerCase(),
          expect.any(AbortSignal),
        ),
      );
    }
  });

  it("affiche une annulation sans proposer de résultat", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-annule",
      status: "pending",
    });
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );

    await act(async () =>
      latestPollingOptions().onStatus({
        id: "job-annule",
        status: "cancelled",
        created_at: "2026-10-11T08:00:00+11:00",
        started_at: null,
        completed_at: null,
        cancelled_at: "2026-10-11T08:00:05+11:00",
      }),
    );

    expect(screen.getByRole("status")).toHaveTextContent("Annulée");
    expect(latestPollingOptions().enabled).toBe(false);
    expect(
      screen.queryByRole("button", { name: /Télécharger au format/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^Aperçu PDF/)).not.toBeInTheDocument();
    expect(getDocumentPdf).not.toHaveBeenCalled();
  });

  it("agrandit le PDF déjà chargé sans nouvel appel ni révocation prématurée", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-apercu",
      status: "pending",
    });
    const user = userEvent.setup();
    const rendered = await prepareGeneration(user);
    vi.mocked(URL.revokeObjectURL).mockClear();
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await screen.findByText("Votre document est en attente de traitement.");

    await act(async () =>
      latestPollingOptions().onStatus({
        id: "job-apercu",
        status: "completed",
        created_at: "2026-10-11T08:00:00+11:00",
        started_at: "2026-10-11T08:00:03+11:00",
        completed_at: "2026-10-11T08:01:00+11:00",
      }),
    );

    const compactPreview = await screen.findByLabelText(/^Aperçu PDF —/);
    expect(compactPreview).toHaveAttribute("data", "blob:preview");
    expect(compactPreview).toHaveClass("h-[50svh]", "sm:h-[65vh]");
    expect(compactPreview).not.toHaveClass("h-full");
    expect(getDocumentPdf).toHaveBeenCalledOnce();
    vi.mocked(URL.revokeObjectURL).mockClear();

    const enlarge = screen.getByRole("button", {
      name: "Agrandir l’aperçu",
    });
    await user.click(enlarge);
    const expandedPreview = await screen.findByLabelText(
      /^Aperçu PDF agrandi —/,
    );
    expect(expandedPreview).toHaveAttribute("data", "blob:preview");
    expect(expandedPreview).toHaveClass("h-full", "min-h-0");
    expect(screen.getByRole("dialog").parentElement).toBe(document.body);
    expect(getDocumentPdf).toHaveBeenCalledOnce();

    await user.click(
      screen.getByRole("button", { name: "Fermer la prévisualisation" }),
    );
    expect(screen.getByLabelText(/^Aperçu PDF —/)).toBeInTheDocument();
    expect(URL.revokeObjectURL).not.toHaveBeenCalledWith("blob:preview");
    expect(enlarge).toHaveFocus();

    await user.click(enlarge);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(getDocumentPdf).toHaveBeenCalledOnce();

    rendered.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  });

  it("affiche l'échec terminal et autorise une nouvelle génération", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-echec",
      status: "pending",
    });
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await screen.findByText("Votre document est en attente de traitement.");

    await act(async () =>
      latestPollingOptions().onStatus({
        id: "job-echec",
        status: "failed",
        created_at: "2026-10-11T08:00:00+11:00",
        started_at: "2026-10-11T08:00:03+11:00",
        completed_at: "2026-10-11T08:00:10+11:00",
      }),
    );

    expect(
      screen.getByText("La génération du document a échoué."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Générer le document" }),
    ).toBeEnabled();
  });

  it("reprend un suivi interrompu sans recréer le job", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-reprise",
      status: "pending",
    });
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await screen.findByText("Votre document est en attente de traitement.");

    await act(async () =>
      latestPollingOptions().onError(
        new ApiError({ kind: "network", message: "Réseau indisponible" }),
      ),
    );
    expect(screen.getByText("Connexion interrompue")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Reprendre le suivi" }),
    );

    expect(createDocumentJob).toHaveBeenCalledOnce();
    expect(
      screen.getByText("Votre document est en attente de traitement."),
    ).toBeInTheDocument();
    expect(latestPollingOptions().enabled).toBe(true);
  });

  it("empêche un double POST pendant l'envoi", async () => {
    let resolveCreation:
      ((value: { id: string; status: "pending" }) => void) | undefined;
    vi.mocked(createDocumentJob).mockReturnValue(
      new Promise((resolve) => {
        resolveCreation = resolve;
      }),
    );
    const user = userEvent.setup();
    await prepareGeneration(user);
    const button = screen.getByRole("button", { name: "Générer le document" });

    await user.click(button);
    await user.click(button);
    expect(createDocumentJob).toHaveBeenCalledOnce();

    await act(async () =>
      resolveCreation?.({ id: "job-unique", status: "pending" }),
    );
  });

  it.each([
    [
      "timeout incertain",
      new ApiError({ kind: "timeout", message: "Trop long" }),
      /Le job a peut-être été créé/,
    ],
    [
      "erreur réseau incertaine",
      new ApiError({ kind: "network", message: "Réseau indisponible" }),
      /Le job a peut-être été créé/,
    ],
  ])("distingue un %s lors de la création", async (_label, error, message) => {
    vi.mocked(createDocumentJob).mockRejectedValue(error);
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );

    expect((await screen.findAllByText(message)).length).toBeGreaterThan(0);
    expect(createDocumentJob).toHaveBeenCalledOnce();
  });

  it("nettoie le suivi et le brouillon après un 401 pendant la création", async () => {
    vi.mocked(createDocumentJob).mockRejectedValue(
      new ApiError({ kind: "http", status: 401, message: "Refusée" }),
    );
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );

    expect(
      await screen.findByText("Aucun document à prévisualiser"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Camille Exemple")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Numéro AVP")).toHaveValue("");
    expect(screen.queryByText(/Demande non confirmée/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    expect(
      screen.queryByText("Connecté", { exact: true }),
    ).not.toBeInTheDocument();
  });

  it("nettoie le suivi après un 401 de polling et ignore une réponse tardive", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-cle-revoquee",
      status: "pending",
    });
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await screen.findByText("Votre document est en attente de traitement.");
    const oldPolling = latestPollingOptions();

    await act(async () =>
      oldPolling.onError(
        new ApiError({ kind: "http", status: 401, message: "Clé révoquée" }),
      ),
    );
    await act(async () =>
      oldPolling.onStatus({
        id: "job-cle-revoquee",
        status: "completed",
        created_at: "2026-10-11T08:00:00+11:00",
        started_at: "2026-10-11T08:00:03+11:00",
        completed_at: "2026-10-11T08:01:00+11:00",
      }),
    );

    expect(
      screen.getByText("Aucun document à prévisualiser"),
    ).toBeInTheDocument();
    expect(screen.queryByText("job-cle-revoquee")).not.toBeInTheDocument();
    expect(screen.queryByText("Camille Exemple")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Numéro AVP")).toHaveValue("");
    expect(screen.queryByText("Connexion interrompue")).not.toBeInTheDocument();
  });

  it("exige une confirmation explicite avant une relance incertaine", async () => {
    vi.mocked(createDocumentJob)
      .mockRejectedValueOnce(
        new ApiError({ kind: "timeout", message: "Trop long" }),
      )
      .mockResolvedValueOnce({ id: "job-confirme", status: "pending" });
    const user = userEvent.setup();
    await prepareGeneration(user);

    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    const blockedButton = await screen.findByRole("button", {
      name: "Confirmation requise",
    });
    expect(blockedButton).toBeDisabled();
    expect(createDocumentJob).toHaveBeenCalledOnce();
    expect(
      screen.getByText(/une seconde demande pourra créer un doublon/i),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "J'ai compris, autoriser une nouvelle demande",
      }),
    );
    expect(
      screen.getByRole("button", { name: "Générer le document" }),
    ).toBeEnabled();
    expect(createDocumentJob).toHaveBeenCalledOnce();

    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    expect(createDocumentJob).toHaveBeenCalledTimes(2);
  });

  it("permet une nouvelle tentative après une erreur de création certaine", async () => {
    vi.mocked(createDocumentJob)
      .mockRejectedValueOnce(
        new ApiError({ kind: "http", status: 500, message: "Erreur serveur" }),
      )
      .mockResolvedValueOnce({ id: "job-reessai", status: "pending" });
    const user = userEvent.setup();
    await prepareGeneration(user);

    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    expect(
      await screen.findByRole("button", { name: "Générer le document" }),
    ).toBeEnabled();
    expect(
      screen.queryByRole("button", {
        name: "J'ai compris, autoriser une nouvelle demande",
      }),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    expect(createDocumentJob).toHaveBeenCalledTimes(2);
  });

  it("arrête uniquement le suivi local et conserve le brouillon", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-abandonne",
      status: "pending",
    });
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await screen.findByText("Votre document est en attente de traitement.");
    await act(async () =>
      latestPollingOptions().onError(
        new ApiError({ kind: "network", message: "Réseau indisponible" }),
      ),
    );

    expect(
      screen.getByText(/Le traitement continue côté serveur/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Arrêter le suivi" }));

    expect(
      screen.getByText("Aucun document à prévisualiser"),
    ).toBeInTheDocument();
    expect(screen.getByText("Camille Exemple")).toBeInTheDocument();
    expect(screen.getByLabelText("Numéro AVP")).toHaveValue("3134-26-1382/SR");
    expect(
      screen.getByRole("radio", { name: /Préparation à l'entretien/ }),
    ).toBeChecked();
    expect(createDocumentJob).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("ignore la réponse tardive d'un POST après suppression de la clé", async () => {
    let resolveCreation:
      ((value: { id: string; status: "pending" }) => void) | undefined;
    vi.mocked(createDocumentJob).mockReturnValue(
      new Promise((resolve) => {
        resolveCreation = resolve;
      }),
    );
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    await user.click(screen.getByRole("button", { name: "Supprimer la clé" }));

    await act(async () =>
      resolveCreation?.({ id: "job-ancien-client", status: "pending" }),
    );
    await user.click(screen.getByRole("link", { name: /Générer/ }));

    expect(
      screen.getByText("Aucun document à prévisualiser"),
    ).toBeInTheDocument();
    expect(screen.queryByText("job-ancien-client")).not.toBeInTheDocument();
    expect(screen.queryByText("Camille Exemple")).not.toBeInTheDocument();
  });

  it("ignore les anciennes réponses de polling après un remplacement de clé", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-ancienne-cle",
      status: "pending",
    });
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await screen.findByText("Votre document est en attente de traitement.");
    const oldPolling = latestPollingOptions();

    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    const keyInput = screen.getByLabelText("Clé API");
    await user.clear(keyInput);
    await user.type(keyInput, "nouvelle-cle");
    await user.click(
      screen.getByRole("button", { name: "Vérifier et remplacer" }),
    );
    await screen.findByText("La clé a été vérifiée et enregistrée.");

    await act(async () =>
      oldPolling.onStatus({
        id: "job-ancienne-cle",
        status: "completed",
        created_at: "2026-10-11T08:00:00+11:00",
        started_at: "2026-10-11T08:00:03+11:00",
        completed_at: "2026-10-11T08:01:00+11:00",
      }),
    );
    await act(async () =>
      oldPolling.onError(
        new ApiError({ kind: "http", status: 401, message: "Ancienne clé" }),
      ),
    );

    expect(screen.getByText("Connecté")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Générer/ }));
    expect(
      screen.getByText("Aucun document à prévisualiser"),
    ).toBeInTheDocument();
    expect(screen.queryByText("job-ancienne-cle")).not.toBeInTheDocument();
  });

  it("conserve le suivi lorsque le remplacement de clé est refusé", async () => {
    vi.mocked(createDocumentJob).mockResolvedValue({
      id: "job-conserve",
      status: "pending",
    });
    vi.mocked(fetch)
      .mockResolvedValueOnce(authResponse())
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            detail: { code: "invalid_api_key", message: "Clé refusée" },
          }),
          { status: 401, headers: { "Content-Type": "application/json" } },
        ),
      );
    const user = userEvent.setup();
    await prepareGeneration(user);
    await user.click(
      screen.getByRole("button", { name: "Générer le document" }),
    );
    await screen.findByText("Votre document est en attente de traitement.");

    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    const keyInput = screen.getByLabelText("Clé API");
    await user.clear(keyInput);
    await user.type(keyInput, "cle-refusee");
    await user.click(
      screen.getByRole("button", { name: "Vérifier et remplacer" }),
    );
    expect(await screen.findByText(/La clé a été refusée/)).toBeInTheDocument();
    expect(screen.getByText("Connecté")).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: /Générer/ }));
    expect(
      screen.getByText("Votre document est en attente de traitement."),
    ).toBeInTheDocument();
    expect(screen.getByText("job-conserve")).toBeInTheDocument();
  });
});
