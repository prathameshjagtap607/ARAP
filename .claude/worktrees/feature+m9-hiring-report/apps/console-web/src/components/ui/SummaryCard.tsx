interface SummaryCardProps {
  label: string;
  value: string | number;
  delta?: string;
}

export function SummaryCard({ label, value, delta }: SummaryCardProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-1">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-slate-800">{value}</p>
      {delta && (
        <p
          className={`text-xs ${
            delta.startsWith("-") ? "text-red-500" : "text-emerald-600"
          }`}
        >
          {delta}
        </p>
      )}
    </div>
  );
}
