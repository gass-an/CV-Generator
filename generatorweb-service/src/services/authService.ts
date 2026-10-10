import { apiRequest } from "@/services/apiClient";

export async function verifyApiKey(
  apiKey: string,
  signal?: AbortSignal,
): Promise<void> {
  await apiRequest("/documents?limit=1&offset=0", {
    method: "GET",
    apiKey,
    signal,
  });
}
