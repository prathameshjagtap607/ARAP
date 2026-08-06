import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useRouter } from 'next/navigation';
import InviteForm from '../InviteForm';
import * as assessmentsApi from '@/lib/api/assessments';
import * as sessionsApi from '@/lib/api/sessions';
import * as resumeApi from '@/lib/api/resume';
import * as apiIndex from '@/lib/api';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock every API module the full invite pipeline calls
jest.mock('@/lib/api/assessments', () => ({
  sendInvite: jest.fn(),
}));
jest.mock('@/lib/api/sessions', () => ({
  sendSessionInvite: jest.fn(),
}));
jest.mock('@/lib/api/resume', () => ({
  uploadResume: jest.fn(),
  analyzeResume: jest.fn(),
}));
jest.mock('@/lib/api', () => ({
  apiFetch: jest.fn(),
}));

const mockRouter = {
  push: jest.fn(),
  back: jest.fn(),
};

const testFile = new File(['resume content'], 'resume.pdf', { type: 'application/pdf' });

// jsdom applies native HTML5 constraint validation (the resume input has
// `required`) on a real click-triggered submit, which silently blocks the
// form's onSubmit handler from ever running — same as a real browser would,
// but it means fireEvent.click() on the submit button can't reliably test
// the component's own JS validation. Firing `submit` on the form directly
// bypasses that native gate and exercises the JS handler, same as RTL docs
// recommend for this exact situation.
const submitForm = () => {
  fireEvent.submit(screen.getByRole('button', { name: /Send Invite/i }).closest('form')!);
};

const mockHappyPath = (overrides?: { emailSent?: boolean }) => {
  (assessmentsApi.sendInvite as jest.Mock).mockResolvedValue({
    link: 'https://example.com/assess/token123',
    email_sent: true,
    session_id: 'session-123',
    candidate_id: 'candidate-123',
  });
  (resumeApi.uploadResume as jest.Mock).mockResolvedValue({
    s3_key: 'resumes/resume.pdf',
    presigned_url: 'https://example.com/resumes/resume.pdf',
  });
  (resumeApi.analyzeResume as jest.Mock).mockResolvedValue({});
  (apiIndex.apiFetch as jest.Mock).mockResolvedValue({});
  (sessionsApi.sendSessionInvite as jest.Mock).mockResolvedValue({
    link: 'https://example.com/assess/token123',
    email_sent: overrides?.emailSent ?? true,
  });
};

const fillValidForm = () => {
  fireEvent.change(screen.getByLabelText(/Candidate Name/i), { target: { value: 'John Doe' } });
  fireEvent.change(screen.getByLabelText(/Candidate Email Address/i), {
    target: { value: 'candidate@example.com' },
  });
  const resumeInput = screen.getByLabelText(/Resume/i) as HTMLInputElement;
  fireEvent.change(resumeInput, { target: { files: [testFile] } });
};

describe('InviteForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue(mockRouter);
  });

  test('renders with name, email, and resume fields', () => {
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);
    expect(screen.getByLabelText(/Candidate Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Candidate Email Address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Resume/i)).toBeInTheDocument();
    expect(screen.getByText(/Senior Developer/)).toBeInTheDocument();
  });

  // Note: the resume <input> has a native HTML5 `required` attribute, which
  // blocks the whole form from submitting (in jsdom, same as a real browser)
  // before any JS validation runs. So testing the JS-level name/email
  // validation requires a file already attached to get past native
  // validation first — the JS checks (name -> email -> format -> file) then
  // run in their own order on top of that.
  test('shows error when name field is empty on submit', async () => {
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fireEvent.change(screen.getByLabelText(/Resume/i), { target: { files: [testFile] } });
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/Candidate name is required/i)).toBeInTheDocument();
    });
  });

  test('shows error when email field is empty on submit', async () => {
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fireEvent.change(screen.getByLabelText(/Candidate Name/i), { target: { value: 'John Doe' } });
    fireEvent.change(screen.getByLabelText(/Resume/i), { target: { files: [testFile] } });
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/Email is required/i)).toBeInTheDocument();
    });
  });

  test('shows error for invalid email format', async () => {
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fireEvent.change(screen.getByLabelText(/Candidate Name/i), { target: { value: 'John Doe' } });
    fireEvent.change(screen.getByLabelText(/Candidate Email Address/i), {
      target: { value: 'invalid-email' },
    });
    fireEvent.change(screen.getByLabelText(/Resume/i), { target: { files: [testFile] } });
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/Please enter a valid email address/i)).toBeInTheDocument();
    });
  });

  test('runs the full pipeline and shows success on valid submission', async () => {
    mockHappyPath();
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/Invite Sent!/i)).toBeInTheDocument();
    });

    expect(assessmentsApi.sendInvite).toHaveBeenCalledWith(
      'test-session',
      'John Doe',
      'candidate@example.com',
      3600
    );
    expect(resumeApi.uploadResume).toHaveBeenCalledWith(testFile);
    expect(resumeApi.analyzeResume).toHaveBeenCalled();
    expect(apiIndex.apiFetch).toHaveBeenCalledWith(
      '/candidate-profiles/synthesize',
      expect.objectContaining({ method: 'POST' })
    );
    expect(apiIndex.apiFetch).toHaveBeenCalledWith(
      '/question-sets/generate/session-123',
      expect.objectContaining({ method: 'POST' })
    );
    expect(sessionsApi.sendSessionInvite).toHaveBeenCalledWith('session-123');
  });

  test('shows "not emailed" message when email provider is unavailable', async () => {
    mockHappyPath({ emailSent: false });
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/Candidate Ready — Invite Not Emailed/i)).toBeInTheDocument();
    });
  });

  test('shows "Send Another" button after successful submission', async () => {
    mockHappyPath();
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Send Another/i })).toBeInTheDocument();
    });
  });

  test('allows sending to another candidate with "Send Another"', async () => {
    mockHappyPath();
    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/Invite Sent!/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Send Another/i }));

    await waitFor(() => {
      expect(screen.queryByText(/Invite Sent!/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText(/Candidate Name/i)).toBeInTheDocument();
    });
  });

  test('displays user-friendly error message on API failure', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockRejectedValue(new Error('Network error'));

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument();
    });
  });

  test('shows processing state while submitting', async () => {
    (assessmentsApi.sendInvite as jest.Mock).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                link: 'https://example.com/assess/token123',
                email_sent: true,
                session_id: 'session-123',
                candidate_id: 'candidate-123',
              }),
            100
          )
        )
    );

    render(<InviteForm sessionId="test-session" jobTitle="Senior Developer" />);

    fillValidForm();
    submitForm();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Processing…/i })).toBeDisabled();
    });
  });
});
