import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// next/navigation router mock — page calls router.replace on existing session.
const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
    push: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  // M1 fix (2026-05-09 PR #171): page now reads ?error=&?expired= via
  // useSearchParams to surface OAuth/session-expired banners. Default mock
  // returns no params (clean state — no banner rendered).
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/login",
}));

// useAuth mock — controllable per-test via the holder object.
const authState: {
  user: unknown | null;
  loading: boolean;
} = { user: null, loading: false };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: authState.user,
    loading: authState.loading,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  }),
}));

// Import AFTER mocks are registered.
import LoginPageV2 from "@/app/(auth)/login/_v2/page-v2";

describe("LoginPageV2", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    authState.user = null;
    authState.loading = false;
  });

  it("renders Continue with Google + Continue with Kakao buttons (default unauth state)", () => {
    render(<LoginPageV2 />);

    expect(screen.getByText(/Continue with Google/i)).toBeInTheDocument();
    expect(screen.getByText(/Continue with Kakao/i)).toBeInTheDocument();
  });

  it("renders the editorial hero eyebrow + signup link", () => {
    render(<LoginPageV2 />);

    // Eyebrow is rendered by AuthHeroV2.
    expect(screen.getByText(/PivoxQuant/i)).toBeInTheDocument();

    // Bottom switch link to /signup.
    const signupLink = screen.getByRole("link", { name: /회원가입/ });
    expect(signupLink).toHaveAttribute("href", "/signup");
  });

  it("renders terms + privacy footer links", () => {
    render(<LoginPageV2 />);

    const terms = screen.getByRole("link", { name: /이용약관/ });
    const privacy = screen.getByRole("link", { name: /개인정보처리방침/ });

    expect(terms).toHaveAttribute("href", "/terms");
    expect(privacy).toHaveAttribute("href", "/privacy");
  });

  it("shows the loading spinner state when auth is still loading", () => {
    authState.loading = true;
    const { container } = render(<LoginPageV2 />);

    // Loading state: no OAuth buttons rendered.
    expect(screen.queryByText(/Continue with Google/i)).not.toBeInTheDocument();
    // Spinner div is the only visible content under the wrapper.
    expect(container.querySelector(".animate-spin")).toBeTruthy();
  });
});
