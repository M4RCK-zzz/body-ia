import { getAccessToken, notifyUnauthorized } from "./authToken";

export interface FieldError {
  field: string;
  message: string;
}

export class HttpError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: FieldError[];

  constructor(status: number, code: string, message: string, fields: FieldError[] = []) {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

type QueryValue = string | number | boolean | null | undefined;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  query?: Record<string, QueryValue>;
  body?: unknown;
}

const BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://127.0.0.1:8000";
const TIMEOUT_MS = 10_000;

async function toHttpError(response: Response): Promise<HttpError> {
  let code = "http_error";
  let message = `Error ${response.status}`;
  let fields: FieldError[] = [];
  try {
    const data = (await response.json()) as {
      error?: { code?: string; message?: string; fields?: FieldError[] };
    };
    if (data.error) {
      code = data.error.code ?? code;
      message = data.error.message ?? message;
      fields = data.error.fields ?? [];
    }
  } catch {
    /* cuerpo no JSON */
  }
  return new HttpError(response.status, code, message, fields);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(path, BASE_URL);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const headers: Record<string, string> = {};
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });
  } catch {
    throw new HttpError(0, "network_error", "No se pudo conectar con la API.");
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 401 && token) {
    notifyUnauthorized();
  }

  if (!response.ok) throw await toHttpError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}