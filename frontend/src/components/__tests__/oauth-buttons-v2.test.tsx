import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { API } from "@/lib/endpoints";
import { LocaleProvider } from "@/lib/locale";

// Helper: render with LocaleProvider (ko default).
function renderWithLocale(ui: React.ReactElement, locale: "ko" | "en" = "ko") {
  // Force the locale cookie so the provider picks it up.
  document.cookie = `sp_locale=${locale}`;
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("OAuthButtonsV2", () => {
  it("renders both Google and Kakao buttons in enabled state with correct hrefs (ko)", () => {
    renderWithLocale(<OAuthButtonsV2 />, "ko");

    // ko locale: "Google로 계속" / "Kakao로 계속"
    const google = screen.getByText(/Google/).closest("a");
    const kakao = screen.getByText(/Kakao/).closest("a");

    expect(google).toBeInTheDocument();
    expect(kakao).toBeInTheDocument();
    expect(google).toHaveAttribute("href", API.auth.google);
    expect(kakao).toHaveAttribute("href", API.auth.kakao);
  });

  it("collapses anchors to disabled buttons when disabled=true (legal gate)", () => {
    renderWithLocale(<OAuthButtonsV2 disabled hint="동의해 주세요" />, "ko");

    // Should render <button> elements, not <a>
    const googleBtn = screen.getByText(/Google/).closest("button");
    const kakaoBtn = screen.getByText(/Kakao/).closest("button");

    expect(googleBtn).toBeInTheDocument();
    expect(kakaoBtn).toBeInTheDocument();
    expect(googleBtn).toHaveAttribute("aria-disabled", "true");
    expect(kakaoBtn).toHaveAttribute("aria-disabled", "true");

    // Hint should also render
    expect(screen.getByText(/동의해 주세요/)).toBeInTheDocument();
  });

  it("calls onDisabledClick when a disabled button is clicked", async () => {
    const onDisabledClick = vi.fn();
    const user = userEvent.setup();
    renderWithLocale(<OAuthButtonsV2 disabled onDisabledClick={onDisabledClick} />, "ko");

    const googleBtn = screen.getByText(/Google/).closest("button");
    expect(googleBtn).toBeInTheDocument();
    await user.click(googleBtn!);

    expect(onDisabledClick).toHaveBeenCalledTimes(1);
  });

  it("renders hint with role=alert when hintEmphasized=true", () => {
    renderWithLocale(<OAuthButtonsV2 disabled hint="필수 동의 누락" hintEmphasized />, "ko");
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/필수 동의 누락/);
  });
});
