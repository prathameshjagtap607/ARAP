import type { Role } from "@arap/shared-types";

export interface TokenClaims {
  sub: string;       // user ID (UUID)
  role: Role;
  org_id: string;    // org UUID
  exp: number;       // unix timestamp
}

export interface ConsoleUser {
  id: string;
  role: Role;
  orgId: string;
}
