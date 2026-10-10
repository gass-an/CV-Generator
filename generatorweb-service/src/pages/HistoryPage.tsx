import { CalendarDays, FileClock, FileText, Search } from "lucide-react";

import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Card } from "@/components/ui/card";

export function HistoryPage() {
  return (
    <div className="w-full space-y-8">
      <PageHeader
        eyebrow="Vos candidatures"
        title="Historique des documents"
        description="Retrouvez ici vos générations, leur état et, prochainement, leurs options de prévisualisation et de téléchargement."
      />

      <Card className="overflow-hidden py-0">
        <div className="border-border bg-muted/30 hidden grid-cols-[1.2fr_1fr_1fr_0.8fr] gap-4 border-b px-6 py-3 text-xs font-bold tracking-wide uppercase lg:grid">
          <span className="flex items-center gap-2">
            <FileText className="size-3.5" aria-hidden="true" />
            Document
          </span>
          <span>Candidat</span>
          <span>AVP et date</span>
          <span>Statut</span>
        </div>
        <EmptyState
          icon={FileClock}
          title="Aucun document à afficher pour le moment"
          description="Vos futurs CV, lettres de motivation et guides d'entretien apparaîtront ici après leur génération."
        >
          <div className="text-muted-foreground mt-6 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs">
            <span className="flex items-center gap-1.5">
              <Search className="size-3.5" aria-hidden="true" />
              Recherche à venir
            </span>
            <span className="flex items-center gap-1.5">
              <CalendarDays className="size-3.5" aria-hidden="true" />
              Tri chronologique
            </span>
          </div>
        </EmptyState>
      </Card>
    </div>
  );
}
