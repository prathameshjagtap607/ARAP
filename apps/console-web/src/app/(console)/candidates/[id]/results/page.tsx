'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getSessionReport, type SessionReport } from '@/lib/api/sessions';

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const [report, setReport] = useState<SessionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (loading) return <p className="text-center py-12">Loading results...</p>;
  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
        <p className="text-sm font-medium text-red-900">{error}</p>
      </div>
    );
  if (!report) return <p className="text-center py-12">Results not found</p>;

  const getVerdictColor = (verdict: string | null) => {
    const colors: Record<string, string> = {
      strong_hire: 'text-green-700 bg-green-50 border-green-200',
      hire: 'text-green-600 bg-green-50 border-green-200',
      consider: 'text-yellow-600 bg-yellow-50 border-yellow-200',
      borderline: 'text-orange-600 bg-orange-50 border-orange-200',
      reject: 'text-red-700 bg-red-50 border-red-200',
    };
    return (verdict && colors[verdict]) || 'text-gray-700 bg-gray-50 border-gray-200';
  };

  const full = report.full_report || {};
  const isFullReportGenerated = full.executive_summary !== undefined;
  const overallPct =
    full.overall_rating !== undefined ? Math.round((full.overall_rating / 5) * 100) : null;
  const confidencePct =
    report.ai_confidence_score !== null ? Math.round(report.ai_confidence_score) : null;

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

      {/* Overall Score Card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-slate-600 mb-1">Overall Score</p>
            <p className="text-3xl font-bold text-slate-900">
              {overallPct !== null ? `${overallPct}%` : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-600 mb-1">AI Confidence</p>
            <p className="text-3xl font-bold text-slate-900">
              {confidencePct !== null ? `${confidencePct}%` : '—'}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-600 mb-1">Verdict</p>
            <div className={`rounded-lg border px-3 py-2 text-sm font-medium ${getVerdictColor(report.verdict)}`}>
              {report.verdict ? report.verdict.replace(/_/g, ' ').toUpperCase() : '—'}
            </div>
          </div>
        </div>
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
        </>
      )}
    </div>
  );
}
