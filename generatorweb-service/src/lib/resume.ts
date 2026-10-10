import type {
  JsonObject,
  ParsedResumeFile,
  ResumeMetadata,
} from "@/types/resume";

export const MAX_RESUME_FILE_SIZE = 2 * 1024 * 1024;
export const MAX_AVP_NUMBER_LENGTH = 128;

export class ResumeValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ResumeValidationError";
  }
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown, field: string): string | null {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  if (typeof value !== "string") {
    throw new ResumeValidationError(
      `Le champ « ${field} » doit être un texte.`,
    );
  }
  const normalized = value.trim();
  return normalized || null;
}

function validateObjectArray(value: unknown, field: string): JsonObject[] {
  if (value === undefined) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new ResumeValidationError(
      `Le champ « ${field} » doit être une liste.`,
    );
  }
  if (!value.every(isObject)) {
    throw new ResumeValidationError(
      `Chaque élément du champ « ${field} » doit être un objet.`,
    );
  }
  return value;
}

function validateResume(resume: unknown): JsonObject {
  if (!isObject(resume)) {
    throw new ResumeValidationError(
      "Le profil JSON Resume doit être un objet JSON.",
    );
  }
  if (Object.keys(resume).length === 0) {
    throw new ResumeValidationError("Le profil JSON Resume est vide.");
  }

  if (resume.basics !== undefined && !isObject(resume.basics)) {
    throw new ResumeValidationError("Le champ « basics » doit être un objet.");
  }
  const basics = isObject(resume.basics) ? resume.basics : undefined;
  if (basics) {
    optionalString(basics.name, "basics.name");
    optionalString(basics.label, "basics.label");
    if (basics.location !== undefined && !isObject(basics.location)) {
      throw new ResumeValidationError(
        "Le champ « basics.location » doit être un objet.",
      );
    }
  }

  validateObjectArray(resume.work, "work");
  validateObjectArray(resume.education, "education");
  validateObjectArray(resume.skills, "skills");

  return resume;
}

function metadataFromResume(resume: JsonObject): ResumeMetadata {
  const basics = isObject(resume.basics) ? resume.basics : {};
  const location = isObject(basics.location) ? basics.location : {};
  const city = optionalString(location.city, "basics.location.city");
  const region = optionalString(location.region, "basics.location.region");

  return {
    candidateName: optionalString(basics.name, "basics.name"),
    professionalTitle: optionalString(basics.label, "basics.label"),
    location: [city, region].filter(Boolean).join(", ") || null,
    workCount: validateObjectArray(resume.work, "work").length,
    educationCount: validateObjectArray(resume.education, "education").length,
    skillCount: validateObjectArray(resume.skills, "skills").length,
  };
}

export function validateAvpNumber(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) {
    return "Renseignez un numéro AVP.";
  }
  if (normalized.length > MAX_AVP_NUMBER_LENGTH) {
    return `Le numéro AVP ne peut pas dépasser ${MAX_AVP_NUMBER_LENGTH} caractères.`;
  }
  return null;
}

export async function parseResumeFile(file: File): Promise<ParsedResumeFile> {
  const hasJsonExtension = file.name.toLowerCase().endsWith(".json");
  const hasJsonMime =
    file.type === "application/json" || file.type === "text/json";
  if (!hasJsonExtension && !hasJsonMime) {
    throw new ResumeValidationError("Sélectionnez un fichier au format JSON.");
  }
  if (file.size > MAX_RESUME_FILE_SIZE) {
    throw new ResumeValidationError(
      "Le fichier dépasse la taille maximale autorisée de 2 Mo.",
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text()) as unknown;
  } catch {
    throw new ResumeValidationError(
      "Le fichier ne contient pas un JSON valide. Vérifiez sa syntaxe.",
    );
  }

  if (!isObject(parsed)) {
    throw new ResumeValidationError(
      "La racine du fichier doit être un objet JSON.",
    );
  }
  if (Object.keys(parsed).length === 0) {
    throw new ResumeValidationError("Le fichier JSON est vide.");
  }

  const isEnvelope = Object.hasOwn(parsed, "resume");
  const resume = validateResume(isEnvelope ? parsed.resume : parsed);
  let avpNumber: string | null = null;

  if (isEnvelope && parsed.avp_number !== undefined) {
    if (typeof parsed.avp_number !== "string") {
      throw new ResumeValidationError(
        "Le champ « avp_number » de l'enveloppe doit être un texte.",
      );
    }
    const normalized = parsed.avp_number.trim();
    if (normalized.length > MAX_AVP_NUMBER_LENGTH) {
      throw new ResumeValidationError(
        `Le numéro AVP ne peut pas dépasser ${MAX_AVP_NUMBER_LENGTH} caractères.`,
      );
    }
    avpNumber = normalized || null;
  }

  return {
    resume,
    avpNumber,
    fileName: file.name,
    fileSize: file.size,
    metadata: metadataFromResume(resume),
  };
}
