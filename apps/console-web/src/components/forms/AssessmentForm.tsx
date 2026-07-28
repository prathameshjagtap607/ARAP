'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import type { AssessmentFormData, Competency, CreateAssessmentRequest } from '@/lib/types/assessment';
import { apiFetch } from '@/lib/api';

interface AssessmentFormProps {
  competencies: Competency[];
  initialData?: Partial<AssessmentFormData>;
  assessmentId?: string;
  isEditing?: boolean;
}

const DIFFICULTY_OPTIONS = ['junior', 'mid', 'senior', 'executive'];

export default function AssessmentForm({
  competencies,
  initialData,
  assessmentId,
  isEditing = false,
}: AssessmentFormProps) {
  const router = useRouter();

  const [formData, setFormData] = useState<AssessmentFormData>({
    jobTitle: initialData?.jobTitle || '',
    jobRole: initialData?.jobRole || '',
    experienceMinYears: initialData?.experienceMinYears || 0,
    experienceMaxYears: initialData?.experienceMaxYears || 10,
    difficulty: initialData?.difficulty || 'mid',
    durationMinutes: initialData?.durationMinutes || 60,
    competencies: initialData?.competencies || [],
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const calculateWeightageSum = useCallback(() => {
    return formData.competencies.reduce((sum, c) => sum + c.weightage, 0);
  }, [formData.competencies]);

  const validateForm = useCallback(() => {
    const newErrors: Record<string, string> = {};

    if (!formData.jobTitle.trim()) newErrors.jobTitle = 'Job title is required';
    if (!formData.jobRole.trim()) newErrors.jobRole = 'Job role is required';
    if (formData.experienceMinYears < 0) newErrors.experienceMinYears = 'Min years must be >= 0';
    if (formData.experienceMaxYears < formData.experienceMinYears) {
      newErrors.experienceMaxYears = 'Max years must be >= min years';
    }
    if (formData.durationMinutes < 5) newErrors.durationMinutes = 'Duration must be >= 5 minutes';
    if (formData.competencies.length === 0) newErrors.competencies = 'At least one competency required';

    const sum = calculateWeightageSum();
    const tolerance = 0.01;
    if (Math.abs(sum - 100) > tolerance) {
      newErrors.competencies = `Weightage must sum to 100% (current: ${sum.toFixed(2)}%)`;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData, calculateWeightageSum]);

  const handleCompetencyWeightageChange = (competencyId: string, newWeightage: number) => {
    setFormData((prev) => ({
      ...prev,
      competencies: prev.competencies.map((c) =>
        c.competencyId === competencyId ? { ...c, weightage: newWeightage } : c
      ),
    }));
  };

  const handleAddCompetency = (competencyId: string) => {
    if (!formData.competencies.find((c) => c.competencyId === competencyId)) {
      setFormData((prev) => ({
        ...prev,
        competencies: [...prev.competencies, { competencyId, weightage: 0 }],
      }));
    }
  };

  const handleRemoveCompetency = (competencyId: string) => {
    setFormData((prev) => ({
      ...prev,
      competencies: prev.competencies.filter((c) => c.competencyId !== competencyId),
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!validateForm()) return;

    setLoading(true);

    try {
      const competencyWeightage: Record<string, number> = {};
      formData.competencies.forEach((c) => {
        competencyWeightage[c.competencyId] = c.weightage;
      });

      const payload: CreateAssessmentRequest = {
        title: formData.jobTitle,
        difficulty_level: formData.difficulty,
        duration_minutes: formData.durationMinutes,
        competency_weightage: competencyWeightage,
      };

      if (isEditing && assessmentId) {
        setSubmitError('Editing assessments is not yet supported');
        setLoading(false);
        return;
      }

      await apiFetch('/job-assessments', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      router.push('/assessments');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save assessment';
      setSubmitError(message);
    } finally {
      setLoading(false);
    }
  };

  const weightageSum = calculateWeightageSum();

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-2xl">
      {/* Error Alert */}
      {submitError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">{submitError}</p>
        </div>
      )}

      {/* Job Title */}
      <div>
        <label htmlFor="jobTitle" className="block text-sm font-medium text-slate-700 mb-1">
          Job Title *
        </label>
        <input
          id="jobTitle"
          type="text"
          value={formData.jobTitle}
          onChange={(e) => setFormData((prev) => ({ ...prev, jobTitle: e.target.value }))}
          className={`w-full px-3 py-2 border rounded-lg focus:outline focus:outline-2 focus:outline-offset-2 ${
            errors.jobTitle ? 'border-red-500' : 'border-slate-300'
          }`}
          aria-invalid={!!errors.jobTitle}
        />
        {errors.jobTitle && <p className="text-xs text-red-600 mt-1">{errors.jobTitle}</p>}
      </div>

      {/* Job Role */}
      <div>
        <label htmlFor="jobRole" className="block text-sm font-medium text-slate-700 mb-1">
          Job Role *
        </label>
        <input
          id="jobRole"
          type="text"
          value={formData.jobRole}
          onChange={(e) => setFormData((prev) => ({ ...prev, jobRole: e.target.value }))}
          className={`w-full px-3 py-2 border rounded-lg focus:outline focus:outline-2 focus:outline-offset-2 ${
            errors.jobRole ? 'border-red-500' : 'border-slate-300'
          }`}
          aria-invalid={!!errors.jobRole}
        />
        {errors.jobRole && <p className="text-xs text-red-600 mt-1">{errors.jobRole}</p>}
      </div>

      {/* Experience Range */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="minYears" className="block text-sm font-medium text-slate-700 mb-1">
            Min Years Experience
          </label>
          <input
            id="minYears"
            type="number"
            min="0"
            value={formData.experienceMinYears}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, experienceMinYears: parseInt(e.target.value) || 0 }))
            }
            className={`w-full px-3 py-2 border rounded-lg focus:outline focus:outline-2 focus:outline-offset-2 ${
              errors.experienceMinYears ? 'border-red-500' : 'border-slate-300'
            }`}
          />
          {errors.experienceMinYears && (
            <p className="text-xs text-red-600 mt-1">{errors.experienceMinYears}</p>
          )}
        </div>
        <div>
          <label htmlFor="maxYears" className="block text-sm font-medium text-slate-700 mb-1">
            Max Years Experience
          </label>
          <input
            id="maxYears"
            type="number"
            min="0"
            value={formData.experienceMaxYears}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, experienceMaxYears: parseInt(e.target.value) || 10 }))
            }
            className={`w-full px-3 py-2 border rounded-lg focus:outline focus:outline-2 focus:outline-offset-2 ${
              errors.experienceMaxYears ? 'border-red-500' : 'border-slate-300'
            }`}
          />
          {errors.experienceMaxYears && (
            <p className="text-xs text-red-600 mt-1">{errors.experienceMaxYears}</p>
          )}
        </div>
      </div>

      {/* Difficulty & Duration */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="difficulty" className="block text-sm font-medium text-slate-700 mb-1">
            Difficulty Level
          </label>
          <select
            id="difficulty"
            value={formData.difficulty}
            onChange={(e) =>
              setFormData((prev) => ({
                ...prev,
                difficulty: e.target.value as AssessmentFormData['difficulty'],
              }))
            }
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline focus:outline-2 focus:outline-offset-2"
          >
            {DIFFICULTY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt.charAt(0).toUpperCase() + opt.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="duration" className="block text-sm font-medium text-slate-700 mb-1">
            Duration (minutes)
          </label>
          <input
            id="duration"
            type="number"
            min="5"
            value={formData.durationMinutes}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, durationMinutes: parseInt(e.target.value) || 60 }))
            }
            className={`w-full px-3 py-2 border rounded-lg focus:outline focus:outline-2 focus:outline-offset-2 ${
              errors.durationMinutes ? 'border-red-500' : 'border-slate-300'
            }`}
          />
          {errors.durationMinutes && (
            <p className="text-xs text-red-600 mt-1">{errors.durationMinutes}</p>
          )}
        </div>
      </div>

      {/* Competencies */}
      <div>
        <div className="flex justify-between items-center mb-3">
          <label className="block text-sm font-medium text-slate-700">Competencies *</label>
          <span
            className={`text-xs font-medium ${
              Math.abs(weightageSum - 100) < 0.01 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            Weightage: {weightageSum.toFixed(2)}%
          </span>
        </div>

        {errors.competencies && (
          <p className="text-xs text-red-600 mb-2">{errors.competencies}</p>
        )}

        {/* Selected Competencies */}
        <div className="space-y-2 mb-4">
          {formData.competencies.map((selected) => {
            const comp = competencies.find((c) => c.id === selected.competencyId);
            return (
              <div key={selected.competencyId} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-900">{comp?.name}</p>
                </div>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={selected.weightage}
                  onChange={(e) =>
                    handleCompetencyWeightageChange(selected.competencyId, parseFloat(e.target.value) || 0)
                  }
                  className="w-20 px-2 py-1 border border-slate-300 rounded text-sm focus:outline focus:outline-2"
                  aria-label={`Weightage for ${comp?.name}`}
                />
                <span className="text-sm text-slate-600 w-8">%</span>
                <button
                  type="button"
                  onClick={() => handleRemoveCompetency(selected.competencyId)}
                  className="text-red-600 hover:text-red-800 text-sm font-medium"
                >
                  Remove
                </button>
              </div>
            );
          })}
        </div>

        {/* Add Competency Selector */}
        <div>
          <label htmlFor="addCompetency" className="block text-xs font-medium text-slate-600 mb-1">
            Add competency
          </label>
          <select
            id="addCompetency"
            onChange={(e) => {
              if (e.target.value) {
                handleAddCompetency(e.target.value);
                e.target.value = '';
              }
            }}
            className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline focus:outline-2"
          >
            <option value="">Select a competency...</option>
            {competencies.map((comp) => (
              <option
                key={comp.id}
                value={comp.id}
                disabled={formData.competencies.some((c) => c.competencyId === comp.id)}
              >
                {typeof comp === 'object' && comp.name ? comp.name : String(comp)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Submit Button */}
      <div className="flex gap-3 pt-4">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 disabled:opacity-50 focus:outline focus:outline-2 focus:outline-offset-2"
        >
          {loading ? 'Saving...' : isEditing ? 'Update Assessment' : 'Create Assessment'}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="px-6 py-2 border border-slate-300 text-slate-900 font-medium rounded-lg hover:bg-slate-50 focus:outline focus:outline-2 focus:outline-offset-2"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
