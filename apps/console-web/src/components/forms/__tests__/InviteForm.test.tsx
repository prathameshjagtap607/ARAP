import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useRouter } from 'next/navigation';
import InviteForm from '../InviteForm';
import * as assessmentsApi from '@/lib/api/assessments';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock the API
jest.mock('@/lib/api/assessments', () => ({
  sendInvite: jest.fn(),
}));

const mockRouter = {
  push: jest.fn(),
  back: jest.fn(),
};

describe('InviteForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
  });

  test('renders with email input field', () => {
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);
    expect(screen.getByLabelText(/Candidate Email Address/i)).toBeInTheDocument();
    expect(screen.getByText(/Senior Developer/)).toBeInTheDocument();
  });

  test('shows error when email field is empty on submit', async () => {
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const submitButton = screen.getByRole('button', { name: /Send Invite/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Email is required/i)).toBeInTheDocument();
    });
  });

  test('shows error for invalid email format', async () => {
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });

    const submitButton = screen.getByRole('button', { name: /Send Invite/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Please enter a valid email address/i)).toBeInTheDocument();
    });
  });

  test('accepts valid email format', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockResolvedValue({
      link: 'https://example.com/assess/token123',
      email_sent: true,
    });

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'candidate@example.com' } });

    const submitButton = screen.getByRole('button', { name: /Send Invite/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(assessmentsApi.sendInvite).toHaveBeenCalledWith('test-session', 'candidate@example.com');
    });
  });

  test('shows success message and generated link after successful submission', async () => {
    const testLink = 'https://example.com/assess/token123';
    (assessmentsApi.sendInvite as jest.Mock).mockResolvedValue({
      link: testLink,
      email_sent: true,
    });

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'candidate@example.com' } });

    const submitButton = screen.getByRole('button', { name: /Send Invite/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Invite Sent!/i)).toBeInTheDocument();
      expect(screen.getByDisplayValue(testLink)).toBeInTheDocument();
    });
  });

  test('shows "Send Another" button after successful submission', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockResolvedValue({
      link: 'https://example.com/assess/token123',
      email_sent: true,
    });

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'candidate@example.com' } });

    const submitButton = screen.getByRole('button', { name: /Send Invite/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Send Another/i })).toBeInTheDocument();
    });
  });

  test('allows sending to multiple candidates with "Send Another"', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockResolvedValue({
      link: 'https://example.com/assess/token123',
      email_sent: true,
    });

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    // First submission
    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'candidate1@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invite Sent!/i)).toBeInTheDocument();
    });

    // Click "Send Another"
    const sendAnotherButton = screen.getByRole('button', { name: /Send Another/i });
    fireEvent.click(sendAnotherButton);

    // Form should be back to initial state
    await waitFor(() => {
      expect(screen.queryByText(/Invite Sent!/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText(/Candidate Email Address/i)).toBeInTheDocument();
    });
  });

  test('displays user-friendly error message on API failure', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockRejectedValue(
      new Error('Network error')
    );

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'candidate@example.com' } });

    const submitButton = screen.getByRole('button', { name: /Send Invite/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });

  test('shows loading state while submitting', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({
        link: 'https://example.com/assess/token123',
        email_sent: true,
      }), 100))
    );

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'candidate@example.com' } });

    const submitButton = screen.getByRole('button', { name: /Send Invite/i });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Sending.../i })).toBeDisabled();
    });
  });

  test('calls sendInvite with correct parameters', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockResolvedValue({
      link: 'https://example.com/assess/token123',
      email_sent: true,
    });

    render(<InviteForm sessionId="session-123" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });

    fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }));

    await waitFor(() => {
      expect(assessmentsApi.sendInvite).toHaveBeenCalledWith('session-123', 'test@example.com');
      expect(assessmentsApi.sendInvite).toHaveBeenCalledTimes(1);
    });
  });

  test('clears email input after successful submission', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockResolvedValue({
      link: 'https://example.com/assess/token123',
      email_sent: true,
    });

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    const emailInput = screen.getByLabelText(/Candidate Email Address/i) as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: 'candidate@example.com' } });

    fireEvent.click(screen.getByRole('button', { name: /Send Invite/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invite Sent!/i)).toBeInTheDocument();
    });

    // Click "Send Another" to reset form
    fireEvent.click(screen.getByRole('button', { name: /Send Another/i }));

    await waitFor(() => {
      const resetEmailInput = screen.getByLabelText(/Candidate Email Address/i) as HTMLInputElement;
      expect(resetEmailInput.value).toBe('');
    });
  });
});
