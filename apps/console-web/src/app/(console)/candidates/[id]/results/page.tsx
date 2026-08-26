'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  getSessionReport,
  getSessionAnswers,
  type SessionReport,
  type SessionAnswerItem,
} from '@/lib/api/sessions';

export default function ResultsPage() {
  const { id } = useParams();
  const router = useRouter();
  const [report, setReport] = useState<SessionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<SessionAnswerItem[]>([]);

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

      // Natural-vs-adaptive comparison — best-effort, non-blocking: if it
      // fails, the rest of the report still renders normally.
      try {
        const answerData = await getSessionAnswers(id as string);
        setAnswers(answerData.questions);
      } catch {
        // no-op — comparison section simply won't render
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

  const full = report.full_report || {};
  const isFullReportGenerated = full.executive_summary !== undefined;
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

      {/* Developmental Insights — DISC-Based Generative Leadership Question
          Framework §11. Additive: renders only when present, never replaces
          or alters any existing report section below. */}
      {full.developmental_insights && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Developmental Insights</h2>
            <p className="text-xs text-slate-500 mt-1">
              These reflect natural behavioural tendencies, not judgments — the goal is to
              identify where a tendency helps and where it may need conscious adaptation.
            </p>
          </div>

          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">Natural Leadership Tendencies</p>
            <p className="text-sm text-slate-700 leading-relaxed">
              {full.developmental_insights.natural_leadership_tendencies}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Where This Helps</p>
              <ul className="space-y-1">
                {full.developmental_insights.behavioural_strengths.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-green-600 font-bold">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Where It May Need Adapting</p>
              <ul className="space-y-1">
                {full.developmental_insights.potential_blind_spots.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-amber-600 font-bold">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-slate-700">
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Under Pressure</p>
              <p>{full.developmental_insights.behaviour_under_pressure}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Communication Style</p>
              <p>{full.developmental_insights.communication_preferences}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Conflict Tendency</p>
              <p>{full.developmental_insights.conflict_tendencies}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Decision-Making</p>
              <p>{full.developmental_insights.decision_making_tendencies}</p>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-slate-600 mb-1">Adaptability</p>
            <p className="text-sm text-slate-700 leading-relaxed">
              {full.developmental_insights.adaptability_assessment}
            </p>
          </div>

          {full.developmental_insights.areas_for_behavioural_development.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-600 mb-1">Suggested Development Areas</p>
              <ul className="space-y-1">
                {full.developmental_insights.areas_for_behavioural_development.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-indigo-600 font-bold">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Natural vs Adaptive comparison — DISC-Based Generative Leadership
          Question Framework §8. Additive: only shown for questions where the
          candidate answered both the natural and adaptive prompt; never
          blocks or alters any other section of this page. */}
      {answers.some((a) => a.answer_text && a.adaptive_answer_text) && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Natural vs. Adaptive Response
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              &quot;Natural&quot; is the candidate&apos;s instinctive choice. &quot;Adaptive&quot; is
              what they identified as most effective, even if not their instinct — a
              measure of behavioural flexibility, not a right/wrong comparison.
            </p>
          </div>
          <div className="space-y-4">
            {answers
              .filter((a) => a.answer_text && a.adaptive_answer_text)
              .map((a) => (
                <div key={a.id} className="border-t border-slate-100 pt-4">
                  <p className="text-sm font-medium text-slate-800 mb-2">{a.question.text}</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs font-medium text-slate-500 mb-1">Natural</p>
                      <p className="text-sm text-slate-800">
                        {a.options?.[a.answer_text as string] ?? a.answer_text}
                      </p>
                    </div>
                    <div className="rounded-lg bg-indigo-50 p-3">
                      <p className="text-xs font-medium text-indigo-600 mb-1">Adaptive</p>
                      <p className="text-sm text-slate-800">
                        {a.options?.[a.adaptive_answer_text as string] ?? a.adaptive_answer_text}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Ranking responses — DISC-Based Generative Leadership Question
          Framework §7 (Ranking format). Additive: only shown for questions
          the candidate actually answered in ranking form. */}
      {answers.some((a) => a.ranking_order && a.ranking_order.length > 0) && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-900">Ranking Responses</h2>
          <div className="space-y-4">
            {answers
              .filter((a) => a.ranking_order && a.ranking_order.length > 0)
              .map((a) => (
                <div key={a.id} className="border-t border-slate-100 pt-4">
                  <p className="text-sm font-medium text-slate-800 mb-2">{a.question.text}</p>
                  <ol className="space-y-1">
                    {a.ranking_order!.map((letter, i) => (
                      <li key={letter} className="text-sm text-slate-700">
                        {i + 1}. {a.options?.[letter] ?? letter}
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Reflection responses — DISC-Based Generative Leadership Question
          Framework §7 (Reflection format). Additive: only shown for
          questions the candidate actually answered in free-text form. */}
      {answers.some((a) => a.reflection_text) && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-900">Reflection Responses</h2>
          <div className="space-y-4">
            {answers
              .filter((a) => a.reflection_text)
              .map((a) => (
                <div key={a.id} className="border-t border-slate-100 pt-4">
                  <p className="text-sm font-medium text-slate-800 mb-2">{a.question.text}</p>
                  <p className="text-sm text-slate-700 leading-relaxed">{a.reflection_text}</p>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Other responses — any answered question that isn't already covered
          above (Natural/Adaptive pair, Ranking, or Reflection), e.g.
          Situational Response, First Action, standalone Behavioural Choice,
          or Self-Awareness formats. Additive: only fills the gap so every
          answered question is visible somewhere on this page. */}
      {answers.some(
        (a) => a.answer_text && !a.adaptive_answer_text && !a.ranking_order && !a.reflection_text
      ) && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-900">Other Responses</h2>
          <div className="space-y-4">
            {answers
              .filter(
                (a) =>
                  a.answer_text && !a.adaptive_answer_text && !a.ranking_order && !a.reflection_text
              )
              .map((a) => (
                <div key={a.id} className="border-t border-slate-100 pt-4">
                  <p className="text-sm font-medium text-slate-800 mb-2">{a.question.text}</p>
                  <p className="text-sm text-slate-700 leading-relaxed">
                    {a.options?.[a.answer_text as string] ?? a.answer_text}
                  </p>
                </div>
              ))}
          </div>
        </div>
      )}

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

        </>
      )}
    </div>
  );
}
