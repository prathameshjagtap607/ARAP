import { getStatusBadge, getDaysElapsed } from "../status";

describe("getStatusBadge", () => {
  it.each([
    ["invited", "Invited", "blue"],
    ["in_progress", "In Progress", "blue"],
    ["completed", "Completed", "amber"],
    ["expired", "Expired", "red"],
  ] as const)("maps %s to label %s and color %s", (state, label, color) => {
    expect(getStatusBadge(state)).toEqual({ label, color });
  });
});

describe("getDaysElapsed", () => {
  it("returns null when startedAt is not provided", () => {
    expect(getDaysElapsed(null)).toBeNull();
    expect(getDaysElapsed(undefined)).toBeNull();
  });

  it("returns 0 for a timestamp from earlier today", () => {
    const now = new Date();
    expect(getDaysElapsed(now.toISOString())).toBe(0);
  });

  it("returns the correct number of whole days elapsed", () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000);
    expect(getDaysElapsed(threeDaysAgo.toISOString())).toBe(3);
  });

  it("returns null for a future timestamp", () => {
    const future = new Date(Date.now() + 24 * 60 * 60 * 1000);
    expect(getDaysElapsed(future.toISOString())).toBeNull();
  });
});
