interface ReportCardProps {
  title: string;
  meta: string;
  onDownload?: () => void;
}

export function ReportCard({ title, meta, onDownload }: ReportCardProps) {
  return (
    <div className="flex items-center justify-between bg-white rounded-lg
                    border border-slate-200 px-4 py-3">
      <div className="space-y-0.5">
        <p className="text-sm font-medium text-slate-800">{title}</p>
        <p className="text-xs text-slate-500">{meta}</p>
      </div>
      {onDownload && (
        <button
          onClick={onDownload}
          className="text-xs text-slate-600 hover:text-slate-900
                     border border-slate-200 rounded px-2 py-1
                     hover:border-slate-400 transition-colors"
        >
          Download
        </button>
      )}
    </div>
  );
}
