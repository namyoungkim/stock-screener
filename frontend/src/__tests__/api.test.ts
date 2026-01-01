import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ScreenRequest } from "@/lib/api";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("api", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ total: 0, stocks: [] }),
    });
  });

  describe("ScreenRequest", () => {
    it("should include search field in type", () => {
      // This test verifies that ScreenRequest type includes search field
      const request: ScreenRequest = {
        preset: "graham",
        market: "US",
        search: "apple", // This should be valid
        limit: 50,
        offset: 0,
      };

      expect(request.search).toBe("apple");
    });

    it("should pass search parameter to screen API", async () => {
      const request: ScreenRequest = {
        preset: "graham",
        search: "AAPL",
        limit: 50,
      };

      await api.screen(request);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/screen"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(request),
        })
      );

      // Verify the body contains search
      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.search).toBe("AAPL");
    });
  });
});
