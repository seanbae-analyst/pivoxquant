import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubscriptionCardV2 } from "@/components/settings/v2/subscription-card-v2";

// Regression guard (#2): Free-tier users have no Stripe subscription, so EVERY
// billing-portal entry point must be hidden — clicking any would hit POST
// /api/billing/portal and 400 (no billing account) or 503 (billing disabled).
// There are THREE entry points (live-verification 2026-05-21 caught that the
// first fix only hid one): "Billing portal ›" (header), "Manage billing"
// (current-tier card), and "Open in Stripe ›" (receipt strip). Paid tiers see all.

const BILLING_CTAS = [/Billing portal/i, /Manage billing/i, /Open in Stripe/i];

describe("SubscriptionCardV2 — billing entry points", () => {
  it("hides ALL billing portal entry points for Free tier", () => {
    render(<SubscriptionCardV2 currentTier="free" onManageBilling={vi.fn()} />);
    for (const re of BILLING_CTAS) {
      expect(screen.queryByText(re)).not.toBeInTheDocument();
    }
    // Free shows a static "current plan" label instead.
    expect(screen.getByText(/Current plan/i)).toBeInTheDocument();
  });

  it("shows billing entry points for Pro tier", () => {
    render(<SubscriptionCardV2 currentTier="pro" onManageBilling={vi.fn()} />);
    expect(screen.getByText(/Billing portal/i)).toBeInTheDocument();
    expect(screen.getByText(/Manage billing/i)).toBeInTheDocument();
    expect(screen.getByText(/Open in Stripe/i)).toBeInTheDocument();
  });

  it("shows billing entry points for Premium tier", () => {
    render(
      <SubscriptionCardV2 currentTier="premium" onManageBilling={vi.fn()} />,
    );
    expect(screen.getByText(/Billing portal/i)).toBeInTheDocument();
    expect(screen.getByText(/Manage billing/i)).toBeInTheDocument();
  });
});
