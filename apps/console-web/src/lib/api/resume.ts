const INGESTION_BASE_URL =
  process.env.NEXT_PUBLIC_INGESTION_API_URL ?? "http://localhost:8001";

async function parseErrorDetail(res: Response): Promise<string> {
  const body = await res.json().catch(() => ({}));
  if (typeof body?.detail === "string") return body.detail;
  return `HTTP ${res.status}`;
}

export interface UploadResumeResult {
  s3_key: string;
  presigned_url: string;
}

export async function uploadResume(file: File): Promise<UploadResumeResult> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${INGESTION_BASE_URL}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }

  return res.json();
}

export interface AnalyzeResumeParams {
  candidateId: string;
  jobAssessmentId: string;
  orgId: string;
  s3Key: string;
}

export interface AnalyzeResumeResult {
  match_score: number | null;
  parsing_confidence: number | null;
  [key: string]: unknown;
}

export async function analyzeResume(
  params: AnalyzeResumeParams
): Promise<AnalyzeResumeResult> {
  const res = await fetch(`${INGESTION_BASE_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      candidate_id: params.candidateId,
      job_assessment_id: params.jobAssessmentId,
      org_id: params.orgId,
      s3_key: params.s3Key,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }

  return res.json();
}
