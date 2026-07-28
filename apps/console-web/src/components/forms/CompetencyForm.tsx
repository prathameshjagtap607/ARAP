'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { createCompetency, updateCompetency } from '@/lib/api/competencies';
import type { Competency } from '@/lib/types/competency';

interface CompetencyFormProps {
  competency?: Competency;
  onSuccess?: () => void;
}

export default function CompetencyForm({ competency, onSuccess }: CompetencyFormProps) {
  const router = useRouter();
  const [name, setName] = useState(competency?.name ?? '');
  const [rubric, setRubric] = useState(competency?.rubric ?? '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditing = !!competency;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Competency name is required');
      return;
    }

    if (!rubric.trim()) {
      setError('Rubric is required');
      return;
    }

    setLoading(true);

    try {
      const data = { name: name.trim(), rubric: rubric.trim() };

      if (isEditing) {
        await updateCompetency(competency.id, data);
      } else {
        await createCompetency(data);
      }

      if (onSuccess) {
        onSuccess();
      } else {
        router.refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">{error}</p>
        </div>
      )}

      <div>
        <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1">
          Competency Name *
        </label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g., Problem Solving"
          className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline focus:outline-2 focus:outline-offset-2"
        />
        <p className="text-xs text-slate-600 mt-1">
          A clear, concise name for the competency.
        </p>
      </div>

      <div>
        <label htmlFor="rubric" className="block text-sm font-medium text-slate-700 mb-1">
          Rubric *
        </label>
        <textarea
          id="rubric"
          rows={6}
          value={rubric}
          onChange={(e) => setRubric(e.target.value)}
          placeholder="Describe the evaluation criteria and levels..."
          className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline focus:outline-2 focus:outline-offset-2 resize-y"
        />
        <p className="text-xs text-slate-600 mt-1">
          Define how this competency will be assessed and the criteria for different proficiency levels.
        </p>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 disabled:opacity-50 focus:outline focus:outline-2 focus:outline-offset-2"
        >
          {loading ? (isEditing ? 'Updating...' : 'Creating...') : (isEditing ? 'Update' : 'Create')}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="px-6 py-2 border border-slate-300 text-slate-900 font-medium rounded-lg hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
