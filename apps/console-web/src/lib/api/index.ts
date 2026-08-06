const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STORAGE_KEY = "arap_auth_token";

let globalAccessToken: string | null = null;

export function setGlobalAccessToken(token: string | null) {
  globalAccessToken = token;
}

export function getGlobalAccessToken(): string | null {
  return globalAccessToken;
}

function getTokenFromStorage(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function getAuthToken(): string | null {
  return getGlobalAccessToken() || getTokenFromStorage();
}

function persistAccessToken(token: string) {
  setGlobalAccessToken(token);
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(STORAGE_KEY, token);
    } catch {
      // ignore storage failures (e.g. private browsing)
    }
  }
}

function clearPersistedAccessToken() {
  setGlobalAccessToken(null);
  if (typeof window !== 'undefined') {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore storage failures
    }
  }
}

// Dedupe concurrent refresh attempts so multiple 401s in flight only
// trigger one call to /auth/refresh.
let refreshInFlight: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      // Lazy import avoids a circular dependency (lib/auth.ts doesn't import this module).
      const { refresh } = await import('@/lib/auth');
      const { accessToken } = await refresh();
      persistAccessToken(accessToken);
      return accessToken;
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { jwt?: string } = {}
): Promise<T> {
  const { jwt, ...rest } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string>),
  };

  // Use provided JWT, global token, or read from localStorage
  const originalToken = jwt || getGlobalAccessToken() || getTokenFromStorage();
  if (originalToken) headers["Authorization"] = `Bearer ${originalToken}`;

  let res = await fetch(`${BASE_URL}${path}`, { ...rest, headers });

  // On an expired console session (not an explicitly-passed candidate/client JWT),
  // silently refresh the access token once and retry before giving up.
  if (res.status === 401 && !jwt && originalToken) {
    try {
      const newToken = await refreshAccessToken();
      const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` };
      res = await fetch(`${BASE_URL}${path}`, { ...rest, headers: retryHeaders });
    } catch {
      clearPersistedAccessToken();
    }
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    let errorMessage = `HTTP ${res.status}`;

    if (detail?.detail) {
      if (typeof detail.detail === 'string') {
        errorMessage = detail.detail;
      } else if (Array.isArray(detail.detail)) {
        errorMessage = detail.detail
          .map((item: unknown) => typeof item === 'string' ? item : JSON.stringify(item))
          .join(', ');
      } else if (typeof detail.detail === 'object') {
        errorMessage = Object.entries(detail.detail)
          .map(([key, value]) => {
            const valueStr = typeof value === 'string' ? value : JSON.stringify(value);
            return `${key}: ${valueStr}`;
          })
          .join(', ');
      }
    }

    throw new Error(errorMessage);
  }

  // Handle 204 No Content (common for DELETE operations)
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}
