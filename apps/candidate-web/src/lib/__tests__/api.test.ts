import { apiFetch } from "../api";

describe("apiFetch", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.resetAllMocks();
  });

  it("sends JSON content-type header by default", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ hello: "world" }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    const result = await apiFetch<{ hello: string }>("/status");

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/status",
      expect.objectContaining({
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      })
    );
    expect(result).toEqual({ hello: "world" });
  });

  it("adds an Authorization header when a jwt is passed", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    await apiFetch("/session", { jwt: "abc123" });

    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/session",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer abc123" }),
      })
    );
  });

  it("throws with the server-provided detail message on a non-ok response", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Session not found" }),
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    await expect(apiFetch("/session/missing")).rejects.toThrow("Session not found");
  });

  it("falls back to an HTTP status message when the error body has no detail", async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json");
      },
    });
    global.fetch = mockFetch as unknown as typeof fetch;

    await expect(apiFetch("/session/broken")).rejects.toThrow("HTTP 500");
  });
});
