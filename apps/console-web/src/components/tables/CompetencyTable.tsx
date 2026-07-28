'use client';

import { useState } from 'react';
import type { Competency } from '@/lib/types/competency';

interface CompetencyTableProps {
  competencies: Competency[];
  onDelete: (id: string) => Promise<void>;
  onEdit: (competency: Competency) => void;
}

export default function CompetencyTable({
  competencies,
  onDelete,
  onEdit,
}: CompetencyTableProps) {
  const [deleting, setDeleting] = useState<string | null>(null);

  const handleDelete = async (id: string) => {
    if (confirm('Delete this competency? This action cannot be undone.')) {
      setDeleting(id);
      try {
        await onDelete(id);
      } finally {
        setDeleting(null);
      }
    }
  };

  const truncateRubric = (text: string, maxLength: number = 80) => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  if (competencies.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-600">No competencies defined yet</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border border-slate-200 rounded-lg">
      <table className="w-full">
        <thead className="bg-slate-50 border-b border-slate-200">
          <tr>
            <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
              Name
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-slate-900">
              Rubric
            </th>
            <th className="px-6 py-3 text-right text-sm font-semibold text-slate-900">
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {competencies.map((competency) => (
            <tr
              key={competency.id}
              className="border-b border-slate-200 hover:bg-slate-50"
            >
              <td className="px-6 py-4 text-sm text-slate-900 font-medium">
                {competency.name}
              </td>
              <td className="px-6 py-4 text-sm text-slate-600">
                {truncateRubric(competency.rubric)}
              </td>
              <td className="px-6 py-4 text-right space-x-2">
                <button
                  onClick={() => onEdit(competency)}
                  className="inline text-sm font-medium text-blue-600 hover:text-blue-800"
                >
                  Edit
                </button>
                <button
                  onClick={() => handleDelete(competency.id)}
                  disabled={deleting === competency.id}
                  className="inline text-sm font-medium text-red-600 hover:text-red-800 disabled:opacity-50"
                >
                  {deleting === competency.id ? 'Deleting...' : 'Delete'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
