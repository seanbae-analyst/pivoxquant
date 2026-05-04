import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OAuthButtonsV2 } from "@/components/auth/v2/oauth-buttons-v2";
import { API } from "@/lib/endpoints";

describe("OAuthButtonsV2", () => {
  it("renders both Google and Kakao buttons in enabled state with correct hrefs", () => {
    render(<OAuthButtonsV2 />);

    const google = screen.getByText(/Continue with Google/i).closest("a");
    const kakao = screen.getByText(/Continue with Kakao/i).closest("a");

    expect(google).toBeInTheDocument();
    expect(kakao).toBeInTheDocument();
    expect(google).toHaveAttribute("href", API.auth.google);
    expect(kakao).toHaveAttribute("href", API.auth.kakao);
  });

  it("collapses anchors to disabled buttons when disabled=true (legal gate)", () => {
    render(<OAuthButtonsV2 disabled hint="동의해 주세요" />);

    // Should render <button> elements, not <a>
    const googleBtn = screen.getByText(/Continue with Google/i).closest("button");
    const kakaoBtn = screen.getByText(/Continue with Kakao/i).closest("button");

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
    render(<OAuthButtonsV2 disabled onDisabledClick={onDisabledClick} />);

    const googleBtn = screen.getByText(/Continue with Google/i).closest("button");
    expect(googleBtn).toBeInTheDocument();
    await user.click(googleBtn!);

    expect(onDisabledClick).toHaveBeenCalledTimes(1);
  });

  it("renders hint with role=alert when hintEmphasized=true", () => {
    render(<OAuthButtonsV2 disabled hint="필수 동의 누락" hintEmphasized />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/필수 동의 누락/);
  });
});
