import { ApiError, apiRequest, apiRequestBody } from "@/services/apiClient";
import type {
  CreateDocumentPayload,
  DocumentAvpNumbersResponse,
  DocumentJobCreatedResponse,
  DocumentJobStatusResponse,
  DocumentHistoryQuery,
  DocumentHistoryResponse,
  DocumentExportFormat,
  DocumentType,
} from "@/types/document";

export const PDF_TIMEOUT_MS = 90_000;
export const DOCX_TIMEOUT_MS = 30_000;
export const PDF_MEDIA_TYPE = "application/pdf";
export const DOCX_MEDIA_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
export const ASCIIDOC_MEDIA_TYPE = "text/asciidoc";
export const MARKDOWN_MEDIA_TYPE = "text/markdown";

export const documentExportFormats: Record<
  DocumentExportFormat,
  {
    endpoint: string;
    extension: DocumentExportFormat;
    mediaType: string;
    timeoutMs: number;
  }
> = {
  pdf: {
    endpoint: "pdf",
    extension: "pdf",
    mediaType: PDF_MEDIA_TYPE,
    timeoutMs: PDF_TIMEOUT_MS,
  },
  docx: {
    endpoint: "docx",
    extension: "docx",
    mediaType: DOCX_MEDIA_TYPE,
    timeoutMs: DOCX_TIMEOUT_MS,
  },
  adoc: {
    endpoint: "adoc",
    extension: "adoc",
    mediaType: ASCIIDOC_MEDIA_TYPE,
    timeoutMs: DOCX_TIMEOUT_MS,
  },
  md: {
    endpoint: "md",
    extension: "md",
    mediaType: MARKDOWN_MEDIA_TYPE,
    timeoutMs: DOCX_TIMEOUT_MS,
  },
};

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
  format: DocumentExportFormat,
  signal?: AbortSignal,
): Promise<Blob> {
  const config = documentExportFormats[format];
  return apiRequestBody(
    `/documents/${encodeURIComponent(jobId)}/${config.endpoint}`,
    { method: "GET", apiKey, signal, timeoutMs: config.timeoutMs },
    async (response) => {
      const mediaType = response.headers.get("Content-Type")?.split(";", 1)[0];
      if (mediaType !== config.mediaType) {
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
  return getDocumentBlob(jobId, apiKey, "pdf", signal);
}

export function getDocumentDocx(
  jobId: string,
  apiKey: string,
  signal?: AbortSignal,
): Promise<Blob> {
  return getDocumentBlob(jobId, apiKey, "docx", signal);
}

export function getDocumentExport(
  jobId: string,
  apiKey: string,
  format: DocumentExportFormat,
  signal?: AbortSignal,
): Promise<Blob> {
  return getDocumentBlob(jobId, apiKey, format, signal);
}
