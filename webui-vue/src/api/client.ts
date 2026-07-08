// Thin typed fetch wrapper, mirroring pipeline/lib/api_client.py's
// hand-written minimalism. baseUrl is '' in both dev (Vite proxies /api to
// :8080, see vite.config.ts) and prod (built assets are served same-origin
// by FastAPI), so callers always use relative paths.

const BASE_URL = ''

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.status = status
    this.body = body
  }
}

interface Envelope<T> {
  status: number
  message?: string
  data: T
}

async function request<T>(
  method: string,
  path: string,
  { params, json }: { params?: Record<string, string | number | boolean | undefined>; json?: unknown } = {},
): Promise<T> {
  const url = new URL(BASE_URL + path, window.location.origin)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value))
    }
  }

  const response = await fetch(url.toString().replace(window.location.origin, ''), {
    method,
    headers: json !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: json !== undefined ? JSON.stringify(json) : undefined,
  })

  let body: unknown = null
  const text = await response.text()
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  if (!response.ok) {
    let message = `${method} ${path} failed: ${response.status}`
    if (body && typeof body === 'object' && 'message' in body) {
      message = String((body as Envelope<unknown>).message)
    }
    throw new ApiError(response.status, message, body)
  }

  const envelope = body as Envelope<T>
  return envelope && typeof envelope === 'object' && 'data' in envelope ? envelope.data : (body as T)
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>('GET', path, { params }),
  post: <T>(path: string, json?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>('POST', path, { json: json ?? {}, params }),
  patch: <T>(path: string, json?: unknown, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>('PATCH', path, { json: json ?? {}, params }),
  delete: <T>(path: string, params?: Record<string, string | number | boolean | undefined>) =>
    request<T>('DELETE', path, { params }),
}
