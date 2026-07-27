'use client';

import React, { useState } from 'react';
import { Filter } from '@/lib/types/dashboard';

interface FilterBarProps {
  filters: Filter[];
  onApply: (values: Record<string, any>) => void;
  onReset: () => void;
  loading?: boolean;
}

export default function FilterBar({
  filters,
  onApply,
  onReset,
  loading = false,
}: FilterBarProps) {
  const [values, setValues] = useState<Record<string, any>>(
    filters.reduce((acc, filter) => {
      if (filter.type === 'date-range') {
        acc[`${filter.key}_start`] = '';
        acc[`${filter.key}_end`] = '';
      } else if (filter.type === 'multi-select') {
        acc[filter.key] = [];
      } else {
        acc[filter.key] = '';
      }
      return acc;
    }, {} as Record<string, any>)
  );

  const handleChange = (key: string, value: any) => {
    setValues((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleCheckboxChange = (filterKey: string, optionValue: string, checked: boolean) => {
    setValues((prev) => {
      const currentValues = prev[filterKey] || [];
      if (checked) {
        return {
          ...prev,
          [filterKey]: [...currentValues, optionValue],
        };
      } else {
        return {
          ...prev,
          [filterKey]: currentValues.filter((v: string) => v !== optionValue),
        };
      }
    });
  };

  const handleApply = () => {
    onApply(values);
  };

  const handleReset = () => {
    const resetValues = filters.reduce((acc, filter) => {
      if (filter.type === 'date-range') {
        acc[`${filter.key}_start`] = '';
        acc[`${filter.key}_end`] = '';
      } else if (filter.type === 'multi-select') {
        acc[filter.key] = [];
      } else {
        acc[filter.key] = '';
      }
      return acc;
    }, {} as Record<string, any>);

    setValues(resetValues);
    onReset();
  };

  return (
    <div className="flex flex-wrap gap-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
      {filters.map((filter) => (
        <div key={filter.key}>
          <label className="text-sm font-medium text-slate-700 mb-1 block">
            {filter.label}
          </label>

          {filter.type === 'select' && (
            <select
              value={values[filter.key] || ''}
              onChange={(e) => handleChange(filter.key, e.target.value)}
              disabled={loading}
              className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
            >
              <option value="">{filter.placeholder || 'Select...'}</option>
              {filter.options?.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          )}

          {filter.type === 'search' && (
            <input
              type="text"
              value={values[filter.key] || ''}
              onChange={(e) => handleChange(filter.key, e.target.value)}
              placeholder={filter.placeholder || 'Search...'}
              disabled={loading}
              className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
            />
          )}

          {filter.type === 'date-range' && (
            <div className="flex gap-2">
              <input
                type="date"
                value={values[`${filter.key}_start`] || ''}
                onChange={(e) => handleChange(`${filter.key}_start`, e.target.value)}
                disabled={loading}
                className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
              />
              <input
                type="date"
                value={values[`${filter.key}_end`] || ''}
                onChange={(e) => handleChange(`${filter.key}_end`, e.target.value)}
                disabled={loading}
                className="px-3 py-2 border border-slate-300 rounded text-sm disabled:opacity-50"
              />
            </div>
          )}

          {filter.type === 'multi-select' && (
            <div className="space-y-2">
              {filter.options?.map((option) => (
                <div key={option.value} className="flex items-center">
                  <input
                    type="checkbox"
                    id={`${filter.key}_${option.value}`}
                    checked={values[filter.key]?.includes(option.value) || false}
                    onChange={(e) =>
                      handleCheckboxChange(filter.key, option.value, e.target.checked)
                    }
                    disabled={loading}
                    className="w-4 h-4 border border-slate-300 rounded disabled:opacity-50"
                  />
                  <label
                    htmlFor={`${filter.key}_${option.value}`}
                    className="ml-2 text-sm text-slate-700 disabled:opacity-50"
                  >
                    {option.label}
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      <div className="flex gap-2 ml-auto self-end">
        <button
          onClick={handleReset}
          disabled={loading}
          className="px-4 py-2 text-sm font-medium rounded border border-slate-300 text-slate-700 disabled:opacity-50"
        >
          Reset
        </button>
        <button
          onClick={handleApply}
          disabled={loading}
          className="px-4 py-2 text-sm font-medium rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
