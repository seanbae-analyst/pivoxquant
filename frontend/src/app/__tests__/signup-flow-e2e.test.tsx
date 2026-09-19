/**
 * 가입 플로우 E2E — 만 14세 자가선언 회귀 게이트 (2026-09-19).
 *
 * 이력: 2026-05-11 SHIP-BLOCKER fix 는 "DOB 입력해도 agree_age 영구 unchecked
 * → 가입 funnel 차단" P0 를 DOB 자동 도출로 막았다. 2026-09-19 에 생년월일
 * 수집 자체를 없앴으므로 자동 도출 로직도 함께 사라졌다. 남은 보호 대상:
 *   - `age` 는 이용자가 직접 켜는 일반 필수 체크박스다 (잠금 없음).
 *   - 필수 4종을 켜면 제출이 열린다 — funnel 이 막히지 않는다.
 *   - `age` 만 빠지면 제출이 막힌다 (PIPA §22 ⑥ fail-fast).
 *
 * 2 surface 회귀 게이트:
 *   - oauth-finalize (동의 스택의 집 — `/login` 경유 신규자까지 덮는 유일한 지점)
 *   - legal-consent-modal.tsx
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 인터스티셜은 인증된 신규 OAuth 가입자에게만 뜬다
// (ageConfirmationRequired(user) 가 false 면 즉시 replace 된다).
vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return {
    ...actual,
    useAuth: () => ({
      user: {
        id: 1,
        email: "new-oauth-user@example.com",
        age_confirmation_required: true,
      },
      loading: false,
      login: vi.fn(),
      signup: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    }),
  };
});

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

describe("OAuthFinalizePage — age self-declaration checkbox (PIPA §22 ⑥)", () => {
  it("age checkbox toggles on click (no birthdate needed)", async () => {
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "false");
    await user.click(ageCheckbox);
    expect(ageCheckbox).toHaveAttribute("aria-checked", "true");
  });

  it("age unticked keeps submit disabled (fail-fast preserved)", async () => {
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    await user.click(screen.getByRole("checkbox", { name: /국외 이전에 동의/ }));

    expect(
      screen.getByRole("checkbox", { name: /만 14세/ }),
    ).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("button", { name: /계속하기/ })).toBeDisabled();
  });

  it("submit enables after all 4 required consents are ticked", async () => {
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    await user.click(screen.getByRole("checkbox", { name: /만 14세/ }));
    await user.click(screen.getByRole("checkbox", { name: /국외 이전에 동의/ }));

    expect(screen.getByRole("button", { name: /계속하기/ })).toBeEnabled();
  });
});

describe("LegalConsentModal — age self-declaration checkbox (PIPA §22 ⑥)", () => {
  it("age checkbox toggles on click (no birthdate needed)", async () => {
    const user = userEvent.setup();
    render(<LegalConsentModal onAgree={vi.fn()} />);

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "false");
    await user.click(ageCheckbox);
    expect(ageCheckbox).toHaveAttribute("aria-checked", "true");
  });

  it("submit enables after all 4 required consents are ticked", async () => {
    const user = userEvent.setup();
    render(<LegalConsentModal onAgree={vi.fn()} />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    await user.click(screen.getByRole("checkbox", { name: /만 14세/ }));
    await user.click(screen.getByRole("checkbox", { name: /국외 이전/ }));

    const submitBtn = screen.getByRole("button", {
      name: /동의하고 계속하기/,
    });
    expect(submitBtn).not.toBeDisabled();
  });
});
