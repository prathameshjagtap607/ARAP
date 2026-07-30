import { apiFetch } from "../index";
import { sendSessionInvite, deleteSession } from "../sessions";

jest.mock("../index", () => ({
  apiFetch: jest.fn(),
}));

const mockedApiFetch = apiFetch as jest.Mock;

describe("sendSessionInvite", () => {
  beforeEach(() => mockedApiFetch.mockReset());

  it("POSTs to /sessions/{id}/invite and returns link + email_sent", async () => {
    mockedApiFetch.mockResolvedValue({ link: "http://x/y", email_sent: true });

    const result = await sendSessionInvite("session-1");

    expect(result.email_sent).toBe(true);
    expect(mockedApiFetch).toHaveBeenCalledWith("/sessions/session-1/invite", {
      method: "POST",
    });
  });
});

describe("deleteSession", () => {
  beforeEach(() => mockedApiFetch.mockReset());

  it("DELETEs /sessions/{id}", async () => {
    mockedApiFetch.mockResolvedValue(undefined);

    await deleteSession("session-1");

    expect(mockedApiFetch).toHaveBeenCalledWith("/sessions/session-1", {
      method: "DELETE",
    });
  });
});
