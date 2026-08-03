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
  const token = jwt || getGlobalAccessToken() || getTokenFromStorage();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...rest, headers });
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
