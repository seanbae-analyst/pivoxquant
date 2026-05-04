import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// next/navigation mock.
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
}));

// useAuth mock — default to unauth, not-loading.
const authState: {
  user: unknown | null;
  loading: boolean;
} = { user: null, loading: false };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: authState.user,
    loading: authState.loading,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  }),
}));

// Import AFTER mocks.
import SignupPageV2 from "@/app/(auth)/signup/_v2/page-v2";

describe("SignupPageV2", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    authState.user = null;
    authState.loading = false;
  });

  it("renders 3 mandatory consents + 1 optional marketing consent", () => {
    render(<SignupPageV2 />);

    // Three required + one optional = four checkboxes.
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(4);

    // Specific labels by id.
    expect(document.getElementById("agree_terms")).toBeInTheDocument();
    expect(document.getElementById("agree_non_advisory")).toBeInTheDocument();
    expect(document.getElementById("agree_age")).toBeInTheDocument();
    expect(document.getElementById("agree_marketing")).toBeInTheDocument();
  });

  it("renders OAuth buttons in disabled state until all required consents checked", () => {
    render(<SignupPageV2 />);

    // Unchecked → OAuth buttons are <button aria-disabled="true">, not anchors.
    const googleBtn = screen
      .getByText(/Continue with Google/i)
      .closest("button");
    expect(googleBtn).toHaveAttribute("aria-disabled", "true");

    const kakaoBtn = screen
      .getByText(/Continue with Kakao/i)
      .closest("button");
    expect(kakaoBtn).toHaveAttribute("aria-disabled", "true");
  });

  it("enables OAuth anchors after all 3 required consents are checked", async () => {
    const user = userEvent.setup();
    render(<SignupPageV2 />);

    // Click the three required checkboxes.
    await user.click(screen.getByRole("checkbox", { name: /이용약관/ }));
    await user.click(
      screen.getByRole("checkbox", { name: /자본시장법상 투자자문업/ }),
    );
    await user.click(screen.getByRole("checkbox", { name: /만 14세/ }));

    // Now both OAuth controls collapse from <button> → <a>.
    const google = screen.getByText(/Continue with Google/i).closest("a");
    const kakao = screen.getByText(/Continue with Kakao/i).closest("a");
    expect(google).toBeInTheDocument();
    expect(kakao).toBeInTheDocument();
  });

  it("renders terms + privacy links inside the consent block", () => {
    render(<SignupPageV2 />);

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

  it("renders a /login switch link in the footer", () => {
    render(<SignupPageV2 />);

    const loginLink = screen.getByRole("link", { name: /로그인/ });
    expect(loginLink).toHaveAttribute("href", "/login");
  });
});
