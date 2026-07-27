// Shared TypeScript types between ARAP apps.
// Populated in auth session and Phase 1.

export type Role = "admin" | "user" | "candidate" | "client";

export interface ApiResponse<T> {
  data: T;
  status: number;
}
