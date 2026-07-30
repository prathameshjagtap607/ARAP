'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { sendInvite } from '@/lib/api/assessments';
import { sendSessionInvite } from '@/lib/api/sessions';
import { uploadResume, analyzeResume } from '@/lib/api/resume';
import { apiFetch } from '@/lib/api';

interface InviteFormProps {
  sessionId: string;
  jobTitle: string;
  orgId?: string;
  durationMinutes?: number;
}

type Step =
  | 'idle'
  | 'registering'
  | 'uploading'
  | 'analyzing'
  | 'synthesizing'
  | 'generating'
  | 'sending';

const STEP_LABEL: Record<Step, string> = {
  idle: '',
  registering: 'Registering candidate…',
  uploading: 'Uploading resume…',
  analyzing: 'Parsing resume and computing match score…',
  synthesizing: 'Synthesizing candidate profile…',
  generating: 'Generating personalized questions…',
  sending: 'Sending assessment invite…',
};

export default function InviteForm({ sessionId, jobTitle, orgId = '', durationMinutes = 60 }: InviteFormProps) {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [step, setStep] = useState<Step>('idle');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  const loading = step !== 'idle';

  const validateEmail = (e: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Candidate name is required');
      return;
    }

    if (!email.trim()) {
      setError('Email is required');
      return;
    }

    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    if (!file) {
      setError('Resume is required');
      return;
    }

    try {
      setStep('registering');
      const invite = await sendInvite(sessionId, name, email, durationMinutes * 60);

      setStep('uploading');
      const { s3_key } = await uploadResume(file);

      setStep('analyzing');
      await analyzeResume({
        candidateId: invite.candidate_id,
        jobAssessmentId: sessionId,
        orgId,
        s3Key: s3_key,
      });

      setStep('synthesizing');
      await apiFetch('/candidate-profiles/synthesize', {
        method: 'POST',
        body: JSON.stringify({
          candidate_id: invite.candidate_id,
          job_assessment_id: sessionId,
        }),
      });

      setStep('generating');
      await apiFetch(`/question-sets/generate/${invite.session_id}`, {
        method: 'POST',
      });

      setStep('sending');
      const sent = await sendSessionInvite(invite.session_id);
      setEmailSent(sent.email_sent);

      setSuccess(true);
      setName('');
      setEmail('');
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send invite');
    } finally {
      setStep('idle');
    }
  };

  if (success) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-green-200 bg-green-50 px-6 py-4">
          <h3 className="text-sm font-semibold text-green-900 mb-2">
            {emailSent ? 'Invite Sent!' : 'Candidate Ready — Invite Not Emailed'}
          </h3>
          <p className="text-sm text-green-800 mb-4">
            {emailSent
              ? 'Resume parsed, candidate profile synthesized, questions generated, and the assessment invite has been sent. They’ll receive an email with the assessment link.'
              : 'Resume parsed, candidate profile synthesized, and questions generated — but no email provider is configured, so the invite link was not emailed. Send it from the Candidates page once email is set up.'}
          </p>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => router.push('/dashboard/assessments')}
            className="px-6 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 focus:outline focus:outline-2 focus:outline-offset-2"
          >
            Back to Assessments
          </button>
          <button
            onClick={() => {
              setSuccess(false);
              setEmailSent(false);
            }}
            className="px-6 py-2 border border-slate-300 text-slate-900 font-medium rounded-lg hover:bg-slate-50"
          >
            Send Another
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-xl">
      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
        <p className="text-sm text-blue-900">
          <strong>Assessment:</strong> {jobTitle}
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm font-medium text-red-900">{error}</p>
        </div>
      )}

      {loading && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-sm text-slate-700">{STEP_LABEL[step]}</p>
        </div>
      )}

      <div>
        <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1">
          Candidate Name *
        </label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="John Doe"
          disabled={loading}
          className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline focus:outline-2 focus:outline-offset-2"
        />
      </div>

      <div>
        <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1">
          Candidate Email Address *
        </label>
        <input
          id="email"
          type="text"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="candidate@example.com"
          disabled={loading}
          className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline focus:outline-2 focus:outline-offset-2"
        />
      </div>

      <div>
        <label htmlFor="resume" className="block text-sm font-medium text-slate-700 mb-1">
          Resume *
        </label>
        <input
          id="resume"
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          disabled={loading}
          required
          className="block w-full text-sm text-slate-700"
        />
        <p className="text-xs text-slate-600 mt-1">
          The resume will be parsed, the candidate profile synthesized against this job&apos;s
          requirements, personalized questions generated and locked, and the assessment invite
          emailed automatically.
        </p>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 disabled:opacity-50 focus:outline focus:outline-2 focus:outline-offset-2"
        >
          {loading ? 'Processing…' : 'Send Invite'}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          disabled={loading}
          className="px-6 py-2 border border-slate-300 text-slate-900 font-medium rounded-lg hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
