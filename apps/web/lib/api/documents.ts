import { mintBackendToken } from "@/lib/api/token";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

export type DocumentStatus =
  | "pending"
  | "processing"
  | "ready"
  | "failed"
  | "unknown";

export interface DocumentRecord {
  document_id: string;
  title: string;
  source: string;
  status: DocumentStatus;
  chunk_count: number;
  format: string;
  size_bytes: number | null;
  metadata: Record<string, unknown>;
  version: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface ListDocumentsParams {
  page?: number;
  pageSize?: number;
  status?: DocumentStatus;
  search?: string;
  sort?: "created_at" | "updated_at" | "title" | "status";
  order?: "asc" | "desc";
}

export interface DocumentUpdateInput {
  title?: string;
  metadata?: Record<string, unknown>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function authedRequest(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const minted = await mintBackendToken();
  if (!minted) throw new ApiError("Not authenticated", 401);

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${minted.token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    let message = res.statusText;
    let code: string | undefined;
    try {
      const body = (await res.clone().json()) as {
        detail?: string;
        error?: { code?: string; message?: string };
      };
      message = body.error?.message ?? body.detail ?? message;
      code = body.error?.code;
    } catch {
      // ignore — non-JSON body
    }
    throw new ApiError(message, res.status, code);
  }

  return res;
}

export async function listDocuments(
  params: ListDocumentsParams = {},
): Promise<DocumentListResponse> {
  const search = new URLSearchParams();
  if (params.page) search.set("page", String(params.page));
  if (params.pageSize) search.set("page_size", String(params.pageSize));
  if (params.status) search.set("status", params.status);
  if (params.search) search.set("search", params.search);
  if (params.sort) search.set("sort", params.sort);
  if (params.order) search.set("order", params.order);

  const qs = search.toString();
  const res = await authedRequest(
    `/api/v1/documents${qs ? `?${qs}` : ""}`,
  );
  return (await res.json()) as DocumentListResponse;
}

export async function getDocument(id: string): Promise<DocumentRecord> {
  const res = await authedRequest(
    `/api/v1/documents/${encodeURIComponent(id)}`,
  );
  return (await res.json()) as DocumentRecord;
}

export async function updateDocument(
  id: string,
  input: DocumentUpdateInput,
): Promise<DocumentRecord> {
  const res = await authedRequest(
    `/api/v1/documents/${encodeURIComponent(id)}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );
  return (await res.json()) as DocumentRecord;
}

export async function deleteDocument(id: string): Promise<void> {
  await authedRequest(`/api/v1/documents/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function reingestDocument(id: string): Promise<void> {
  await authedRequest(
    `/api/v1/documents/${encodeURIComponent(id)}/reingest`,
    { method: "POST" },
  );
}

export async function bulkDeleteDocuments(ids: string[]): Promise<void> {
  await authedRequest(`/api/v1/documents`, {
    method: "DELETE",
    body: JSON.stringify({ ids }),
  });
}
