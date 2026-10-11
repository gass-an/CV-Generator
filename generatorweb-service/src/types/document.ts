import type { JsonObject } from "@/types/resume";

export type DocumentType = "cv" | "cover_letter" | "interview_prep";
export type DocumentJobStatus =
  "pending" | "processing" | "completed" | "failed";

export type CreateDocumentPayload = {
  avp_number: string;
  resume: JsonObject;
};

export type DocumentJobCreatedResponse = {
  id: string;
  status: DocumentJobStatus;
};

export type DocumentJobStatusResponse = {
  id: string;
  status: DocumentJobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type DocumentHistoryItem = {
  id: string;
  type: DocumentType;
  status: DocumentJobStatus;
  avp_number: string;
  candidate_name: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type DocumentHistoryResponse = {
  items: DocumentHistoryItem[];
  total: number;
  limit: number;
  offset: number;
};

export type DocumentHistoryQuery = {
  limit: number;
  offset: number;
  documentType?: DocumentType;
  status?: DocumentJobStatus;
};

export type DocumentMetadata = {
  id: string;
  documentType: DocumentType;
  status: DocumentJobStatus;
  avpNumber: string;
  candidateName: string | null;
  createdAt: string;
};

export type GenerationRequestSnapshot = {
  documentType: DocumentType;
  avpNumber: string;
  candidateName: string | null;
  requestedAt: string;
};

export type TrackedDocumentJob = GenerationRequestSnapshot & {
  id: string;
  status: DocumentJobStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
};

export type GenerationState =
  | { phase: "idle" }
  | { phase: "creating"; request: GenerationRequestSnapshot }
  | {
      phase: "creation_error";
      request: GenerationRequestSnapshot;
      message: string;
      uncertain: boolean;
      authenticationError: boolean;
    }
  | { phase: "pending" | "processing"; job: TrackedDocumentJob }
  | {
      phase: "interrupted";
      job: TrackedDocumentJob;
      message: string;
      authenticationError: boolean;
    }
  | { phase: "completed" | "failed"; job: TrackedDocumentJob };

export const documentTypeLabels: Record<DocumentType, string> = {
  cv: "Curriculum vitæ",
  cover_letter: "Lettre de motivation",
  interview_prep: "Préparation à l'entretien",
};

export const documentStatusLabels: Record<DocumentJobStatus, string> = {
  pending: "En attente",
  processing: "En cours",
  completed: "Terminé",
  failed: "Échec",
};
