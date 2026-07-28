const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let globalAccessToken: string | null = null;

export function setGlobalAccessToken(token: string | null) {
  globalAccessToken = token;
}

export function getGlobalAccessToken(): string | null {
  return globalAccessToken;
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

  // Use provided JWT or global token
  const token = jwt || getGlobalAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...rest, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }

  // Handle 204 No Content (common for DELETE operations)
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}
