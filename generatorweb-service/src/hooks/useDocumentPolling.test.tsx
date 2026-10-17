import { act, renderHook } from "@testing-library/react";

import {
  DOCUMENT_POLLING_INTERVAL_MS,
  useDocumentPolling,
} from "@/hooks/useDocumentPolling";
import { ApiError } from "@/services/apiClient";
import { getDocumentJobStatus } from "@/services/documentService";
import type { DocumentJobStatusResponse } from "@/types/document";

vi.mock("@/services/documentService", () => ({
  getDocumentJobStatus: vi.fn(),
}));

const processing: DocumentJobStatusResponse = {
  id: "job-1",
  status: "processing",
  created_at: "2026-10-11T08:00:00+11:00",
  started_at: "2026-10-11T08:00:03+11:00",
  completed_at: null,
};

describe("useDocumentPolling", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("enchaîne les consultations sans chevauchement et s'arrête au statut terminal", async () => {
    let resolveFirst: ((value: DocumentJobStatusResponse) => void) | undefined;
    vi.mocked(getDocumentJobStatus)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
      )
      .mockResolvedValueOnce({
        ...processing,
        status: "completed",
        completed_at: "2026-10-11T08:01:00+11:00",
      });
    const onStatus = vi.fn();
    const onError = vi.fn();

    renderHook(() =>
      useDocumentPolling({
        jobId: "job-1",
        apiKey: "cle-api",
        enabled: true,
        retryToken: 0,
        onStatus,
        onError,
      }),
    );

    await act(() => vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS));
    expect(getDocumentJobStatus).toHaveBeenCalledOnce();

    await act(() =>
      vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS * 4),
    );
    expect(getDocumentJobStatus).toHaveBeenCalledOnce();

    await act(async () => resolveFirst?.(processing));
    expect(onStatus).toHaveBeenCalledWith(processing);
    await act(() => vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS));
    expect(getDocumentJobStatus).toHaveBeenCalledTimes(2);
    expect(onStatus).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: "completed" }),
    );

    await act(() =>
      vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS * 3),
    );
    expect(getDocumentJobStatus).toHaveBeenCalledTimes(2);
    expect(onError).not.toHaveBeenCalled();
  });

  it("s'arrête définitivement lorsque le job est annulé", async () => {
    const cancelled = {
      ...processing,
      status: "cancelled" as const,
      cancelled_at: "2026-10-11T08:00:05+11:00",
    };
    vi.mocked(getDocumentJobStatus).mockResolvedValue(cancelled);
    const onStatus = vi.fn();

    renderHook(() =>
      useDocumentPolling({
        jobId: "job-1",
        apiKey: "cle-api",
        enabled: true,
        retryToken: 0,
        onStatus,
        onError: vi.fn(),
      }),
    );

    await act(() => vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS));
    expect(onStatus).toHaveBeenCalledWith(cancelled);
    await act(() =>
      vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS * 4),
    );
    expect(getDocumentJobStatus).toHaveBeenCalledOnce();
  });

  it("interrompt le suivi sur erreur et permet une reprise explicite", async () => {
    const failure = new ApiError({
      kind: "network",
      message: "Connexion interrompue",
    });
    vi.mocked(getDocumentJobStatus)
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(processing);
    const onStatus = vi.fn();
    const onError = vi.fn();
    const { rerender } = renderHook(
      ({ retryToken }) =>
        useDocumentPolling({
          jobId: "job-1",
          apiKey: "cle-api",
          enabled: true,
          retryToken,
          onStatus,
          onError,
        }),
      { initialProps: { retryToken: 0 } },
    );

    await act(() => vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS));
    expect(onError).toHaveBeenCalledWith(failure);
    await act(() =>
      vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS * 2),
    );
    expect(getDocumentJobStatus).toHaveBeenCalledOnce();

    rerender({ retryToken: 1 });
    await act(() => vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS));
    expect(getDocumentJobStatus).toHaveBeenCalledTimes(2);
    expect(onStatus).toHaveBeenCalledWith(processing);
  });

  it("ignore la réponse d'un ancien job après nettoyage", async () => {
    let resolveOld: ((value: DocumentJobStatusResponse) => void) | undefined;
    vi.mocked(getDocumentJobStatus).mockReturnValue(
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
    );
    const onStatus = vi.fn();
    const { rerender } = renderHook(
      ({ jobId }) =>
        useDocumentPolling({
          jobId,
          apiKey: "cle-api",
          enabled: true,
          retryToken: 0,
          onStatus,
          onError: vi.fn(),
        }),
      { initialProps: { jobId: "ancien-job" } },
    );

    await act(() => vi.advanceTimersByTimeAsync(DOCUMENT_POLLING_INTERVAL_MS));
    rerender({ jobId: "nouveau-job" });
    await act(async () => resolveOld?.({ ...processing, id: "ancien-job" }));

    expect(onStatus).not.toHaveBeenCalled();
  });
});
