import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "@/App";
import { ApiError } from "@/services/apiClient";
import {
  createDocumentJob,
  getDocumentDocx,
  getDocumentHistory,
  getDocumentPdf,
} from "@/services/documentService";
import type {
  DocumentHistoryItem,
  DocumentHistoryResponse,
} from "@/types/document";

vi.mock("@/services/documentService", () => ({
  createDocumentJob: vi.fn(),
  getDocumentJobStatus: vi.fn(),
  getDocumentHistory: vi.fn(),
  getDocumentPdf: vi.fn(),
  getDocumentDocx: vi.fn(),
}));

const SESSION_KEY = "cv-generator.api-key.session";
const items: DocumentHistoryItem[] = [
  {
    id: "job-pending",
    type: "cv",
    status: "pending",
    avp_number: "AVP-1",
    candidate_name: "Camille Exemple",
    created_at: "2026-10-11T08:00:00+11:00",
    started_at: null,
    completed_at: null,
  },
  {
    id: "job-processing",
    type: "cover_letter",
    status: "processing",
    avp_number: "AVP-2",
    candidate_name: null,
    created_at: "2026-10-10T08:00:00+11:00",
    started_at: "2026-10-10T08:00:03+11:00",
    completed_at: null,
  },
  {
    id: "job-completed",
    type: "interview_prep",
    status: "completed",
    avp_number: "AVP-3",
    candidate_name: "Léa Martin",
    created_at: "2026-10-09T08:00:00+11:00",
    started_at: "2026-10-09T08:00:03+11:00",
    completed_at: "2026-10-09T08:01:00+11:00",
  },
  {
    id: "job-failed",
    type: "cv",
    status: "failed",
    avp_number: "AVP-4",
    candidate_name: "Noé Test",
    created_at: "2026-10-08T08:00:00+11:00",
    started_at: null,
    completed_at: "2026-10-08T08:01:00+11:00",
  },
];

function page(
  pageItems = items,
  total = pageItems.length,
  offset = 0,
): DocumentHistoryResponse {
  return { items: pageItems, total, limit: 20, offset };
}

function renderHistory(withKey = true) {
  if (withKey) window.sessionStorage.setItem(SESSION_KEY, "cle-valide");
  return render(
    <MemoryRouter initialEntries={["/historique"]}>
      <App />
    </MemoryRouter>,
  );
}

describe("historique documentaire", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ items: [], total: 0, limit: 1, offset: 0 }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
    );
    vi.mocked(getDocumentHistory).mockReset();
    vi.mocked(getDocumentHistory).mockResolvedValue(page());
    vi.mocked(getDocumentPdf).mockResolvedValue(
      new Blob(["%PDF"], { type: "application/pdf" }),
    );
    vi.mocked(getDocumentDocx).mockResolvedValue(
      new Blob(["docx"], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      }),
    );
    vi.mocked(createDocumentJob).mockReset();
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("distingue l'absence de clé sans appeler l'historique", () => {
    renderHistory(false);
    expect(
      screen.getByText("Une clé API valide est nécessaire."),
    ).toBeInTheDocument();
    expect(getDocumentHistory).not.toHaveBeenCalled();
  });

  it("affiche les métadonnées réelles et les actions adaptées aux statuts", async () => {
    renderHistory();
    expect(await screen.findByText("Camille Exemple")).toBeInTheDocument();
    expect(screen.getByText("Léa Martin")).toBeInTheDocument();
    expect(screen.getByText("Candidat non renseigné")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Reprendre le suivi" }),
    ).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: "Prévisualiser" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "DOCX" })).toHaveLength(1);
    expect(screen.queryByText(/job-failed/)).not.toBeInTheDocument();
  });

  it("affiche un véritable état vide", async () => {
    vi.mocked(getDocumentHistory).mockResolvedValue(page([]));
    renderHistory();
    expect(
      await screen.findByRole("heading", {
        name: "Aucun document à afficher pour le moment",
      }),
    ).toBeInTheDocument();
  });

  it("applique les filtres côté API et revient à la première page", async () => {
    const user = userEvent.setup();
    renderHistory();
    await screen.findByText("Camille Exemple");
    await user.selectOptions(
      screen.getByLabelText("Filtrer par type"),
      "cover_letter",
    );
    await waitFor(() =>
      expect(getDocumentHistory).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 0, documentType: "cover_letter" }),
        "cle-valide",
        expect.any(AbortSignal),
      ),
    );
    await user.selectOptions(
      screen.getByLabelText("Filtrer par statut"),
      "completed",
    );
    await waitFor(() =>
      expect(getDocumentHistory).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 0, status: "completed" }),
        "cle-valide",
        expect.any(AbortSignal),
      ),
    );
  });

  it("pagine avec limit, offset et total", async () => {
    vi.mocked(getDocumentHistory).mockResolvedValue(page(items, 25));
    const user = userEvent.setup();
    renderHistory();
    await screen.findByText("Page 1 sur 2 · 25 documents");
    screen.getByRole("button", { name: "Suivante" }).focus();
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(getDocumentHistory).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 20, offset: 20 }),
        "cle-valide",
        expect.any(AbortSignal),
      ),
    );
  });

  it("affiche une erreur réseau puis permet une nouvelle tentative", async () => {
    vi.mocked(getDocumentHistory)
      .mockRejectedValueOnce(
        new ApiError({ kind: "network", message: "API injoignable" }),
      )
      .mockResolvedValueOnce(page([]));
    const user = userEvent.setup();
    renderHistory();
    expect(await screen.findByText("API injoignable")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(
      await screen.findByRole("heading", {
        name: "Aucun document à afficher pour le moment",
      }),
    ).toBeInTheDocument();
  });

  it("invalide globalement la clé active après un refus 401 de l'historique", async () => {
    vi.mocked(getDocumentHistory).mockRejectedValue(
      new ApiError({ kind: "http", status: 401, message: "Clé révoquée" }),
    );
    renderHistory();
    expect(
      await screen.findByText("Une clé API valide est nécessaire."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /Paramètres/ }));
    expect(
      screen.queryByText("Connecté", { exact: true }),
    ).not.toBeInTheDocument();
  });

  it("ignore une ancienne réponse après un changement rapide de filtre", async () => {
    let resolveOld: ((value: DocumentHistoryResponse) => void) | undefined;
    vi.mocked(getDocumentHistory)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
      )
      .mockResolvedValueOnce(
        page([{ ...items[2], candidate_name: "Résultat récent" }]),
      );
    const user = userEvent.setup();
    renderHistory();
    await user.selectOptions(
      await screen.findByLabelText("Filtrer par statut"),
      "completed",
    );
    expect(await screen.findByText("Résultat récent")).toBeInTheDocument();
    await act(async () =>
      resolveOld?.(
        page([{ ...items[0], candidate_name: "Résultat obsolète" }]),
      ),
    );
    expect(screen.queryByText("Résultat obsolète")).not.toBeInTheDocument();
  });

  it("reprend un job existant sans JSON Resume ni nouveau POST", async () => {
    const user = userEvent.setup();
    renderHistory();
    await user.click(
      (await screen.findAllByRole("button", { name: "Reprendre le suivi" }))[0],
    );
    expect(
      await screen.findByText("Votre document est en attente de traitement."),
    ).toBeInTheDocument();
    expect(screen.getByText("job-pending")).toBeInTheDocument();
    expect(createDocumentJob).not.toHaveBeenCalled();
  });

  it("demande confirmation avant de remplacer un autre suivi local", async () => {
    const user = userEvent.setup();
    renderHistory();
    const followButtons = await screen.findAllByRole("button", {
      name: "Reprendre le suivi",
    });
    await user.click(followButtons[0]);
    await user.click(screen.getByRole("link", { name: /Historique/ }));
    const refreshedButtons = await screen.findAllByRole("button", {
      name: "Reprendre le suivi",
    });
    await user.click(refreshedButtons[1]);

    expect(
      screen.getByText("Un autre document est déjà suivi."),
    ).toBeInTheDocument();
    expect(createDocumentJob).not.toHaveBeenCalled();
  });

  it("ne conserve aucun document après suppression de la clé", async () => {
    const user = userEvent.setup();
    renderHistory();
    expect(await screen.findByText("Camille Exemple")).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    await user.click(screen.getByRole("button", { name: "Supprimer la clé" }));
    await user.click(screen.getByRole("link", { name: /Historique/ }));

    expect(
      screen.getByText("Une clé API valide est nécessaire."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Camille Exemple")).not.toBeInTheDocument();
  });

  it("charge le PDF uniquement lorsque la prévisualisation est demandée et le libère à la fermeture", async () => {
    const user = userEvent.setup();
    renderHistory();
    await screen.findByText("Léa Martin");
    expect(getDocumentPdf).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Prévisualiser" }));
    expect(await screen.findByLabelText(/Aperçu PDF/)).toHaveAttribute(
      "data",
      "blob:preview",
    );
    expect(getDocumentPdf).toHaveBeenCalledWith(
      "job-completed",
      "cle-valide",
      expect.any(AbortSignal),
    );
    await user.click(
      screen.getByRole("button", { name: "Fermer la prévisualisation" }),
    );
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  });

  it("gère le focus, Escape et sa restauration dans la fenêtre PDF", async () => {
    const user = userEvent.setup();
    renderHistory();
    const opener = await screen.findByRole("button", { name: "Prévisualiser" });
    opener.focus();
    await user.keyboard("{Enter}");
    const close = await screen.findByRole("button", {
      name: "Fermer la prévisualisation",
    });
    expect(close).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("contient la navigation au clavier dans la fenêtre PDF", async () => {
    const user = userEvent.setup();
    renderHistory();
    await user.click(
      await screen.findByRole("button", { name: "Prévisualiser" }),
    );
    const close = await screen.findByRole("button", {
      name: "Fermer la prévisualisation",
    });
    await user.tab({ shift: true });
    expect(
      within(screen.getByRole("dialog")).getByRole("button", { name: "PDF" }),
    ).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();
  });

  it("ferme immédiatement l'aperçu et libère son Blob après suppression de la clé", async () => {
    const user = userEvent.setup();
    renderHistory();
    await user.click(
      await screen.findByRole("button", { name: "Prévisualiser" }),
    );
    await screen.findByLabelText(/Aperçu PDF/);
    await user.click(screen.getByRole("link", { name: /Paramètres/ }));
    await user.click(screen.getByRole("button", { name: "Supprimer la clé" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  });

  it("télécharge le DOCX terminé avec un nom convivial", async () => {
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const user = userEvent.setup();
    renderHistory();
    await screen.findByText("Léa Martin");
    screen.getByRole("button", { name: "DOCX" }).focus();
    await user.keyboard("{Enter}");

    expect(getDocumentDocx).toHaveBeenCalledWith(
      "job-completed",
      "cle-valide",
      expect.any(AbortSignal),
    );
    expect(click).toHaveBeenCalledOnce();
  });

  it("ignore un téléchargement tardif après un changement de document", async () => {
    let resolveDownload: ((blob: Blob) => void) | undefined;
    vi.mocked(getDocumentDocx).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveDownload = resolve;
      }),
    );
    vi.mocked(getDocumentHistory)
      .mockResolvedValueOnce(page())
      .mockResolvedValueOnce(page([{ ...items[2], id: "nouveau-document" }]));
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const user = userEvent.setup();
    renderHistory();
    await user.click(
      (await screen.findAllByRole("button", { name: "DOCX" }))[0],
    );
    await user.selectOptions(
      screen.getByLabelText("Filtrer par statut"),
      "completed",
    );
    await waitFor(() => expect(getDocumentHistory).toHaveBeenCalledTimes(2));
    await act(async () =>
      resolveDownload?.(new Blob(["ancien"], { type: "application/docx" })),
    );
    expect(click).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "DOCX" })).toBeEnabled();
  });

  it("invalide globalement la clé active après un refus 401 de téléchargement", async () => {
    vi.mocked(getDocumentDocx).mockRejectedValue(
      new ApiError({ kind: "http", status: 401, message: "Clé révoquée" }),
    );
    const user = userEvent.setup();
    renderHistory();
    await user.click(
      (await screen.findAllByRole("button", { name: "DOCX" }))[0],
    );
    expect(
      await screen.findByText("Une clé API valide est nécessaire."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Clé révoquée")).not.toBeInTheDocument();
  });
});
