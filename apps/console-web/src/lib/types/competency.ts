export interface Competency {
  id: string;
  name: string;
  rubric_notes: string | null;
  description?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCompetencyRequest {
  name: string;
  rubric_notes: string;
}
