import { useState } from "react";
import {
  BriefcaseBusiness,
  CheckCircle2,
  Circle,
  FileText,
  GraduationCap,
  KeyRound,
  LoaderCircle,
  Mail,
  Send,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";

import { DocumentPreview } from "@/components/DocumentPreview";
import { DocumentTypeCard } from "@/components/DocumentTypeCard";
import { PageHeader } from "@/components/PageHeader";
import { ResumeImporter } from "@/components/ResumeImporter";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useAppState } from "@/hooks/useAppState";
import { MAX_AVP_NUMBER_LENGTH, validateAvpNumber } from "@/lib/resume";

export function GenerationPage() {
  const { auth, draft, generation } = useAppState();
  const [avpTouched, setAvpTouched] = useState(false);
  const avpError = avpTouched ? validateAvpNumber(draft.avpNumber) : null;
  const generationBusy =
    generation.state.phase === "creating" ||
    generation.state.phase === "pending" ||
    generation.state.phase === "processing" ||
    generation.state.phase === "interrupted" ||
    (generation.state.phase === "creation_error" && generation.state.uncertain);
  const requirements = [
    {
      met: auth.status === "valid",
      label: "Clé API vérifiée",
      link: "/parametres",
    },
    { met: draft.profileValid, label: "Profil JSON Resume importé" },
    { met: draft.avpValid, label: "Numéro AVP valide" },
    {
      met: draft.selectedDocumentType !== null,
      label: "Type de document sélectionné",
    },
  ];
  const canStart =
    requirements.every((requirement) => requirement.met) && !generationBusy;

  return (
    <div className="w-full space-y-8 lg:space-y-10">
      <PageHeader
        eyebrow="Assistant de candidature"
        title="Préparez une candidature qui vous ressemble"
        description="À partir de votre parcours et d'un avis de vacance de poste OPT, CV-Generator vous aidera à créer des documents personnalisés avec une IA locale."
        action={
          <Badge variant="outline" className="gap-2 self-start sm:self-auto">
            <Sparkles className="size-3.5" aria-hidden="true" />
            Génération locale et confidentielle
          </Badge>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)] xl:gap-8">
        <div className="space-y-6">
          <Card>
            <CardHeader className="sm:grid-cols-[auto_1fr] sm:items-center sm:gap-x-4">
              <span className="bg-primary/10 text-primary flex size-10 items-center justify-center rounded-xl">
                <span className="text-sm font-bold">1</span>
              </span>
              <div>
                <h2 className="font-semibold">Votre profil professionnel</h2>
                <p className="text-muted-foreground mt-1 text-sm">
                  Importez votre JSON Resume pour présenter votre parcours.
                </p>
              </div>
            </CardHeader>
            <CardContent>
              <ResumeImporter />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="sm:grid-cols-[auto_1fr] sm:items-center sm:gap-x-4">
              <span className="bg-primary/10 text-primary flex size-10 items-center justify-center rounded-xl">
                <span className="text-sm font-bold">2</span>
              </span>
              <div>
                <h2 className="font-semibold">Avis de vacance de poste</h2>
                <p className="text-muted-foreground mt-1 text-sm">
                  Indiquez le numéro de l'AVP OPT qui vous intéresse.
                </p>
              </div>
            </CardHeader>
            <CardContent>
              <label htmlFor="avp-number" className="text-sm font-semibold">
                Numéro AVP
              </label>
              <div className="relative mt-2">
                <BriefcaseBusiness
                  className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2"
                  aria-hidden="true"
                />
                <input
                  id="avp-number"
                  type="text"
                  value={draft.avpNumber}
                  maxLength={MAX_AVP_NUMBER_LENGTH}
                  placeholder="3134-26-1382/SR"
                  aria-invalid={Boolean(avpError)}
                  aria-describedby="avp-help avp-error"
                  onBlur={() => {
                    draft.setAvpNumber(draft.avpNumber.trim());
                    setAvpTouched(true);
                  }}
                  onChange={(event) => draft.setAvpNumber(event.target.value)}
                  className="border-border bg-card focus:border-primary focus:ring-primary/15 min-h-11 w-full rounded-lg border pr-4 pl-10 text-sm transition-shadow focus:ring-4 focus:outline-none"
                />
              </div>
              <div className="mt-2 flex items-start justify-between gap-4 text-xs">
                <p id="avp-help" className="text-muted-foreground">
                  Exemple : 3134-26-1382/SR. Tirets, barres obliques et suffixes
                  sont acceptés.
                </p>
                <span className="text-muted-foreground shrink-0">
                  {draft.avpNumber.length}/{MAX_AVP_NUMBER_LENGTH}
                </span>
              </div>
              {avpError ? (
                <p
                  id="avp-error"
                  className="text-accent mt-2 text-sm"
                  role="alert"
                >
                  {avpError}
                </p>
              ) : null}
            </CardContent>
          </Card>

          <section aria-labelledby="document-types-title">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <span className="bg-primary/10 text-primary flex size-10 items-center justify-center rounded-xl text-sm font-bold">
                    3
                  </span>
                  <h2 id="document-types-title" className="font-semibold">
                    Choisissez votre document
                  </h2>
                </div>
                <p className="text-muted-foreground mt-2 text-sm">
                  Trois formats adaptés aux différentes étapes de votre
                  candidature.
                </p>
              </div>
            </div>
            <div
              className="grid gap-3 sm:grid-cols-3"
              role="radiogroup"
              aria-labelledby="document-types-title"
            >
              <DocumentTypeCard
                icon={FileText}
                title="Curriculum vitæ"
                description="Valorisez votre parcours au regard du poste visé."
                accent="blue"
                value="cv"
                selected={draft.selectedDocumentType === "cv"}
                onSelect={draft.setSelectedDocumentType}
              />
              <DocumentTypeCard
                icon={Mail}
                title="Lettre de motivation"
                description="Présentez une motivation claire et personnalisée."
                accent="cyan"
                value="cover_letter"
                selected={draft.selectedDocumentType === "cover_letter"}
                onSelect={draft.setSelectedDocumentType}
              />
              <DocumentTypeCard
                icon={GraduationCap}
                title="Préparation à l'entretien"
                description="Anticipez les questions et préparez vos réponses."
                accent="red"
                value="interview_prep"
                selected={draft.selectedDocumentType === "interview_prep"}
                onSelect={draft.setSelectedDocumentType}
              />
            </div>
          </section>

          <Card className="border-primary/20 bg-primary/[0.025]">
            <CardContent className="space-y-5 border-0 pt-0">
              <div className="flex gap-3">
                <span className="bg-card text-primary flex size-10 shrink-0 items-center justify-center rounded-xl border shadow-sm">
                  <KeyRound className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <h2 className="font-semibold">Prêt à générer ?</h2>
                  <p className="text-muted-foreground mt-1 text-sm leading-6">
                    Vérifiez les informations avant d'envoyer une demande au
                    service de génération.
                  </p>
                </div>
              </div>

              <ul className="grid gap-2 text-sm sm:grid-cols-2">
                {requirements.map((requirement) => (
                  <li
                    key={requirement.label}
                    className={`flex items-center gap-2 ${
                      requirement.met ? "text-primary" : "text-muted-foreground"
                    }`}
                  >
                    {requirement.met ? (
                      <CheckCircle2
                        className="size-4 shrink-0"
                        aria-hidden="true"
                      />
                    ) : (
                      <Circle className="size-4 shrink-0" aria-hidden="true" />
                    )}
                    {requirement.link && !requirement.met ? (
                      <Link
                        to={requirement.link}
                        className="hover:text-primary underline-offset-4 hover:underline"
                      >
                        {requirement.label}
                      </Link>
                    ) : (
                      requirement.label
                    )}
                  </li>
                ))}
              </ul>

              {generation.state.phase === "creation_error" ? (
                <div
                  className="border-accent/20 bg-accent/5 space-y-3 rounded-lg border p-4"
                  role="alert"
                >
                  <p className="text-accent text-sm leading-6">
                    {generation.state.message}
                  </p>
                  {generation.state.uncertain ? (
                    <div className="space-y-3">
                      <p className="text-muted-foreground text-sm leading-6">
                        Consultez votre historique lorsqu'il sera disponible. Si
                        vous choisissez de continuer, une seconde demande pourra
                        créer un doublon.
                      </p>
                      <button
                        type="button"
                        onClick={generation.allowUncertainRetry}
                        className="border-accent/30 text-accent hover:bg-accent/8 min-h-11 rounded-lg border px-4 text-sm font-semibold transition-colors"
                      >
                        J'ai compris, autoriser une nouvelle demande
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}

              <button
                type="button"
                disabled={!canStart}
                onClick={() => void generation.start()}
                className="bg-primary text-primary-foreground hover:bg-primary/90 flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
              >
                {generation.state.phase === "creating" ? (
                  <LoaderCircle
                    className="size-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Send className="size-4" aria-hidden="true" />
                )}
                {generation.state.phase === "creating"
                  ? "Envoi de la demande…"
                  : generation.state.phase === "creation_error" &&
                      generation.state.uncertain
                    ? "Confirmation requise"
                    : generationBusy
                      ? "Génération en cours"
                      : "Générer le document"}
              </button>
            </CardContent>
          </Card>
        </div>

        <DocumentPreview />
      </div>
    </div>
  );
}
