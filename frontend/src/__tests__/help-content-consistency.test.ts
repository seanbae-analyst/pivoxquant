/**
 * Help content — /docs, /support (FAQ + inquiry form) and /contact must state
 * the same facts (2026-09-29).
 *
 *   - /docs reads the broker/import answer and the account-deletion answer
 *     from messages/en.json instead of keeping its own copy, so the pages
 *     cannot drift apart again.
 *   - No fill-approval claim covers "every path": hand entry and the holdings
 *     capture record directly; only uploaded / imported fills wait for approval.
 *   - Billing is gated off in the free beta — no 결제·환불 FAQ group and no
 *     billing option in the inquiry form.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import ko from "@/messages/ko.json";
import en from "@/messages/en.json";
import { SUPPORT_CATEGORY_OPTIONS } from "@/components/support/support-meta";

type SupportMessages = {
  categories: Record<string, string>;
  faq: Record<string, { q: string; a: string }>;
};
const supportKo = (ko as unknown as { support: SupportMessages }).support;
const supportEn = (en as unknown as { support: SupportMessages }).support;

const read = (...p: string[]) => readFileSync(join(__dirname, "..", ...p), "utf8");

describe("help content consistency", () => {
  it("support FAQ keys match across locales", () => {
    expect(Object.keys(supportKo.faq).sort()).toEqual(Object.keys(supportEn.faq).sort());
    expect(Object.keys(supportKo.categories).sort()).toEqual(
      Object.keys(supportEn.categories).sort(),
    );
  });

  it("offers no billing / refund help while payment is gated off", () => {
    expect(supportKo.categories.billing).toBeUndefined();
    expect(supportKo.faq.refund).toBeUndefined();
    expect(SUPPORT_CATEGORY_OPTIONS.map((o) => o.value)).not.toContain("billing");
    const faqSrc = read("components", "support", "faq-section.tsx");
    expect(faqSrc).not.toMatch(/support\.(categories\.billing|faq\.refund)/);
  });

  it("/docs reads shared facts from the message catalog", () => {
    const docs = read("app", "docs", "page.tsx");
    expect(docs).toContain("en.landing.faq.a5");
    expect(docs).toContain("en.support.faq.deleteAccount.a");
    // The old over-broad claim: false for hand entry and the holdings capture.
    expect(docs).not.toMatch(/On every path a fill is not recorded/);
    // Trades live on /portfolio, not in the journal timeline.
    expect(docs).not.toMatch(/alongside the trades you recorded/);
  });

  it("fill automation and holdings answers are shared, and state the iPhone split (2026-10-11)", () => {
    const docs = read("app", "docs", "page.tsx");
    expect(docs).toContain("en.support.faq.autoFill.a");
    expect(docs).toContain("en.support.faq.editHoldings.a");
    const faqSrc = read("components", "support", "faq-section.tsx");
    expect(faqSrc).toContain("support.faq.autoFill.a");
    expect(faqSrc).toContain("support.faq.editHoldings.a");
    // iPhone: SMS on any iOS, an app's push only from iOS 27 — never the old
    // "iPhone can only forward SMS" claim.
    for (const a of [supportKo.faq.autoFill.a, ko.landing.faq.a7]) {
      expect(a).toContain("iOS 27");
      expect(a).toContain("문자");
    }
    for (const a of [supportEn.faq.autoFill.a, en.landing.faq.a7]) {
      expect(a).toContain("iOS 27");
      expect(a).not.toMatch(/only with brokers that still send fills by text message/);
    }
    // Approval wording stays scoped to imported fills — not "every path".
    expect(supportEn.faq.autoFill.a).not.toMatch(/every path/i);
  });

  it("deletion answer states the 30-day grace window in both locales", () => {
    expect(supportKo.faq.deleteAccount.a).toContain("30일");
    expect(supportEn.faq.deleteAccount.a).toContain("30-day");
  });
});
