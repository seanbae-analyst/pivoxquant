import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

  it("renders 4 mandatory consents + 1 optional marketing consent", () => {
    render(<SignupPageV2 />);

    // Four required (terms / non_advisory / age / cross_border per
    // PIPA §28-8 added 2026-05-04 commit c9c6827) + one optional = 5 checkboxes.
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(5);

    // Specific labels by id.
    expect(document.getElementById("agree_terms")).toBeInTheDocument();
    expect(document.getElementById("agree_non_advisory")).toBeInTheDocument();
    expect(document.getElementById("agree_age")).toBeInTheDocument();
    expect(document.getElementById("agree_cross_border")).toBeInTheDocument();
    expect(document.getElementById("agree_marketing")).toBeInTheDocument();
  });

  it("renders OAuth buttons in disabled state until all required consents checked", () => {
    render(<SignupPageV2 />);

    // Unchecked → OAuth buttons are <button aria-disabled="true">, not anchors.
    // Match by aria-disabled attribute rather than text content (i18n-safe).
    const disabledBtns = screen.getAllByRole("button", { hidden: false })
      .filter((b) => b.getAttribute("aria-disabled") === "true");
    expect(disabledBtns.length).toBeGreaterThanOrEqual(2); // Google + Kakao
  });

  it("enables OAuth anchors after all 4 required consents are checked", async () => {
    const user = userEvent.setup();
    render(<SignupPageV2 />);

    // Click the four required checkboxes.
    // 2026-05-04 (commit 7084f60 / c9c6827): cross_border added per
    // PIPA §28-8 (Anthropic / Stripe / Vercel / Railway / Google in US).
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

    // Now both OAuth controls collapse from <button> → <a>.
    // i18n-safe: find anchors with google/kakao OAuth hrefs.
    const links = screen.getAllByRole("link");
    const googleLink = links.find((l) => l.getAttribute("href")?.includes("google"));
    const kakaoLink = links.find((l) => l.getAttribute("href")?.includes("kakao"));
    expect(googleLink).toBeInTheDocument();
    expect(kakaoLink).toBeInTheDocument();
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
