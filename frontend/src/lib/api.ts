import { supabase } from "./supabase";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const API_BASE_URL = (
  configuredBaseUrl || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string;

  constructor(
    message: string,
    options: { status?: number | null; code?: string } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? null;
    this.code = options.code ?? "api_error";
  }
}

export type ApiRequestOptions = Omit<RequestInit, "headers"> & {
  headers?: HeadersInit;
  skipAuth?: boolean;
  skipRefresh?: boolean;
};

let refreshPromise: Promise<boolean> | null = null;

async function getAccessToken(): Promise<string | null> {
  let result: Awaited<ReturnType<typeof supabase.auth.getSession>>;

  try {
    result = await supabase.auth.getSession();
  } catch {
    throw new ApiError(
      "Unable to read the authentication session. Please try again.",
      { code: "session_retrieval_failed" },
    );
  }

  if (result.error) {
    throw new ApiError(
      "Unable to read the authentication session. Please try again.",
      { code: "session_retrieval_failed" },
    );
  }

  if (!result.data.session) {
    return null;
  }

  if (!result.data.session.access_token) {
    throw new ApiError(
      "Unable to read the authentication session. Please try again.",
      { code: "session_retrieval_failed" },
    );
  }

  return result.data.session.access_token;
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = supabase.auth
      .refreshSession()
      .then(({ data, error }) => !error && Boolean(data.session))
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

function shouldSetJsonContentType(body: BodyInit | null | undefined): boolean {
  if (body == null) {
    return false;
  }

  if (
    body instanceof FormData ||
    body instanceof Blob ||
    body instanceof URLSearchParams ||
    body instanceof ArrayBuffer ||
    ArrayBuffer.isView(body)
  ) {
    return false;
  }

  if (
    typeof ReadableStream !== "undefined" &&
    body instanceof ReadableStream
  ) {
    return false;
  }

  return true;
}

async function readResponseBody(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.toLowerCase().includes("json")) {
    try {
      return await response.json();
    } catch {
      if (response.ok) {
        throw new ApiError(
          "The server returned an invalid response.",
          { status: response.status, code: "invalid_response" },
        );
      }

      return null;
    }
  }

  const text = await response.text();
  return text.trim() ? text : null;
}

function getErrorMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "string" && payload.trim()) {
    return payload.trim();
  }

  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;

    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
  }

  return fallback;
}

function getDefaultErrorMessage(status: number): string {
  if (status === 401) {
    return "Authentication is required.";
  }

  if (status === 403) {
    return "You do not have permission to perform this action.";
  }

  if (status === 404) {
    return "The requested resource was not found.";
  }

  if (status >= 500) {
    return "The server could not complete the request.";
  }

  return "The request could not be completed.";
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
  retryOnUnauthorized = true,
): Promise<T> {
  const {
    skipAuth = false,
    skipRefresh = false,
    headers: providedHeaders,
    ...requestInit
  } = options;

  const accessToken = skipAuth ? null : await getAccessToken();
  const headers = new Headers(providedHeaders);

  if (shouldSetJsonContentType(requestInit.body) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  } else {
    headers.delete("Authorization");
  }

  const url = `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  let response: Response;

  try {
    response = await fetch(url, {
      ...requestInit,
      headers,
    });
  } catch {
    throw new ApiError(
      "Unable to reach the server. Check your connection and try again.",
      { code: "network_error" },
    );
  }

  if (response.status === 401 && accessToken && !skipAuth) {
    if (!skipRefresh && retryOnUnauthorized && (await refreshAccessToken())) {
      return apiRequest<T>(path, options, false);
    }

    try {
      await supabase.auth.signOut();
    } catch {
      /* Session cleanup is best effort. */
    }

    throw new ApiError(
      "Your session has expired. Please sign in again.",
      { status: 401, code: "session_expired" },
    );
  }

  const payload = await readResponseBody(response);

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(payload, getDefaultErrorMessage(response.status)),
      { status: response.status, code: "http_error" },
    );
  }

  return payload as T;
}

// ---------------------------------------------------------------------------
// Typed Domain Interfaces matching backend schemas
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  application: string;
  database?: string;
}

export type ProjectVisibility = "private" | "unlisted" | "public";

export interface Project {
  id: number;
  name: string;
  hackathon_name: string;
  problem_statement: string;
  description: string;
  tech_stack: string;
  development_stage: string;
  visibility: ProjectVisibility;
  owner_id?: string | null;
  owner_type?: string | null;
  creator_id?: string | null;
  unlisted_token?: string | null;
  created_at: string;
  updated_at?: string | null;
  deleted_at?: string | null;
}

export interface ProjectCreateData {
  name: string;
  hackathon_name: string;
  problem_statement: string;
  description: string;
  tech_stack: string;
  development_stage: string;
  visibility?: ProjectVisibility;
}

export interface ProjectUpdateData {
  name?: string;
  hackathon_name?: string;
  problem_statement?: string;
  description?: string;
  tech_stack?: string;
  development_stage?: string;
  visibility?: ProjectVisibility;
}

// ---------------------------------------------------------------------------
// Authenticated Projects API Service
// ---------------------------------------------------------------------------

export const projectsApi = {
  getHealth: () =>
    apiRequest<HealthResponse>("/api/health", { skipAuth: true }),

  list: () =>
    apiRequest<Project[]>("/api/projects"),

  get: (id: number, token?: string) =>
    apiRequest<Project>(
      `/api/projects/${id}${token ? `?token=${encodeURIComponent(token)}` : ""}`,
    ),

  getByToken: (token: string) =>
    apiRequest<Project>(`/api/projects/unlisted/${encodeURIComponent(token)}`),

  create: (data: ProjectCreateData) =>
    apiRequest<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: number, data: ProjectUpdateData) =>
    apiRequest<Project>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (id: number) =>
    apiRequest<{ detail: string }>(`/api/projects/${id}`, {
      method: "DELETE",
    }),

  restore: (id: number) =>
    apiRequest<Project>(`/api/projects/${id}/restore`, {
      method: "POST",
    }),
};
