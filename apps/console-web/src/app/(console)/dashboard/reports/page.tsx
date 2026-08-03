'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import FilterBar from '@/components/dashboard/FilterBar';
import ChartCard from '@/components/dashboard/ChartCard';
import { fetchReportsList, downloadReportPdf } from '@/lib/api/dashboards';
import type { Filter } from '@/lib/types/dashboard';
import type { ReportsDashboardData } from '@/lib/types/dashboard';

const verdictBadgeMap: Record<string, { color: 'green' | 'blue' | 'amber' | 'orange' | 'red' }> = {
  strong_hire: { color: 'green' },
  hire: { color: 'blue' },
  consider: { color: 'amber' },
  borderline: { color: 'orange' },
  reject: { color: 'red' },
};

const verdictLabels: Record<string, string> = {
  strong_hire: 'Strong Hire',
  hire: 'Hire',
  consider: 'Consider',
  borderline: 'Borderline',
  reject: 'Reject',
};

export default function ReportsDashboardPage() {
  const { user } = useAuth();
  const orgId = user?.orgId || '';

  // State for reports data
  const [data, setData] = useState<ReportsDashboardData>({
    reports: [],
    verdictDistribution: [],
    scoreBandDistribution: [],
    totalCount: 0,
    currentPage: 0,
    pageSize: 20,
  });
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // State for filters
  const [verdictFilter, setVerdictFilter] = useState<string[]>([]);
  const [scoreBandFilter, setScoreBandFilter] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // State for pagination
  const [currentPage, setCurrentPage] = useState(0);

  const filters: Filter[] = [
    {
      key: 'search',
      label: 'Search',
      type: 'search',
      placeholder: 'Search by candidate name or job title',
    },
    {
      key: 'verdict',
      label: 'Verdict',
      type: 'multi-select',
      options: [
        { label: 'Strong Hire', value: 'strong_hire' },
        { label: 'Hire', value: 'hire' },
        { label: 'Consider', value: 'consider' },
        { label: 'Borderline', value: 'borderline' },
        { label: 'Reject', value: 'reject' },
      ],
    },
    {
      key: 'scoreBand',
      label: 'Score Band',
      type: 'multi-select',
      options: [
        { label: '4.5-5.0', value: '4.5-5.0' },
        { label: '4.0-4.4', value: '4.0-4.4' },
        { label: '3.5-3.9', value: '3.5-3.9' },
        { label: '3.0-3.4', value: '3.0-3.4' },
        { label: '<3.0', value: '<3.0' },
      ],
    },
    {
      key: 'dateRange',
      label: 'Date Range',
      type: 'date-range',
    },
  ];

  // Fetch reports data on mount and when filters/pagination changes
  useEffect(() => {
    if (!orgId) return;

    const controller = new AbortController();

    const loadReports = async () => {
      setLoading(true);
      try {
        // Build filters object for API
        const apiFilters: Record<string, unknown> = {};

        if (verdictFilter.length > 0) {
          apiFilters.verdict = verdictFilter;
        }
        if (dateFrom) {
          apiFilters.dateFrom = dateFrom;
        }
        if (dateTo) {
          apiFilters.dateTo = dateTo;
        }

        const response = await fetchReportsList(
          orgId,
          Object.keys(apiFilters).length > 0 ? apiFilters : undefined,
          20,
          currentPage * 20,
          controller.signal
        );

        if (!controller.signal.aborted) {
          // Filter by score band and search query if provided
          let filteredReports = response.reports;

          if (scoreBandFilter.length > 0) {
            filteredReports = filteredReports.filter((report) => {
              const score = report.overallScore;
              return scoreBandFilter.some((band) => {
                if (band === '4.5-5.0') return score >= 4.5 && score <= 5.0;
                if (band === '4.0-4.4') return score >= 4.0 && score < 4.5;
                if (band === '3.5-3.9') return score >= 3.5 && score < 4.0;
                if (band === '3.0-3.4') return score >= 3.0 && score < 3.5;
                if (band === '<3.0') return score < 3.0;
                return false;
              });
            });
          }

          if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            filteredReports = filteredReports.filter((report) =>
              report.candidateName.toLowerCase().includes(query) ||
              report.jobTitle.toLowerCase().includes(query)
            );
          }

          setData({
            ...response,
            reports: filteredReports,
          });
        }
      } catch (error) {
        if (error instanceof Error && error.name !== 'AbortError') {
          console.error('Failed to load reports:', error);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    loadReports();

    return () => {
      controller.abort();
    };
  }, [orgId, verdictFilter, scoreBandFilter, searchQuery, dateFrom, dateTo, currentPage]);

  const handleFilterApply = (values: Record<string, any>) => {
    setSearchQuery(values.search || '');
    setVerdictFilter(values.verdict || []);
    setScoreBandFilter(values.scoreBand || []);
    setDateFrom(values.dateRange_start || '');
    setDateTo(values.dateRange_end || '');
    setCurrentPage(0); // Reset to first page
  };

  const handleFilterReset = () => {
    setSearchQuery('');
    setVerdictFilter([]);
    setScoreBandFilter([]);
    setDateFrom('');
    setDateTo('');
    setCurrentPage(0);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateString;
    }
  };

  const formatScore = (score: number) => {
    return score.toFixed(2);
  };

  const handleDownload = async (reportId: string) => {
    setDownloadingId(reportId);
    try {
      await downloadReportPdf(reportId);
    } catch (error) {
      console.error('Failed to download report:', error);
    } finally {
      setDownloadingId(null);
    }
  };

  const totalPages = Math.ceil(data.totalCount / data.pageSize);
  const canPrevious = currentPage > 0;
  const canNext = currentPage < totalPages - 1;

  // Transform verdict distribution for pie chart
  const verdictChartData = data.verdictDistribution.map((item) => ({
    name: verdictLabels[item.verdict] || item.verdict,
    value: item.count,
  }));

  // Transform score band distribution for bar chart
  const scoreBandChartData = data.scoreBandDistribution.map((item) => ({
    band: item.band,
    count: item.count,
  }));

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <h1 className="text-2xl font-bold text-slate-900">Reports Dashboard</h1>

      {/* Filter Bar */}
      <FilterBar
        filters={filters}
        onApply={handleFilterApply}
        onReset={handleFilterReset}
        loading={loading}
      />

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard
          title="Verdict Distribution"
          data={verdictChartData}
          chartType="pie"
          xKey="name"
          yKey="value"
          loading={loading}
          height={300}
        />
        <ChartCard
          title="Score Band Distribution"
          data={scoreBandChartData}
          chartType="bar"
          xKey="band"
          yKey="count"
          loading={loading}
          height={300}
        />
      </div>

      {/* Reports Table */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-slate-900">Reports</h2>
          <p className="text-sm text-slate-600">
            Total: {data.totalCount}
          </p>
        </div>

        {loading && data.reports.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <div className="inline-block">
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
                <div className="h-12 bg-slate-200 rounded w-96"></div>
              </div>
            </div>
          </div>
        ) : data.reports.length === 0 ? (
          <div className="px-6 py-12 text-center text-slate-500">
            <p>No reports found</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    <th className="px-6 py-3 text-left font-semibold text-slate-900">
                      Candidate
                    </th>
                    <th className="px-6 py-3 text-left font-semibold text-slate-900">
                      Job
                    </th>
                    <th className="px-6 py-3 text-left font-semibold text-slate-900">
                      Verdict
                    </th>
                    <th className="px-6 py-3 text-left font-semibold text-slate-900">
                      Score
                    </th>
                    <th className="px-6 py-3 text-left font-semibold text-slate-900">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left font-semibold text-slate-900">
                      Report
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.reports.map((report) => (
                    <tr
                      key={report.id}
                      className="border-b border-slate-200 hover:bg-slate-50 transition-colors"
                    >
                      <td className="px-6 py-4 text-slate-900 font-medium">
                        {report.candidateName}
                      </td>
                      <td className="px-6 py-4 text-slate-700">
                        {report.jobTitle}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                            verdictBadgeMap[report.verdict]?.color === 'green'
                              ? 'bg-green-100 text-green-900'
                              : verdictBadgeMap[report.verdict]?.color === 'blue'
                              ? 'bg-blue-100 text-blue-900'
                              : verdictBadgeMap[report.verdict]?.color === 'amber'
                              ? 'bg-amber-100 text-amber-900'
                              : verdictBadgeMap[report.verdict]?.color === 'orange'
                              ? 'bg-orange-100 text-orange-900'
                              : 'bg-red-100 text-red-900'
                          }`}
                        >
                          {verdictLabels[report.verdict] || report.verdict}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-700">
                        {formatScore(report.overallScore)}
                      </td>
                      <td className="px-6 py-4 text-slate-700">
                        {formatDate(report.createdAt)}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => handleDownload(report.id)}
                          disabled={downloadingId === report.id}
                          className="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 rounded px-2 py-1 hover:border-slate-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {downloadingId === report.id ? 'Downloading…' : 'Download'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="px-6 py-4 border-t border-slate-200 flex items-center justify-between">
              <div className="text-sm text-slate-600">
                Page {currentPage + 1} of {Math.max(1, totalPages)}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setCurrentPage((prev) => Math.max(0, prev - 1))}
                  disabled={!canPrevious || loading}
                  className="px-4 py-2 text-sm font-medium rounded border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <button
                  onClick={() => setCurrentPage((prev) => prev + 1)}
                  disabled={!canNext || loading}
                  className="px-4 py-2 text-sm font-medium rounded border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
