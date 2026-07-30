import { uploadResume, analyzeResume } from "../resume";

describe("uploadResume", () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  it("posts the file as multipart form data to the ingestion service /upload endpoint", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ s3_key: "resumes/abc.pdf" }),
    });

    const file = new File(["dummy content"], "resume.pdf", { type: "application/pdf" });
    const result = await uploadResume(file);

    expect(result.s3_key).toBe("resumes/abc.pdf");
    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/upload");
    expect(options.body).toBeInstanceOf(FormData);
  });

  it("throws with the server detail message when upload fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "Unsupported file type: text/csv" }),
    });

    const file = new File(["x"], "resume.csv", { type: "text/csv" });
    await expect(uploadResume(file)).rejects.toThrow("Unsupported file type: text/csv");
  });
});

describe("analyzeResume", () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  it("posts candidate_id, job_assessment_id, org_id and s3_key as JSON", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ match_score: 0.8, parsing_confidence: 0.9 }),
    });

    const result = await analyzeResume({
      candidateId: "c1",
      jobAssessmentId: "j1",
      orgId: "o1",
      s3Key: "resumes/abc.pdf",
    });

    expect(result.match_score).toBe(0.8);
    const [url, options] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/analyze");
    const body = JSON.parse(options.body as string);
    expect(body).toEqual({
      candidate_id: "c1",
      job_assessment_id: "j1",
      org_id: "o1",
      s3_key: "resumes/abc.pdf",
    });
  });
});
