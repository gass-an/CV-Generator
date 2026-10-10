import {
  createDocumentJob,
  getDocumentJobStatus,
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
  afterEach(() => vi.unstubAllGlobals());

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
});
