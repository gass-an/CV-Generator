import {
  ASCIIDOC_MEDIA_TYPE,
  createDocumentJob,
  DOCX_MEDIA_TYPE,
  getDocumentAvpNumbers,
  getDocumentDocx,
  getDocumentExport,
  getDocumentHistory,
  getDocumentJobStatus,
  getDocumentPdf,
  MARKDOWN_MEDIA_TYPE,
  PDF_TIMEOUT_MS,
  PDF_MEDIA_TYPE,
} from "@/services/documentService";
import type { DocumentType } from "@/types/document";

const payload = {
  avp_number: "3134-26-1382/SR",
  resume: {
    basics: { name: "Camille Exemple" },
    work: [],
    extension_personnalisee: { permis: "B" },
  },
};

describe("documentService", () => {
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it.each<[DocumentType, string]>([
    ["cv", "/api/v1/documents/cv"],
    ["cover_letter", "/api/v1/documents/cover-letter"],
    ["interview_prep", "/api/v1/documents/interview-prep"],
  ])("crée un job %s avec le payload exact", async (type, expectedPath) => {
    const fetchMock = vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1", status: "pending" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(createDocumentJob(type, payload, "cle-api")).resolves.toEqual({
      id: "job-1",
      status: "pending",
    });

    const [path, options] = fetchMock.mock.calls[0];
    expect(path).toBe(expectedPath);
    expect(options?.method).toBe("POST");
    expect(new Headers(options?.headers).get("X-API-Key")).toBe("cle-api");
    expect(JSON.parse(String(options?.body))).toEqual(payload);
  });

  it("consulte le statut du job sans créer une nouvelle demande", async () => {
    const fetchMock = vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "job/avec espace",
          status: "processing",
          created_at: "2026-10-11T08:00:00+11:00",
          started_at: "2026-10-11T08:00:03+11:00",
          completed_at: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const status = await getDocumentJobStatus("job/avec espace", "cle-api");

    expect(status.status).toBe("processing");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/documents/job%2Favec%20espace/status",
    );
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("GET");
  });

  it("applique les filtres et la pagination à l'historique", async () => {
    const fetchMock = vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, limit: 20, offset: 20 }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await getDocumentHistory(
      {
        limit: 20,
        offset: 20,
        documentType: "cover_letter",
        status: "completed",
        avpNumber: "3134-26-1382/SR",
      },
      "cle-api",
    );

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/documents?limit=20&offset=20&document_type=cover_letter&status=completed&avp_number=3134-26-1382%2FSR",
    );
  });

  it("récupère les AVP distincts avec la clé active", async () => {
    const fetchMock = vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ items: ["AVP-1", "AVP-2"] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getDocumentAvpNumbers("cle-api")).resolves.toEqual([
      "AVP-1",
      "AVP-2",
    ]);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/documents/avp-numbers");
    expect(
      new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("X-API-Key"),
    ).toBe("cle-api");
  });

  it.each([
    ["pdf", getDocumentPdf, "/api/v1/documents/job-1/pdf", PDF_MEDIA_TYPE],
    ["docx", getDocumentDocx, "/api/v1/documents/job-1/docx", DOCX_MEDIA_TYPE],
  ] as const)(
    "récupère le Blob %s authentifié",
    async (_format, loader, path, mediaType) => {
      const fetchMock = vi.mocked(fetch).mockResolvedValue(
        new Response("document", {
          status: 200,
          headers: { "Content-Type": mediaType },
        }),
      );

      const blob = await loader("job-1", "cle-secrete");

      expect(blob.type).toBe(mediaType);
      expect(fetchMock.mock.calls[0]?.[0]).toBe(path);
      expect(
        new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("X-API-Key"),
      ).toBe("cle-secrete");
      expect(String(fetchMock.mock.calls[0]?.[0])).not.toContain("cle-secrete");
    },
  );

  it.each([
    ["adoc", "/api/v1/documents/job-1/adoc", ASCIIDOC_MEDIA_TYPE],
    ["md", "/api/v1/documents/job-1/md", MARKDOWN_MEDIA_TYPE],
  ] as const)(
    "récupère le Blob %s via la configuration centralisée",
    async (format, path, mediaType) => {
      const fetchMock = vi.mocked(fetch).mockResolvedValue(
        new Response("document", {
          status: 200,
          headers: { "Content-Type": `${mediaType}; charset=utf-8` },
        }),
      );

      await getDocumentExport("job-1", "cle-secrete", format);

      expect(fetchMock.mock.calls[0]?.[0]).toBe(path);
      expect(
        new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("X-API-Key"),
      ).toBe("cle-secrete");
    },
  );

  it("refuse une réponse JSON présentée à la place d'un PDF", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: { message: "Erreur" } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getDocumentPdf("job-1", "cle-api")).rejects.toMatchObject({
      code: "invalid_document_media_type",
    });
  });

  it("accorde 90 secondes à la conversion PDF sans modifier le timeout général", async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockImplementation(
      (_input, options) =>
        new Promise((_resolve, reject) => {
          options?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );

    const request = getDocumentPdf("job-1", "cle-api");
    const rejection = expect(request).rejects.toMatchObject({
      kind: "timeout",
    });
    await vi.advanceTimersByTimeAsync(PDF_TIMEOUT_MS);
    await rejection;
  });
});
