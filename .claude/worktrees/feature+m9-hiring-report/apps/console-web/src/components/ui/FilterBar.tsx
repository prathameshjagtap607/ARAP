export interface FilterDef {
  key: string;
  label: string;
  options: { label: string; value: string }[];
}

interface FilterBarProps {
  search: string;
  onSearch: (value: string) => void;
  filters: FilterDef[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

export function FilterBar({
  search,
  onSearch,
  filters,
  values,
  onChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="search"
        placeholder="Search…"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
        className="h-8 rounded border border-slate-200 px-3 text-sm
                   text-slate-700 placeholder:text-slate-400
                   focus:outline-none focus:ring-1 focus:ring-slate-400
                   w-48"
      />
      {filters.map((f) => (
        <select
          key={f.key}
          value={values[f.key] ?? ""}
          onChange={(e) => onChange(f.key, e.target.value)}
          className="h-8 rounded border border-slate-200 px-2 text-sm
                     text-slate-700 focus:outline-none focus:ring-1
                     focus:ring-slate-400"
        >
          <option value="">{f.label}</option>
          {f.options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ))}
    </div>
  );
}
