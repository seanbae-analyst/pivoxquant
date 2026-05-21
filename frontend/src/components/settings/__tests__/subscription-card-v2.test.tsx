import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubscriptionCardV2 } from "@/components/settings/v2/subscription-card-v2";

// Regression guard (#2): Free-tier users have no Stripe subscription to
// manage, so the "Billing portal ›" entry point must NOT render — clicking
// it would hit POST /api/billing/portal and 400 (no billing account) or 503
// (billing disabled pre-launch). Paid tiers still see it.

describe("SubscriptionCardV2 — billing portal visibility", () => {
  it("hides the billing portal button for Free tier", () => {
    render(<SubscriptionCardV2 currentTier="free" onManageBilling={vi.fn()} />);
    expect(screen.queryByText(/Billing portal/i)).not.toBeInTheDocument();
  });

  it("shows the billing portal button for Pro tier", () => {
    const onManage = vi.fn();
    render(<SubscriptionCardV2 currentTier="pro" onManageBilling={onManage} />);
    expect(screen.getByText(/Billing portal/i)).toBeInTheDocument();
  });

  it("shows the billing portal button for Premium tier", () => {
    render(
      <SubscriptionCardV2 currentTier="premium" onManageBilling={vi.fn()} />,
    );
    expect(screen.getByText(/Billing portal/i)).toBeInTheDocument();
  });
});
