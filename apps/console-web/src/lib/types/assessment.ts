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
  title: string;
  description?: string;
  difficulty_level: string;
  duration_minutes: number;
  competency_weightage: Record<string, number>;
}

export interface AssessmentResponse {
  id: string;
  title: string;
  difficulty_level: string;
  duration_minutes: number;
  competency_weightage: Record<string, number>;
  created_at: string;
  updated_at?: string;
}
