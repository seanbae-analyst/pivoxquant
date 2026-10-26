/**
 * DoorwaySection — /settings · 「문 앞의 한 줄」 (2026-10-15).
 *
 * Pins: the iOS body carries the chosen app and the menu-result placeholder;
 * the address is the doorway webhook on this origin; Android opens the web
 * door with the same app tag; both phone paths say 시험 중; the token is the
 * one from 체결 자동 기록 (linked, never re-issued here); the copy promises
 * nothing the product does not do (deleting answers lives on the web door).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const tokens = vi.hoisted(() => ({ list: [] as unknown[] }));
vi.mock("@/lib/hooks", () => ({
  useImportTokens: () => ({ tokens: tokens.list, activeLimit: 5, isLoading: false, error: undefined, mutate: vi.fn() }),
}));
vi.mock("@/lib/locale", () => ({
  useLocale: () => ({ locale: "ko" }),
  useT: () => (k: string) => k,
}));

import {
  DoorwaySection,
  doorPageUrl,
  openSignalBody,
  doorwayWebhookUrl,
  shortcutBody,
} from "@/components/settings/doorway-section";

afterEach(cleanup);

describe("DoorwaySection", () => {
  it("builds the address, body and door URL for the chosen app", () => {
    expect(doorwayWebhookUrl("https://pivoxquant.com")).toBe("https://pivoxquant.com/api/doorway/webhook");
    expect(shortcutBody("kiwoom")).toBe('{"text":"[메뉴 결과]","app":"kiwoom"}');
    // launch=1: the automation opened it — the page records the open before any answer.
    expect(doorPageUrl("https://pivoxquant.com", "toss")).toBe("https://pivoxquant.com/pre-trade/door?app=toss&launch=1");
    expect(openSignalBody("toss")).toBe('{"text":"열림","app":"toss"}');
  });

  it("switches every copy field when another broker app is picked", () => {
    render(<DoorwaySection />);
    expect(screen.getByTestId("doorway-body").textContent).toContain('"app":"toss"');
    fireEvent.change(screen.getByTestId("doorway-app"), { target: { value: "mirae" } });
    expect(screen.getByTestId("doorway-body").textContent).toContain('"app":"mirae"');
    expect(screen.getByTestId("doorway-door-url").textContent).toMatch(/\/pre-trade\/door\?app=mirae&launch=1$/);
    expect(screen.getByTestId("doorway-open-body").textContent).toContain('"app":"mirae"');
    expect(screen.getByTestId("doorway-url").textContent).toMatch(/\/api\/doorway\/webhook$/);
    expect(screen.getByRole("link", { name: "웹 문 열어 보기" })).toHaveAttribute("href", "/pre-trade/door?app=mirae");
  });

  it("says which active key may send door answers", () => {
    tokens.list = [
      { id: 1, name: "옛 열쇠", prefix: "pvx_a", created_at: "2026-09-13T00:00:00", last_used_at: null, revoked_at: null, batches_today: 0, doorway_ok: false },
      { id: 2, name: "아이폰 문 앞", prefix: "pvx_b", created_at: "2026-10-15T00:00:00", last_used_at: null, revoked_at: null, batches_today: 0, doorway_ok: true },
      { id: 3, name: "폐기됨", prefix: "pvx_c", created_at: "2026-10-15T00:00:00", last_used_at: null, revoked_at: "2026-10-15T01:00:00", batches_today: 0, doorway_ok: true },
    ];
    render(<DoorwaySection />);
    expect(screen.getByTestId("doorway-key-status").textContent).toBe("문 앞 기록을 보낼 수 있는 열쇠: 아이폰 문 앞");
    cleanup();
    tokens.list = [tokens.list[0]];
    render(<DoorwaySection />);
    expect(screen.getByTestId("doorway-key-status").textContent).toBe("아직 문 앞 기록을 보낼 수 있는 열쇠가 없어요.");
    tokens.list = [];
  });

  it("marks both phone paths as 시험 중 and points at the new-token rule", () => {
    render(<DoorwaySection />);
    expect(screen.getByText("아이폰 · 단축어 (시험 중)")).toBeInTheDocument();
    expect(screen.getByText("안드로이드 · MacroDroid (시험 중)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "체결 자동 기록" })).toHaveAttribute("href", "/settings?s=import");
    const text = document.body.textContent ?? "";
    expect(text).toContain("증권사 계정이나 주문에는 닿지 않습니다");
    expect(text).toContain("동의 문구가 생기기 전에 만든 열쇠는 쓸 수 없어요");
    // No effect claim and no label on the user's trading (legal review 2026-10-15).
    expect(text).not.toMatch(/충동|멈추는 장치/);
    expect(text).not.toMatch(/추천|조언|\bBUY\b|\bSELL\b/);
  });
});
