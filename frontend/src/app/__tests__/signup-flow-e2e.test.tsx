/**
 * /signup E2E flow — DOB auto-derive 회귀 게이트 (2026-05-11 SHIP-BLOCKER fix).
 *
 * E2E user-tester가 발견한 P0 회귀 reproduction:
 *   - DOB 입력해도 agree_age 체크박스 영구 unchecked
 *   - OAuth 버튼 영구 aria-disabled=true
 *   - 신규 가입 funnel 완전히 차단
 *
 * Fix: DOB onChange 에서 valid + ≥14 이면 agree_age = true 자동 도출.
 *      invalid/<14 이면 agree_age = false 로 초기화 (fail-fast 유지).
 *
 * 3 surface 회귀 게이트:
 *   - signup _v1 (page-v1.tsx)
 *   - signup _v2 (page-v2.tsx)
 *   - legal-consent-modal.tsx
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: null,
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
}));

import SignupPageV1 from "@/app/(auth)/signup/_v1/page-v1";
import SignupPageV2 from "@/app/(auth)/signup/_v2/page-v2";
import { LegalConsentModal } from "@/components/ui/legal-consent-modal";

function makeBirthdate(yearsAgo: number): string {
  const today = new Date();
  const y = today.getFullYear() - yearsAgo;
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

describe("SignupPageV1 — DOB auto-derive agree_age (SHIP-BLOCKER fix)", () => {
  it("valid DOB ≥14 auto-checks agree_age (no manual click required)", async () => {
    render(<SignupPageV1 />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });

    // agree_age checkbox should be aria-checked=true WITHOUT manual click.
    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "true");
  });

  it("DOB <14 keeps agree_age false + OAuth disabled (fail-fast preserved)", async () => {
    render(<SignupPageV1 />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(13) } });

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "false");

    // OAuth still disabled.
    const googleBtn = screen.getByText(/Google로 계속하기/i).closest("button");
    expect(googleBtn).toHaveAttribute("aria-disabled", "true");
  });

  it("OAuth enables after DOB+other consents (no agree_age click needed)", async () => {
    const user = userEvent.setup();
    render(<SignupPageV1 />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });
    await user.click(
      screen.getByRole("checkbox", { name: /국외 이전에 동의/ }),
    );

    // OAuth collapses from <button> → <a> when allRequired = true.
    const google = screen.getByText(/Google로 계속하기/i).closest("a");
    expect(google).toBeInTheDocument();
  });

  it("DOB change from ≥14 to <14 resets agree_age to false", async () => {
    render(<SignupPageV1 />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;

    // First: 35 yo → auto-checked
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });
    expect(
      screen.getByRole("checkbox", { name: /만 14세/ }),
    ).toHaveAttribute("aria-checked", "true");

    // Then: 13 yo → auto-unchecked
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(13) } });
    expect(
      screen.getByRole("checkbox", { name: /만 14세/ }),
    ).toHaveAttribute("aria-checked", "false");
  });
});

describe("SignupPageV2 — DOB auto-derive agree_age (SHIP-BLOCKER fix)", () => {
  it("valid DOB ≥14 auto-checks agree_age (no manual click required)", async () => {
    render(<SignupPageV2 />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "true");
  });

  it("DOB <14 keeps agree_age false + OAuth disabled (fail-fast preserved)", async () => {
    render(<SignupPageV2 />);

    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(13) } });

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "false");

    const googleBtn = screen
      .getByText(/Continue with Google/i)
      .closest("button");
    expect(googleBtn).toHaveAttribute("aria-disabled", "true");
  });

  it("OAuth enables after DOB+other consents (no agree_age click needed)", async () => {
    const user = userEvent.setup();
    render(<SignupPageV2 />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    const birthdateInput = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(birthdateInput, { target: { value: makeBirthdate(35) } });
    await user.click(
      screen.getByRole("checkbox", { name: /국외 이전에 동의/ }),
    );

    const google = screen.getByText(/Continue with Google/i).closest("a");
    expect(google).toBeInTheDocument();
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
