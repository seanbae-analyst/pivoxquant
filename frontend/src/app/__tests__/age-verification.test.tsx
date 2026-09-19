/**
 * PIPA §22 ⑥ 만 14세 확인 회귀 게이트 — 자가선언 체크박스 (2026-09-19).
 *
 * 2026-09-19 전환: 생년월일 입력 + 만 나이 계산(`lib/age-verification`) 은
 * 삭제됐다. 만 14세 확인은 이용자가 직접 켜는 **일반 필수 체크박스**이며,
 * 값은 `/api/auth/oauth-finalize` 본문의 `consents.age` 로 서버에 가고
 * 서버가 `users.age_confirmed_at` 을 찍는다.
 *
 * Verifies (두 surface):
 *   1. /signup/oauth-finalize — `age` 행이 잠기지 않은 일반 체크박스이고,
 *      생년월일 입력이 없으며, `age` 미체크면 제출이 막힌다.
 *   2. legal-consent-modal — 동일한 규칙.
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import OAuthFinalizePage from "@/app/(auth)/signup/oauth-finalize/page";
import { LegalConsentModal } from "@/components/ui/legal-consent-modal";

// 인터스티셜은 인증된 신규 OAuth 가입자(age_confirmation_required === true)
// 에게만 폼을 렌더한다. `ageConfirmationRequired` 는 실물을 쓴다.
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
      refresh: vi.fn(),
    }),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/signup/oauth-finalize",
}));

describe("<OAuthFinalizePage /> — PIPA §22 ⑥ age self-declaration", () => {
  it("does not render a birthdate input any more", () => {
    render(<OAuthFinalizePage />);
    expect(screen.queryByLabelText(/생년월일/)).not.toBeInTheDocument();
    expect(document.querySelector('input[type="date"]')).toBeNull();
  });

  it("age checkbox is a plain, enabled checkbox (no pointer-events gating)", () => {
    render(<OAuthFinalizePage />);
    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox).toHaveAttribute("aria-checked", "false");
    const label = ageCheckbox.closest("label");
    expect(label).not.toHaveStyle({ pointerEvents: "none" });
    expect(label).not.toHaveStyle({ opacity: "0.5" });
  });

  it("keeps submit disabled while age is unticked, even with the other 3 ticked", async () => {
    const user = userEvent.setup();
    render(<OAuthFinalizePage />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    await user.click(screen.getByRole("checkbox", { name: /국외 이전에 동의/ }));

    expect(screen.getByRole("button", { name: /계속하기/ })).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: /만 14세/ }));
    expect(
      screen.getByRole("checkbox", { name: /만 14세/ }),
    ).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("button", { name: /계속하기/ })).toBeEnabled();
  });
});

describe("<LegalConsentModal /> — PIPA §22 ⑥ age self-declaration", () => {
  it("does not render a birthdate input any more", () => {
    render(<LegalConsentModal onAgree={vi.fn()} />);
    expect(screen.queryByLabelText(/생년월일/)).not.toBeInTheDocument();
    expect(document.querySelector('input[type="date"]')).toBeNull();
  });

  it("submit stays disabled until the age checkbox is ticked", async () => {
    const user = userEvent.setup();
    render(<LegalConsentModal onAgree={vi.fn()} />);

    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    await user.click(screen.getByRole("checkbox", { name: /국외 이전/ }));

    const submitBtn = screen.getByRole("button", { name: /동의하고 계속하기/ });
    expect(submitBtn).toBeDisabled();

    const ageCheckbox = screen.getByRole("checkbox", { name: /만 14세/ });
    expect(ageCheckbox.closest("label")).not.toHaveStyle({ pointerEvents: "none" });
    await user.click(ageCheckbox);
    expect(submitBtn).toBeEnabled();
  });
});
