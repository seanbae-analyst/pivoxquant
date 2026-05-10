/**
 * Wave 1 Task 4 — PIPA §22 ⑥ 생년월일 검증 회귀 게이트.
 *
 * Verifies:
 *   1. computeAgeYears / isAtLeastMinAge 헬퍼 정확성 (경계값 포함)
 *   2. signup _v2 페이지에서 만 13세 생년월일 입력 시 age 체크박스 disabled
 *      + 회원가입 버튼 (OAuth 앵커) disabled
 *   3. legal-consent-modal 에서 동일한 fail-fast 동작
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  computeAgeYears,
  isAtLeastMinAge,
  isValidBirthdate,
  MIN_AGE_YEARS,
  UNDER_AGE_KO,
} from "@/lib/age-verification";

import SignupPageV2 from "@/app/(auth)/signup/_v2/page-v2";
import { LegalConsentModal } from "@/components/ui/legal-consent-modal";

// Mocks shared with signup-v2.test.tsx
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: null, loading: false, refresh: vi.fn() }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    back: vi.fn(),
  }),
}));

describe("age-verification helper", () => {
  it("MIN_AGE_YEARS is 14 (PIPA §22 ⑥)", () => {
    expect(MIN_AGE_YEARS).toBe(14);
  });

  it("rejects malformed birthdates", () => {
    expect(isValidBirthdate("")).toBe(false);
    expect(isValidBirthdate("2000")).toBe(false);
    expect(isValidBirthdate("2000-13-01")).toBe(false);
    expect(isValidBirthdate("2000-02-30")).toBe(false);
    expect(isValidBirthdate("not-a-date")).toBe(false);
  });

  it("computes age in completed years correctly", () => {
    const now = new Date("2026-05-10T00:00:00Z");
    expect(computeAgeYears("2000-01-01", now)).toBe(26);
    // Birthday not yet reached this year
    expect(computeAgeYears("2000-12-31", now)).toBe(25);
    // Exactly 14
    expect(computeAgeYears("2012-05-10", now)).toBe(14);
    // 13 years 11 months — fails
    expect(computeAgeYears("2012-05-11", now)).toBe(13);
  });

  it("isAtLeastMinAge enforces ≥14", () => {
    const now = new Date("2026-05-10T00:00:00Z");
    expect(isAtLeastMinAge("2012-05-10", now)).toBe(true); // exactly 14
    expect(isAtLeastMinAge("2012-05-11", now)).toBe(false); // 13y364d
    expect(isAtLeastMinAge("2013-01-01", now)).toBe(false); // 13
    expect(isAtLeastMinAge("2000-01-01", now)).toBe(true);
  });

  it("invalid birthdate returns -1 (treated as ineligible)", () => {
    expect(computeAgeYears("")).toBe(-1);
    expect(isAtLeastMinAge("")).toBe(false);
  });
});

describe("<SignupPageV2 /> — PIPA §22 ⑥ birthdate fail-fast", () => {
  it("age checkbox is disabled when birthdate makes user < 14", async () => {
    const user = userEvent.setup();
    render(<SignupPageV2 />);

    // Compute a birthdate that is exactly 13 years before today.
    const today = new Date();
    const thirteen = new Date(
      today.getFullYear() - 13,
      today.getMonth(),
      today.getDate(),
    );
    const yyyy = thirteen.getFullYear();
    const mm = String(thirteen.getMonth() + 1).padStart(2, "0");
    const dd = String(thirteen.getDate()).padStart(2, "0");
    const birthdate = `${yyyy}-${mm}-${dd}`;

    const input = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    // jsdom: type="date" inputs don't accept user.type() — use fireEvent.change
    fireEvent.change(input, { target: { value: birthdate } });

    // Under-age error message appears.
    expect(screen.getByText(UNDER_AGE_KO)).toBeInTheDocument();

    // Age checkbox is rendered but its parent label has pointer-events: none.
    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    const label = ageCheckbox.closest("label");
    expect(label).toHaveStyle({ pointerEvents: "none" });

    // OAuth controls remain in their disabled <button> form (not <a>).
    const googleBtn = screen
      .getByText(/Continue with Google/i)
      .closest("button");
    expect(googleBtn).toHaveAttribute("aria-disabled", "true");
  });

  it("age checkbox unlocks when birthdate yields ≥14", async () => {
    const user = userEvent.setup();
    render(<SignupPageV2 />);

    const input = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "2000-01-01" } });

    // Under-age error must NOT appear.
    expect(screen.queryByText(UNDER_AGE_KO)).not.toBeInTheDocument();

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    const label = ageCheckbox.closest("label");
    expect(label).not.toHaveStyle({ pointerEvents: "none" });
  });
});

describe("<LegalConsentModal /> — PIPA §22 ⑥ birthdate fail-fast", () => {
  it("submit button is disabled when birthdate makes user < 14", async () => {
    const user = userEvent.setup();
    render(<LegalConsentModal onAgree={vi.fn()} />);

    // Pick a birthdate clearly under 14.
    const today = new Date();
    const yyyy = today.getFullYear() - 13;
    const birthdate = `${yyyy}-${String(today.getMonth() + 1).padStart(
      2,
      "0",
    )}-${String(today.getDate()).padStart(2, "0")}`;

    const input = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    // jsdom: type="date" inputs don't accept user.type() — use fireEvent.change
    fireEvent.change(input, { target: { value: birthdate } });

    expect(screen.getByText(UNDER_AGE_KO)).toBeInTheDocument();

    // The submit button below the consent block must be disabled.
    const submitBtn = screen.getByRole("button", { name: /동의|시작|계속|확인/ });
    expect(submitBtn).toBeDisabled();
  });
});
