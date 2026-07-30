import { redirect } from "next/navigation";

jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
}));

describe("Dashboard root page", () => {
  it("redirects to the real HR dashboard instead of showing the placeholder shell", () => {
    const DashboardPage = require("../page").default;
    DashboardPage();
    expect(redirect).toHaveBeenCalledWith("/dashboard/hr");
  });
});

describe("Reports page", () => {
  it("redirects to the real reports dashboard instead of showing placeholder cards", () => {
    const ReportsPage = require("../reports/page").default;
    ReportsPage();
    expect(redirect).toHaveBeenCalledWith("/dashboard/reports");
  });
});
