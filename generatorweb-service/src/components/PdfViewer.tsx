import { FileWarning, LoaderCircle, RefreshCw } from "lucide-react";

import { usePdfPreview } from "@/hooks/usePdfPreview";
import type { PdfPreviewState } from "@/hooks/usePdfPreview";

export function PdfPreviewContent({
  state,
  title,
  onRetry,
}: {
  state: PdfPreviewState;
  title: string;
  onRetry: () => void;
}) {
  if (state.status === "ready") {
    return (
      <object
        data={state.url}
        type="application/pdf"
        aria-label={title}
        className="h-[50svh] min-h-64 w-full rounded-lg border sm:h-[65vh] sm:min-h-[480px]"
      >
        <p className="text-muted-foreground p-5 text-sm">
          Votre navigateur ne peut pas afficher ce PDF. Utilisez le bouton de
          téléchargement PDF.
        </p>
      </object>
    );
  }

  if (state.status === "loading") {
    return (
      <div className="flex min-h-80 flex-col items-center justify-center text-center">
        <LoaderCircle
          className="text-primary size-8 animate-spin"
          aria-hidden="true"
        />
        <p className="mt-4 font-semibold">Préparation de l'aperçu PDF…</p>
        <p className="text-muted-foreground mt-1 text-sm">
          La conversion peut prendre jusqu'à une minute.
        </p>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="flex min-h-80 flex-col items-center justify-center px-5 text-center">
        <FileWarning className="text-accent size-9" aria-hidden="true" />
        <p className="mt-4 font-semibold">Aperçu PDF indisponible</p>
        <p className="text-muted-foreground mt-2 max-w-sm text-sm">
          {state.message}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="border-border text-primary hover:bg-primary/5 mt-4 flex min-h-11 items-center gap-2 rounded-lg border px-4 text-sm font-semibold"
        >
          <RefreshCw className="size-4" aria-hidden="true" />
          Réessayer
        </button>
      </div>
    );
  }

  return null;
}

export function PdfViewer({
  documentId,
  apiKey,
  enabled,
  title,
  onApiKeyRejected,
}: {
  documentId: string | null;
  apiKey: string | null;
  enabled: boolean;
  title: string;
  onApiKeyRejected?: (apiKey: string) => void;
}) {
  const preview = usePdfPreview({
    documentId,
    apiKey,
    enabled,
    onApiKeyRejected,
  });

  return (
    <PdfPreviewContent
      state={preview.state}
      title={title}
      onRetry={preview.retry}
    />
  );
}
