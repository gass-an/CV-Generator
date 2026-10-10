import {
  ArrowRight,
  BriefcaseBusiness,
  FileText,
  GraduationCap,
  KeyRound,
  Mail,
  Sparkles,
  UploadCloud,
} from "lucide-react";

import { DocumentPreview } from "@/components/DocumentPreview";
import { DocumentTypeCard } from "@/components/DocumentTypeCard";
import { PageHeader } from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function GenerationPage() {
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
              <div className="border-primary/20 bg-primary/[0.025] flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed px-5 py-8 text-center">
                <UploadCloud
                  className="text-primary size-8"
                  aria-hidden="true"
                />
                <p className="mt-3 font-semibold">Import JSON Resume</p>
                <p className="text-muted-foreground mt-1 max-w-sm text-sm leading-6">
                  La sélection et la validation du fichier seront disponibles à
                  la prochaine étape.
                </p>
                <Badge variant="muted" className="mt-4">
                  Bientôt disponible
                </Badge>
              </div>
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
                  disabled
                  placeholder="Saisie disponible prochainement"
                  className="border-border bg-muted/40 text-muted-foreground min-h-11 w-full cursor-not-allowed rounded-lg border pr-4 pl-10 text-sm opacity-80"
                />
              </div>
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
                    La clé API et les informations du document seront requises.
                  </p>
                </div>
              </div>
              <div className="text-muted-foreground flex items-center gap-2 text-sm font-semibold">
                Fonction disponible prochainement
                <ArrowRight className="size-4" aria-hidden="true" />
              </div>
            </CardContent>
          </Card>
        </div>

        <DocumentPreview />
      </div>
    </div>
  );
}
