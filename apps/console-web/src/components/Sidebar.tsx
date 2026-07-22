const navItems = [
  { label: "Dashboard", href: "/" },
  { label: "Assessments", href: "/assessments" },
  { label: "Candidates", href: "/candidates" },
  { label: "Reports", href: "/reports" },
  { label: "Settings", href: "/settings" },
];

export function Sidebar() {
  return (
    <aside className="flex flex-col w-56 min-h-screen bg-slate-800 text-slate-300 shrink-0">
      <div className="px-4 py-5 border-b border-slate-700">
        <span className="text-white font-semibold text-sm tracking-wide">
          ARAP Console
        </span>
      </div>
      <nav className="flex-1 px-2 py-4 space-y-1">
        {navItems.map((item) => (
          <a
            key={item.href}
            href={item.href}
            className="flex items-center px-3 py-2 rounded-md text-sm
                       text-slate-300 hover:bg-slate-700 hover:text-white
                       transition-colors"
          >
            {item.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}
