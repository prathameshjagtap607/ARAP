'use client';

import { useState } from 'react';
import Link from 'next/link';
import type { AssessmentResponse } from '@/lib/types/assessment';

interface AssessmentTableProps {
  assessments: AssessmentResponse[];
  onDelete: (id: string) => Promise<void>;
}

export default function AssessmentTable({
  assessments,
  onDelete,
}: AssessmentTableProps) {
  const [deleting, setDeleting] = useState<string | null>(null);

  const handleDelete = async (id: string) => {
    if (confirm('Delete this assessment? This action cannot be undone.')) {
      setDeleting(id);
      try {
        await onDelete(id);
      } finally {
        setDeleting(null);
      }
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  if (assessments.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-600 mb-4">No assessments yet</p>
        <Link
          href="/assessments/create"
          className="inline-block px-4 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800"
        >
          Create First Assessment
        </Link>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-lg">
      <table className="w-full">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
            <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
              Job Title
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
              Difficulty
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
              Duration
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
              Created
            </th>
            <th className="px-6 py-3 text-right text-sm font-semibold text-slate-900">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {assessments.map((assessment) => (
            <tr
              key={assessment.id}
              className="border-b border-slate-200 hover:bg-slate-50"
            >
              <td className="px-6 py-4 text-sm text-slate-900 font-medium">
                {assessment.title}
              </td>
              <td className="px-6 py-4 text-sm text-slate-600">
                {assessment.difficulty_level}
              </td>
              <td className="px-6 py-4 text-sm text-slate-600">
                {assessment.duration_minutes} min
              </td>
              <td className="px-6 py-4 text-sm text-slate-600">
                {formatDate(assessment.created_at)}
              </td>
              <td className="px-6 py-4 text-right space-x-2">
                <Link
                  href={`/assessments/${assessment.id}/invite`}
                  className="inline text-sm font-medium text-green-600 hover:text-green-800"
                >
                  Invite
                </Link>
                <button
                  onClick={() => handleDelete(assessment.id)}
                  disabled={deleting === assessment.id}
                  className="inline text-sm font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
                >
                  {deleting === assessment.id ? 'Deleting...' : 'Delete'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
