'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { uploadResume, analyzeResume } from '@/lib/api/resume';
import { apiFetch } from '@/lib/api';

type Step = 'idle' | 'uploading' | 'analyzing' | 'synthesizing' | 'done' | 'error';

export default function UploadResumePage() {
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const orgId = user?.orgId || '';
  const candidateId = searchParams.get('candidateId') || '';
  const jobAssessmentId = searchParams.get('jobAssessmentId') || '';

  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<Step>('idle');
  const [error, setError] = useState<string | null>(null);
  const [matchScore, setMatchScore] = useState<number | null>(null);

  const canSubmit = Boolean(file) && Boolean(candidateId) && Boolean(jobAssessmentId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);

    try {
      setStep('uploading');
      const { s3_key } = await uploadResume(file);

      setStep('analyzing');
      const analysis = await analyzeResume({
        candidateId,
        jobAssessmentId,
        orgId,
        s3Key: s3_key,
      });
      setMatchScore(analysis.match_score ?? null);

      setStep('synthesizing');
      await apiFetch('/candidate-profiles/synthesize', {
        method: 'POST',
        body: JSON.stringify({
          candidate_id: candidateId,
          job_assessment_id: jobAssessmentId,
        }),
      });

      setStep('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setStep('error');
    }
  }

  const stepLabel: Record<Step, string> = {
    idle: '',
    uploading: 'Uploading resume…',
    analyzing: 'Parsing resume and computing match score…',
    synthesizing: 'Synthesizing candidate profile…',
    done: 'Done — candidate profile is ready. You can now generate questions for this session.',
    error: 'Something went wrong.',
  };

  return (
    <div className="space-y-6 max-w-xl">
      <h1 className="text-2xl font-bold text-slate-900">Upload Resume</h1>

      {(!candidateId || !jobAssessmentId) && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">
            Missing candidate or job assessment reference — open this page via the
            &quot;Upload Resume&quot; link on the Candidates page.
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={step !== 'idle' && step !== 'error'}
          className="block w-full text-sm text-slate-700"
        />
        <button
          type="submit"
          disabled={!canSubmit || (step !== 'idle' && step !== 'error')}
          className="px-4 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 disabled:opacity-50"
        >
          Upload &amp; Analyze
        </button>
      </form>

      {step !== 'idle' && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm ${
            step === 'error'
              ? 'border-red-200 bg-red-50 text-red-900'
              : step === 'done'
              ? 'border-green-200 bg-green-50 text-green-900'
              : 'border-slate-200 bg-slate-50 text-slate-700'
          }`}
        >
          <p>{stepLabel[step]}</p>
          {error && <p className="mt-1">{error}</p>}
          {step === 'done' && matchScore !== null && (
            <p className="mt-1">Resume-to-JD match score: {(matchScore * 100).toFixed(0)}%</p>
          )}
        </div>
      )}

      <Link href="/candidates" className="text-sm font-medium text-blue-600 hover:text-blue-800">
        Back to Candidates
      </Link>
    </div>
  );
}
