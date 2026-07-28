export interface Competency {
  id: string;
  name: string;
  rubric: string;
  created_at?: string;
  updated_at?: string;
}

export interface CreateCompetencyRequest {
  name: string;
  rubric: string;
}
