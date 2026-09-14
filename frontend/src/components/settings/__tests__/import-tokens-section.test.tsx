/**
 * import-tokens-section.test.tsx — DOM coverage for the /settings
 * "가져오기 토큰" section (IMPORT_INBOX_DESIGN.md §Phase 2 v3-A 테스트).
 *
 * Mirrors journal/__tests__/import-inbox.test.tsx: the SWR hook and the
 * locale are mocked so assertions target i18n keys + data-derived output;
 * `apiFetch` is mocked so no request leaves the test.
 *
 *   1. list renders, revoked rows are dimmed
 *   2. issue is disabled until name AND consent are present
 *   3. after a successful issue the raw token is on screen (once, from the
 *      201 body) and never in the list
 *   4. revoke → in-place confirm → DELETE → mutate
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  cleanup,
  screen,
  within,
  fireEvent,
  waitFor,
} from "@testing-library/react";

const hooks = vi.hoisted(() => ({
  useImportTokens: vi.fn(),
}));
vi.mock("@/lib/hooks", () => hooks);
vi.mock("@/lib/locale", () => ({
  // Keys echo back as themselves, except the one template the list interpolates.
  useT: () => (k: string) => (k === "settingsV2.importTokens.todayCount" ? "{n}건" : k),
  useLocale: () => ({ locale: "ko" }),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, apiFetch: vi.fn() };
});
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import {
  ImportTokensSection,
  tokenNameOk,
  curlExample,
} from "@/components/settings/import-tokens-section";
import type { ImportTokenDTO } from "@/lib/types";

const apiFetchMock = vi.mocked(apiFetch);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const TOKENS: ImportTokenDTO[] = [
  {
    id: 1,
    name: "폰 MacroDroid",
    prefix: "pvx_abc12345",
    created_at: "2026-09-13T01:00:00Z",
    last_used_at: "2026-09-13T02:30:00Z",
    revoked_at: null,
    batches_today: 3,
  },
  {
    id: 2,
    name: "옛 노트북",
    prefix: "pvx_zzz98765",
    created_at: "2026-09-01T01:00:00Z",
    last_used_at: null,
    revoked_at: "2026-09-10T00:00:00Z",
    batches_today: 0,
  },
];

function loaded(tokens: ImportTokenDTO[], activeLimit = 5) {
  const mutate = vi.fn().mockResolvedValue(undefined);
  hooks.useImportTokens.mockReturnValue({
    tokens,
    activeLimit,
    isLoading: false,
    error: undefined,
    mutate,
  });
  return mutate;
}

describe("ImportTokensSection", () => {
  it("renders the list with revoked rows dimmed and no raw token anywhere", () => {
    loaded(TOKENS);
    const { container } = render(<ImportTokensSection />);

    const rows = screen.getAllByTestId("import-token-row");
    expect(rows).toHaveLength(2);

    expect(within(rows[0]).getByText("폰 MacroDroid")).toBeInTheDocument();
    expect(within(rows[0]).getByText(/pvx_abc12345/)).toBeInTheDocument();
    expect(within(rows[0]).getByText("3건")).toBeInTheDocument(); // todayCount "{n}건"
    expect(rows[0]).toHaveAttribute("data-revoked", "false");
    expect(rows[0]).toHaveStyle({ opacity: "1" });
    expect(
      within(rows[0]).getByRole("button", { name: "settingsV2.importTokens.revoke" }),
    ).toBeInTheDocument();

    // Revoked row: dimmed, labelled, no revoke button.
    expect(rows[1]).toHaveAttribute("data-revoked", "true");
    expect(rows[1]).toHaveStyle({ opacity: "0.4" });
    expect(within(rows[1]).getByText("settingsV2.importTokens.revoked")).toBeInTheDocument();
    expect(within(rows[1]).getByText("settingsV2.importTokens.neverUsed")).toBeInTheDocument();
    expect(
      within(rows[1]).queryByRole("button", { name: "settingsV2.importTokens.revoke" }),
    ).toBeNull();

    // The one-time reveal box is absent until an issue happens.
    expect(screen.queryByTestId("import-token-reveal")).toBeNull();
    expect(container.textContent ?? "").not.toMatch(/NaN|undefined|null/);
  });

  it("keeps the issue button disabled until both name and consent are present", () => {
    loaded([]);
    render(<ImportTokensSection />);

    const issue = screen.getByRole("button", { name: "settingsV2.importTokens.issue" });
    const name = screen.getByLabelText("settingsV2.importTokens.nameLabel");
    const consent = screen.getByLabelText("settingsV2.importTokens.consentLabel");

    expect(issue).toBeDisabled();

    fireEvent.change(name, { target: { value: "폰" } });
    expect(issue).toBeDisabled(); // name only

    fireEvent.change(name, { target: { value: "" } });
    fireEvent.click(consent);
    expect(issue).toBeDisabled(); // consent only

    fireEvent.change(name, { target: { value: "   " } });
    expect(issue).toBeDisabled(); // whitespace is not a name

    fireEvent.change(name, { target: { value: "폰 MacroDroid" } });
    expect(issue).toBeEnabled();
  });

  it("disables the form at the active limit", () => {
    const five: ImportTokenDTO[] = Array.from({ length: 5 }, (_, i) => ({
      ...TOKENS[0],
      id: 10 + i,
      name: `t${i}`,
    }));
    loaded(five, 5);
    render(<ImportTokensSection />);

    expect(screen.getByLabelText("settingsV2.importTokens.nameLabel")).toBeDisabled();
    expect(screen.getByRole("button", { name: "settingsV2.importTokens.issue" })).toBeDisabled();
    // `t` is a passthrough here, so the {limit} placeholder is absent and
    // the key itself is what lands on screen.
    expect(screen.getByText("settingsV2.importTokens.limitReached")).toBeInTheDocument();
  });

  it("shows the raw token once after a successful issue, then hides it on dismiss", async () => {
    const mutate = loaded([]);
    apiFetchMock.mockResolvedValueOnce({
      id: 7,
      name: "폰 MacroDroid",
      prefix: "pvx_newtoken",
      created_at: "2026-09-13T03:00:00Z",
      token: "pvx_newtoken_RAW_SECRET_VALUE",
    });
    render(<ImportTokensSection />);

    fireEvent.change(screen.getByLabelText("settingsV2.importTokens.nameLabel"), {
      target: { value: "폰 MacroDroid" },
    });
    fireEvent.click(screen.getByLabelText("settingsV2.importTokens.consentLabel"));
    fireEvent.click(screen.getByRole("button", { name: "settingsV2.importTokens.issue" }));

    const reveal = await screen.findByTestId("import-token-reveal");
    expect(within(reveal).getByTestId("import-token-raw")).toHaveTextContent(
      "pvx_newtoken_RAW_SECRET_VALUE",
    );
    expect(within(reveal).getByText("settingsV2.importTokens.revealOnce")).toBeInTheDocument();
    expect(within(reveal).getByText(/curl -X POST/)).toBeInTheDocument();
    expect(within(reveal).getByText("settingsV2.importTokens.macrodroid1")).toBeInTheDocument();

    // Contract: POST tokens with {name, consent:true}; list re-fetched.
    expect(apiFetchMock).toHaveBeenCalledWith(
      API.imports.tokens,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ name: "폰 MacroDroid", consent: true }),
      }),
    );
    expect(mutate).toHaveBeenCalled();

    // Form reset after issue.
    expect(screen.getByLabelText("settingsV2.importTokens.nameLabel")).toHaveValue("");
    expect(screen.getByLabelText("settingsV2.importTokens.consentLabel")).not.toBeChecked();

    // Dismiss — the raw token leaves the DOM and there is no way to see it again.
    fireEvent.click(within(reveal).getByRole("button", { name: "settingsV2.importTokens.dismiss" }));
    expect(screen.queryByTestId("import-token-reveal")).toBeNull();
    expect(document.body.textContent ?? "").not.toContain("pvx_newtoken_RAW_SECRET_VALUE");
  });

  it("falls back to selectable text when the clipboard is blocked", async () => {
    loaded([]);
    apiFetchMock.mockResolvedValueOnce({
      id: 8,
      name: "x",
      prefix: "pvx_x",
      created_at: "2026-09-13T03:00:00Z",
      token: "pvx_x_RAW",
    });
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
    });
    render(<ImportTokensSection />);
    fireEvent.change(screen.getByLabelText("settingsV2.importTokens.nameLabel"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByLabelText("settingsV2.importTokens.consentLabel"));
    fireEvent.click(screen.getByRole("button", { name: "settingsV2.importTokens.issue" }));

    const reveal = await screen.findByTestId("import-token-reveal");
    fireEvent.click(within(reveal).getByRole("button", { name: "settingsV2.importTokens.copy" }));
    expect(await within(reveal).findByText("settingsV2.importTokens.copyFailed")).toBeInTheDocument();
    expect(within(reveal).getByTestId("import-token-raw")).toHaveTextContent("pvx_x_RAW");
  });

  it("revokes only after the in-place confirm, then DELETEs and mutates", async () => {
    const mutate = loaded(TOKENS);
    apiFetchMock.mockResolvedValueOnce({ ok: true });
    render(<ImportTokensSection />);

    const row = screen.getAllByTestId("import-token-row")[0];
    fireEvent.click(within(row).getByRole("button", { name: "settingsV2.importTokens.revoke" }));

    // Nothing sent yet — the confirm replaces the button in place.
    expect(apiFetchMock).not.toHaveBeenCalled();
    const confirm = within(row).getByRole("button", {
      name: "settingsV2.importTokens.revokeConfirm",
    });
    const cancel = within(row).getByRole("button", { name: "settingsV2.importTokens.revokeCancel" });

    // Cancel restores the original button.
    fireEvent.click(cancel);
    expect(
      within(row).getByRole("button", { name: "settingsV2.importTokens.revoke" }),
    ).toBeInTheDocument();
    expect(apiFetchMock).not.toHaveBeenCalled();

    // Confirm → DELETE /tokens/:id → mutate.
    fireEvent.click(within(row).getByRole("button", { name: "settingsV2.importTokens.revoke" }));
    fireEvent.click(
      within(row).getByRole("button", { name: "settingsV2.importTokens.revokeConfirm" }),
    );
    await waitFor(() => expect(mutate).toHaveBeenCalled());
    expect(apiFetchMock).toHaveBeenCalledWith(API.imports.token(1), { method: "DELETE" });
    // React may reuse the same <button> node when the label flips back, so
    // assert by role/name rather than by the captured element.
    expect(
      within(row).queryByRole("button", { name: "settingsV2.importTokens.revokeConfirm" }),
    ).not.toBeInTheDocument();
    expect(confirm).toBeDefined();
  });

  it("tokenNameOk enforces 1~60 on trimmed length; curl example carries the address and bearer", () => {
    expect(tokenNameOk("")).toBe(false);
    expect(tokenNameOk("   ")).toBe(false);
    expect(tokenNameOk("a")).toBe(true);
    expect(tokenNameOk("a".repeat(60))).toBe(true);
    expect(tokenNameOk("a".repeat(61))).toBe(false);

    const line = curlExample("https://app.example", "pvx_abc");
    expect(line).toContain("https://app.example/api/portfolio/imports/webhook");
    expect(line).toContain("Authorization: Bearer pvx_abc");
    expect(line).toContain('{"text":');
  });
});
