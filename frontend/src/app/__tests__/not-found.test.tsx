import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const auth = vi.hoisted(() => ({ user: null as null | { id: number }, loading: false }));
vi.mock("@/lib/auth", () => ({ useAuth: () => auth }));
// The shell pulls in the whole nav tree; the test only needs to know it wraps.
vi.mock("@/components/layout/dashboard-layout", () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dashboard-shell">{children}</div>
  ),
}));

import NotFound from "@/app/not-found";
import DashboardNotFound from "@/app/(dashboard)/not-found";

describe("NotFound page (404) — 2026-10-09 Korean, in-app shell", () => {
  beforeEach(() => {
    auth.user = null;
    auth.loading = false;
  });

  it("guest: Korean headline, bare page, link back to /", () => {
    render(<NotFound />);
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("없는 화면입니다.");
    expect(screen.getByRole("link", { name: "처음으로" })).toHaveAttribute("href", "/");
    expect(screen.queryByTestId("dashboard-shell")).toBeNull();
    expect(screen.queryByText(/Nothing to observe|Back to desk/i)).toBeNull();
  });

  it("signed in: rendered inside the app shell, back to 거울", () => {
    auth.user = { id: 1 };
    render(<NotFound />);
    expect(screen.getByTestId("dashboard-shell")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "거울로 돌아가기" })).toHaveAttribute("href", "/mirror");
  });

  it("(dashboard)/not-found: already inside the layout's shell, no second shell", () => {
    auth.user = { id: 1 };
    render(<DashboardNotFound />);
    expect(screen.queryByTestId("dashboard-shell")).toBeNull();
    expect(screen.getByRole("link", { name: "거울로 돌아가기" })).toHaveAttribute("href", "/mirror");
  });
});
