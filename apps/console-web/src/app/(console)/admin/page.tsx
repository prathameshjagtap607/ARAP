"use client";

import { useState } from "react";
import TenantsTab from "./_components/TenantsTab";
import PromptsTab from "./_components/PromptsTab";
import RoutingTab from "./_components/RoutingTab";
import HealthTab from "./_components/HealthTab";

type Tab = "tenants" | "prompts" | "routing" | "health";

const TABS: { id: Tab; label: string }[] = [
  { id: "tenants", label: "Tenants" },
  { id: "prompts", label: "Prompt Library" },
  { id: "routing", label: "Model Routing" },
  { id: "health", label: "System Health" },
];

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("tenants");
  const [mounted, setMounted] = useState<Set<Tab>>(new Set<Tab>(["tenants"]));

  function handleTabChange(tab: Tab) {
    setActiveTab(tab);
    setMounted((prev) => {
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-slate-800">Platform Administration</h1>

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

      <div className={activeTab === "tenants" ? "" : "hidden"}>
        {mounted.has("tenants") && <TenantsTab />}
      </div>
      <div className={activeTab === "prompts" ? "" : "hidden"}>
        {mounted.has("prompts") && <PromptsTab />}
      </div>
      <div className={activeTab === "routing" ? "" : "hidden"}>
        {mounted.has("routing") && <RoutingTab />}
      </div>
      <div className={activeTab === "health" ? "" : "hidden"}>
        {mounted.has("health") && <HealthTab />}
      </div>
    </div>
  );
}
