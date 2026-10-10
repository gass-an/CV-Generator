import { FilePlus2, History, Settings } from "lucide-react";

export const navigationItems = [
  { label: "Générer", to: "/", icon: FilePlus2, end: true },
  { label: "Historique", to: "/historique", icon: History, end: false },
  { label: "Paramètres", to: "/parametres", icon: Settings, end: false },
] as const;
