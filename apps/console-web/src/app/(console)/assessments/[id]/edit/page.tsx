'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { getAssessment } from '@/lib/api/assessments';
import { getCompetencies } from '@/lib/api/competencies';
import AssessmentForm from '@/components/forms/AssessmentForm';
import type { AssessmentResponse } from '@/lib/types/assessment';
import type { Competency } from '@/lib/types/competency';

export default function EditAssessmentPage() {
  const { id } = useParams();
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getAssessment(id as string), getCompetencies()])
      .then(([ass, comps]) => {
        setAssessment(ass);
        setCompetencies(comps);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Loading...</p>;
  if (!assessment) return <p>Assessment not found</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Edit Assessment</h1>
      <AssessmentForm
        competencies={competencies}
        initialData={{
          jobTitle: assessment.title,
          jobRole: '',
          experienceMinYears: 0,
          experienceMaxYears: 10,
          difficulty: assessment.difficulty_level as any,
          durationMinutes: assessment.duration_minutes,
          competencies: Object.entries(assessment.competency_weightage).map(
            ([compId, weight]) => ({
              competencyId: compId,
              weightage: weight,
            })
          ),
        }}
        assessmentId={id as string}
        isEditing={true}
      />
    </div>
  );
}
