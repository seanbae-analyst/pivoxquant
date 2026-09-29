/**
 * holdings-import.test.tsx — holdings-screen capture import
 * (docs/product/HOLDINGS_IMPORT_DESIGN.md).
 *
 * The OCR session is a fake returning committed Tesseract dumps, so the real
 * parser runs. Checks: a holdings screen is read and resolved via preview, a
 * fill screen is named and skipped, blanks and the consent box block saving,
 * existing positions default to replace, and the commit body is JSON rows only.
 */
import fs from "node:fs";
import path from "node:path";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen, fireEvent, act } from "@testing-library/react";

vi.mock("@/lib/locale", () => ({
  useT: () => (k: string) => k,
  useLocale: () => ({ locale: "ko" }),
}));
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, apiFetch: vi.fn() };
});
vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn(), error: vi.fn() } }));

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import {
  HoldingsImportPanel, rowIssues, commitPayload, mergeIdenticalReads, applyPreview, type HoldingRow,
} from "@/components/portfolio/v2/holdings-import-panel";
import type { OcrWord } from "@/lib/fill-ocr/parse";
import type { HoldingsPreviewRow } from "@/lib/types";

const apiFetchMock = vi.mocked(apiFetch);
const FIX = path.resolve(__dirname, "../../../../../../tests/fixtures/screenshot_import");
const dump = (rel: string) => JSON.parse(fs.readFileSync(path.join(FIX, rel), "utf8")) as OcrWord[];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function fakeSession(byName: Record<string, OcrWord[]>) {
  return async () => ({
    read: async (f: File) => byName[f.name],
    close: async () => {},
  });
}

const TICKERS: Record<string, [string, string]> = {
  삼성전자: ["005930.KS", "삼성전자"], 기아: ["000270.KS", "기아"], 신한지주: ["055550.KS", "신한지주"],
  한국전력: ["015760.KS", "한국전력"],
};

/** Resolve exact names; the first resolved row already exists (10 @ 60,000). */
function mockPreview() {
  apiFetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
    if (url !== API.holdingsImport.preview) return { created: [], replaced: [], added: [], skipped: [] } as never;
    const body = JSON.parse(String(init?.body)) as { rows: { name: string | null }[] };
    return {
      rows: body.rows.map((r, index): HoldingsPreviewRow => {
        const hit = r.name ? TICKERS[r.name] : undefined;
        return {
          index, read_name: r.name, read_code: null,
          ticker: hit?.[0] ?? null, name: hit?.[1] ?? null, currency: hit ? "KRW" : null,
          status: hit ? "resolved" : "needs_ticker", currency_mismatch: false,
          existing: hit && hit[1] === "삼성전자" ? { id: 1, shares: 10, avg_cost: 60000, currency: "KRW" } : null,
        };
      }),
    } as never;
  });
}

async function pickAndRead(names: string[], byName: Record<string, OcrWord[]>) {
  const input = screen.getByTestId("holdings-image-input");
  const files = names.map((n) => new File(["x"], n, { type: "image/png" }));
  await act(async () => { fireEvent.change(input, { target: { files } }); });
  await act(async () => { fireEvent.click(screen.getByTestId("holdings-read")); });
  void byName;
}

describe("HoldingsImportPanel", () => {
  it("reads a holdings screen, rejects a fill screen, and blocks saving until blanks + consent", async () => {
    mockPreview();
    const byName = {
      "hold.png": dump("holdings/ocr/t01_dark_cards.png.json"),
      "fills.png": dump("synthetic/ocr/a_card_list.png.json"),
    };
    render(<HoldingsImportPanel onDone={vi.fn()} onCancel={vi.fn()} openSession={fakeSession(byName) as never} />);
    await pickAndRead(["hold.png", "fills.png"], byName);

    const notes = screen.getByTestId("holdings-notes").textContent ?? "";
    expect(notes).toContain("dashboard.portfolio.holdingsImport.screen.fills");
    expect(notes).toContain("dashboard.portfolio.holdingsImport.noteRead");
    const rows = screen.getAllByTestId("holdings-review-row");
    expect(rows.length).toBe(5);
    // Existing position → replace by default; new ones → add.
    const modes = screen.getAllByTestId("holdings-mode").map((el) => (el as HTMLSelectElement).value);
    expect(modes[0]).toBe("replace");
    expect(modes.slice(1).every((m) => m === "add")).toBe(true);

    // The LG에너지솔루션 row cannot be resolved by name → the save stays off.
    const send = screen.getByTestId("holdings-send") as HTMLButtonElement;
    fireEvent.click(screen.getByTestId("holdings-consent"));
    expect(send.disabled).toBe(true);

    // Skip the unresolved row → everything else is proven → save enabled.
    const unresolved = rows.findIndex((r) => r.querySelector("[data-testid=holdings-ticker]") === null);
    expect(unresolved).toBeGreaterThanOrEqual(0);
    fireEvent.change(screen.getAllByTestId("holdings-mode")[unresolved], { target: { value: "skip" } });
    expect(send.disabled).toBe(false);

    // Consent off → disabled again.
    fireEvent.click(screen.getByTestId("holdings-consent"));
    expect(send.disabled).toBe(true);
    fireEvent.click(screen.getByTestId("holdings-consent"));

    apiFetchMock.mockResolvedValueOnce({ created: [], replaced: [], added: [], skipped: [] } as never);
    await act(async () => { fireEvent.click(send); });
    const commit = apiFetchMock.mock.calls.find(([u]) => u === API.holdingsImport.commit)!;
    const body = JSON.parse(String(commit[1]!.body));
    expect(body.consent).toBe(true);
    expect(Object.keys(body).sort()).toEqual(["consent", "rows"]);
    expect(body.rows.length).toBe(4); // the skipped row is not sent
    for (const r of body.rows) expect(Object.keys(r).sort()).toEqual(["avg_cost", "currency", "mode", "shares", "ticker"]);
    expect(body.rows[0]).toEqual({ ticker: "005930.KS", shares: 42, avg_cost: 68200, currency: "KRW", mode: "replace" });
    expect(String(commit[1]!.body)).not.toMatch(/data:image|base64/);
    // Preview got names/codes only — no numbers, no image.
    const prev = apiFetchMock.mock.calls.find(([u]) => u === API.holdingsImport.preview)!;
    for (const r of JSON.parse(String(prev[1]!.body)).rows) expect(Object.keys(r).sort()).toEqual(["code", "currency", "name"]);
  });

  it("shows what to capture, labels each cell, and fills an unproven reading in one tap", async () => {
    mockPreview();
    // Toss 내 투자 row whose printed rate does not reproduce: the average is a hint only.
    let y = 0;
    const line = (...ws: [string, string | undefined, number][]) => {
      y += 70;
      return ws.map(([t, alt, x]) => ({ t, c: 90, x0: x, y0: y, x1: x + t.length * 20, y1: y + 30, ...(alt !== undefined ? { alt } : {}) }));
    };
    const words = [
      ...line(["삼성전자", undefined, 190], ["1,000,000", "1,000,000", 700], ["원", undefined, 900]),
      ...line(["3", "3", 190], ["주", undefined, 220], ["-100,000", "100,000", 600], ["(20.0%)", "20.0", 800]),
      ...line(["기아", undefined, 190], ["500,000", "500,000", 700], ["원", undefined, 900]),
      ...line(["5", "5", 190], ["주", undefined, 220], ["-50,000", "50,000", 600], ["(20.0%)", "20.0", 800]),
    ] as OcrWord[];
    render(<HoldingsImportPanel onDone={vi.fn()} onCancel={vi.fn()} openSession={fakeSession({ "toss.png": words }) as never} />);
    expect(screen.getByTestId("holdings-capture-guide").textContent).toContain("dashboard.portfolio.holdingsImport.shot.toss");
    await pickAndRead(["toss.png"], {});

    const row = screen.getAllByTestId("holdings-review-row")[0];
    expect(row.textContent).toContain("dashboard.portfolio.holdingsImport.help.shares");
    expect(row.textContent).toContain("dashboard.portfolio.holdingsImport.help.avgCost");
    const avg = row.querySelector("input[aria-label='dashboard.portfolio.holdingsImport.col.avgCost']") as HTMLInputElement;
    expect(avg.value).toBe("");
    fireEvent.click(row.querySelector("[data-testid=holdings-use-read]")!);
    expect(avg.value).toBe("366667"); // (1,000,000 + 100,000) ÷ 3, read but not proven
  });

  it("does not offer a won average reading that the row would reject ('170.850원')", async () => {
    mockPreview();
    let y = 0;
    const line = (...ws: [string, string | undefined, number][]) => {
      y += 70;
      return ws.map(([t, alt, x]) => ({ t, c: 90, x0: x, y0: y, x1: x + t.length * 20, y1: y + 30, ...(alt !== undefined ? { alt } : {}) }));
    };
    const words = [
      ...line(["보유종목", undefined, 20]),
      ...line(["삼성전자", undefined, 20]),
      ...line(["보유수량", undefined, 20], ["10", "10", 500], ["주", undefined, 560]),
      ...line(["평균단가", undefined, 20], ["170.850", "170.850", 500], ["원", undefined, 660]),
    ] as OcrWord[];
    render(<HoldingsImportPanel onDone={vi.fn()} onCancel={vi.fn()} openSession={fakeSession({ "card.png": words }) as never} />);
    await pickAndRead(["card.png"], {});
    const row = screen.getAllByTestId("holdings-review-row")[0];
    const avg = row.querySelector("input[aria-label='dashboard.portfolio.holdingsImport.col.avgCost']") as HTMLInputElement;
    expect(avg.value).toBe("");
    expect(row.querySelector("[data-testid=holdings-use-read]")).toBeNull();
  });

  it("a fill screen alone yields no rows and no preview call", async () => {
    mockPreview();
    const byName = { "fills.png": dump("synthetic/ocr/b_hts_table.png.json") };
    render(<HoldingsImportPanel onDone={vi.fn()} onCancel={vi.fn()} openSession={fakeSession(byName) as never} />);
    await pickAndRead(["fills.png"], byName);
    expect(screen.queryAllByTestId("holdings-review-row")).toHaveLength(0);
    expect(apiFetchMock).not.toHaveBeenCalled();
  });
});

describe("row rules", () => {
  const base: HoldingRow = {
    key: "k", fileName: "a.png", sourceText: "", flags: [], readName: "삼성전자", readCode: "", hints: {},
    shares: "10", avgCost: "70000", currency: "KRW", screenCurrency: "KRW", ticker: "005930.KS",
    tickerName: "삼성전자", tickerCurrency: "KRW", status: "resolved", confirmed: false, existing: null, mode: "add",
  };
  it("blank or invalid cells block the row", () => {
    expect(rowIssues(base, [base])).toEqual([]);
    expect(rowIssues({ ...base, avgCost: "" }, [base])).toContain("avgCost");
    expect(rowIssues({ ...base, shares: "1.5" }, [base])).toContain("shares");
    expect(rowIssues({ ...base, currency: "" }, [base])).toContain("currency");
    expect(rowIssues({ ...base, status: "needs_confirm" }, [base])).toContain("confirm");
    expect(rowIssues({ ...base, ticker: "", status: "needs_ticker" }, [base])).toContain("ticker");
  });
  it("a won average is whole won and at least 100 — '170.85' is 170,850 misread", () => {
    expect(rowIssues({ ...base, avgCost: "170.85" }, [base])).toContain("avgCost");
    expect(rowIssues({ ...base, avgCost: "50" }, [base])).toContain("avgCost");
    const us = { ...base, ticker: "AAPL", tickerCurrency: "USD", currency: "USD" as const, avgCost: "23.15" };
    expect(rowIssues(us, [us])).toEqual([]);
  });
  it("a US ticker with a won average is a currency mismatch, never silently converted", () => {
    const us = { ...base, ticker: "AAPL", tickerCurrency: "USD", currency: "KRW" as const };
    expect(rowIssues(us, [us])).toContain("currencyMismatch");
  });
  it("the same ticker twice must be settled by the user; skipped rows are not sent", () => {
    const b = { ...base, key: "k2", shares: "11" };
    expect(rowIssues(base, [base, b])).toContain("duplicate");
    const skipped = { ...b, mode: "skip" as const };
    expect(rowIssues(base, [base, skipped])).toEqual([]);
    expect(commitPayload([base, skipped])).toHaveLength(1);
  });
  it("identical reads from overlapping captures merge; differing ones do not", () => {
    const b = { ...base, key: "k2" };
    expect(mergeIdenticalReads([base, b])).toHaveLength(1);
    expect(mergeIdenticalReads([base, { ...b, avgCost: "70100" }])).toHaveLength(2);
  });

  it("a won average worked out for what resolves to a US stock is dropped", () => {
    const row = { ...base, ticker: "", status: "needs_ticker" as const, flags: ["derived_avg"], avgCost: "33779", shares: "24" };
    const out = applyPreview(row, { index: 0, read_name: "뉴스케일파워", read_code: null, ticker: "SMR", name: "뉴스케일파워",
      currency: "USD", status: "resolved", currency_mismatch: true, existing: null } as HoldingsPreviewRow);
    expect([out.ticker, out.shares, out.avgCost, out.currency]).toEqual(["SMR", "24", "", ""]);
    expect(out.flags).toContain("foreign_in_krw");
  });

  it("a proven read absorbs the same holding read only as hints elsewhere", () => {
    const hinted = { ...base, key: "k3", shares: "", avgCost: "", hints: { shares: base.shares, avgCost: base.avgCost } };
    const merged = mergeIdenticalReads([hinted, base]);
    expect(merged).toHaveLength(1);
    expect([merged[0].shares, merged[0].avgCost]).toEqual([base.shares, base.avgCost]);
    const other = { ...hinted, hints: { shares: "9" } };
    expect(mergeIdenticalReads([other, base])).toHaveLength(2);
  });
});
