import { clearAccessToken, getAccessToken, notifyUnauthorized } from "./authToken";

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
  /** JSON por defecto; FormData para subidas multipart (el navegador fija el Content-Type). */
  body?: unknown;
  /** Devuelve un Blob en lugar de JSON (descargas autenticadas). */
  blob?: boolean;
  /** No adjunta el token ni dispara el cierre de sesión (login, registro, health). */
  skipAuth?: boolean;
  signal?: AbortSignal;
  timeoutMs?: number;
}

const BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://127.0.0.1:8000";

const DEFAULT_TIMEOUT_MS = 10_000;

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
  const {
    method = "GET",
    query,
    body,
    blob = false,
    skipAuth = false,
    signal,
    timeoutMs = DEFAULT_TIMEOUT_MS,
  } = options;

  const url = new URL(path, BASE_URL);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  const headers: Record<string, string> = {
    Accept: blob ? "image/*, application/octet-stream" : "application/json",
  };
  if (body !== undefined && !isFormData) headers["Content-Type"] = "application/json";

  const token = skipAuth ? null : getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onExternalAbort, { once: true });
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? (isFormData ? body : JSON.stringify(body)) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error; // cancelación del llamador
    if (timedOut) throw new HttpError(0, "timeout", "La API tardó demasiado en responder.");
    throw new HttpError(0, "network_error", "No se pudo conectar con la API.");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onExternalAbort);
  }

  // Solo si el token rechazado sigue siendo el vigente (evita borrar uno recién renovado).
  if (response.status === 401 && token && getAccessToken() === token) {
    clearAccessToken();
    notifyUnauthorized();
  }

  if (!response.ok) throw await toHttpError(response);
  if (response.status === 204) return undefined as T;
  if (blob) return (await response.blob()) as T;
  return (await response.json()) as T;
}
