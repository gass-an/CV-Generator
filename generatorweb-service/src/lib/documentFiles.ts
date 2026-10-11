import type { DocumentMetadata, DocumentType } from "@/types/document";

const filenamePrefixes: Record<DocumentType, string> = {
  cv: "cv",
  cover_letter: "lettre-motivation",
  interview_prep: "preparation-entretien",
};

function filenamePart(value: string | null, fallback: string): string {
  const normalized = (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return normalized || fallback;
}

export function documentFilename(
  metadata: DocumentMetadata,
  extension: "docx" | "pdf",
): string {
  const date =
    /^\d{4}-\d{2}-\d{2}/.exec(metadata.createdAt)?.[0] ?? "date-inconnue";
  const parts = [
    filenamePrefixes[metadata.documentType],
    filenamePart(metadata.candidateName, "candidat"),
    filenamePart(metadata.avpNumber, "avp"),
    date,
  ];
  return `${parts.join("_").slice(0, 180)}.${extension}`;
}

export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  try {
    document.body.append(link);
    link.click();
  } finally {
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
  }
}
