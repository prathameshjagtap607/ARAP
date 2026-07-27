import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import FilterBar from '../FilterBar';
import { Filter } from '@/lib/types/dashboard';

describe('FilterBar', () => {
  const mockFilters: Filter[] = [
    {
      key: 'status',
      label: 'Status',
      type: 'select',
      options: [
        { label: 'Active', value: 'active' },
        { label: 'Inactive', value: 'inactive' },
      ],
    },
    {
      key: 'dateRange',
      label: 'Date Range',
      type: 'date-range',
    },
    {
      key: 'search',
      label: 'Search',
      type: 'search',
      placeholder: 'Enter text...',
    },
    {
      key: 'tags',
      label: 'Tags',
      type: 'multi-select',
      options: [
        { label: 'Tag A', value: 'tag-a' },
        { label: 'Tag B', value: 'tag-b' },
      ],
    },
  ];

  test('renders filter labels', () => {
    const mockOnApply = jest.fn();
    const mockOnReset = jest.fn();

    render(
      <FilterBar
        filters={mockFilters}
        onApply={mockOnApply}
        onReset={mockOnReset}
      />
    );

    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Date Range')).toBeInTheDocument();
    expect(screen.getByText('Search')).toBeInTheDocument();
    expect(screen.getByText('Tags')).toBeInTheDocument();
  });

  test('calls onApply when Apply button is clicked', () => {
    const mockOnApply = jest.fn();
    const mockOnReset = jest.fn();

    render(
      <FilterBar
        filters={mockFilters}
        onApply={mockOnApply}
        onReset={mockOnReset}
      />
    );

    const applyButton = screen.getByRole('button', { name: /Apply/i });
    fireEvent.click(applyButton);

    expect(mockOnApply).toHaveBeenCalledTimes(1);
    expect(mockOnApply).toHaveBeenCalledWith(
      expect.objectContaining({
        status: '',
        dateRange_start: '',
        dateRange_end: '',
        search: '',
        tags: [],
      })
    );
  });

  test('calls onReset when Reset button is clicked', () => {
    const mockOnApply = jest.fn();
    const mockOnReset = jest.fn();

    render(
      <FilterBar
        filters={mockFilters}
        onApply={mockOnApply}
        onReset={mockOnReset}
      />
    );

    const resetButton = screen.getByRole('button', { name: /Reset/i });
    fireEvent.click(resetButton);

    expect(mockOnReset).toHaveBeenCalledTimes(1);
  });

  test('renders loading state with disabled buttons', () => {
    const mockOnApply = jest.fn();
    const mockOnReset = jest.fn();

    render(
      <FilterBar
        filters={mockFilters}
        onApply={mockOnApply}
        onReset={mockOnReset}
        loading={true}
      />
    );

    const applyButton = screen.getByRole('button', { name: /Apply/i });
    const resetButton = screen.getByRole('button', { name: /Reset/i });

    expect(applyButton).toBeDisabled();
    expect(resetButton).toBeDisabled();
  });
});
