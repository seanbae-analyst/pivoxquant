/**
 * image-import.test.tsx — screenshot import UI (docs/product/SCREENSHOT_IMPORT_DESIGN.md).
 *
 * The OCR session is replaced by a fake that returns a committed Tesseract
 * dump (tests/fixtures/screenshot_import/synthetic/ocr), so the real rule
 * parser runs. Checks: (1) wrong screens are named and skipped, (2) blanks
 * block sending until the user fills them, (3) the request is JSON rows only
 * — no image — with `user_filled` naming what the user typed, (4) a fuzzy
 * stock match in the inbox needs the confirm tick before approval.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen, fireEvent, act, within } from "@testing-library/react";

vi.mock("@/lib/hooks", () => ({ usePendingImports: vi.fn() }));
vi.mock("@/lib/locale", () => ({
  useT: () => (k: string) => k,
  useLocale: () => ({ locale: "ko" }),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { ImageImportPanel } from "@/components/journal/image-import-panel";
import { PendingTradeRow } from "@/components/journal/import-inbox";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import type { PendingTradeDTO } from "@/lib/types";

const apiFetchMock = vi.mocked(apiFetch);
const FIX = path.resolve(__dirname, "../../../../../tests/fixtures/screenshot_import/synthetic/ocr");
const dump = (f: string) => JSON.parse(fs.readFileSync(path.join(FIX, `${f}.json`), "utf8")) as OcrWord[];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function fakeSession(byName: Record<string, OcrWord[]>) {
  const close = vi.fn(async () => {});
  const open = vi.fn(async () => ({
    read: async (file: File) => byName[file.name],
    close,
  }));
  return { open, close };
}

function pick(names: string[]) {
  const files = names.map((n) => new File([new Uint8Array([1])], n, { type: "image/png" }));
  fireEvent.change(screen.getByTestId("image-input"), { target: { files } });
}

async function readAll() {
  await act(async () => {
    fireEvent.click(screen.getByTestId("image-read"));
  });
}

describe("ImageImportPanel", () => {
  it("names and skips a holdings screen", async () => {
    const s = fakeSession({ "j.png": dump("j_holdings.png") });
    render(<ImageImportPanel consent onResult={() => {}} openSession={s.open} />);
    pick(["j.png"]);
    await readAll();
    expect(screen.getByTestId("image-notes").textContent).toContain("journal.import.image.screen.holdings");
    expect(screen.queryByTestId("ocr-review-table")).toBeNull();
    expect(s.close).toHaveBeenCalled();
  });

  it("blocks sending until blanks are filled, then sends JSON rows only", async () => {
    apiFetchMock.mockResolvedValue({
      batch: { id: 1, source: "screenshot_image", broker_guess: "unknown", row_count: 1,
               parsed_count: 1, duplicate_count: 0, unresolved_count: 0, created_at: "" },
      pending: [], mapping: null, unmapped_headers: [], skipped: [],
    });
    const onResult = vi.fn();
    const s = fakeSession({ "a.png": dump("a_card_list.png") });
    render(<ImageImportPanel consent onResult={onResult} openSession={s.open} />);
    pick(["a.png"]);
    await readAll();

    const rows = screen.getAllByTestId("ocr-review-row");
    expect(rows.length).toBe(6);
    const send = screen.getByTestId("image-send") as HTMLButtonElement;
    // Some cells could not be proven → blank + outlined → send blocked.
    const missing = document.querySelectorAll("[data-missing='true']");
    expect(missing.length).toBeGreaterThan(0);
    expect(send.disabled).toBe(true);

    // Keep only the first row and fill whatever it is missing.
    rows.slice(1).forEach((r) => fireEvent.click(within(r).getByLabelText("journal.import.image.includeRow")));
    const first = rows[0];
    const fill: Record<string, string> = {
      "journal.import.image.col.date": "2026-09-23",
      "journal.import.image.col.shares": "10",
      "journal.import.image.col.price": "72400",
      "journal.import.image.col.name": "삼성전자",
    };
    for (const [label, value] of Object.entries(fill)) {
      const el = within(first).getByLabelText(label) as HTMLInputElement;
      if (!el.value) fireEvent.change(el, { target: { value } });
    }
    for (const label of ["journal.import.image.col.side", "journal.import.image.col.currency"]) {
      const el = within(first).getByLabelText(label) as HTMLSelectElement;
      if (!el.value) fireEvent.change(el, { target: { value: label.endsWith("side") ? "BUY" : "KRW" } });
    }
    expect(send.disabled).toBe(false);
    await act(async () => {
      fireEvent.click(send);
    });

    const [url, init] = apiFetchMock.mock.calls[0];
    expect(url).toBe(API.imports.image);
    const body = JSON.parse((init as { body: string }).body);
    expect(body.consent).toBe(true);
    expect(body.rows).toHaveLength(1);
    const row = body.rows[0];
    expect(row).toMatchObject({ date: "2026-09-23", shares: 10, price: 72400, currency: "KRW", action: "buy" });
    expect(Array.isArray(row.user_filled)).toBe(true);
    expect(JSON.stringify(body)).not.toMatch(/data:image|base64/);
    expect(onResult).toHaveBeenCalled();
  });

  it("send stays off without the collection consent", async () => {
    const s = fakeSession({ "a.png": dump("a_card_list.png") });
    render(<ImageImportPanel consent={false} onResult={() => {}} openSession={s.open} />);
    pick(["a.png"]);
    await readAll();
    expect((screen.getByTestId("image-send") as HTMLButtonElement).disabled).toBe(true);
  });
});

const FUZZY_ROW: PendingTradeDTO = {
  id: 21,
  batch_id: 3,
  ticker: "000660.KS",
  name: "SK하이닉스",
  action: "BUY",
  shares: 4,
  price: 198500,
  currency: "KRW",
  traded_at: "2026-09-23T05:21:07",
  confidence: 0.6,
  status: "pending",
  needs_ticker: false,
  pre_trade_reflection_id: null,
  raw_snippet: "하이닉스 체결 4주 [확인: 종목 — 읽은 이름 '하이닉스' → SK하이닉스]",
  approved_trade_id: null,
  approved_at: null,
  source: "screenshot_image",
  needs_confirm: true,
};

describe("PendingTradeRow — fuzzy stock match", () => {
  it("disables approve until confirmed, then sends confirm_values", async () => {
    apiFetchMock.mockResolvedValue({ ok: true });
    render(<PendingTradeRow row={FUZZY_ROW} onChanged={() => {}} />);
    expect(screen.getByTestId("import-needs-confirm")).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText("journal.import.thesisPlaceholder"), {
      target: { value: "기록으로 남긴다" },
    });
    const approve = screen.getByText("journal.import.approve") as HTMLButtonElement;
    expect(approve.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("journal.import.image.confirmLabel"));
    expect(approve.disabled).toBe(false);
    await act(async () => {
      fireEvent.click(approve);
    });
    const [url, init] = apiFetchMock.mock.calls[0];
    expect(url).toBe(API.imports.approve(21));
    expect(JSON.parse((init as { body: string }).body)).toEqual({
      thesis: "기록으로 남긴다",
      confirm_values: true,
    });
  });

  it("rows without needs_confirm have no check box", () => {
    render(<PendingTradeRow row={{ ...FUZZY_ROW, needs_confirm: false, confidence: 0.9 }} onChanged={() => {}} />);
    expect(screen.queryByTestId("import-needs-confirm")).toBeNull();
  });
});

import { currencyConflict, rowComplete, rowFromParsed } from "@/components/journal/ocr-review-table";
import { parseFillScreen } from "@/lib/fill-ocr/parse";

describe("review-table guards", () => {
  const base = () => {
    const f = parseFillScreen(dump("a_card_list.png")).rows[0];
    const r = rowFromParsed(f, "image.jpeg", 0, 0);
    r.values = { date: "2026-09-23", time: "", name: "Apple", code: "AAPL", side: "BUY",
                 shares: "1", price: "312000", currency: "KRW" };
    return r;
  };

  it("blocks a US symbol with a won price", () => {
    const r = base();
    expect(currencyConflict(r)).toBe("usd_needed");
    expect(rowComplete(r)).toBe(false);
    r.values.currency = "USD";
    r.values.price = "231.5";
    expect(rowComplete(r)).toBe(true);
  });

  it("keys stay unique when two picks share a file name", () => {
    const f = parseFillScreen(dump("a_card_list.png")).rows[0];
    expect(rowFromParsed(f, "image.jpeg", 0, 0).key).not.toBe(rowFromParsed(f, "image.jpeg", 0, 1).key);
  });
});

describe("parser guards", () => {
  it("does not date month-only headers across a Dec/Jan boundary", () => {
    const w = (t: string, y: number, x = 40) => ({ t, c: 95, x0: x, y0: y, x1: x + 20 * t.length, y1: y + 20, alt: /\d/.test(t) ? t : undefined });
    const words = [
      w("거래내역", 10), w("2026년", 40),
      w("12월", 80), w("30일", 80, 120),
      w("삼성전자", 120), w("10", 150), w("주", 150, 90), w("구매", 150, 130), w("주당", 150, 200), w("72,400", 150, 260), w("원", 150, 380),
      w("1월", 200), w("2일", 200, 100),
      w("카카오", 240), w("5", 270), w("주", 270, 70), w("판매", 270, 110), w("주당", 270, 180), w("41,850", 270, 240), w("원", 270, 360),
    ];
    const res = parseFillScreen(words);
    expect(res.rows.length).toBeGreaterThan(0);
    for (const r of res.rows) expect(r.date.value).toBeNull();
  });
});

describe("name guard", () => {
  it("a split date header is never a stock name", () => {
    const w = (t: string, y: number, x: number) => ({ t, c: 95, x0: x, y0: y, x1: x + 18 * t.length, y1: y + 20, alt: /\d/.test(t) ? t : undefined });
    const words = [
      w("체결내역", 10, 20),
      w("2026", 60, 20), w("년", 60, 100), w("9", 60, 130), w("월", 60, 150), w("22", 60, 180), w("일", 60, 220), w("(화)", 60, 250),
      w("10", 100, 20), w("주", 100, 70), w("구매", 100, 100), w("주당", 100, 160), w("72,400", 100, 220), w("원", 100, 340),
    ];
    for (const r of parseFillScreen(words).rows) expect(r.name.value ?? "").not.toMatch(/년|월|일/);
  });
});
