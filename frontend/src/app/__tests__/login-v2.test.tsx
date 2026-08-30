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
import LoginPageV2 from "@/app/(auth)/login/page";
import { LocaleProvider } from "@/lib/locale";

function renderWithLocale(ui: React.ReactElement) {
  // ko default — locale cookie not set in test env.
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("LoginPageV2", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    authState.user = null;
    authState.loading = false;
  });

  it("renders Continue with Google + Continue with Kakao buttons (default unauth state)", () => {
    renderWithLocale(<LoginPageV2 />);

    // i18n: ko default → "Google로 계속" / "Kakao로 계속"; match by provider name only.
    expect(screen.getByText(/Google/)).toBeInTheDocument();
    expect(screen.getByText(/Kakao/)).toBeInTheDocument();
  });

  it("renders the editorial hero eyebrow + signup link", () => {
    renderWithLocale(<LoginPageV2 />);

    // Eyebrow is rendered by AuthHeroV2.
    expect(screen.getByText(/PivoxQuant/i)).toBeInTheDocument();

    // Bottom switch link to /signup — i18n key "auth.login.createAccount" → "계정 만들기".
    const signupLink = screen.getByRole("link", { name: /계정 만들기|Create account|회원가입/i });
    expect(signupLink).toHaveAttribute("href", "/signup");
  });

  it("renders terms + privacy footer links", () => {
    renderWithLocale(<LoginPageV2 />);

    const terms = screen.getByRole("link", { name: /이용약관|Terms/i });
    const privacy = screen.getByRole("link", { name: /개인정보처리방침|Privacy/i });

    expect(terms).toHaveAttribute("href", "/terms");
    expect(privacy).toHaveAttribute("href", "/privacy");
  });

  it("shows the loading skeleton state when auth is still loading", () => {
    authState.loading = true;
    const { container } = renderWithLocale(<LoginPageV2 />);

    // Loading state: no OAuth buttons rendered.
    expect(screen.queryByText(/Google/)).not.toBeInTheDocument();
    // 2026-05-19 sweep: spinner → Vantablack skeleton.
    expect(container.querySelector(".pq-skeleton-dark")).toBeTruthy();
    // role=status + aria-live="polite" is the a11y contract.
    expect(container.querySelector('[role="status"]')).toBeTruthy();
  });
});
