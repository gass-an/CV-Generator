import { Download, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useAppState } from "@/hooks/useAppState";
import { documentFilename, triggerBlobDownload } from "@/lib/documentFiles";
import { ApiError } from "@/services/apiClient";
import { getDocumentDocx, getDocumentPdf } from "@/services/documentService";
import type { DocumentMetadata } from "@/types/document";

type DownloadFormat = "docx" | "pdf";

export function DocumentDownloadActions({
  document,
  compact = false,
}: {
  document: DocumentMetadata;
  compact?: boolean;
}) {
  const { auth } = useAppState();
  const [activeFormat, setActiveFormat] = useState<DownloadFormat | null>(null);
  const [message, setMessage] = useState<{
    kind: "success" | "error";
    text: string;
  } | null>(null);
  const available = document.status === "completed" && auth.activeApiKey;
  const controller = useRef<AbortController | null>(null);
  const operation = useRef(0);

  useEffect(() => {
    const currentOperation = ++operation.current;
    controller.current?.abort();
    controller.current = null;
    queueMicrotask(() => {
      if (operation.current !== currentOperation) return;
      setActiveFormat(null);
      setMessage(null);
    });
    return () => {
      operation.current += 1;
      controller.current?.abort();
      controller.current = null;
    };
  }, [auth.activeApiKey, document.id]);

  async function download(format: DownloadFormat) {
    if (!available || activeFormat) return;
    const apiKey = auth.activeApiKey!;
    const currentOperation = ++operation.current;
    const requestController = new AbortController();
    controller.current?.abort();
    controller.current = requestController;
    setActiveFormat(format);
    setMessage(null);
    try {
      const blob =
        format === "pdf"
          ? await getDocumentPdf(document.id, apiKey, requestController.signal)
          : await getDocumentDocx(
              document.id,
              apiKey,
              requestController.signal,
            );
      if (
        requestController.signal.aborted ||
        controller.current !== requestController ||
        operation.current !== currentOperation
      )
        return;
      triggerBlobDownload(blob, documentFilename(document, format));
      setMessage({
        kind: "success",
        text: `Téléchargement ${format.toUpperCase()} lancé.`,
      });
    } catch (error) {
      if (
        operation.current !== currentOperation ||
        (error instanceof ApiError && error.kind === "aborted")
      )
        return;
      if (error instanceof ApiError && error.status === 401) {
        auth.reportApiKeyRejected(apiKey);
        return;
      }
      setMessage({
        kind: "error",
        text:
          error instanceof ApiError
            ? error.message
            : "Le téléchargement a échoué.",
      });
    } finally {
      if (
        controller.current === requestController &&
        operation.current === currentOperation
      ) {
        controller.current = null;
        setActiveFormat(null);
      }
    }
  }

  return (
    <div className="space-y-2">
      <div className={`grid grid-cols-2 gap-2 ${compact ? "text-xs" : ""}`}>
        {(["docx", "pdf"] as const).map((format) => (
          <button
            key={format}
            type="button"
            disabled={!available || activeFormat !== null}
            onClick={() => void download(format)}
            className="border-border text-primary hover:bg-primary/5 disabled:bg-muted disabled:text-muted-foreground flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3 font-semibold transition-colors disabled:cursor-not-allowed"
          >
            {activeFormat === format ? (
              <LoaderCircle
                className="size-4 animate-spin"
                aria-hidden="true"
              />
            ) : (
              <Download className="size-4" aria-hidden="true" />
            )}
            {format.toUpperCase()}
          </button>
        ))}
      </div>
      {message ? (
        <p
          className={`text-xs ${message.kind === "error" ? "text-accent" : "text-primary"}`}
          role={message.kind === "error" ? "alert" : "status"}
        >
          {message.text}
        </p>
      ) : null}
    </div>
  );
}
