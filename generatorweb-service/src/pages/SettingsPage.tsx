import { CircleHelp, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function SettingsPage() {
  return (
    <div className="w-full space-y-8">
      <PageHeader
        eyebrow="Configuration"
        title="Paramètres"
        description="Cette page accueillera les informations nécessaires pour connecter l'interface à votre espace CV-Generator."
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
        <Card>
          <CardHeader className="sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-x-4">
            <span className="bg-primary/10 text-primary flex size-11 items-center justify-center rounded-xl">
              <KeyRound className="size-5" aria-hidden="true" />
            </span>
            <div>
              <h2 className="font-semibold">Accès à l'API</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Une clé valide sera nécessaire pour accéder à vos documents.
              </p>
            </div>
            <Badge variant="muted" className="mt-2 sm:mt-0">
              Non configurée
            </Badge>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <label htmlFor="api-key" className="text-sm font-semibold">
                Clé API
              </label>
              <div className="relative mt-2">
                <LockKeyhole
                  className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2"
                  aria-hidden="true"
                />
                <input
                  id="api-key"
                  type="password"
                  disabled
                  placeholder="Configuration disponible prochainement"
                  className="border-border bg-muted/40 text-muted-foreground min-h-11 w-full cursor-not-allowed rounded-lg border pr-4 pl-10 text-sm opacity-80"
                />
              </div>
              <p className="text-muted-foreground mt-2 text-xs leading-5">
                Aucune clé n'est actuellement saisie, enregistrée ou transmise.
              </p>
            </div>

            <label className="text-muted-foreground flex cursor-not-allowed items-start gap-3 text-sm opacity-70">
              <input
                type="checkbox"
                disabled
                className="border-border mt-0.5 size-4 rounded"
              />
              <span>
                Mémoriser la clé sur cet appareil
                <span className="mt-1 block text-xs">
                  Cette option sera configurable lors de l'intégration de
                  l'authentification.
                </span>
              </span>
            </label>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <span className="bg-primary/10 text-primary flex size-10 items-center justify-center rounded-xl">
                <ShieldCheck className="size-5" aria-hidden="true" />
              </span>
              <h2 className="mt-2 font-semibold">À propos de votre clé</h2>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-sm leading-6">
                La clé API permettra d'identifier votre espace et de protéger
                l'accès à votre historique. Ne la partagez pas et saisissez-la
                uniquement dans cette interface.
              </p>
            </CardContent>
          </Card>

          <div className="border-border bg-card flex gap-3 rounded-xl border p-4 text-sm shadow-sm">
            <CircleHelp
              className="text-primary mt-0.5 size-5 shrink-0"
              aria-hidden="true"
            />
            <p className="text-muted-foreground leading-6">
              La vérification de connexion sera ajoutée avec les prochains
              outils de configuration.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
