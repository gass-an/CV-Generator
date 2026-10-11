import { useState, type FormEvent } from "react";
import {
  CheckCircle2,
  CircleHelp,
  Eye,
  EyeOff,
  KeyRound,
  LoaderCircle,
  LockKeyhole,
  Moon,
  ShieldCheck,
  Sun,
  Trash2,
  TriangleAlert,
} from "lucide-react";

import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useTheme } from "@/app/ThemeProvider";
import { useAppState } from "@/hooks/useAppState";

const statusPresentation = {
  absent: { label: "Non configurée", variant: "muted" as const },
  verifying: { label: "Vérification…", variant: "outline" as const },
  valid: { label: "Connecté", variant: "default" as const },
  rejected: { label: "Clé refusée", variant: "accent" as const },
  unavailable: { label: "Service indisponible", variant: "outline" as const },
};

export function SettingsPage() {
  const { auth } = useAppState();
  const { theme, setTheme } = useTheme();
  const [keyInput, setKeyInput] = useState(auth.credentialKey ?? "");
  const [showKey, setShowKey] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFeedback(null);
    setIsSubmitting(true);
    const result = await auth.authenticate(keyInput, auth.remember);
    setIsSubmitting(false);
    setFeedback(
      result.ok
        ? {
            kind: "success",
            message: "La clé a été vérifiée et enregistrée.",
          }
        : { kind: "error", message: result.message },
    );
  }

  function handleClear() {
    auth.clearCredential();
    setKeyInput("");
    setShowKey(false);
    setFeedback({
      kind: "success",
      message: "La clé API a été supprimée de ce navigateur.",
    });
  }

  const presentation = statusPresentation[auth.status];

  return (
    <div className="w-full space-y-8">
      <PageHeader
        eyebrow="Configuration"
        title="Paramètres"
        description="Personnalisez l'interface et connectez-la à votre espace CV-Generator pour accéder à vos documents."
      />

      <Card>
        <CardHeader className="sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-x-4">
          <span className="bg-primary/10 text-primary flex size-11 items-center justify-center rounded-xl">
            {theme === "dark" ? (
              <Moon className="size-5" aria-hidden="true" />
            ) : (
              <Sun className="size-5" aria-hidden="true" />
            )}
          </span>
          <div>
            <h2 className="font-semibold">Apparence</h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Utilisez une palette sombre adaptée aux environnements peu
              éclairés.
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={theme === "dark"}
            aria-label="Activer le mode sombre"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="relative mt-1 h-11 w-14 shrink-0 rounded-full sm:mt-0"
          >
            <span
              className={`absolute top-2 left-1 h-7 w-12 rounded-full border transition-colors ${
                theme === "dark"
                  ? "border-primary bg-primary"
                  : "border-field-border bg-field"
              }`}
              aria-hidden="true"
            >
              <span
                className={`absolute top-0.5 left-0.5 flex size-5 items-center justify-center rounded-full shadow-sm transition-[transform,background-color] ${
                  theme === "dark"
                    ? "bg-primary-foreground translate-x-5"
                    : "bg-field-border translate-x-0"
                }`}
              >
                {theme === "dark" ? (
                  <Moon className="text-primary size-3" />
                ) : (
                  <Sun className="text-field size-3" />
                )}
              </span>
            </span>
          </button>
        </CardHeader>
      </Card>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
        <Card>
          <CardHeader className="sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-x-4">
            <span className="bg-primary/10 text-primary flex size-11 items-center justify-center rounded-xl">
              <KeyRound className="size-5" aria-hidden="true" />
            </span>
            <div>
              <h2 className="font-semibold">Accès à l'API</h2>
              <p className="text-muted-foreground mt-1 text-sm">
                Seule une clé acceptée par le backend devient active.
              </p>
            </div>
            <Badge variant={presentation.variant} className="mt-2 sm:mt-0">
              {auth.status === "verifying" ? (
                <LoaderCircle
                  className="mr-1.5 size-3.5 animate-spin"
                  aria-hidden="true"
                />
              ) : null}
              {presentation.label}
            </Badge>
          </CardHeader>

          <CardContent>
            <form className="space-y-5" onSubmit={handleSubmit}>
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
                    type={showKey ? "text" : "password"}
                    value={keyInput}
                    autoComplete="off"
                    spellCheck="false"
                    disabled={isSubmitting || auth.status === "verifying"}
                    placeholder="Saisissez votre clé API"
                    onChange={(event) => {
                      setKeyInput(event.target.value);
                      setFeedback(null);
                    }}
                    className="border-field-border bg-field focus-visible:border-primary focus-visible:ring-primary/30 min-h-11 w-full rounded-lg border pr-12 pl-10 text-sm transition-shadow focus-visible:ring-4 focus-visible:outline-none disabled:cursor-wait"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey((visible) => !visible)}
                    disabled={!keyInput || isSubmitting}
                    className="text-muted-foreground hover:text-primary disabled:bg-muted absolute top-1/2 right-1.5 flex size-9 -translate-y-1/2 items-center justify-center rounded-md disabled:cursor-not-allowed"
                    aria-label={
                      showKey ? "Masquer la clé API" : "Afficher la clé API"
                    }
                  >
                    {showKey ? (
                      <EyeOff className="size-4" aria-hidden="true" />
                    ) : (
                      <Eye className="size-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
                <p className="text-muted-foreground mt-2 text-xs leading-5">
                  La clé est envoyée uniquement dans l'en-tête sécurisé
                  X-API-Key lors des appels authentifiés.
                </p>
              </div>

              <label className="flex items-start gap-3 text-sm">
                <input
                  type="checkbox"
                  checked={auth.remember}
                  disabled={isSubmitting}
                  onChange={(event) => auth.setRemember(event.target.checked)}
                  className="border-field-border accent-primary mt-0.5 size-4 rounded"
                />
                <span>
                  <span className="font-semibold">
                    Mémoriser la clé sur cet appareil
                  </span>
                  <span className="text-muted-foreground mt-1 block text-xs leading-5">
                    Sinon, elle sera conservée uniquement pour la session de cet
                    onglet. Le stockage navigateur n'est pas chiffré.
                  </span>
                </span>
              </label>

              {feedback ? (
                <div
                  className={`flex gap-2 rounded-lg border p-3 text-sm ${
                    feedback.kind === "success"
                      ? "border-primary/20 bg-primary/5 text-primary"
                      : "border-accent/20 bg-accent/5 text-accent"
                  }`}
                  role={feedback.kind === "error" ? "alert" : "status"}
                >
                  {feedback.kind === "success" ? (
                    <CheckCircle2
                      className="mt-0.5 size-4 shrink-0"
                      aria-hidden="true"
                    />
                  ) : (
                    <TriangleAlert
                      className="mt-0.5 size-4 shrink-0"
                      aria-hidden="true"
                    />
                  )}
                  <span>{feedback.message}</span>
                </div>
              ) : null}

              {auth.storageError ? (
                <p className="text-accent text-sm" role="alert">
                  {auth.storageError}
                </p>
              ) : null}

              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
                {auth.credentialKey ? (
                  <button
                    type="button"
                    onClick={handleClear}
                    disabled={isSubmitting}
                    className="text-accent hover:bg-accent/8 disabled:bg-muted disabled:text-muted-foreground flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed"
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                    Supprimer la clé
                  </button>
                ) : (
                  <span />
                )}
                <button
                  type="submit"
                  disabled={
                    !keyInput.trim() ||
                    isSubmitting ||
                    auth.status === "verifying"
                  }
                  className="bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground flex min-h-11 items-center justify-center gap-2 rounded-lg px-5 text-sm font-semibold transition-colors disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <LoaderCircle
                      className="size-4 animate-spin"
                      aria-hidden="true"
                    />
                  ) : (
                    <ShieldCheck className="size-4" aria-hidden="true" />
                  )}
                  {auth.credentialKey
                    ? "Vérifier et remplacer"
                    : "Vérifier et enregistrer"}
                </button>
              </div>
            </form>
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
                La clé API identifie votre espace et protège l'accès à votre
                historique. Ne la partagez pas et saisissez-la uniquement dans
                cette interface.
              </p>
            </CardContent>
          </Card>

          <div className="border-border bg-card flex gap-3 rounded-xl border p-4 text-sm shadow-sm">
            <CircleHelp
              className="text-primary mt-0.5 size-5 shrink-0"
              aria-hidden="true"
            />
            <p className="text-muted-foreground leading-6">
              Une erreur réseau signifie que l'API est injoignable ; elle ne
              permet pas de conclure que votre clé est invalide.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
