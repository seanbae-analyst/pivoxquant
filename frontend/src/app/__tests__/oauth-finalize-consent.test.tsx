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
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 2026-09-17 P1 — 제출 계약(본문의 `consents` + 성공 시 스냅숏 정리)을
// 검증하려면 네트워크를 가로채야 한다. `apiFetch` 만 mock 하고 `ApiError`
// 는 실물을 쓴다(페이지가 `instanceof` 로 분기한다).
// `vi.mock` 은 파일 최상단으로 호이스팅되므로 mock 함수도 `vi.hoisted` 로
// 같이 올려야 한다(그러지 않으면 TDZ ReferenceError).
const { apiFetchMock } = vi.hoisted(() => ({ apiFetchMock: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, apiFetch: apiFetchMock };
});

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

/**
 * ── 2026-09-17 P1: 동의는 서버 게이트다 ──────────────────────────────────
 *
 * 감사 실측: 동의 스택이 OAuth 이후 인터스티셜로 옮겨졌는데 서버는 여전히
 * `{ birthdate }` 만 받아서, 세션만 있으면 체크박스를 하나도 건드리지 않고
 * curl 로 전 기능을 열 수 있었다. 서버 쪽 게이트는
 * `tests/test_oauth_finalize_consents.py` 가 지킨다. 이 블록은 **프론트가
 * 그 계약을 실제로 지키는지** — 동의를 본문에 담아 보내는지, 성공 후
 * localStorage 스냅숏을 지우는지 — 를 지킨다.
 */
describe("OAuthFinalizePage — 제출 계약 (서버 동의 게이트)", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    apiFetchMock.mockReset();
    apiFetchMock.mockResolvedValue({ ok: true });
    window.localStorage.clear();
  });

  /** 필수 4종을 모두 만족시킨 뒤 제출한다. */
  async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    fireEvent.change(screen.getByLabelText(/생년월일/), {
      target: { value: "1990-01-01" },
    });
    await user.click(screen.getByRole("checkbox", { name: /국외 이전에 동의/ }));
    await user.click(submitButton());
  }

  /** oauth-finalize 호출만 골라낸다 (마케팅 POST 와 구분). */
  function finalizeCall() {
    return apiFetchMock.mock.calls.find(
      (c) => c[0] === "/api/auth/oauth-finalize",
    );
  }

  it("sends the 3 mandatory consents in the request body", async () => {
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);
    await fillAndSubmit(user);

    await waitFor(() => expect(finalizeCall()).toBeTruthy());
    const body = JSON.parse(finalizeCall()![1].body as string);

    expect(body.birthdate).toBe("1990-01-01");
    expect(body.consents).toEqual({
      terms: true,
      non_advisory: true,
      cross_border: true,
    });
  });

  it("does NOT double-record cross-border consent via /api/consents", async () => {
    // 서버가 finalize 와 같은 트랜잭션에서 cross_border_consent_at 을 찍는다.
    // 프론트가 별도로 POST 하면 같은 사실이 두 번 기록되어 타임스탬프가
    // 실제 동의 시각에서 밀린다 — 그 경로를 제거했다는 회귀 가드.
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);
    await fillAndSubmit(user);

    await waitFor(() => expect(finalizeCall()).toBeTruthy());
    const urls = apiFetchMock.mock.calls.map((c) => c[0]);
    expect(urls).not.toContain("/api/consents/cross-border");
  });

  it("clears the localStorage snapshot after a successful finalize", async () => {
    // 남겨 두면 (dashboard) 레이아웃의 flushPendingCrossBorderConsent 가
    // 다음 마운트에서 재전송해 타임스탬프를 덮어쓴다 (감사 지적 사항).
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);
    await fillAndSubmit(user);

    await waitFor(() =>
      expect(window.localStorage.getItem("pivox_signup_consents")).toBeNull(),
    );
  });

  it("keeps the snapshot when the finalize request fails", async () => {
    // 실패 시에는 증거를 버리지 않는다 — 스냅숏이 남아야 재시도 경로가 산다.
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>(
      "@/lib/api",
    );
    apiFetchMock.mockRejectedValueOnce(
      new ApiError(400, "필수 동의 항목", "consents_required"),
    );
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);
    await fillAndSubmit(user);

    await waitFor(() =>
      expect(
        window.localStorage.getItem("pivox_signup_consents"),
      ).not.toBeNull(),
    );
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("surfaces the server's consents_required code as its own copy", async () => {
    // ApiError.message 는 로케일에 따라 한국어 문구라 코드가 아니다 —
    // 페이지는 ApiError.code 를 봐야 한다.
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>(
      "@/lib/api",
    );
    apiFetchMock.mockRejectedValueOnce(
      new ApiError(400, "필수 동의 항목을 모두 확인해주세요.", "consents_required"),
    );
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);
    await fillAndSubmit(user);

    expect(await screen.findByText(/새로고침한 뒤 다시 시도/)).toBeInTheDocument();
  });
});
