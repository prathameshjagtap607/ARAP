export interface StatusBadge {
  label: string;
  color: "blue" | "amber" | "red";
}

export function getStatusBadge(
  state: "invited" | "in_progress" | "completed" | "expired"
): StatusBadge {
  switch (state) {
    case "invited":
      return { label: "Invited", color: "blue" };
    case "in_progress":
      return { label: "In Progress", color: "blue" };
    case "completed":
      return { label: "Completed", color: "amber" };
    case "expired":
      return { label: "Expired", color: "red" };
    default:
      const _exhaustive: never = state;
      return _exhaustive;
  }
}

export function getDaysElapsed(startedAt: string | Date | null | undefined): number | null {
  if (!startedAt) return null;

  const start = new Date(startedAt);
  const now = new Date();

  // Calculate milliseconds difference
  const diffMs = now.getTime() - start.getTime();

  // Convert to days
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  return days >= 0 ? days : null;
}
