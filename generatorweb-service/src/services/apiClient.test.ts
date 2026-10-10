import { apiRequest } from "@/services/apiClient";

describe("apiRequest", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("applique le timeout sans exposer les en-têtes", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, options?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          options?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        });
      }),
    );

    const request = apiRequest("/documents", {
      apiKey: "secret-ne-doit-pas-apparaitre",
      timeoutMs: 50,
    });
    const rejection = request.catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(51);
    const error = await rejection;

    expect(error).toMatchObject({ kind: "timeout" });
    expect(String(error)).not.toContain("secret-ne-doit-pas-apparaitre");
  });

  it("extrait une erreur FastAPI structurée", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: { code: "invalid_api_key", message: "Clé invalide" },
          }),
          { status: 401 },
        ),
      ),
    );

    await expect(apiRequest("/documents")).rejects.toMatchObject({
      kind: "http",
      status: 401,
      code: "invalid_api_key",
      message: "Clé invalide",
    });
  });
});
