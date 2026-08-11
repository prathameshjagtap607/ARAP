'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getAssessments, deleteAssessment } from '@/lib/api/assessments';
import { fetchUsersList } from '@/lib/api/dashboards';
import AssessmentTable from '@/components/tables/AssessmentTable';
import { useAuth } from '@/context/AuthContext';
import type { AssessmentResponse } from '@/lib/types/assessment';

export default function AssessmentsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  const [assessments, setAssessments] = useState<AssessmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filterUserId, setFilterUserId] = useState('');
  const [userOptions, setUserOptions] = useState<{ id: string; email: string }[]>([]);

  useEffect(() => {
    if (!isAdmin) return;
    fetchUsersList().then(setUserOptions);
  }, [isAdmin]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await getAssessments(filterUserId || undefined);
        setAssessments(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load assessments');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [filterUserId]);

  const handleDelete = async (id: string) => {
    setError(null);
    try {
      await deleteAssessment(id);
      setAssessments((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete assessment');
    }
  };

  const filteredAssessments = assessments.filter((a) =>
    a.title.toLowerCase().includes(search.trim().toLowerCase())
  );

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

      <div className="flex gap-3 flex-wrap">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by job title..."
          className="w-full max-w-sm px-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-slate-900"
        />

        {isAdmin && (
          <select
            value={filterUserId}
            onChange={(e) => setFilterUserId(e.target.value)}
            className="px-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-slate-900"
          >
            <option value="">All Users</option>
            {userOptions.map((u) => (
              <option key={u.id} value={u.id}>
                {u.email}
              </option>
            ))}
          </select>
        )}
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
          assessments={filteredAssessments}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}
