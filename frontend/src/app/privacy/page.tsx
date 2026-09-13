/**
 * /privacy — PIPA-compliant Korean privacy policy.
 * Reads frontend/src/content/privacy-ko.md (single source of truth)
 * and renders it through `renderLegalMarkdown` (lib/legal-markdown.ts — shared
 * with /terms; see that file for why bold is paired before `marked`).
 *
 * 한국 이용자에게 한국어로 공시 (PIPA §30 의무).
 */

import Link from "next/link";
import { promises as fs } from "node:fs";
import path from "node:path";
import type { Metadata } from "next";
import { renderLegalMarkdown } from "@/lib/legal-markdown";

export const metadata: Metadata = {
  title: "개인정보처리방침",
  alternates: { canonical: "/privacy" },
};

export default async function PrivacyPage() {
  const filePath = path.join(process.cwd(), "src/content/privacy-ko.md");
  const raw = await fs.readFile(filePath, "utf8");
  const html = renderLegalMarkdown(raw);

  return (
    <div className="min-h-[100dvh] bg-[var(--pq-ink)] text-[var(--pq-ivory)]">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:py-20">
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 text-sm text-[var(--pq-ivory-dim)] hover:text-[var(--pq-bronze)] transition-colors mb-8"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back
        </Link>
        <article
          className="max-w-none text-pq-lead leading-7 text-[var(--pq-ivory-strong)] [&_h1]:font-[var(--font-display)] [&_h1]:text-pq-avatar [&_h1]:font-medium [&_h1]:text-[var(--pq-ivory)] [&_h1]:mt-0 [&_h1]:mb-8 [&_h2]:font-[var(--font-serif)] [&_h2]:text-pq-h5 [&_h2]:font-medium [&_h2]:text-[var(--pq-ivory)] [&_h2]:mt-10 [&_h2]:mb-3 [&_h3]:text-pq-lead [&_h3]:font-semibold [&_h3]:text-[var(--pq-ivory)] [&_h3]:mt-6 [&_h3]:mb-2 [&_p]:my-3 [&_ul]:my-3 [&_ol]:my-3 [&_li]:my-1 [&_strong]:text-[var(--pq-ivory)] [&_strong]:font-semibold [&_table]:w-full [&_table]:border-collapse [&_table]:my-4 [&_th]:border [&_th]:border-[rgba(245,240,232,0.12)] [&_th]:px-3 [&_th]:py-2 [&_th]:bg-[rgba(255,255,255,0.03)] [&_th]:text-left [&_th]:text-[var(--pq-bronze)] [&_th]:text-xs [&_th]:uppercase [&_th]:tracking-wider [&_td]:border [&_td]:border-[var(--pq-ivory-line)] [&_td]:px-3 [&_td]:py-2 [&_blockquote]:border-l-2 [&_blockquote]:border-[var(--pq-bronze)] [&_blockquote]:pl-4 [&_blockquote]:text-[var(--pq-ivory-muted)] [&_hr]:my-8 [&_hr]:border-[rgba(245,240,232,0.1)] [&_a]:text-[var(--pq-bronze)] [&_a]:underline [&_a]:underline-offset-2 [&_a:hover]:text-[var(--pq-bronze-light)] [&_code]:text-[var(--pq-bronze)] [&_code]:bg-[rgba(184,149,106,0.08)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-pq-body-sm"
          dangerouslySetInnerHTML={{ __html: html as string }}
        />
      </div>
    </div>
  );
}
