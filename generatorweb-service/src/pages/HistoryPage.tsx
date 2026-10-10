import { History } from "lucide-react";

import { PageIntro } from "@/components/layout/PageIntro";

export function HistoryPage() {
  return (
    <PageIntro
      title="Historique"
      description="Retrouvez ici les documents générés et suivez l'état de vos demandes."
      icon={History}
    />
  );
}
