import { useEffect } from "react";

import { ApiError } from "@/services/apiClient";
import { getDocumentJobStatus } from "@/services/documentService";
import type { DocumentJobStatusResponse } from "@/types/document";

export const DOCUMENT_POLLING_INTERVAL_MS = 2_500;

type UseDocumentPollingOptions = {
  jobId: string | null;
  apiKey: string | null;
  enabled: boolean;
  retryToken: number;
  onStatus: (status: DocumentJobStatusResponse) => void;
  onError: (error: ApiError) => void;
};

export function useDocumentPolling({
  jobId,
  apiKey,
  enabled,
  retryToken,
  onStatus,
  onError,
}: UseDocumentPollingOptions) {
  useEffect(() => {
    if (!enabled || !jobId || !apiKey) {
      return;
    }

    let stopped = false;
    let timerId: number | null = null;
    let controller: AbortController | null = null;

    const poll = async () => {
      controller = new AbortController();
      try {
        const status = await getDocumentJobStatus(
          jobId,
          apiKey,
          controller.signal,
        );
        if (stopped) {
          return;
        }
        onStatus(status);
        if (status.status === "completed" || status.status === "failed") {
          stopped = true;
          return;
        }
        timerId = window.setTimeout(poll, DOCUMENT_POLLING_INTERVAL_MS);
      } catch (error) {
        if (
          stopped ||
          (error instanceof ApiError && error.kind === "aborted")
        ) {
          return;
        }
        stopped = true;
        onError(
          error instanceof ApiError
            ? error
            : new ApiError({
                kind: "network",
                message: "Impossible de consulter le statut du document.",
              }),
        );
      }
    };

    timerId = window.setTimeout(poll, DOCUMENT_POLLING_INTERVAL_MS);

    return () => {
      stopped = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
      controller?.abort();
    };
  }, [apiKey, enabled, jobId, onError, onStatus, retryToken]);
}
