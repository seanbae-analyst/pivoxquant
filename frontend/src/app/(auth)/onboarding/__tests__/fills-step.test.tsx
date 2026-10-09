/**
 * Onboarding · 체결 자동 기록 (2026-10-07). Optional step between holdings and
 * the questions: picks the guide for the phone in hand, issues the import
 * token only after the consent tick, shows the token once with the copy
 * fields, and "나중에" goes straight on.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, screen, fireEvent, act } from "@testing-library/react";

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace }) }));
vi.mock("@/lib/locale", () => ({ useT: () => (k: string) => k }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: 1, onboarding_completed: false }, loading: false }),
}));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), apiFetch: vi.fn() }));

let tokens: { id: number; revoked_at: string | null }[] = [];
let positions: unknown[] = [{ id: 1 }];
let tokensLoading = false;
const mutate = vi.fn();
vi.mock("@/lib/hooks", () => ({
  useImportTokens: () => ({ tokens, isLoading: tokensLoading, mutate }),
  usePortfolioPositions: () => ({ data: { positions } }),
}));

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { detectPhone } from "@/lib/phone";
import OnboardingFillsPage from "../fills/page";

const apiFetchMock = vi.mocked(apiFetch);
const UA = Object.getOwnPropertyDescriptor(window.navigator, "userAgent");

function setUA(ua: string) {
  Object.defineProperty(window.navigator, "userAgent", { value: ua, configurable: true });
}

beforeEach(() => {
  tokens = [];
  positions = [{ id: 1 }];
  tokensLoading = false;
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  if (UA) Object.defineProperty(window.navigator, "userAgent", UA);
  else Reflect.deleteProperty(window.navigator, "userAgent");
});

describe("detectPhone", () => {
  it("iPhone → ios, everything else → android", () => {
    expect(detectPhone("Mozilla/5.0 (iPhone; CPU iPhone OS 27_0 like Mac OS X)")).toBe("ios");
    expect(detectPhone("Mozilla/5.0 (Linux; Android 15; SM-S928N)")).toBe("android");
    expect(detectPhone("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")).toBe("android");
  });
});

describe("onboarding · phone fill automation", () => {
  it("opens the iPhone guide on an iPhone, and the user can switch", () => {
    setUA("Mozilla/5.0 (iPhone; CPU iPhone OS 27_0 like Mac OS X)");
    render(<OnboardingFillsPage />);
    expect(screen.getByTestId("fills-steps-ios")).toBeTruthy();
    expect(screen.getByText("settingsV2.importTokens.ios7")).toBeTruthy();
    fireEvent.click(screen.getByTestId("fills-phone-android"));
    expect(screen.getByTestId("fills-steps-android")).toBeTruthy();
    expect(screen.getByText("settingsV2.importTokens.android1")).toBeTruthy();
  });

  it("issues the token only after consent, then shows it once with the copy fields", async () => {
    setUA("Mozilla/5.0 (Linux; Android 15)");
    render(<OnboardingFillsPage />);
    const issue = screen.getByTestId("fills-issue") as HTMLButtonElement;
    expect(issue.disabled).toBe(true);
    fireEvent.click(issue);
    expect(apiFetchMock).not.toHaveBeenCalled();

    apiFetchMock.mockResolvedValueOnce({ id: 7, name: "안드로이드 폰", prefix: "pq_ab", created_at: "", token: "pq_secret" });
    fireEvent.click(screen.getByTestId("fills-consent"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("fills-issue"));
    });
    const [url, init] = apiFetchMock.mock.calls[0];
    expect(url).toBe(API.imports.tokens);
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ name: "안드로이드 폰", consent: true });
    expect(screen.getByTestId("fills-header").textContent).toBe("Bearer pq_secret");
    expect(screen.getByTestId("fills-url").textContent).toContain(API.imports.webhook);
    expect(screen.getByTestId("fills-body")).toBeTruthy();
    expect(mutate).toHaveBeenCalled();
  });

  it("with a token already active, does not offer a second one", () => {
    tokens = [{ id: 1, revoked_at: null }];
    render(<OnboardingFillsPage />);
    expect(screen.getByTestId("fills-has-token")).toBeTruthy();
    expect(screen.queryByTestId("fills-issue")).toBeNull();
  });

  it("does not flash the issue form while the key list is loading", () => {
    tokensLoading = true;
    render(<OnboardingFillsPage />);
    expect(screen.getByTestId("fills-token-loading")).toBeTruthy();
    expect(screen.queryByTestId("fills-issue")).toBeNull();
    expect(screen.queryByTestId("fills-consent")).toBeNull();
  });

  it("is optional — later and next both go on to the questions", () => {
    render(<OnboardingFillsPage />);
    fireEvent.click(screen.getByTestId("fills-skip"));
    fireEvent.click(screen.getByTestId("fills-next"));
    expect(push).toHaveBeenNthCalledWith(1, "/onboarding");
    expect(push).toHaveBeenNthCalledWith(2, "/onboarding");
  });

  it("sends a user with no holding back to step 0", () => {
    positions = [];
    render(<OnboardingFillsPage />);
    expect(replace).toHaveBeenCalledWith("/onboarding/broker");
  });
});
