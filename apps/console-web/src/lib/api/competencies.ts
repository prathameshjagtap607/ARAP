import { apiFetch } from './index';
import type { Competency, CreateCompetencyRequest } from '@/lib/types/competency';

export async function getCompetencies(): Promise<Competency[]> {
  return apiFetch('/competency-library');
}

export async function createCompetency(data: CreateCompetencyRequest): Promise<Competency> {
  return apiFetch('/competency-library', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateCompetency(
  id: string,
  data: CreateCompetencyRequest
): Promise<Competency> {
  return apiFetch(`/competency-library/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteCompetency(id: string): Promise<void> {
  return apiFetch(`/competency-library/${id}`, {
    method: 'DELETE',
  });
}
