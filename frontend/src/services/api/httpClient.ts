import { API_BASE_URL } from './config'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

type RequestOptions = RequestInit & { timeoutMs?: number }

async function readErrorBody(response: Response): Promise<{ message?: string; code?: string }> {
  try {
    const body = await response.json()
    return body?.error ?? {}
  } catch {
    return {}
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 8000, headers, ...init } = options
  const requestHeaders = new Headers(headers)
  if (!requestHeaders.has('Accept')) requestHeaders.set('Accept', 'application/json')

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: requestHeaders,
      signal: controller.signal,
    })
    if (!response.ok) {
      const { message, code } = await readErrorBody(response)
      throw new ApiError(message ?? response.statusText, response.status, code)
    }
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Tiempo de espera agotado', 0, 'timeout')
    }
    throw new ApiError('No se pudo conectar con la API', 0, 'network_error')
  } finally {
    clearTimeout(timer)
  }
}