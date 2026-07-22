export function Topbar() {
  return (
    <header className="h-12 flex items-center justify-between px-6
                       bg-white border-b border-slate-200 shrink-0">
      <span className="text-sm font-medium text-slate-600">Dashboard</span>
      <div className="flex items-center gap-4">
        <span className="text-xs text-slate-400">Admin</span>
        <div className="w-7 h-7 rounded-full bg-slate-200" />
      </div>
    </header>
  );
}
