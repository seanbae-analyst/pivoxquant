/**
 * /pivox — the Pivox family page: the one link in the Instagram bio.
 *
 * PIVOX on Vantablack (the landing cover's wordmark), then the three products,
 * each as its own cover wordmark — "PIVOX" Ivory + product name Bronze, the
 * rule all three landings share (2026-10-25). The other two products live on
 * their own subdomains and are plain links out; nothing here signs anyone in.
 */

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Pivox",
  description: "나의 거래 · 회사의 데이터 · 산업의 변화 — 흘려보내지 않고 숫자로 봅니다.",
  alternates: { canonical: "/pivox" },
};

interface Product {
  name: string;
  tag: string;
  line: string;
  href: string;
  host: string;
  note?: string;
}

const PRODUCTS: Product[] = [
  {
    name: "Quant",
    tag: "나의 거래",
    line: "사기 전에 멈추고, 적고, 돌아봅니다.",
    href: "/",
    host: "pivoxquant.com",
    note: "관측 자료이며 투자 권유가 아닙니다.",
  },
  {
    name: "Map",
    tag: "회사의 데이터",
    line: "파일의 컬럼마다 표준용어를 붙입니다.",
    href: "https://map.pivoxquant.com",
    host: "map.pivoxquant.com",
  },
  {
    name: "Data",
    tag: "산업의 변화",
    line: "기업의 AI 전환을 매일 숫자로 봅니다.",
    href: "https://data.pivoxquant.com",
    host: "data.pivoxquant.com",
  },
];

const WORDMARK = {
  letterSpacing: "0.22em",
  marginRight: "-0.22em",
  lineHeight: 1,
  fontWeight: 500,
  textTransform: "uppercase",
} as const;

function ProductCard({ p }: { p: Product }) {
  const body = (
    <>
      <span className="text-pq-caption font-semibold text-[var(--pq-bronze)]">{p.tag}</span>
      <span
        className="pq-splash-wordmark mt-3 block text-[var(--pq-ivory)]"
        style={{ ...WORDMARK, fontSize: "var(--pq-text-h4)", animation: "none" }}
      >
        Pivox<span style={{ color: "var(--pq-bronze)" }}>{p.name}</span>
      </span>
      <span className="mt-3 block text-pq-body text-[var(--pq-ivory-dim)]">{p.line}</span>
      <span className="mt-4 flex items-center justify-between text-pq-caption text-[var(--pq-ivory-faint)]">
        <span>{p.host}</span>
        <span aria-hidden className="text-[var(--pq-bronze)]">→</span>
      </span>
    </>
  );
  const className =
    "block rounded-[var(--pq-radius-card)] border border-[var(--pq-ivory-line)] px-6 py-5 transition-colors hover:border-[var(--pq-bronze)]";
  return p.href.startsWith("/") ? (
    <Link href={p.href} className={className} data-testid={`pivox-${p.name.toLowerCase()}`}>
      {body}
    </Link>
  ) : (
    <a href={p.href} className={className} data-testid={`pivox-${p.name.toLowerCase()}`}>
      {body}
    </a>
  );
}

export default function PivoxPage() {
  return (
    <main
      className="relative flex min-h-[100dvh] flex-col items-center bg-[var(--pq-ink)] px-4 pb-12 text-[var(--pq-ivory)]"
      style={{ paddingTop: "calc(env(safe-area-inset-top, 0px) + 72px)" }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 18%, rgba(245,240,232,0.03) 0%, rgba(245,240,232,0.012) 40%, transparent 75%)",
        }}
      />
      <h1
        className="pq-splash-wordmark relative text-center"
        style={{ ...WORDMARK, fontSize: "min(var(--pq-text-display), 14vw)" }}
      >
        Pivox
      </h1>
      <p className="relative mt-6 text-center text-pq-body text-[var(--pq-ivory-dim)]">
        나의 거래 · 회사의 데이터 · 산업의 변화
        <br />
        흘려보내지 않고 숫자로 봅니다.
      </p>

      <nav aria-label="Pivox 제품" className="relative mt-12 flex w-full max-w-md flex-col gap-3">
        {PRODUCTS.map((p) => (
          <ProductCard key={p.name} p={p} />
        ))}
      </nav>

      <p className="relative mt-8 max-w-md text-center text-pq-caption text-[var(--pq-ivory-faint)]">
        {PRODUCTS[0].note}
      </p>
    </main>
  );
}
