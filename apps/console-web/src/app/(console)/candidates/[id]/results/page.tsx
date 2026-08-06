'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getSessionReport, submitReviewerFeedback, type SessionReport } from '@/lib/api/sessions';

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const [report, setReport] = useState<SessionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<'hire' | 'no_hire' | 'hold'>('hold');
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getSessionReport(id as string);
        setReport(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load results');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [id]);

  const handleSubmitDecision = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitReviewerFeedback(id as string, { final_decision: decision, comment });
      setReport((prev) =>
        prev
          ? {
              ...prev,
              reviewer_override: {
                final_decision: decision,
                comment,
                submitted_at: new Date().toISOString(),
              },
            }
          : prev
      );
      setSubmitted(true);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to submit decision');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <p className="text-center py-12">Loading results...</p>;
  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm font-medium text-red-900">{error}</p>
      </div>
    );
  if (!report) return <p className="text-center py-12">Results not found</p>;

  const full = report.full_report || {};
  const isFullReportGenerated = full.executive_summary !== undefined;
  const alreadySubmitted = submitted || report.reviewer_override != null;
  const discPct =
    full.disc_profile?.confidence != null ? Math.round(full.disc_profile.confidence * 100) : null;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold text-slate-900">Assessment Results</h1>
        <button
          onClick={() => router.back()}
          className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-900 hover:bg-slate-50"
        >
          Back
        </button>
      </div>

      {/* DISC Profile Card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-slate-600 mb-1">Primary DISC Style</p>
            <p className="text-3xl font-bold text-slate-900">
              {full.disc_profile?.primary || '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-600 mb-1">Secondary DISC Style</p>
            <p className="text-3xl font-bold text-slate-900">
              {full.disc_profile?.secondary || '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-600 mb-1">Confidence</p>
            <p className="text-3xl font-bold text-slate-900">
              {discPct !== null ? `${discPct}%` : '—'}
            </p>
          </div>
        </div>
        {full.disc_profile?.rationale && (
          <p className="text-slate-700 text-sm leading-relaxed">{full.disc_profile.rationale}</p>
        )}
      </div>

      {!isFullReportGenerated ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-sm font-medium text-amber-900">
            The full report is still being generated. Check back shortly.
          </p>
        </div>
      ) : (
        <>
          {/* Executive Summary */}
          <div className="rounded-lg border border-slate-200 bg-white p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-3">Executive Summary</h2>
            <p className="text-slate-700 text-sm leading-relaxed">{full.executive_summary}</p>
          </div>

          {/* Strengths */}
          {full.strengths && full.strengths.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-3">Strengths</h2>
              <ul className="space-y-2">
                {full.strengths.map((strength, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-green-600 font-bold">•</span>
                    <span>{strength}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Weaknesses */}
          {full.weaknesses && full.weaknesses.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-3">Weaknesses</h2>
              <ul className="space-y-2">
                {full.weaknesses.map((weakness, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-amber-600 font-bold">•</span>
                    <span>{weakness}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Potential Risks */}
          {full.potential_risks && (
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-3">Potential Risks</h2>
              <p className="text-slate-700 text-sm leading-relaxed">{full.potential_risks}</p>
            </div>
          )}

          {/* Composite Scores */}
          {full.scores && Object.keys(full.scores).length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-3">Composite Scores</h2>
              <div className="space-y-3">
                {Object.entries(full.scores).map(([composite, data]) => (
                  <div key={composite}>
                    <div className="flex justify-between mb-1">
                      <span className="text-sm font-medium text-slate-700">
                        {composite.replace(/_/g, ' ')}
                      </span>
                      <span className="text-sm font-semibold text-slate-900">
                        {data.score.toFixed(2)} / 5.0
                      </span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-2">
                      <div
                        className="bg-slate-900 h-2 rounded-full transition-all"
                        style={{ width: `${(data.score / 5) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Final Verdict */}
          {full.final_verdict && (
            <div className="rounded-lg border border-slate-200 bg-white p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-3">Final Verdict</h2>
              <p className="text-slate-700 text-sm leading-relaxed">{full.final_verdict}</p>
            </div>
          )}

          {/* Reviewer Decision */}
          <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">Assessment Stage Decision</h2>
            <p className="text-xs text-slate-500 -mt-2">
              This only reflects the outcome of this AI assessment stage, not a final hiring decision.
            </p>
            {alreadySubmitted ? (
              <p className="text-sm text-green-700 font-medium">
                {report.reviewer_override
                  ? `Decision submitted: ${report.reviewer_override.final_decision.replace('_', ' ').toUpperCase()}`
                  : 'Decision submitted.'}
              </p>
            ) : (
              <>
                <div className="flex gap-3">
                  {(
                    [
                      { value: 'hire', label: 'Proceed to Next Round' },
                      { value: 'hold', label: 'Hold' },
                      { value: 'no_hire', label: 'Reject at This Stage' },
                    ] as const
                  ).map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setDecision(option.value)}
                      className={`px-4 py-2 rounded-lg border text-sm font-medium ${
                        decision === option.value
                          ? 'border-slate-900 bg-slate-900 text-white'
                          : 'border-slate-300 text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Comment (optional)"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  rows={3}
                />
                {submitError && (
                  <p className="text-sm text-red-700">{submitError}</p>
                )}
                <button
                  type="button"
                  onClick={handleSubmitDecision}
                  disabled={submitting}
                  className="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 disabled:opacity-50"
                >
                  {submitting ? 'Submitting...' : 'Submit Decision'}
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
