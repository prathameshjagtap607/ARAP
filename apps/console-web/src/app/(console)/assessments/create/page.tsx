'use client';

import { useState, useEffect } from 'react';
import { getCompetencies } from '@/lib/api/competencies';
import AssessmentForm from '@/components/forms/AssessmentForm';
import type { Competency } from '@/lib/types/competency';

export default function CreateAssessmentPage() {
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCompetencies()
      .then(setCompetencies)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading competencies...</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Create New Assessment</h1>
      <AssessmentForm competencies={competencies} />
    </div>
  );
}
