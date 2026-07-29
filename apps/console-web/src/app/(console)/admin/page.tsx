'use client';

import { useState, useEffect } from 'react';
import { SummaryCard } from "@/components/ui/SummaryCard";
import CompetencyTable from "@/components/tables/CompetencyTable";
import CompetencyForm from "@/components/forms/CompetencyForm";
import { getCompetencies, deleteCompetency } from "@/lib/api/competencies";
import type { Competency } from '@/lib/types/competency';

export default function AdminPage() {
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [selectedCompetency, setSelectedCompetency] = useState<Competency | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCompetencies = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCompetencies();
      setCompetencies(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load competencies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompetencies();
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await deleteCompetency(id);
      setCompetencies(competencies.filter(c => c.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete competency');
    }
  };

  const handleEdit = (competency: Competency) => {
    setSelectedCompetency(competency);
    setIsCreating(true);
  };

  const handleFormSuccess = () => {
    setIsCreating(false);
    setSelectedCompetency(null);
    loadCompetencies();
  };

  if (isCreating) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-slate-800">
            {selectedCompetency ? 'Edit Competency' : 'Create Competency'}
          </h1>
          <button
            onClick={() => {
              setIsCreating(false);
              setSelectedCompetency(null);
            }}
            className="text-sm text-slate-600 hover:text-slate-900"
          >
            Back
          </button>
        </div>
        <CompetencyForm
          competency={selectedCompetency ?? undefined}
          onSuccess={handleFormSuccess}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-800">Admin</h1>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <SummaryCard label="Organisations" value="—" />
        <SummaryCard label="Total Users" value="—" />
        <SummaryCard label="Active Orgs" value="—" />
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-800">Competencies</h2>
          <button
            onClick={() => {
              setSelectedCompetency(null);
              setIsCreating(true);
            }}
            className="px-4 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 text-sm"
          >
            Add Competency
          </button>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm font-medium text-red-900">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="text-center py-12">
            <p className="text-slate-600">Loading competencies...</p>
          </div>
        ) : (
          <CompetencyTable
            competencies={competencies}
            onDelete={handleDelete}
            onEdit={handleEdit}
          />
        )}
      </div>

      <p className="text-xs text-slate-400">
        Organisation & user management — Phase 1. Competency management — Phase 2.
      </p>
    </div>
  );
}
