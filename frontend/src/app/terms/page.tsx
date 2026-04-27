/**
 * /terms — Korean terms of service (전자상거래법 + 약관규제법 준수).
 * Reads frontend/src/content/terms-ko.md (single source of truth)
 * and renders via `marked`. Strips YAML frontmatter before parsing.
 */

import Link from "next/link";
import { promises as fs } from "node:fs";
import path from "node:path";
import { marked } from "marked";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "이용약관 - PivoxQuant",
};

function stripFrontmatter(md: string): string {
  if (!md.startsWith("---")) return md;
  const end = md.indexOf("\n---", 3);
  return end === -1 ? md : md.slice(end + 4).trimStart();
}

export default async function TermsPage() {
  const filePath = path.join(process.cwd(), "src/content/terms-ko.md");
  const raw = await fs.readFile(filePath, "utf8");
  const html = await marked.parse(stripFrontmatter(raw));

  return (
    <div className="min-h-[100dvh] bg-white">
      <div className="mx-auto max-w-3xl px-4 py-12 sm:py-20">
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors mb-8"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back
        </Link>
        <article
          className="prose prose-slate prose-sm max-w-none [&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:mt-0 [&_h1]:mb-6 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:mt-8 [&_h2]:mb-3 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-6 [&_h3]:mb-2 [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_th]:border-slate-300 [&_th]:px-3 [&_th]:py-2 [&_th]:bg-slate-50 [&_th]:text-left [&_td]:border [&_td]:border-slate-300 [&_td]:px-3 [&_td]:py-2 [&_blockquote]:border-l-4 [&_blockquote]:border-slate-300 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-slate-600 [&_hr]:my-8 [&_a]:text-blue-600 [&_a]:underline [&_p]:my-3 [&_ul]:my-3 [&_ol]:my-3 [&_li]:my-1"
          dangerouslySetInnerHTML={{ __html: html as string }}
        />
      </div>
    </div>
  );
}
