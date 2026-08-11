'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import FilterBar from '@/components/dashboard/FilterBar';
import ChartCard from '@/components/dashboard/ChartCard';
import { fetchReportsList, downloadReportPdf } from '@/lib/api/dashboards';
import type { Filter } from '@/lib/types/dashboard';
import type { ReportsDashboardData } from '@/lib/types/dashboard';

const discBadgeMap: Record<string, { color: 'green' | 'blue' | 'amber' | 'orange' | 'red' }> = {
  D: { color: 'red' },
  I: { color: 'amber' },
  S: { color: 'green' },
  C: { color: 'blue' },
};

const discLabels: Record<string, string> = {
  D: 'Dominance',
  I: 'Influence',
  S: 'Steadiness',
  C: 'Conscientiousness',
};

export default function ReportsDashboardPage() {
  const { user } = useAuth();
  const orgId = user?.orgId || '';

  // State for reports data
  const [data, setData] = useState<ReportsDashboardData>({
    reports: [],
    discCategoryDistribution: [],
    discConfidenceDistribution: [],
    totalCount: 0,
    currentPage: 0,
    pageSize: 20,
  });
  const [loading, setLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // State for filters
  const [discCategoryFilter, setDiscCategoryFilter] = useState<string[]>([]);
  const [discConfidenceFilter, setDiscConfidenceFilter] = useState<string[]>([]);
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
      key: 'discCategory',
      label: 'DISC Category',
      type: 'multi-select',
      options: [
        { label: 'D — Dominance', value: 'D' },
        { label: 'I — Influence', value: 'I' },
        { label: 'S — Steadiness', value: 'S' },
        { label: 'C — Conscientiousness', value: 'C' },
      ],
    },
    {
      key: 'discConfidence',
      label: 'DISC Confidence',
      type: 'multi-select',
      options: [
        { label: '80-100%', value: '80-100%' },
        { label: '60-79%', value: '60-79%' },
        { label: '40-59%', value: '40-59%' },
        { label: '<40%', value: '<40%' },
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

        if (discCategoryFilter.length > 0) {
          apiFilters.discCategory = discCategoryFilter;
        }
        if (discConfidenceFilter.length > 0) {
          apiFilters.discConfidence = discConfidenceFilter;
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
          // Filter by search query if provided (not sent to the backend)
          let filteredReports = response.reports;

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
  }, [orgId, discCategoryFilter, discConfidenceFilter, searchQuery, dateFrom, dateTo, currentPage]);

  const handleFilterApply = (values: Record<string, any>) => {
    setSearchQuery(values.search || '');
    setDiscCategoryFilter(values.discCategory || []);
    setDiscConfidenceFilter(values.discConfidence || []);
    setDateFrom(values.dateRange_start || '');
    setDateTo(values.dateRange_end || '');
    setCurrentPage(0); // Reset to first page
  };

  const handleFilterReset = () => {
    setSearchQuery('');
    setDiscCategoryFilter([]);
    setDiscConfidenceFilter([]);
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

  const formatConfidence = (confidence: number | null) => {
    return confidence == null ? '—' : `${Math.round(confidence * 100)}%`;
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

  // Transform DISC category distribution for pie chart
  const discCategoryChartData = data.discCategoryDistribution.map((item) => ({
    name: discLabels[item.category] || item.category,
    value: item.count,
  }));

  // Transform DISC confidence distribution for bar chart
  const discConfidenceChartData = data.discConfidenceDistribution.map((item) => ({
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
          title="DISC Category Distribution"
          data={discCategoryChartData}
          chartType="pie"
          xKey="name"
          yKey="value"
          loading={loading}
          height={300}
        />
        <ChartCard
          title="DISC Confidence Distribution"
          data={discConfidenceChartData}
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
                      DISC Category
                    </th>
                    <th className="px-6 py-3 text-left font-semibold text-slate-900">
                      Confidence
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
                        {report.discPrimary ? (
                          <span
                            className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                              discBadgeMap[report.discPrimary]?.color === 'green'
                                ? 'bg-green-100 text-green-900'
                                : discBadgeMap[report.discPrimary]?.color === 'blue'
                                ? 'bg-blue-100 text-blue-900'
                                : discBadgeMap[report.discPrimary]?.color === 'amber'
                                ? 'bg-amber-100 text-amber-900'
                                : 'bg-red-100 text-red-900'
                            }`}
                          >
                            {report.discPrimary} — {discLabels[report.discPrimary]}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-slate-700">
                        {formatConfidence(report.discConfidence)}
                      </td>
                      <td className="px-6 py-4 text-slate-700">
                        {formatDate(report.createdAt)}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => handleDownload(report.sessionId)}
                          disabled={downloadingId === report.sessionId}
                          className="text-xs text-slate-600 hover:text-slate-900 border border-slate-200 rounded px-2 py-1 hover:border-slate-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {downloadingId === report.sessionId ? 'Downloading…' : 'Download'}
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
