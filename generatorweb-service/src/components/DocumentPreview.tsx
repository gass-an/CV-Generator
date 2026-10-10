import { Download, FileSearch, LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export function DocumentPreview() {
  return (
    <Card className="overflow-hidden py-0 lg:sticky lg:top-28">
      <div className="border-border flex items-center justify-between border-b px-5 py-4 sm:px-6">
        <div>
          <h2 className="font-semibold">Aperçu du document</h2>
          <p className="text-muted-foreground mt-0.5 text-xs">
            Le futur PDF apparaîtra ici
          </p>
        </div>
        <Badge variant="outline">En attente</Badge>
      </div>

      <div className="bg-muted/60 p-4 sm:p-6">
        <div className="bg-card border-border mx-auto flex aspect-[1/1.32] min-h-80 max-w-md flex-col items-center justify-center rounded-lg border shadow-sm">
          <span className="bg-primary/8 text-primary flex size-14 items-center justify-center rounded-2xl">
            <FileSearch className="size-7" aria-hidden="true" />
          </span>
          <p className="mt-5 px-6 text-center font-semibold">
            Aucun document à prévisualiser
          </p>
          <p className="text-muted-foreground mt-2 max-w-xs px-6 text-center text-sm leading-6">
            L’aperçu sera disponible après la génération de votre document.
          </p>
        </div>
      </div>

      <div className="border-border space-y-4 border-t px-5 py-5 sm:px-6">
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <LoaderCircle className="size-4" aria-hidden="true" />
          <span>Le suivi de la génération apparaîtra ici.</span>
        </div>
        <div
          className="grid grid-cols-2 gap-3"
          aria-label="Futurs téléchargements"
        >
          <button
            type="button"
            disabled
            className="border-border text-muted-foreground flex min-h-11 cursor-not-allowed items-center justify-center gap-2 rounded-lg border text-sm font-semibold opacity-60"
          >
            <Download className="size-4" aria-hidden="true" />
            DOCX
          </button>
          <button
            type="button"
            disabled
            className="border-border text-muted-foreground flex min-h-11 cursor-not-allowed items-center justify-center gap-2 rounded-lg border text-sm font-semibold opacity-60"
          >
            <Download className="size-4" aria-hidden="true" />
            PDF
          </button>
        </div>
      </div>
    </Card>
  );
}
