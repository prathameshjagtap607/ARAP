'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import type { AssessmentFormData, CreateAssessmentRequest } from '@/lib/types/assessment';
import { apiFetch } from '@/lib/api';

interface AssessmentFormProps {
  initialData?: Partial<AssessmentFormData>;
  assessmentId?: string;
  isEditing?: boolean;
}

const DIFFICULTY_OPTIONS = ['junior', 'mid', 'senior', 'executive'];

export default function AssessmentForm({
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
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const validateForm = useCallback(() => {
    const newErrors: Record<string, string> = {};

    if (!formData.jobTitle.trim()) newErrors.jobTitle = 'Job title is required';
    if (!formData.jobRole.trim()) newErrors.jobRole = 'Job role is required';
    if (formData.experienceMinYears < 0) newErrors.experienceMinYears = 'Min years must be >= 0';
    if (formData.experienceMaxYears < formData.experienceMinYears) {
      newErrors.experienceMaxYears = 'Max years must be >= min years';
    }
    if (formData.durationMinutes < 5) newErrors.durationMinutes = 'Duration must be >= 5 minutes';

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!validateForm()) return;

    setLoading(true);

    try {
      const payload: CreateAssessmentRequest = {
        title: formData.jobTitle,
        difficulty_level: formData.difficulty,
        duration_minutes: formData.durationMinutes,
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
