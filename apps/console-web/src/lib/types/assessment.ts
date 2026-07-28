export interface Competency {
  id: string;
  name: string;
  rubric: string;
}

export interface AssessmentFormData {
  jobTitle: string;
  jobRole: string;
  experienceMinYears: number;
  experienceMaxYears: number;
  difficulty: 'junior' | 'mid' | 'senior' | 'executive';
  durationMinutes: number;
  competencies: Array<{
    competencyId: string;
    weightage: number;
  }>;
}

export interface CreateAssessmentRequest {
  job_title: string;
  job_role: string;
  experience_min_years: number;
  experience_max_years: number;
  difficulty: string;
  duration_minutes: number;
  competency_weightage: Record<string, number>;
}

export interface AssessmentResponse {
  id: string;
  job_title: string;
  job_role: string;
  difficulty: string;
  duration_minutes: number;
  competency_weightage: Record<string, number>;
  created_at: string;
  updated_at: string;
  is_template: boolean;
}
