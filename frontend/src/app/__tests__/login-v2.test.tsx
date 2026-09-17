/**
 * 통합 auth entry 화면 (`AuthEntryPage`) 회귀 게이트.
 *
 * 2026-09-17: `/login` 과 `/signup` 이 이 한 컴포넌트로 합쳐졌다
 * (`signup/page.tsx` 가 이 파일을 그대로 렌더한다). 전환 링크
 * ("계정이 없으신가요? 회원가입 ›") 는 갈 곳이 없어져 소스에서 제거됐고,
 * 필수 동의는 OAuth 이후 인터스티셜에서 받는다.
 */
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
import AuthEntryPage from "@/app/(auth)/login/page";
import { LocaleProvider } from "@/lib/locale";

function renderWithLocale(ui: React.ReactElement) {
  // ko default — locale cookie not set in test env.
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("AuthEntryPage", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    authState.user = null;
    authState.loading = false;
  });

  it("renders Continue with Google + Continue with Kakao buttons (default unauth state)", () => {
    renderWithLocale(<AuthEntryPage />);

    // i18n: ko default → "Google로 계속" / "Kakao로 계속"; match by provider name only.
    expect(screen.getByText(/Google/)).toBeInTheDocument();
    expect(screen.getByText(/Kakao/)).toBeInTheDocument();
  });

  it("renders the editorial hero eyebrow + the OAuth affordance", () => {
    renderWithLocale(<AuthEntryPage />);

    // Eyebrow is rendered by AuthHeroV2. 2026-09-17: neutral for both
    // first-time and returning visitors ("PivoxQuant · Entry").
    expect(screen.getByText(/PivoxQuant · Entry/)).toBeInTheDocument();

    // 삭제된 단언: 하단 /signup 전환 링크.
    //   `/login` 과 `/signup` 이 같은 화면이 되면서 전환 링크는 소스에서
    //   제거됐다 — 옮길 대상 화면이 없어 단언을 유지할 수 없다. 대신
    //   이 화면이 실제로 제공하는 것(두 OAuth 앵커)을 단언해 진입 경로
    //   자체를 계속 보호한다.
    const links = screen.getAllByRole("link");
    const googleLink = links.find((l) =>
      l.getAttribute("href")?.includes("google"),
    );
    const kakaoLink = links.find((l) =>
      l.getAttribute("href")?.includes("kakao"),
    );
    expect(googleLink).toBeInTheDocument();
    expect(kakaoLink).toBeInTheDocument();
  });

  it("renders terms + privacy footer links", () => {
    renderWithLocale(<AuthEntryPage />);

    const terms = screen.getByRole("link", { name: /이용약관|Terms/i });
    const privacy = screen.getByRole("link", { name: /개인정보처리방침|Privacy/i });

    expect(terms).toHaveAttribute("href", "/terms");
    expect(privacy).toHaveAttribute("href", "/privacy");
  });

  it("shows the loading skeleton state when auth is still loading", () => {
    authState.loading = true;
    const { container } = renderWithLocale(<AuthEntryPage />);

    // Loading state: no OAuth buttons rendered.
    expect(screen.queryByText(/Google/)).not.toBeInTheDocument();
    // 2026-05-19 sweep: spinner → Vantablack skeleton.
    expect(container.querySelector(".pq-skeleton-dark")).toBeTruthy();
    // role=status + aria-live="polite" is the a11y contract.
    expect(container.querySelector('[role="status"]')).toBeTruthy();
  });
});
