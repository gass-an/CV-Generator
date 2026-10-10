import { Settings } from "lucide-react";

import { PageIntro } from "@/components/layout/PageIntro";

export function SettingsPage() {
  return (
    <PageIntro
      title="Paramètres"
      description="Configurez ici l'accès à l'API et les préférences de l'interface."
      icon={Settings}
    />
  );
}
