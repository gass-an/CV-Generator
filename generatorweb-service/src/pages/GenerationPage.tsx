import { useState } from "react";
import {
  ArrowRight,
  BriefcaseBusiness,
  FileText,
  GraduationCap,
  KeyRound,
  Mail,
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
  const { auth, draft } = useAppState();
  const [avpTouched, setAvpTouched] = useState(false);
  const avpError = avpTouched ? validateAvpNumber(draft.avpNumber) : null;

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
            <div className="grid gap-3 sm:grid-cols-3">
              <DocumentTypeCard
                icon={FileText}
                title="Curriculum vitæ"
                description="Valorisez votre parcours au regard du poste visé."
                accent="blue"
              />
              <DocumentTypeCard
                icon={Mail}
                title="Lettre de motivation"
                description="Présentez une motivation claire et personnalisée."
                accent="cyan"
              />
              <DocumentTypeCard
                icon={GraduationCap}
                title="Préparation à l'entretien"
                description="Anticipez les questions et préparez vos réponses."
                accent="red"
              />
            </div>
          </section>

          <Card className="border-primary/20 bg-primary/[0.025]">
            <CardContent className="flex flex-col gap-4 border-0 pt-0 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex gap-3">
                <span className="bg-card text-primary flex size-10 shrink-0 items-center justify-center rounded-xl border shadow-sm">
                  <KeyRound className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <h2 className="font-semibold">Prêt à générer ?</h2>
                  <p className="text-muted-foreground mt-1 text-sm leading-6">
                    {auth.status === "valid"
                      ? "Votre clé API est vérifiée. Importez un profil et renseignez l'AVP pour préparer la prochaine étape."
                      : "Configurez et vérifiez votre clé API avant de pouvoir générer un document."}
                  </p>
                </div>
              </div>
              {auth.status === "valid" ? (
                <Badge variant="default">Clé vérifiée</Badge>
              ) : (
                <Link
                  to="/parametres"
                  className="text-primary hover:bg-primary/8 flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors"
                >
                  Configurer la clé
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              )}
            </CardContent>
          </Card>
        </div>

        <DocumentPreview />
      </div>
    </div>
  );
}
