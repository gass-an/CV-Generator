import { documentFilename, triggerBlobDownload } from "@/lib/documentFiles";

describe("documentFiles", () => {
  it("construit un nom lisible et nettoie les caractères interdits", () => {
    expect(
      documentFilename(
        {
          id: "job-1",
          documentType: "cover_letter",
          status: "completed",
          avpNumber: "3134/26:1382 SR",
          candidateName: "Camille Éxemple",
          createdAt: "2026-10-11T08:00:00+11:00",
        },
        "pdf",
      ),
    ).toBe("lettre-motivation_Camille-Exemple_3134-26-1382-SR_2026-10-11.pdf");
  });

  it("utilise des valeurs de remplacement lorsque les métadonnées manquent", () => {
    const filename = documentFilename(
      {
        id: "job-1",
        documentType: "interview_prep",
        status: "completed",
        avpNumber: "",
        candidateName: null,
        createdAt: "invalide",
      },
      "docx",
    );
    expect(filename).toBe(
      "preparation-entretien_candidat_avp_date-inconnue.docx",
    );
  });

  it("déclenche puis libère un téléchargement Blob après un délai", async () => {
    vi.useFakeTimers();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    const create = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:fichier");
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);

    triggerBlobDownload(new Blob(["fichier"]), "document.pdf");

    expect(create).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revoke).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1_000);
    expect(revoke).toHaveBeenCalledWith("blob:fichier");
    vi.useRealTimers();
  });

  it("nettoie le lien et l'URL même si le clic échoue", async () => {
    vi.useFakeTimers();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("clic impossible");
    });
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:erreur");
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);

    expect(() =>
      triggerBlobDownload(new Blob(["fichier"]), "document.pdf"),
    ).toThrow("clic impossible");
    expect(document.querySelector('a[href="blob:erreur"]')).toBeNull();
    expect(revoke).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1_000);
    expect(revoke).toHaveBeenCalledWith("blob:erreur");
    vi.useRealTimers();
  });
});
