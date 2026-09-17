/**
 * Wave 1 Task 4 — PIPA §22 ⑥ 생년월일 검증 회귀 게이트.
 *
 * Verifies:
 *   1. computeAgeYears / isAtLeastMinAge 헬퍼 정확성 (경계값 포함)
 *   2. 동의 스택 화면에서 만 13세 생년월일 입력 시 age 체크박스 disabled
 *      + 제출 버튼 disabled
 *   3. legal-consent-modal 에서 동일한 fail-fast 동작
 *
 * 2026-09-17 대상 이동 (커버리지 삭제 아님): 2번의 대상이었던 `/signup` 의
 * 동의 스택 + 생년월일 입력이 OAuth 이후 인터스티셜
 * `/signup/oauth-finalize` 로 이사했다 (`/login` 으로 들어온 신규 가입자까지
 * 덮는 유일한 지점). 만 14세 미만 fail-fast 규칙 자체는 그대로다.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import {
  computeAgeYears,
  isAtLeastMinAge,
  isValidBirthdate,
  MIN_AGE_YEARS,
  UNDER_AGE_KO,
} from "@/lib/age-verification";

import OAuthFinalizePage from "@/app/(auth)/signup/oauth-finalize/page";
import { LegalConsentModal } from "@/components/ui/legal-consent-modal";

// Mocks shared with oauth-finalize-consent.test.tsx — 인터스티셜은 인증된
// 신규 OAuth 가입자(birthdate_required === true)에게만 폼을 렌더한다.
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: "new-oauth-user@example.com",
      birthdate_required: true,
    },
    loading: false,
    refresh: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/signup/oauth-finalize",
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

describe("<OAuthFinalizePage /> — PIPA §22 ⑥ birthdate fail-fast", () => {
  it("age checkbox is disabled when birthdate makes user < 14", async () => {
    render(<OAuthFinalizePage />);

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

    // Under-age error message appears. 인터스티셜은 ko + en 을 한 span(role=alert)
    // 안에 같이 렌더하므로 텍스트 일치가 아니라 alert 의 내용으로 확인한다.
    expect(screen.getByRole("alert")).toHaveTextContent(UNDER_AGE_KO);

    // Age checkbox is rendered but its parent label has pointer-events: none.
    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    const label = ageCheckbox.closest("label");
    expect(label).toHaveStyle({ pointerEvents: "none" });

    // 제출 컨트롤은 잠긴 상태로 남는다 (이관 전에는 OAuth 앵커가 <button
    // aria-disabled> 로 접히는 것을 확인했다).
    expect(screen.getByRole("button", { name: /계속하기/ })).toBeDisabled();
  });

  it("age checkbox unlocks when birthdate yields ≥14", async () => {
    render(<OAuthFinalizePage />);

    const input = screen.getByLabelText(/생년월일/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "2000-01-01" } });

    // Under-age error must NOT appear.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    const label = ageCheckbox.closest("label");
    expect(label).not.toHaveStyle({ pointerEvents: "none" });
  });
});

describe("<LegalConsentModal /> — PIPA §22 ⑥ birthdate fail-fast", () => {
  it("submit button is disabled when birthdate makes user < 14", async () => {
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
