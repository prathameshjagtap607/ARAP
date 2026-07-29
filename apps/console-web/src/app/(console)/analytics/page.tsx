"use client";

import { useState } from "react";
import ScoreTrends from "./_components/ScoreTrends";
import HiringFunnel from "./_components/HiringFunnel";
import QuestionAnalytics from "./_components/QuestionAnalytics";
import Benchmarking from "./_components/Benchmarking";
import SkillTrends from "./_components/SkillTrends";

type Tab = "score-trends" | "funnel" | "questions" | "benchmarking" | "skill-trends";

const TABS: { id: Tab; label: string }[] = [
  { id: "score-trends", label: "Score Trends" },
  { id: "funnel", label: "Hiring Funnel" },
  { id: "questions", label: "Question Analytics" },
  { id: "benchmarking", label: "Benchmarking" },
  { id: "skill-trends", label: "Skill Trends" },
];

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("score-trends");
  const [mounted, setMounted] = useState<Set<Tab>>(new Set<Tab>(["score-trends"]));

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    setMounted((prev) => {
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Analytics</h1>

      {/* Tab bar */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-slate-800 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab panels — mount on first activation, stay mounted */}
      <div className={activeTab === "score-trends" ? "" : "hidden"}>
        {mounted.has("score-trends") && <ScoreTrends />}
      </div>
      <div className={activeTab === "funnel" ? "" : "hidden"}>
        {mounted.has("funnel") && <HiringFunnel />}
      </div>
      <div className={activeTab === "questions" ? "" : "hidden"}>
        {mounted.has("questions") && <QuestionAnalytics />}
      </div>
      <div className={activeTab === "benchmarking" ? "" : "hidden"}>
        {mounted.has("benchmarking") && <Benchmarking />}
      </div>
      <div className={activeTab === "skill-trends" ? "" : "hidden"}>
        {mounted.has("skill-trends") && <SkillTrends />}
      </div>
    </div>
  );
}
