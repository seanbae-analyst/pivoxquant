/**
 * /signup — 통합 auth entry 별칭 회귀 게이트.
 *
 * 2026-09-17: `/login` 과 `/signup` 이 하나의 `AuthEntryPage` 로 통합됐다.
 * `signup/page.tsx` 는 `../login/page` 를 그대로 렌더하는 34행 별칭이다.
 *
 * 이 파일에서 옮겨간 것 (삭제 아님 — `oauth-finalize-consent.test.tsx` 참조):
 *   - 4 필수 + 1 선택 동의 렌더
 *   - 전부 체크 전/후 게이트
 *   - 동의 블록 안 약관 · 개인정보 링크
 *   동의 스택은 `/signup/oauth-finalize` 인터스티셜로 이사했다
 *   (`user.birthdate_required === true` 인 신규 OAuth 가입자만 본다).
 *
 * 이 파일에서 삭제된 단언 (옮길 곳이 없음):
 *   - "renders a /login switch link in the footer"
 *     → `/signup` 과 `/login` 이 **같은 화면**이 됐으므로 전환 링크 자체가
 *       소스에서 제거됐다 (login/page.tsx 헤더 주석: "계정이 없으신가요?
 *       회원가입 › 은 가고, 갈 곳이 없다"). 다른 화면으로 옮길 수 없는
 *       단언이라 삭제한다. 두 URL 이 모두 살아 있다는 보호는 아래
 *       "renders the unified OAuth entry" 가 대신 맡는다.
 *
 * 여기에 남은 것: /signup 이 여전히 200 을 주고 통합 화면을 렌더하는지,
 * 그리고 동의·생년월일이 이 화면에 **다시 들어오지 않았는지**(재발 방지).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

// next/navigation mock.
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
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/signup",
}));

// useAuth mock — default to unauth, not-loading.
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

// Import AFTER mocks.
import SignupPageV2 from "@/app/(auth)/signup/page";
import { LocaleProvider } from "@/lib/locale";

function renderWithLocale(ui: React.ReactElement) {
  // ko default — locale cookie not set in test env.
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("SignupPageV2 — unified auth entry alias", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    authState.user = null;
    authState.loading = false;
  });

  it("renders the unified OAuth entry (Google + Kakao anchors)", () => {
    renderWithLocale(<SignupPageV2 />);

    // i18n-safe: find anchors with google/kakao OAuth hrefs.
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

  it("does not collect consents or birthdate here (they moved after OAuth)", () => {
    renderWithLocale(<SignupPageV2 />);

    // 동의 스택 / 생년월일이 이 화면으로 되돌아오면 신규 가입자는 OAuth 전에
    // 다시 동의를 요구받고, 로그인으로 들어온 신규 가입자는 여전히 동의를
    // 건너뛴다 — 이관이 닫은 구멍이 다시 열린다.
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.queryByLabelText(/생년월일/)).not.toBeInTheDocument();
  });

  it("keeps the terms + privacy disclosure line on the entry screen", () => {
    renderWithLocale(<SignupPageV2 />);

    // 동의 체크박스는 인터스티셜로 갔지만, 진입 화면의 고지 링크는 남는다.
    const termsLinks = screen.getAllByRole("link", { name: /이용약관|Terms/i });
    const privacyLinks = screen.getAllByRole("link", {
      name: /개인정보처리방침|Privacy/i,
    });

    expect(termsLinks[0]).toHaveAttribute("href", "/terms");
    expect(privacyLinks[0]).toHaveAttribute("href", "/privacy");
  });
});
