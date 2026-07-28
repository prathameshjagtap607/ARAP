'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { getAssessment } from '@/lib/api/assessments';
import InviteForm from '@/components/forms/InviteForm';
import type { AssessmentResponse } from '@/lib/types/assessment';

export default function InvitePage() {
  const { id } = useParams();
  const [assessment, setAssessment] = useState<AssessmentResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAssessment(id as string)
      .then(setAssessment)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p>Loading assessment...</p>;
  if (!assessment) return <p>Assessment not found</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Send Assessment Invite</h1>
      <InviteForm sessionId={id as string} jobTitle={assessment.title} />
    </div>
  );
}
