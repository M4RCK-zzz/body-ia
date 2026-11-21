const STORAGE_KEY = "bodyvision.access_token";

type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();

export function getAccessToken(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token: string): void {
  sessionStorage.setItem(STORAGE_KEY, token);
}

export function clearAccessToken(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* almacenamiento no disponible */
  }
}

export function onUnauthorized(listener: Listener): () => void {
  unauthorizedListeners.add(listener);
  return () => {
    unauthorizedListeners.delete(listener);
  };
}

export function notifyUnauthorized(): void {
  unauthorizedListeners.forEach((listener) => listener());
}