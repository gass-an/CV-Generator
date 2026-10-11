import { ApiError, apiRequest, apiRequestBody } from "@/services/apiClient";
import type {
  CreateDocumentPayload,
  DocumentAvpNumbersResponse,
  DocumentJobCreatedResponse,
  DocumentJobStatusResponse,
  DocumentHistoryQuery,
  DocumentHistoryResponse,
  DocumentType,
} from "@/types/document";

export const PDF_TIMEOUT_MS = 90_000;
export const DOCX_TIMEOUT_MS = 30_000;
export const PDF_MEDIA_TYPE = "application/pdf";
export const DOCX_MEDIA_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

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

export async function getDocumentHistory(
  query: DocumentHistoryQuery,
  apiKey: string,
  signal?: AbortSignal,
): Promise<DocumentHistoryResponse> {
  const parameters = new URLSearchParams({
    limit: String(query.limit),
    offset: String(query.offset),
  });
  if (query.documentType) {
    parameters.set("document_type", query.documentType);
  }
  if (query.status) {
    parameters.set("status", query.status);
  }
  if (query.avpNumber) {
    parameters.set("avp_number", query.avpNumber);
  }
  const response = await apiRequest(`/documents?${parameters.toString()}`, {
    method: "GET",
    apiKey,
    signal,
  });
  return (await response.json()) as DocumentHistoryResponse;
}

export async function getDocumentAvpNumbers(
  apiKey: string,
  signal?: AbortSignal,
): Promise<string[]> {
  const response = await apiRequest("/documents/avp-numbers", {
    method: "GET",
    apiKey,
    signal,
  });
  const payload = (await response.json()) as DocumentAvpNumbersResponse;
  return payload.items;
}

async function getDocumentBlob(
  jobId: string,
  apiKey: string,
  path: "pdf" | "download",
  expectedMediaType: string,
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<Blob> {
  return apiRequestBody(
    `/documents/${encodeURIComponent(jobId)}/${path}`,
    { method: "GET", apiKey, signal, timeoutMs },
    async (response) => {
      const mediaType = response.headers.get("Content-Type")?.split(";", 1)[0];
      if (mediaType !== expectedMediaType) {
        throw new ApiError({
          kind: "http",
          status: response.status,
          code: "invalid_document_media_type",
          message: "Le service a retourné un format de fichier inattendu.",
        });
      }
      return await response.blob();
    },
  );
}

export function getDocumentPdf(
  jobId: string,
  apiKey: string,
  signal?: AbortSignal,
): Promise<Blob> {
  return getDocumentBlob(
    jobId,
    apiKey,
    "pdf",
    PDF_MEDIA_TYPE,
    PDF_TIMEOUT_MS,
    signal,
  );
}

export function getDocumentDocx(
  jobId: string,
  apiKey: string,
  signal?: AbortSignal,
): Promise<Blob> {
  return getDocumentBlob(
    jobId,
    apiKey,
    "download",
    DOCX_MEDIA_TYPE,
    DOCX_TIMEOUT_MS,
    signal,
  );
}
