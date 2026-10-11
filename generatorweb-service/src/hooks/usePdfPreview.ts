import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/services/apiClient";
import { getDocumentPdf } from "@/services/documentService";

export type PdfPreviewState =
  | { status: "idle" | "loading" }
  | { status: "ready"; url: string; documentId: string; apiKey: string }
  | { status: "error"; message: string; documentId: string; apiKey: string };

export function usePdfPreview(options: {
  documentId: string | null;
  apiKey: string | null;
  enabled: boolean;
  onApiKeyRejected?: (apiKey: string) => void;
}) {
  const { documentId, apiKey, enabled, onApiKeyRejected } = options;
  const [retryToken, setRetryToken] = useState(0);
  const [state, setState] = useState<PdfPreviewState>({ status: "idle" });
  const objectUrl = useRef<string | null>(null);

  const releaseUrl = useCallback(() => {
    if (objectUrl.current) {
      URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = null;
    }
  }, []);

  useEffect(() => {
    releaseUrl();
    if (!enabled || !documentId || !apiKey) {
      return;
    }
    const controller = new AbortController();
    let current = true;
    queueMicrotask(() => {
      if (current) setState({ status: "loading" });
    });
    getDocumentPdf(documentId, apiKey, controller.signal)
      .then((blob) => {
        if (!current) return;
        const url = URL.createObjectURL(blob);
        objectUrl.current = url;
        setState({ status: "ready", url, documentId, apiKey });
      })
      .catch((error: unknown) => {
        if (
          !current ||
          (error instanceof ApiError && error.kind === "aborted")
        ) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          onApiKeyRejected?.(apiKey);
          return;
        }
        setState({
          status: "error",
          documentId,
          apiKey,
          message:
            error instanceof ApiError
              ? error.message
              : "La prévisualisation PDF est indisponible.",
        });
      });
    return () => {
      current = false;
      controller.abort();
      releaseUrl();
    };
  }, [apiKey, documentId, enabled, onApiKeyRejected, releaseUrl, retryToken]);

  const retry = useCallback(() => setRetryToken((value) => value + 1), []);
  const close = useCallback(() => {
    releaseUrl();
    setState({ status: "idle" });
  }, [releaseUrl]);

  const visibleState: PdfPreviewState =
    !enabled || !documentId
      ? { status: "idle" }
      : (state.status === "ready" || state.status === "error") &&
          (state.documentId !== documentId || state.apiKey !== apiKey)
        ? { status: "loading" }
        : state;

  return { state: visibleState, retry, close };
}
