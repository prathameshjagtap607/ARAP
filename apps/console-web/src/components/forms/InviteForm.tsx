'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { sendInvite } from '@/lib/api/assessments';

interface InviteFormProps {
  sessionId: string;
  jobTitle: string;
}

export default function InviteForm({ sessionId, jobTitle }: InviteFormProps) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);

  const validateEmail = (e: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) {
      setError('Email is required');
      return;
    }

    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }

    setLoading(true);

    try {
      const result = await sendInvite(sessionId, email);
      setGeneratedLink(result.link);
      setSuccess(true);
      setEmail('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send invite');
    } finally {
      setLoading(false);
    }
  };

  if (success && generatedLink) {
    return (
      <div className="space-y-6">
        <div className="rounded-lg border border-green-200 bg-green-50 px-6 py-4">
          <h3 className="text-sm font-semibold text-green-900 mb-2">Invite Sent!</h3>
          <p className="text-sm text-green-800 mb-4">
            Assessment invite has been sent to {email}. They&apos;ll receive an email with the assessment link.
          </p>
          <div className="bg-white rounded p-3 mb-4">
            <p className="text-xs text-slate-600 mb-2">Direct link (copy if needed):</p>
            <input
              type="text"
              value={generatedLink}
              readOnly
              className="w-full px-3 py-2 border border-slate-300 rounded text-sm font-mono focus:outline focus:outline-2"
            />
          </div>
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
              setGeneratedLink(null);
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
          className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline focus:outline-2 focus:outline-offset-2"
        />
        <p className="text-xs text-slate-600 mt-1">
          Candidate will receive an email with the assessment link and instructions.
        </p>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 disabled:opacity-50 focus:outline focus:outline-2 focus:outline-offset-2"
        >
          {loading ? 'Sending...' : 'Send Invite'}
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
