import {
  CircleCheck,
  CircleX,
  Download,
  FileSearch,
  LoaderCircle,
  Send,
  WifiOff,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useAppState } from "@/hooks/useAppState";
import { documentTypeLabels } from "@/types/document";

export function DocumentPreview() {
  const { auth, generation } = useAppState();
  const state = generation.state;
  const request =
    state.phase === "idle"
      ? null
      : state.phase === "creating" || state.phase === "creation_error"
        ? state.request
        : state.job;
  const job =
    state.phase === "pending" ||
    state.phase === "processing" ||
    state.phase === "completed" ||
    state.phase === "failed" ||
    state.phase === "interrupted"
      ? state.job
      : null;
  const isRunning =
    state.phase === "creating" ||
    state.phase === "pending" ||
    state.phase === "processing";

  const content = (() => {
    switch (state.phase) {
      case "idle":
        return {
          badge: "En attente",
          variant: "outline" as const,
          icon: FileSearch,
          title: "Aucun document à prévisualiser",
          description:
            "L’aperçu sera disponible après la génération de votre document.",
        };
      case "creating":
        return {
          badge: "Envoi",
          variant: "outline" as const,
          icon: Send,
          title: "Envoi de votre demande…",
          description:
            "La demande est transmise une seule fois au service de génération.",
        };
      case "pending":
        return {
          badge: "En attente",
          variant: "outline" as const,
          icon: LoaderCircle,
          title: "Votre document est en attente de traitement.",
          description:
            "Le worker prendra en charge la demande dès qu'il sera disponible.",
        };
      case "processing":
        return {
          badge: "En cours",
          variant: "default" as const,
          icon: LoaderCircle,
          title: "L'IA prépare votre document…",
          description:
            "Le contenu est en cours de génération. Cette opération peut prendre quelques instants.",
        };
      case "completed":
        return {
          badge: "Terminé",
          variant: "default" as const,
          icon: CircleCheck,
          title: "Votre document est prêt !",
          description:
            "La prévisualisation PDF et les téléchargements seront activés à la prochaine étape.",
        };
      case "failed":
        return {
          badge: "Échec",
          variant: "accent" as const,
          icon: CircleX,
          title: "La génération du document a échoué.",
          description:
            "Aucun détail supplémentaire n'est fourni par le suivi. Vous pouvez lancer une nouvelle génération.",
        };
      case "interrupted":
        return {
          badge: "Suivi interrompu",
          variant: "accent" as const,
          icon: WifiOff,
          title: "Connexion interrompue",
          description: state.message,
        };
      case "creation_error":
        return {
          badge: "Demande non confirmée",
          variant: "accent" as const,
          icon: state.uncertain ? WifiOff : CircleX,
          title: state.uncertain
            ? "La création du job n'a pas pu être confirmée."
            : "La demande n'a pas pu être créée.",
          description: state.message,
        };
    }
  })();
  const StatusIcon = content.icon;

  return (
    <Card className="overflow-hidden py-0 lg:sticky lg:top-28">
      <div className="border-border flex items-center justify-between gap-3 border-b px-5 py-4 sm:px-6">
        <div>
          <h2 className="font-semibold">Suivi du document</h2>
          <p className="text-muted-foreground mt-0.5 text-xs">
            Statut réel communiqué par le backend
          </p>
        </div>
        <Badge variant={content.variant}>{content.badge}</Badge>
      </div>

      <div className="bg-muted/60 p-4 sm:p-6">
        <div className="bg-card border-border mx-auto flex aspect-[1/1.32] min-h-80 max-w-md flex-col items-center justify-center rounded-lg border px-5 text-center shadow-sm">
          <span className="bg-primary/8 text-primary flex size-14 items-center justify-center rounded-2xl">
            <StatusIcon
              className={`size-7 ${isRunning && state.phase !== "creating" ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
          </span>
          <p className="mt-5 font-semibold">{content.title}</p>
          <p className="text-muted-foreground mt-2 max-w-xs text-sm leading-6">
            {content.description}
          </p>

          {request ? (
            <dl className="border-border mt-6 w-full max-w-xs space-y-2 border-t pt-4 text-left text-xs">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Document</dt>
                <dd className="text-right font-semibold">
                  {documentTypeLabels[request.documentType]}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">AVP</dt>
                <dd className="text-right font-semibold break-all">
                  {request.avpNumber}
                </dd>
              </div>
              {job ? (
                <div className="flex flex-col gap-1 pt-1">
                  <dt className="text-muted-foreground">Identifiant du job</dt>
                  <dd className="font-mono text-[11px] break-all">{job.id}</dd>
                </div>
              ) : null}
            </dl>
          ) : null}

          {state.phase === "interrupted" ? (
            <div className="mt-5 flex w-full max-w-xs flex-col gap-2">
              {auth.status === "valid" ? (
                <button
                  type="button"
                  onClick={generation.resumeTracking}
                  className="bg-primary text-primary-foreground hover:bg-primary/90 min-h-11 rounded-lg px-4 text-sm font-semibold transition-colors"
                >
                  Reprendre le suivi
                </button>
              ) : (
                <Link
                  to="/parametres"
                  className="text-primary hover:bg-primary/8 flex min-h-11 items-center justify-center rounded-lg px-4 text-sm font-semibold"
                >
                  Vérifier la clé API
                </Link>
              )}
              <button
                type="button"
                onClick={generation.stopTracking}
                className="text-muted-foreground hover:bg-muted min-h-11 rounded-lg px-4 text-sm font-semibold transition-colors"
              >
                Arrêter le suivi
              </button>
              <p className="text-muted-foreground text-xs leading-5">
                Cette action arrête seulement le suivi dans ce navigateur. Le
                traitement continue côté serveur.
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <div className="border-border space-y-4 border-t px-5 py-5 sm:px-6">
        <p className="text-muted-foreground text-sm">
          {state.phase === "completed"
            ? "Les actions de téléchargement seront disponibles prochainement."
            : isRunning
              ? "Le suivi se met à jour automatiquement, sans estimation artificielle."
              : "Les téléchargements restent indisponibles pour le moment."}
        </p>
        <div
          className="grid grid-cols-2 gap-3"
          aria-label="Futurs téléchargements"
        >
          {(["DOCX", "PDF"] as const).map((format) => (
            <button
              key={format}
              type="button"
              disabled
              className="border-border text-muted-foreground flex min-h-11 cursor-not-allowed items-center justify-center gap-2 rounded-lg border text-sm font-semibold opacity-60"
            >
              <Download className="size-4" aria-hidden="true" />
              {format}
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}
