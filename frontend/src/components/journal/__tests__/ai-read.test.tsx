/**
 * ai-read.test.tsx — the AI read offer (lib/ai-read.ts, components/ui/ai-read-offer.tsx).
 *
 * docs/product/AI_READ_EXPERIMENT_2026-10-07.md §5. Pins: off unless the flag
 * is on; the user sees the exact text that will be sent and it carries no
 * account number or name; nothing is sent without the consent tick; AI rows
 * are labelled, replace the table, and the rule-read rows come back on revert.
 * The OCR session returns a committed production dump with fake PII.
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

import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { ImageImportPanel } from "@/components/journal/image-import-panel";
import { AiTextReadPanel, maskPastedText } from "@/components/journal/ai-text-read-panel";
import { fillFromAi, holdingFromAi, AI_SOURCE_TAG, type AiFillRow } from "@/lib/ai-read";
import { maskScreen } from "@/lib/fill-ocr/mask";
import type { OcrWord } from "@/lib/fill-ocr/parse";

const apiFetchMock = vi.mocked(apiFetch);
const DIR = path.resolve(__dirname, "../../../../../tests/fixtures/screenshot_import/ai_read");
const dump = (f: string) => JSON.parse(fs.readFileSync(path.join(DIR, "ocr", `${f}.json`), "utf8")) as OcrWord[];
const PII = (JSON.parse(fs.readFileSync(path.join(DIR, "ground_truth.json"), "utf8")) as Record<string, { pii: string[] }>)[
  "b01_fills.png"
].pii;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllEnvs();
});

function session(words: OcrWord[]) {
  return vi.fn(async () => ({ read: async () => words, close: async () => {} }));
}

async function readCapture() {
  const files = [new File([new Uint8Array([1])], "fills.png", { type: "image/png" })];
  fireEvent.change(screen.getByTestId("image-input"), { target: { files } });
  await act(async () => {
    fireEvent.click(screen.getByTestId("image-read"));
  });
}

const AI_ROW: AiFillRow = {
  name: { value: "삼성전자" }, code: { value: null }, action: { value: "buy" },
  shares: { value: 10 }, price: { value: 71200 }, amount: { value: 712000 },
  date: { value: "2026-09-01" }, time: { value: "10:15" }, currency: "KRW",
  flags: ["ai_read", "cross_checked"],
};

describe("AI read offer — fills capture", () => {
  it("is not offered while the flag is off", async () => {
    render(<ImageImportPanel consent onResult={() => {}} openSession={session(dump("b01_fills.png"))} />);
    await readCapture();
    expect(screen.queryByTestId("ai-read-offer")).toBeNull();
  });

  it("shows exactly the masked text, sends only after consent, labels and reverts", async () => {
    vi.stubEnv("NEXT_PUBLIC_AI_READ", "1");
    const words = dump("b01_fills.png");
    render(<ImageImportPanel consent onResult={() => {}} openSession={session(words)} />);
    await readCapture();

    const preview = screen.getByTestId("ai-read-preview").textContent ?? "";
    expect(preview).toBe(maskScreen(words).text);
    const flat = preview.replace(/\s+/g, "");
    for (const p of PII) for (const part of /\d/.test(p) ? p.split(/\D+/).filter((x) => x.length >= 4) : [p]) {
      expect(flat).not.toContain(part);
    }
    expect(screen.getByTestId("ai-content-badge")).toBeTruthy();

    // no consent → the button does nothing
    expect((screen.getByTestId("ai-read-run") as HTMLButtonElement).disabled).toBe(true);
    const ruleRowCount = screen.queryAllByTestId("ocr-review-row").length;

    apiFetchMock.mockResolvedValueOnce({ screens: [{ screen_type: "fills", reason: "", rows: [AI_ROW] }] });
    fireEvent.click(screen.getByTestId("ai-read-consent"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("ai-read-run"));
    });
    expect(apiFetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = apiFetchMock.mock.calls[0];
    expect(url).toBe(API.imports.aiRead);
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      kind: "fills", screens: [maskScreen(words).text], consent: true,
    });

    expect(screen.getByTestId("ai-read-applied")).toBeTruthy();
    expect(screen.getAllByTestId("ocr-review-row")).toHaveLength(1);
    fireEvent.click(screen.getByTestId("ai-read-revert"));
    expect(screen.queryAllByTestId("ocr-review-row")).toHaveLength(ruleRowCount);
  });
});

describe("AI read — pasted text", () => {
  const PASTED = "[키움] 계좌 1234-5678-90 홍길동님\n삼성전자 매수 10주 71,200원 체결\n2026-09-01 10:15";

  it("drops the account / customer line before anything is sent", () => {
    expect(maskPastedText(PASTED)).toBe("삼성전자 매수 10주 71,200원 체결\n2026-09-01 10:15");
  });

  it("saves the reviewed rows through /image with origin text", async () => {
    vi.stubEnv("NEXT_PUBLIC_AI_READ", "1");
    const onResult = vi.fn();
    render(<AiTextReadPanel text={PASTED} consent onResult={onResult} />);
    apiFetchMock.mockResolvedValueOnce({ screens: [{ screen_type: "fills", reason: "", rows: [AI_ROW] }] });
    fireEvent.click(screen.getByTestId("ai-read-consent"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("ai-read-run"));
    });
    apiFetchMock.mockResolvedValueOnce({ batch: { id: 1 }, pending: [] });
    await act(async () => {
      fireEvent.click(screen.getByTestId("ai-text-send"));
    });
    const [url, init] = apiFetchMock.mock.calls[1];
    expect(url).toBe(API.imports.image);
    const body = JSON.parse(String((init as RequestInit).body));
    expect(body.origin).toBe("text");
    expect(body.rows[0]).toMatchObject({ action: "buy", shares: 10, price: 71200, source_text: AI_SOURCE_TAG });
    expect(onResult).toHaveBeenCalled();
  });
});

describe("lib/ai-read row mapping", () => {
  it("keeps hints as hints and maps buy/sell", () => {
    const f = fillFromAi({ ...AI_ROW, action: { value: "sell" }, shares: { value: null, hint: "1093" } });
    expect(f.side.value).toBe("SELL");
    expect(f.shares).toEqual({ value: null, hint: "1093" });
    const h = holdingFromAi({
      name: { value: null, hint: "LG전자" }, code: { value: null }, shares: { value: 9 },
      avg_cost: { value: 103200 }, currency: "KRW", truncated: false, flags: ["ai_read", "cross_checked"],
    });
    expect(h.name).toEqual({ value: null, hint: "LG전자" });
    expect(h.avgCost.value).toBe(103200);
    expect(h.flags).toContain("ai_read");
  });
});
