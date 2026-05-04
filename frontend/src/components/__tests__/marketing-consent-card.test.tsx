import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the consents lib (network calls) and sonner (toast)
vi.mock("@/lib/consents", () => ({
  fetchMarketingConsent: vi.fn(),
  recordMarketingConsent: vi.fn(),
  revokeMarketingConsent: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import {
  fetchMarketingConsent,
  recordMarketingConsent,
  revokeMarketingConsent,
} from "@/lib/consents";
import { MarketingConsentCardV2 } from "@/components/settings/v2/marketing-consent-card";

const mockedFetch = vi.mocked(fetchMarketingConsent);
const mockedRecord = vi.mocked(recordMarketingConsent);
const mockedRevoke = vi.mocked(revokeMarketingConsent);

describe("MarketingConsentCardV2", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    mockedRecord.mockReset();
    mockedRevoke.mockReset();
  });

  it("calls fetchMarketingConsent on mount and renders the toggle", async () => {
    mockedFetch.mockResolvedValue({
      opted_in: false,
      marketing_consent_at: null,
      marketing_consent_revoked_at: null,
    });

    render(<MarketingConsentCardV2 />);

    // Toggle (switch role) should be in the DOM immediately
    const toggle = screen.getByRole("switch", { name: /Marketing email consent/i });
    expect(toggle).toBeInTheDocument();

    await waitFor(() => {
      expect(mockedFetch).toHaveBeenCalledTimes(1);
    });

    // Korean label always rendered
    expect(screen.getByText(/마케팅 정보 수신 동의/)).toBeInTheDocument();
  });

  it("invokes recordMarketingConsent when toggling from off to on", async () => {
    mockedFetch.mockResolvedValue({
      opted_in: false,
      marketing_consent_at: null,
      marketing_consent_revoked_at: null,
    });
    mockedRecord.mockResolvedValue({
      opted_in: true,
      marketing_consent_at: "2026-05-03T00:00:00Z",
      marketing_consent_revoked_at: null,
    });

    const user = userEvent.setup();
    render(<MarketingConsentCardV2 />);

    // Wait until hydration completes (toggle becomes enabled)
    const toggle = await screen.findByRole("switch", { name: /Marketing email consent/i });
    await waitFor(() => {
      expect(toggle).not.toBeDisabled();
    });

    await user.click(toggle);

    await waitFor(() => {
      expect(mockedRecord).toHaveBeenCalledTimes(1);
    });
    expect(mockedRevoke).not.toHaveBeenCalled();
  });

  it("invokes revokeMarketingConsent when toggling from on to off", async () => {
    mockedFetch.mockResolvedValue({
      opted_in: true,
      marketing_consent_at: "2026-05-01T00:00:00Z",
      marketing_consent_revoked_at: null,
    });
    mockedRevoke.mockResolvedValue({
      opted_in: false,
      marketing_consent_at: "2026-05-01T00:00:00Z",
      marketing_consent_revoked_at: "2026-05-03T00:00:00Z",
    });

    const user = userEvent.setup();
    render(<MarketingConsentCardV2 />);

    const toggle = await screen.findByRole("switch", { name: /Marketing email consent/i });
    await waitFor(() => {
      expect(toggle).toHaveAttribute("aria-checked", "true");
    });

    await user.click(toggle);

    await waitFor(() => {
      expect(mockedRevoke).toHaveBeenCalledTimes(1);
    });
    expect(mockedRecord).not.toHaveBeenCalled();
  });
});
