import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock the consents lib (network calls) and sonner (toast)
vi.mock("@/lib/consents", () => ({
  fetchMarketingConsent: vi.fn(),
  recordMarketingConsent: vi.fn(),
  revokeMarketingConsent: vi.fn(),
  fetchInformationConsent: vi.fn(),
  setInformationConsent: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

import {
  fetchInformationConsent,
  fetchMarketingConsent,
  recordMarketingConsent,
  revokeMarketingConsent,
  setInformationConsent,
} from "@/lib/consents";
import {
  InformationConsentCardV2,
  MarketingConsentCardV2,
} from "@/components/settings/v2/marketing-consent-card";

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
    const toggle = screen.getByRole("switch", { name: /마케팅 메일 수신 동의/ });
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
    const toggle = await screen.findByRole("switch", { name: /마케팅 메일 수신 동의/ });
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

    const toggle = await screen.findByRole("switch", { name: /마케팅 메일 수신 동의/ });
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


// 2026-10-22 — the monthly report is 정보성 mail and the sender reads only
// the 정보성 record; this card is the first thing that ever writes it.
describe("InformationConsentCardV2", () => {
  const mockedInfoFetch = vi.mocked(fetchInformationConsent);
  const mockedInfoSet = vi.mocked(setInformationConsent);

  beforeEach(() => {
    mockedInfoFetch.mockReset();
    mockedInfoSet.mockReset();
    mockedRecord.mockReset();
  });

  it("opts in through the categories record, not the marketing one", async () => {
    mockedInfoFetch.mockResolvedValue({ opted_in: false, consent_at: null, revoked_at: null });
    mockedInfoSet.mockResolvedValue({
      opted_in: true,
      consent_at: "2026-10-22T00:00:00Z",
      revoked_at: null,
    });
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<InformationConsentCardV2 onConsentChange={onChange} />);

    const toggle = await screen.findByRole("switch", { name: /정보성 메일 수신 동의/ });
    expect(toggle.closest("#settings-information-consent")).not.toBeNull();
    await waitFor(() => expect(toggle).not.toBeDisabled());
    expect(onChange).toHaveBeenLastCalledWith(false);

    await user.click(toggle);
    await waitFor(() => expect(mockedInfoSet).toHaveBeenCalledWith(true));
    expect(mockedRecord).not.toHaveBeenCalled();
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith(true));
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("rolls back when the server refuses", async () => {
    mockedInfoFetch.mockResolvedValue({
      opted_in: true,
      consent_at: "2026-10-01T00:00:00Z",
      revoked_at: null,
    });
    mockedInfoSet.mockRejectedValue(new Error("nope"));
    const user = userEvent.setup();
    render(<InformationConsentCardV2 />);
    const toggle = await screen.findByRole("switch", { name: /정보성 메일 수신 동의/ });
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
    await user.click(toggle);
    await waitFor(() => expect(mockedInfoSet).toHaveBeenCalledWith(false));
    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"));
  });
});
