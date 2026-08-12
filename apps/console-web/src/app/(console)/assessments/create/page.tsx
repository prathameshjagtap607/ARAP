'use client';

import AssessmentForm from '@/components/forms/AssessmentForm';

export default function CreateAssessmentPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Create New Assessment</h1>
      <AssessmentForm />
    </div>
  );
}
