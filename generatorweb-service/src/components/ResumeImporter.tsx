import { useId, useRef, useState, type DragEvent } from "react";
import {
  BriefcaseBusiness,
  FileCheck2,
  GraduationCap,
  MapPin,
  RefreshCw,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";

import { useAppState } from "@/hooks/useAppState";
import { parseResumeFile, ResumeValidationError } from "@/lib/resume";

function formatFileSize(size: number) {
  return size < 1024 ? `${size} octets` : `${Math.ceil(size / 1024)} Ko`;
}

export function ResumeImporter() {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);
  const { draft } = useAppState();
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isReading, setIsReading] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);

  async function importFile(file: File | undefined) {
    if (!file) {
      return;
    }
    setIsReading(true);
    setError(null);
    try {
      draft.acceptResume(await parseResumeFile(file));
    } catch (importError) {
      setError(
        importError instanceof ResumeValidationError
          ? importError.message
          : "Le fichier n'a pas pu être lu. Le profil précédent est conservé.",
      );
    } finally {
      setIsReading(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    void importFile(event.dataTransfer.files[0]);
  }

  const fileInput = (
    <input
      ref={input}
      id={inputId}
      type="file"
      accept=".json,application/json,text/json"
      className="sr-only"
      disabled={isReading}
      onFocus={() => setInputFocused(true)}
      onBlur={() => setInputFocused(false)}
      onChange={(event) => {
        void importFile(event.target.files?.[0]);
        event.target.value = "";
      }}
    />
  );

  if (!draft.importedResume) {
    return (
      <div>
        {fileInput}
        <div
          className={`flex min-h-48 flex-col items-center justify-center rounded-xl border border-dashed px-5 py-8 text-center transition-colors ${
            isDragging
              ? "border-primary bg-primary/8"
              : "border-primary/25 bg-primary/[0.025]"
          }`}
          onDragEnter={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (
              !event.currentTarget.contains(event.relatedTarget as Node | null)
            ) {
              setIsDragging(false);
            }
          }}
          onDrop={handleDrop}
        >
          <UploadCloud className="text-primary size-8" aria-hidden="true" />
          <p className="mt-3 font-semibold">
            {isReading ? "Lecture du profil…" : "Déposez votre JSON Resume ici"}
          </p>
          <p className="text-muted-foreground mt-1 max-w-sm text-sm leading-6">
            Fichier JSON de 2 Mo maximum. Il reste dans la mémoire de votre
            navigateur et n'est pas envoyé lors de l'import.
          </p>
          <label
            htmlFor={inputId}
            className={`bg-primary text-primary-foreground hover:bg-primary/90 mt-5 inline-flex min-h-11 cursor-pointer items-center rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
              inputFocused
                ? "ring-ring ring-offset-background ring-2 ring-offset-2"
                : ""
            }`}
          >
            Choisir un fichier
          </label>
        </div>
        {error ? (
          <p className="text-accent mt-3 text-sm" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  const { metadata, fileName, fileSize } = draft.importedResume;
  return (
    <div>
      {fileInput}
      <div className="border-primary/20 bg-primary/[0.025] rounded-xl border p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex min-w-0 gap-3">
            <span className="bg-primary/10 text-primary flex size-11 shrink-0 items-center justify-center rounded-xl">
              <FileCheck2 className="size-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="font-semibold break-words">
                {metadata.candidateName || "Nom non renseigné"}
              </p>
              <p className="text-muted-foreground mt-0.5 text-sm break-words">
                {metadata.professionalTitle ||
                  "Intitulé professionnel non renseigné"}
              </p>
              {metadata.location ? (
                <p className="text-muted-foreground mt-1 flex items-center gap-1.5 text-xs">
                  <MapPin className="size-3.5" aria-hidden="true" />
                  {metadata.location}
                </p>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              draft.removeResume();
              requestAnimationFrame(() => input.current?.focus());
            }}
            className="text-muted-foreground hover:bg-accent/8 hover:text-accent flex min-h-10 items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors"
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Retirer
          </button>
        </div>

        <dl className="mt-5 grid grid-cols-1 gap-2 min-[375px]:grid-cols-3">
          <div className="bg-card rounded-lg border p-3 text-center">
            <BriefcaseBusiness
              className="text-primary mx-auto size-4"
              aria-hidden="true"
            />
            <dt className="text-muted-foreground mt-1 text-xs">Expériences</dt>
            <dd className="mt-0.5 font-bold">{metadata.workCount}</dd>
          </div>
          <div className="bg-card rounded-lg border p-3 text-center">
            <GraduationCap
              className="text-primary mx-auto size-4"
              aria-hidden="true"
            />
            <dt className="text-muted-foreground mt-1 text-xs">Formations</dt>
            <dd className="mt-0.5 font-bold">{metadata.educationCount}</dd>
          </div>
          <div className="bg-card rounded-lg border p-3 text-center">
            <Sparkles
              className="text-primary mx-auto size-4"
              aria-hidden="true"
            />
            <dt className="text-muted-foreground mt-1 text-xs">Compétences</dt>
            <dd className="mt-0.5 font-bold">{metadata.skillCount}</dd>
          </div>
        </dl>

        <div className="border-border mt-4 flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-muted-foreground min-w-0 text-xs break-all">
            {fileName} · {formatFileSize(fileSize)}
          </p>
          <label
            htmlFor={inputId}
            className={`text-primary hover:bg-primary/8 flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors ${
              inputFocused
                ? "ring-ring ring-offset-background ring-2 ring-offset-2"
                : ""
            }`}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            Remplacer
          </label>
        </div>
      </div>
      {error ? (
        <p className="text-accent mt-3 text-sm" role="alert">
          {error} Le profil déjà chargé est conservé.
        </p>
      ) : null}
    </div>
  );
}
