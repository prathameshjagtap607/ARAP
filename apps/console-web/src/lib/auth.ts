import type { ConsoleUser, TokenClaims } from "@/types/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function decodeToken(token: string): TokenClaims {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(
      atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
    ) as TokenClaims;
  } catch {
    throw new Error("Invalid token format received from server");
  }
}

function claimsToUser(claims: TokenClaims): ConsoleUser {
  return { id: claims.sub, role: claims.role, orgId: claims.org_id };
}

// NOTE: The server sets both `refresh_token` (httpOnly) and `user_role` (plain)
// cookies in the Set-Cookie header of the login response.
// middleware.ts reads `user_role` to gate the /admin route.
export async function login(
  email: string,
  password: string
): Promise<{ user: ConsoleUser; accessToken: string }> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password, org_id: process.env.NEXT_PUBLIC_ORG_ID ?? "00000000-0000-0000-0000-000000000001" }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Login failed");
  }
  const { access_token, refresh_token } = (await res.json()) as { access_token: string; refresh_token: string };
  const claims = decodeToken(access_token);
  document.cookie = `refresh_token=${refresh_token}; path=/; SameSite=Lax`;
  document.cookie = `user_role=${claims.role}; path=/; SameSite=Lax`;
  return { user: claimsToUser(claims), accessToken: access_token };
}

export async function refresh(): Promise<{ user: ConsoleUser; accessToken: string }> {
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Refresh failed");
  const { access_token } = (await res.json()) as { access_token: string };
  const claims = decodeToken(access_token);
  return { user: claimsToUser(claims), accessToken: access_token };
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  }).catch(() => undefined);
}
