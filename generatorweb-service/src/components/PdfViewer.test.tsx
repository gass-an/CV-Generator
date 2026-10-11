import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PdfViewer } from "@/components/PdfViewer";
import { ApiError } from "@/services/apiClient";
import { getDocumentPdf } from "@/services/documentService";

vi.mock("@/services/documentService", () => ({ getDocumentPdf: vi.fn() }));

describe("PdfViewer", () => {
  beforeEach(() => {
    vi.mocked(getDocumentPdf).mockReset();
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:pdf");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  afterEach(() => vi.restoreAllMocks());

  it("affiche un Blob PDF puis libère son URL au démontage", async () => {
    vi.mocked(getDocumentPdf).mockResolvedValue(
      new Blob(["%PDF"], { type: "application/pdf" }),
    );
    const { unmount } = render(
      <PdfViewer
        documentId="job-1"
        apiKey="cle-api"
        enabled
        title="Aperçu test"
      />,
    );

    expect(await screen.findByLabelText("Aperçu test")).toHaveAttribute(
      "data",
      "blob:pdf",
    );
    unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:pdf");
  });

  it.each([
    new ApiError({
      kind: "http",
      status: 409,
      message: "Document indisponible",
    }),
    new ApiError({ kind: "http", status: 500, message: "Conversion échouée" }),
    new ApiError({ kind: "timeout", message: "Conversion trop longue" }),
  ])(
    "affiche l'erreur contrôlée et permet une tentative manuelle",
    async (error) => {
      vi.mocked(getDocumentPdf)
        .mockRejectedValueOnce(error)
        .mockResolvedValueOnce(new Blob(["%PDF"], { type: "application/pdf" }));
      const user = userEvent.setup();
      render(
        <PdfViewer
          documentId="job-1"
          apiKey="cle-api"
          enabled
          title="Aperçu test"
        />,
      );

      expect(await screen.findByText(error.message)).toBeInTheDocument();
      expect(getDocumentPdf).toHaveBeenCalledOnce();
      await user.click(screen.getByRole("button", { name: "Réessayer" }));
      expect(await screen.findByLabelText("Aperçu test")).toBeInTheDocument();
      expect(getDocumentPdf).toHaveBeenCalledTimes(2);
    },
  );

  it("ignore le Blob tardif d'un ancien document", async () => {
    let resolveOld: ((value: Blob) => void) | undefined;
    vi.mocked(getDocumentPdf)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
      )
      .mockResolvedValueOnce(
        new Blob(["nouveau"], { type: "application/pdf" }),
      );
    const { rerender } = render(
      <PdfViewer documentId="ancien" apiKey="cle-api" enabled title="Aperçu" />,
    );
    rerender(
      <PdfViewer
        documentId="nouveau"
        apiKey="cle-api"
        enabled
        title="Aperçu"
      />,
    );
    expect(await screen.findByLabelText("Aperçu")).toBeInTheDocument();

    resolveOld?.(new Blob(["ancien"], { type: "application/pdf" }));
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledOnce());
  });

  it("signale uniquement un véritable refus 401 de la clé active", async () => {
    const rejected = vi.fn();
    vi.mocked(getDocumentPdf).mockRejectedValue(
      new ApiError({ kind: "http", status: 401, message: "Clé refusée" }),
    );
    render(
      <PdfViewer
        documentId="job-1"
        apiKey="cle-api"
        enabled
        title="Aperçu"
        onApiKeyRejected={rejected}
      />,
    );
    await waitFor(() => expect(rejected).toHaveBeenCalledWith("cle-api"));
    expect(screen.queryByText("Clé refusée")).not.toBeInTheDocument();
  });
});
