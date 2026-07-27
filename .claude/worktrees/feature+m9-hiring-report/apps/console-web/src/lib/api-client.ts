import { refresh } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function createApiClient(
  getToken: () => string | null,
  onUnauth: () => void
) {
  async function request<T>(
    path: string,
    options: RequestInit & { skipAuth?: boolean } = {}
  ): Promise<T> {
    const { skipAuth, ...fetchOptions } = options;
    const headers = new Headers(fetchOptions.headers);

    if (!skipAuth) {
      const token = getToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
    }

    const res = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      headers,
      credentials: "include",
    });

    if (res.status === 401 && !skipAuth) {
      let newToken: string;
      try {
        const refreshed = await refresh();
        newToken = refreshed.accessToken;
      } catch {
        onUnauth();
        throw new Error("Session expired");
      }
      headers.set("Authorization", `Bearer ${newToken}`);
      const retry = await fetch(`${API_BASE}${path}`, {
        ...fetchOptions,
        headers,
        credentials: "include",
      });
      if (retry.status === 401) {
        onUnauth();
        throw new Error("Session expired");
      }
      if (!retry.ok) {
        const err = await retry.json().catch(() => ({}));
        throw new Error(
          (err as { detail?: string }).detail ?? `Request failed: ${retry.status}`
        );
      }
      return retry.json() as Promise<T>;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(
        (err as { detail?: string }).detail ?? `Request failed: ${res.status}`
      );
    }

    return res.json() as Promise<T>;
  }

  return { request };
}
