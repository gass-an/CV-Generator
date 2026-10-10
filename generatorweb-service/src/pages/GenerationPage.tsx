import { FilePlus2 } from "lucide-react";

import { PageIntro } from "@/components/layout/PageIntro";

export function GenerationPage() {
  return (
    <PageIntro
      title="Génération de documents"
      description="Créez un CV, une lettre de motivation ou un guide de préparation à l'entretien adapté à un avis de vacance de poste."
      icon={FilePlus2}
    />
  );
}
