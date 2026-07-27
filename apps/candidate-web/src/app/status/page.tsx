"use client";

import { useSession } from "@/context/SessionContext";
import { getStatusBadge } from "@/lib/api/status";

const badgeColorMap = {
  blue: "bg-blue-100 text-blue-900",
  amber: "bg-amber-100 text-amber-900",
  red: "bg-red-100 text-red-900",
};

export default function StatusPage() {
  const { state } = useSession();
  const session = state.session;

  if (!session) {
    return (
      <main id="main-content" className="min-h-screen bg-white px-6 py-12">
        <div className="max-w-2xl mx-auto text-center">
          <p className="text-slate-600">Loading your assessment status...</p>
        </div>
      </main>
    );
  }

  const badge = getStatusBadge(session.status);

  return (
    <main id="main-content" className="min-h-screen bg-slate-50 px-6 py-12">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">
            Your Assessment Status
          </h1>
          <p className="text-slate-600">Track your progress and next steps</p>
        </div>

        {/* Assessment Info Card */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <div className="space-y-4">
            <div>
              <p className="text-sm font-medium text-slate-600">Role</p>
              <p className="text-lg font-semibold text-slate-900">
                {session.job_title || "Assessment"}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">Duration</p>
              <p className="text-slate-900">
                {session.duration_minutes} minutes
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-slate-600">
                Questions to Answer
              </p>
              <p className="text-slate-900">{session.questions.length}</p>
            </div>
          </div>
        </div>

        {/* Status Card */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Status</h2>
            <span
              className={`inline-block px-3 py-1 rounded-full text-sm font-semibold ${
                badgeColorMap[badge.color as keyof typeof badgeColorMap]
              }`}
            >
              {badge.label}
            </span>
          </div>
          <div className="text-sm text-slate-700">
            {session.status === "invited" && (
              <p>
                Your assessment is ready. Click the button below to begin
                answering the questions.
              </p>
            )}
            {session.status === "in_progress" && (
              <p>
                You&apos;re currently working on your assessment. Great progress!
                Continue answering the remaining questions at your own pace.
              </p>
            )}
            {session.status === "completed" && (
              <p>
                Your assessment has been submitted successfully. Our hiring team
                is reviewing your responses and will follow up within 5–7
                business days.
              </p>
            )}
            {session.status === "expired" && (
              <p>
                Unfortunately, your assessment link has expired. Please contact
                the hiring team to request a new link.
              </p>
            )}
          </div>
        </div>

        {/* What's Next Section */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">
            What&apos;s Next
          </h2>

          {session.status === "completed" && (
            <div className="space-y-4 text-sm text-slate-700">
              <div>
                <p className="font-medium text-slate-900 mb-1">Review Phase</p>
                <p>
                  Your responses have been received and will be carefully
                  evaluated by our hiring team.
                </p>
              </div>
              <div>
                <p className="font-medium text-slate-900 mb-1">Timeline</p>
                <p>
                  You can expect a decision email within <strong>5–7</strong>{" "}
                  business days.
                </p>
              </div>
              <div>
                <p className="font-medium text-slate-900 mb-1">Questions?</p>
                <p>
                  If you have questions about your assessment, please reach out
                  to the hiring team.
                </p>
              </div>
            </div>
          )}

          {session.status === "in_progress" && (
            <div className="space-y-4 text-sm text-slate-700">
              <div>
                <p className="font-medium text-slate-900 mb-1">Continue Answering</p>
                <p>
                  You have {session.duration_minutes} minutes to complete this
                  assessment. Your progress is automatically saved after each
                  answer.
                </p>
              </div>
              <div>
                <p className="font-medium text-slate-900 mb-1">Navigation</p>
                <p>
                  You can review and update your answers to previous questions
                  before submitting your final responses.
                </p>
              </div>
              <div className="pt-4">
                <a
                  href="/assessment"
                  className="inline-block px-6 py-3 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 transition-colors focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-slate-900"
                >
                  Return to Assessment
                </a>
              </div>
            </div>
          )}

          {session.status === "invited" && (
            <div className="space-y-4 text-sm text-slate-700">
              <div>
                <p className="font-medium text-slate-900 mb-1">Get Started</p>
                <p>
                  Review the assessment overview and accept the terms to begin.
                  You&apos;ll have {session.duration_minutes} minutes to complete it.
                </p>
              </div>
              <div>
                <p className="font-medium text-slate-900 mb-1">Support</p>
                <p>
                  Make sure you&apos;re in a quiet environment with a stable internet
                  connection before starting.
                </p>
              </div>
              <div className="pt-4">
                <a
                  href="/assessment"
                  className="inline-block px-6 py-3 bg-slate-900 text-white font-medium rounded-lg hover:bg-slate-800 transition-colors focus:outline focus:outline-2 focus:outline-offset-2 focus:outline-slate-900"
                >
                  Start Assessment
                </a>
              </div>
            </div>
          )}

          {session.status === "expired" && (
            <div className="space-y-4 text-sm text-slate-700">
              <div>
                <p className="font-medium text-slate-900 mb-1">
                  Request Extension
                </p>
                <p>
                  Your assessment link may have expired. Please contact the
                  hiring team to request a new link with a fresh time window.
                </p>
              </div>
              <div>
                <p className="font-medium text-slate-900 mb-1">Support</p>
                <p>
                  The hiring team is happy to help. Reply to your invitation
                  email or contact the recruiter directly.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Progress Indicator */}
        {session.status === "in_progress" && (
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">
              Progress
            </h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Questions Answered</span>
                <span className="font-medium text-slate-900">
                  {session.questions.filter((q) => q.answer_text).length} of{" "}
                  {session.questions.length}
                </span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div
                  className="bg-slate-900 h-2 rounded-full transition-all"
                  style={{
                    width: `${
                      (session.questions.filter((q) => q.answer_text).length /
                        session.questions.length) *
                      100
                    }%`,
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
