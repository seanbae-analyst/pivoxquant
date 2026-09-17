/**
 * 가입 플로우 E2E — DOB auto-derive 회귀 게이트 (2026-05-11 SHIP-BLOCKER fix).
 *
 * E2E user-tester가 발견한 P0 회귀 reproduction:
 *   - DOB 입력해도 agree_age 체크박스 영구 unchecked
 *   - 제출(당시 OAuth) 컨트롤 영구 비활성
 *   - 신규 가입 funnel 완전히 차단
 *
 * Fix: DOB onChange 에서 valid + ≥14 이면 agree_age = true 자동 도출.
 *      invalid/<14 이면 agree_age = false 로 초기화 (fail-fast 유지).
 *
 * 2026-09-17 대상 이동 (로직은 동일, 삭제 없음):
 *   `/signup` 의 동의 스택이 OAuth 이후 인터스티셜
 *   `/signup/oauth-finalize` 로 이사했고, 자동 도출 로직도 그대로
 *   `ConsentStackV2` 안으로 따라갔다. 그래서 게이트 대상만
 *   SignupPageV2 → OAuthFinalizePage 로 바꾼다. 게이트 컨트롤도
 *   OAuth 앵커 → 제출 버튼("계속하기")이다.
 *
 * 2 surface 회귀 게이트:
 *   - oauth-finalize (동의 스택의 새 집)
 *   - legal-consent-modal.tsx
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 인터스티셜은 인증된 신규 OAuth 가입자에게만 뜬다
// (birthdate_required === true 가 아니면 즉시 replace 된다).
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

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/signup/oauth-finalize",
}));

import OAuthFinalizePage from "@/app/(auth)/signup/oauth-finalize/page";
import { LegalConsentModal } from "@/components/ui/legal-consent-modal";

function makeBirthdate(yearsAgo: number): string {
  const today = new Date();
  const y = today.getFullYear() - yearsAgo;
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

describe("OAuthFinalizePage — DOB auto-derive agree_age (SHIP-BLOCKER fix)", () => {
  it("valid DOB ≥14 auto-checks agree_age (no manual click required)", async () => {
    render(<OAuthFinalizePage />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "true");
  });

  it("DOB <14 keeps agree_age false + submit disabled (fail-fast preserved)", async () => {
    render(<OAuthFinalizePage />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(13) } });

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "false");

    // 이관 전에는 OAuth 버튼의 aria-disabled 로 확인했다. 인터스티셜에서는
    // OAuth 가 이미 끝났으므로 제출 버튼이 그 게이트다.
    expect(screen.getByRole("button", { name: /계속하기/ })).toBeDisabled();
  });

  it("submit enables after DOB+other consents (no agree_age click needed)", async () => {
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });
    await user.click(
      screen.getByRole("checkbox", { name: /국외 이전에 동의/ }),
    );

    expect(screen.getByRole("button", { name: /계속하기/ })).toBeEnabled();
  });
});

describe("LegalConsentModal — DOB auto-derive agree_age (SHIP-BLOCKER fix)", () => {
  it("valid DOB ≥14 auto-checks agree_age", async () => {
    render(<LegalConsentModal onAgree={vi.fn()} />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "true");
  });

  it("submit enables after DOB+other consents (no agree_age click needed)", async () => {
    const user = userEvent.setup();
    render(<LegalConsentModal onAgree={vi.fn()} />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });
    await user.click(
      screen.getByRole("checkbox", { name: /국외 이전/ }),
    );

    const submitBtn = screen.getByRole("button", {
      name: /동의하고 계속하기/,
    });
    expect(submitBtn).not.toBeDisabled();
  });
});
