import { apiRequest } from "@/services/apiClient";
import type {
  CreateDocumentPayload,
  DocumentJobCreatedResponse,
  DocumentJobStatusResponse,
  DocumentType,
} from "@/types/document";

const creationPaths: Record<DocumentType, string> = {
  cv: "/documents/cv",
  cover_letter: "/documents/cover-letter",
  interview_prep: "/documents/interview-prep",
};

export async function createDocumentJob(
  documentType: DocumentType,
  payload: CreateDocumentPayload,
  apiKey: string,
  signal?: AbortSignal,
): Promise<DocumentJobCreatedResponse> {
  const response = await apiRequest(creationPaths[documentType], {
    method: "POST",
    apiKey,
    signal,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return (await response.json()) as DocumentJobCreatedResponse;
}

export async function getDocumentJobStatus(
  jobId: string,
  apiKey: string,
  signal?: AbortSignal,
): Promise<DocumentJobStatusResponse> {
  const response = await apiRequest(
    `/documents/${encodeURIComponent(jobId)}/status`,
    {
      method: "GET",
      apiKey,
      signal,
    },
  );
  return (await response.json()) as DocumentJobStatusResponse;
}
