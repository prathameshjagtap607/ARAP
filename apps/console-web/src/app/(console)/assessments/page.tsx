'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getAssessments, deleteAssessment, cloneAssessment } from '@/lib/api/assessments';
import AssessmentTable from '@/components/tables/AssessmentTable';
import type { AssessmentResponse } from '@/lib/types/assessment';

export default function AssessmentsPage() {
  const [assessments, setAssessments] = useState<AssessmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getAssessments();
        setAssessments(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load assessments');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const handleDelete = async (id: string) => {
    await deleteAssessment(id);
    setAssessments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleClone = async (id: string) => {
    const cloned = await cloneAssessment(id);
    setAssessments((prev) => [cloned, ...prev]);
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Job Assessments</h1>
        <Link
          href="/assessments/create"
          className="px-4 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 focus:outline focus:outline-2 focus:outline-offset-2"
        >
          Create Assessment
        </Link>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-slate-600">Loading assessments...</p>
        </div>
      ) : (
        <AssessmentTable
          assessments={assessments}
          onDelete={handleDelete}
          onClone={handleClone}
        />
      )}
    </div>
  );
}
