import { apiFetch } from "../index";
import {
  fetchHRDashboardCounts,
  fetchRecentSessions,
  fetchReportsList,
  fetchAdminDashboard,
} from "../dashboards";

jest.mock("../index", () => ({
  apiFetch: jest.fn(),
}));

const mockedApiFetch = apiFetch as jest.Mock;

describe("fetchHRDashboardCounts", () => {
  beforeEach(() => mockedApiFetch.mockReset());

  it("counts active (non-template) job assessments from the real /job-assessments list", async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/job-assessments")) {
        return Promise.resolve([
          { id: "1", is_template: false },
          { id: "2", is_template: true },
        ]);
      }
      if (path.startsWith("/sessions")) return Promise.resolve([]);
      if (path.startsWith("/reports")) return Promise.resolve({ items: [], total_count: 0 });
      return Promise.resolve([]);
    });

    const result = await fetchHRDashboardCounts("org-1");
    expect(result.activeAssessments).toBe(1);
    expect(mockedApiFetch).toHaveBeenCalledWith(
      expect.stringContaining("/job-assessments"),
      expect.anything()
    );
  });

  it("counts distinct in-progress candidates from the real /sessions list", async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/job-assessments")) return Promise.resolve([]);
      if (path.startsWith("/sessions")) {
        return Promise.resolve([
          { id: "s1", candidate_email: "a@x.com", status: "in_progress" },
          { id: "s2", candidate_email: "a@x.com", status: "in_progress" },
          { id: "s3", candidate_email: "b@x.com", status: "completed" },
        ]);
      }
      if (path.startsWith("/reports")) return Promise.resolve({ items: [], total_count: 0 });
      return Promise.resolve([]);
    });

    const result = await fetchHRDashboardCounts("org-1");
    expect(result.candidatesInProgress).toBe(1);
  });

  it("reads awaitingReview from the real /reports?status=awaiting_review total_count", async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/job-assessments")) return Promise.resolve([]);
      if (path.startsWith("/sessions")) return Promise.resolve([]);
      if (path.startsWith("/reports")) {
        expect(path).toContain("status=awaiting_review");
        return Promise.resolve({ items: [], total_count: 3 });
      }
      return Promise.resolve([]);
    });

    const result = await fetchHRDashboardCounts("org-1");
    expect(result.awaitingReview).toBe(3);
  });
});

describe("fetchRecentSessions", () => {
  beforeEach(() => mockedApiFetch.mockReset());

  it("maps the plain array response from /sessions into DashboardSession rows", async () => {
    mockedApiFetch.mockResolvedValue([
      {
        id: "s1",
        candidate_email: "alice@example.com",
        job_title: "Engineer",
        status: "invited",
        created_at: "2026-07-28T00:00:00Z",
        started_at: null,
      },
    ]);

    const result = await fetchRecentSessions("org-1");
    expect(result).toHaveLength(1);
    expect(result[0].candidateName).toBe("alice@example.com");
    expect(result[0].jobTitle).toBe("Engineer");
    expect(result[0].status).toBe("invited");
  });
});

describe("fetchReportsList", () => {
  beforeEach(() => mockedApiFetch.mockReset());

  it("maps real /reports items into ReportRow rows", async () => {
    mockedApiFetch.mockResolvedValue({
      items: [
        {
          id: "r1",
          candidate_name: "Bob",
          job_title: "PM",
          verdict: "hire",
          overall_score: 4.2,
          created_at: "2026-07-28T00:00:00Z",
        },
      ],
      total_count: 1,
    });

    const result = await fetchReportsList("org-1");
    expect(result.totalCount).toBe(1);
    expect(result.reports[0].candidateName).toBe("Bob");
    expect(result.reports[0].overallScore).toBe(4.2);
  });
});

describe("fetchAdminDashboard", () => {
  beforeEach(() => mockedApiFetch.mockReset());

  it("reads users from the real /users list endpoint", async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/users")) {
        return Promise.resolve({
          items: [{ id: "u1", email: "a@x.com", role: "admin", created_at: "2026-07-28T00:00:00Z" }],
          total_count: 1,
        });
      }
      if (path.startsWith("/competency-library")) return Promise.resolve([]);
      if (path.startsWith("/job-assessments")) return Promise.resolve([]);
      return Promise.resolve([]);
    });

    const result = await fetchAdminDashboard("org-1");
    expect(result.totalUsers).toBe(1);
    expect(result.users[0].email).toBe("a@x.com");
  });

  it("derives role templates from /job-assessments rows where is_template is true", async () => {
    mockedApiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/users")) return Promise.resolve({ items: [], total_count: 0 });
      if (path.startsWith("/competency-library")) return Promise.resolve([]);
      if (path.startsWith("/job-assessments")) {
        return Promise.resolve([
          { id: "j1", title: "Senior Engineer", is_template: true, competency_weightage: { a: 50, b: 50 }, created_at: "2026-07-28T00:00:00Z" },
          { id: "j2", title: "Other", is_template: false, competency_weightage: {}, created_at: "2026-07-28T00:00:00Z" },
        ]);
      }
      return Promise.resolve([]);
    });

    const result = await fetchAdminDashboard("org-1");
    expect(result.templates).toHaveLength(1);
    expect(result.templates[0].name).toBe("Senior Engineer");
    expect(result.templates[0].competencyCount).toBe(2);
  });
});
