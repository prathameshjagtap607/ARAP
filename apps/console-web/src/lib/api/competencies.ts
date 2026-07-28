import { apiFetch } from './index';
import type { Competency, CreateCompetencyRequest } from '@/lib/types/competency';

export async function getCompetencies(): Promise<Competency[]> {
  return apiFetch('/competencies');
}

export async function createCompetency(data: CreateCompetencyRequest): Promise<Competency> {
  return apiFetch('/competencies', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateCompetency(
  id: string,
  data: CreateCompetencyRequest
): Promise<Competency> {
  return apiFetch(`/competencies/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteCompetency(id: string): Promise<void> {
  return apiFetch(`/competencies/${id}`, {
    method: 'DELETE',
  });
}
