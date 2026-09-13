/**
 * FaqSection — Frequently Asked Questions (native <details> accordion).
 *
 * 4 categories / 9 items. Locale-aware: ko (Korean) | en (English).
 *
 * 2026-09-13: the "what do signal labels (POSITIVE/NEGATIVE/NEUTRAL) mean"
 * item was removed — there is no signal surface left to explain. Every item
 * here must describe something a user can actually reach.
 *
 * Compliance posture (자본시장법 §101 면제 트랙):
 *   - Not investment advice language preserved in both locales.
 *   - No solicitation language used.
 *
 * v3 tone: hairline-ruled rows, Playfair UPRIGHT question, serif body.
 * Rendered client-side to access locale hook.
 */

"use client";

import * as React from "react";
import { useT, useLocale } from "@/lib/locale";

interface FaqItem {
  q: string;
  a: string;
}

interface FaqGroup {
  category: string;
  items: FaqItem[];
}

function FaqRow({ item }: { item: FaqItem }) {
  return (
    <details
      className="group pq-faq-item"
      style={{ borderTop: "0.5px solid var(--pq-ivory-line)" }}
    >
      <summary
        className="flex cursor-pointer list-none items-start justify-between gap-4 py-4"
        style={{ outline: "none" }}
      >
        <span
          className="font-display text-pq-h6"
          style={{
            color: "var(--pq-ivory)",
            lineHeight: 1.4,
            letterSpacing: "-0.01em",
            wordBreak: "keep-all",
          }}
        >
          {item.q}
        </span>
        <span
          aria-hidden="true"
          className="mt-1 shrink-0 text-lg leading-none transition-transform duration-200 group-open:rotate-45"
          style={{ color: "var(--pq-bronze)" }}
        >
          +
        </span>
      </summary>
      <p
        className="pb-4 font-serif text-pq-lead"
        style={{
          lineHeight: 1.7,
          color: "var(--pq-ivory-soft)",
          wordBreak: "keep-all",
        }}
      >
        {item.a}
      </p>
    </details>
  );
}

export function FaqSection() {
  const t = useT();
  const { locale } = useLocale();

  const FAQ_GROUPS: FaqGroup[] =
    locale === "ko"
      ? [
          {
            category: t("support.categories.service"),
            items: [
              { q: t("support.faq.whatIsService.q"), a: t("support.faq.whatIsService.a") },
              { q: t("support.faq.dataSource.q"), a: t("support.faq.dataSource.a") },
            ],
          },
          {
            category: t("support.categories.billing"),
            items: [
              { q: t("support.faq.pricing.q"), a: t("support.faq.pricing.a") },
              { q: t("support.faq.refund.q"), a: t("support.faq.refund.a") },
            ],
          },
          {
            category: t("support.categories.account"),
            items: [
              { q: t("support.faq.howToLogin.q"), a: t("support.faq.howToLogin.a") },
              { q: t("support.faq.deleteAccount.q"), a: t("support.faq.deleteAccount.a") },
            ],
          },
          {
            category: t("support.categories.tech"),
            items: [
              { q: t("support.faq.pwa.q"), a: t("support.faq.pwa.a") },
              { q: t("support.faq.staleData.q"), a: t("support.faq.staleData.a") },
              { q: t("support.faq.contact.q"), a: t("support.faq.contact.a") },
            ],
          },
        ]
      : [
          {
            category: t("support.categories.service"),
            items: [
              { q: t("support.faq.whatIsService.q"), a: t("support.faq.whatIsService.a") },
              { q: t("support.faq.dataSource.q"), a: t("support.faq.dataSource.a") },
            ],
          },
          {
            category: t("support.categories.billing"),
            items: [
              { q: t("support.faq.pricing.q"), a: t("support.faq.pricing.a") },
              { q: t("support.faq.refund.q"), a: t("support.faq.refund.a") },
            ],
          },
          {
            category: t("support.categories.account"),
            items: [
              { q: t("support.faq.howToLogin.q"), a: t("support.faq.howToLogin.a") },
              { q: t("support.faq.deleteAccount.q"), a: t("support.faq.deleteAccount.a") },
            ],
          },
          {
            category: t("support.categories.tech"),
            items: [
              { q: t("support.faq.pwa.q"), a: t("support.faq.pwa.a") },
              { q: t("support.faq.staleData.q"), a: t("support.faq.staleData.a") },
              { q: t("support.faq.contact.q"), a: t("support.faq.contact.a") },
            ],
          },
        ];

  return (
    <section aria-labelledby="faq-heading">
      <h2
        id="faq-heading"
        className="font-sans text-pq-eyebrow uppercase"
        style={{
          letterSpacing: "0.2em",
          color: "var(--pq-bronze)",
          fontWeight: 500,
        }}
      >
        {t("support.faqHeading")}
      </h2>

      <div className="mt-4 space-y-8">
        {FAQ_GROUPS.map((group) => (
          <div key={group.category}>
            <h3
              className="font-display text-pq-h5"
              style={{
                color: "var(--pq-ivory)",
                letterSpacing: "-0.015em",
                marginBottom: 4,
              }}
            >
              {group.category}
            </h3>
            <div
              style={{ borderBottom: "0.5px solid var(--pq-ivory-line)" }}
            >
              {group.items.map((item) => (
                <FaqRow key={item.q} item={item} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
