const API_BASE_PATH = "/api/v1";
const DEFAULT_TIMEOUT_MS = 8_000;

type FastApiErrorBody = {
  detail?: {
    code?: unknown;
    message?: unknown;
  };
};

export type ApiErrorKind = "http" | "network" | "timeout" | "aborted";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string | null;

  constructor(options: {
    message: string;
    kind: ApiErrorKind;
    status?: number;
    code?: string;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.kind = options.kind;
    this.status = options.status ?? null;
    this.code = options.code ?? null;
  }
}

type ApiRequestOptions = Omit<RequestInit, "headers"> & {
  apiKey?: string;
  headers?: HeadersInit;
  timeoutMs?: number;
};

function combineSignals(signals: AbortSignal[]): AbortSignal {
  if (signals.length === 1) {
    return signals[0];
  }
  return AbortSignal.any(signals);
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  let body: FastApiErrorBody | null = null;
  try {
    body = (await response.json()) as FastApiErrorBody;
  } catch {
    // Une réponse non JSON reste représentée par son statut HTTP.
  }
  const detail = body?.detail;
  return new ApiError({
    kind: "http",
    status: response.status,
    code: typeof detail?.code === "string" ? detail.code : undefined,
    message:
      typeof detail?.message === "string"
        ? detail.message
        : `Le service a répondu avec le statut ${response.status}.`,
  });
}

async function executeRequest<T>(
  path: string,
  options: ApiRequestOptions,
  consume: (response: Response) => Promise<T>,
): Promise<T> {
  const {
    apiKey,
    headers: inputHeaders,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal,
    ...requestOptions
  } = options;
  const headers = new Headers(inputHeaders);
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }

  const timeoutController = new AbortController();
  const timeoutId = window.setTimeout(
    () => timeoutController.abort(),
    timeoutMs,
  );
  const requestSignal = signal
    ? combineSignals([signal, timeoutController.signal])
    : timeoutController.signal;

  try {
    const response = await fetch(`${API_BASE_PATH}${path}`, {
      ...requestOptions,
      headers,
      signal: requestSignal,
    });
    if (!response.ok) {
      throw await errorFromResponse(response);
    }
    return await consume(response);
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (requestSignal.aborted) {
      const timedOut = timeoutController.signal.aborted && !signal?.aborted;
      throw new ApiError({
        kind: timedOut ? "timeout" : "aborted",
        message: timedOut
          ? "Le service met trop de temps à répondre. Réessayez plus tard."
          : "La requête a été annulée.",
      });
    }
    throw new ApiError({
      kind: "network",
      message:
        "Impossible de joindre le service. Vérifiez votre connexion puis réessayez.",
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export function apiRequest(
  path: string,
  options: ApiRequestOptions = {},
): Promise<Response> {
  return executeRequest(path, options, async (response) => response);
}

export function apiRequestBody<T>(
  path: string,
  options: ApiRequestOptions,
  consume: (response: Response) => Promise<T>,
): Promise<T> {
  return executeRequest(path, options, consume);
}
