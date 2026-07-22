import type { ConsoleUser, TokenClaims } from "@/types/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function decodeToken(token: string): TokenClaims {
  const payload = token.split(".")[1];
  const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  return decoded as TokenClaims;
}

function claimsToUser(claims: TokenClaims): ConsoleUser {
  return { id: claims.sub, role: claims.role, orgId: claims.org_id };
}

export async function login(
  email: string,
  password: string
): Promise<{ user: ConsoleUser; accessToken: string }> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Login failed");
  }
  const { access_token } = (await res.json()) as { access_token: string };
  const claims = decodeToken(access_token);
  return { user: claimsToUser(claims), accessToken: access_token };
}

export async function refresh(): Promise<{ user: ConsoleUser; accessToken: string }> {
  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Refresh failed");
  const { access_token } = (await res.json()) as { access_token: string };
  const claims = decodeToken(access_token);
  return { user: claimsToUser(claims), accessToken: access_token };
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  }).catch(() => undefined);
}
