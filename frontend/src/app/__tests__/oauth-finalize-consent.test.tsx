/**
 * /signup/oauth-finalize — 법정 필수 동의 게이트 회귀 게이트.
 *
 * 2026-09-17 이관: 이 4개 단언은 원래 `signup-v2.test.tsx` 에서 `/signup`
 * 화면을 대상으로 돌았다. `/login` 과 `/signup` 이 하나의 `AuthEntryPage` 로
 * 통합되면서 동의 수집 지점이 OAuth **이후** 인터스티셜로 옮겨졌고
 * (`user.birthdate_required === true` 인 신규 가입자만 본다), 게이트 대상도
 * OAuth 버튼 → 제출 버튼("계속하기")으로 바뀌었다. 보호 대상은 그대로다:
 *   - CLAUDE.md "가입 시 Terms checkbox 필수"
 *   - PIPA §22 ⑥ (만 14세) / §28-8 (국외 이전) / 정통망법 §50 ① (마케팅, 선택)
 *
 * 커버리지는 삭제되지 않았다 — 위치만 옮겼다.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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
  usePathname: () => "/signup/oauth-finalize",
}));

// 인터스티셜은 인증된 신규 OAuth 가입자에게만 뜬다:
// loading=false + user != null + birthdate_required === true.
// (false 면 페이지가 곧바로 `next` 로 replace 하므로 폼이 렌더되지 않는다.)
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: "new-oauth-user@example.com",
      birthdate_required: true,
    },
    loading: false,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  }),
}));

// Import AFTER mocks.
import OAuthFinalizePage from "@/app/(auth)/signup/oauth-finalize/page";

/** 제출 버튼 — 이 화면의 유일한 role="button" (동의 체크박스는 role="checkbox"). */
function submitButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: /계속하기/ }) as HTMLButtonElement;
}

describe("OAuthFinalizePage — 법정 필수 동의 게이트", () => {
  beforeEach(() => {
    replaceMock.mockClear();
  });

  it("renders 4 mandatory consents + 1 optional marketing consent", () => {
    render(<OAuthFinalizePage />);

    // Four required (terms / non_advisory / age / cross_border per
    // PIPA §28-8 added 2026-05-04 commit c9c6827) + one optional = 5 checkboxes.
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(5);

    // Specific labels by id — ids preserved 1:1 by ConsentStackV2.
    expect(document.getElementById("agree_terms")).toBeInTheDocument();
    expect(document.getElementById("agree_non_advisory")).toBeInTheDocument();
    expect(document.getElementById("agree_age")).toBeInTheDocument();
    expect(document.getElementById("agree_cross_border")).toBeInTheDocument();
    expect(document.getElementById("agree_marketing")).toBeInTheDocument();
  });

  it("keeps the submit control disabled until all required consents are checked", () => {
    render(<OAuthFinalizePage />);

    // 이관 전에는 OAuth 버튼이 aria-disabled="true" 인 것으로 게이트를 확인했다.
    // 인터스티셜에서는 OAuth 가 이미 끝났으므로 제출 버튼이 그 게이트다.
    expect(submitButton()).toBeDisabled();

    // 미충족 사유가 사용자에게 보인다 (필수 4종 안내).
    expect(screen.getByText(/필수 항목 4개/)).toBeInTheDocument();
  });

  it("enables the submit control after all 4 required consents are checked", async () => {
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);

    // 2026-05-04 (commit 7084f60 / c9c6827): cross_border added per
    // PIPA §28-8. Processors: 7 in US (Anthropic / Vercel / Railway /
    // Google / SendGrid / Sentry / Stripe) + 1 in France (Brevo) = 8 total;
    // privacy-ko.md §6 (#cross-border) is the authoritative list.
    // 2026-05-10 (Wave 1 Task 4): birthdate ≥14 required before age
    // checkbox is enabled per PIPA §22 ⑥ (만 14세 미만 fail-fast).
    // 2026-05-11 SHIP-BLOCKER fix: agree_age auto-derived from valid DOB ≥14,
    // so we no longer click the 만 14세 checkbox — it auto-checks on DOB change.
    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    // Fill birthdate (>= 14 years ago) — agree_age auto-derives to true.
    // jsdom: type="date" doesn't accept user.type — use fireEvent.change.
    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: "2000-01-01" } });
    await user.click(
      screen.getByRole("checkbox", { name: /국외 이전에 동의/ }),
    );

    expect(submitButton()).toBeEnabled();
    // 안내 문구는 게이트가 열리면 사라진다.
    expect(screen.queryByText(/필수 항목 4개/)).not.toBeInTheDocument();
  });

  it("renders terms + privacy links inside the consent block", () => {
    render(<OAuthFinalizePage />);

    // Use getAllByRole to handle the two terms/privacy occurrences gracefully.
    const termsLinks = screen.getAllByRole("link", { name: /이용약관/ });
    const privacyLinks = screen.getAllByRole("link", {
      name: /개인정보처리방침/,
    });

    expect(termsLinks.length).toBeGreaterThanOrEqual(1);
    expect(privacyLinks.length).toBeGreaterThanOrEqual(1);
    expect(termsLinks[0]).toHaveAttribute("href", "/terms");
    expect(privacyLinks[0]).toHaveAttribute("href", "/privacy");
  });
});
