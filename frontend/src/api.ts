export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

const CLAVE = 'dhayana_token'

export function leerToken(): string {
  try {
    return localStorage.getItem(CLAVE) ?? ''
  } catch {
    return ''
  }
}

export function guardarToken(t: string) {
  try {
    localStorage.setItem(CLAVE, t)
  } catch {
    /* sin almacenamiento: el token vive solo en esta pestaña */
  }
}

export function mensajeDeError(e: unknown): string {
  const msg = e instanceof Error ? e.message : ''
  // Chrome: "Failed to fetch" · Firefox: "NetworkError…" · Safari: "Load failed"
  return !msg || /failed to fetch|networkerror|load failed/i.test(msg)
    ? 'No pude conectar con el servidor. ¿Está prendido el backend (uvicorn)?'
    : msg
}

export async function api<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const r = await fetch(`${API}${ruta}`, {
    ...opciones,
    headers: { 'Content-Type': 'application/json', 'X-Admin-Token': leerToken(), ...(opciones.headers ?? {}) },
  })
  const tipo = r.headers.get('content-type') ?? ''
  const datos = tipo.includes('json') ? await r.json() : await r.text()
  if (!r.ok) {
    const det = typeof datos === 'object' && datos ? (datos as { detail?: unknown }).detail : datos
    throw new Error(typeof det === 'string' ? det : 'Revisa los datos del pedido.')
  }
  return datos as T
}
