import { apiRequest, apiRequestBody } from "@/services/apiClient";

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

  it("maintient le timeout pendant la lecture complète du corps", async () => {
    vi.useFakeTimers();
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, options?: RequestInit) => {
        requestSignal = options?.signal ?? undefined;
        return Promise.resolve(new Response("ok"));
      }),
    );

    const request = apiRequestBody(
      "/documents/fichier",
      { timeoutMs: 50 },
      () =>
        new Promise<Blob>((_resolve, reject) => {
          requestSignal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    const rejection = request.catch((error: unknown) => error);
    await vi.advanceTimersByTimeAsync(51);
    expect(await rejection).toMatchObject({ kind: "timeout" });
  });

  it("distingue une annulation volontaire pendant la lecture", async () => {
    const controller = new AbortController();
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, options?: RequestInit) => {
        requestSignal = options?.signal ?? undefined;
        return Promise.resolve(new Response("ok"));
      }),
    );
    const request = apiRequestBody(
      "/documents/fichier",
      { timeoutMs: 1000, signal: controller.signal },
      () =>
        new Promise<Blob>((_resolve, reject) => {
          requestSignal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    await Promise.resolve();
    controller.abort();
    await expect(request).rejects.toMatchObject({ kind: "aborted" });
  });

  it("termine une lecture binaire avant expiration", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("ok")));
    await expect(
      apiRequestBody(
        "/documents/fichier",
        { timeoutMs: 1000 },
        async () => new Blob(["fichier"]),
      ),
    ).resolves.toBeInstanceOf(Blob);
  });
});
