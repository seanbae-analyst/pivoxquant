/**
 * /methodology — PUBLIC methodology & data-transparency page.
 *
 * Moved out of (dashboard) 2026-06-05 per CEO: a trust surface belongs on the
 * public landing, not behind login. This is a STATIC, public-safe rendition —
 * it deliberately does NOT dump the per-model `academic_source` lineage (that
 * detailed disclosure stays login-gated behind METHODOLOGY_PUBLIC / Q-DT4 lawyer
 * review). What's shown here is all already-public: the data sources, the model
 * count, the 7-layer risk structure, and the reproducibility philosophy.
 *
 * Legal posture: observation-only. POSITIVE / NEGATIVE / NEUTRAL only; no
 * 추천 / 조언 / 매수 / 매도. Static server component — no gated API call, so it
 * renders for anonymous visitors.
 *
 * Design: Vantablack + Bronze + Playfair, design tokens only (no raw hex / no
 * raw fontSize — typography-token-coverage gate).
 */

import Link from "next/link";
import type { CSSProperties } from "react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology — PivoxQuant",
  description:
    "모든 수치는 공개·라이선스 데이터(FMP · SEC EDGAR · FRED)와 공개된 학술 공식으로 재현 가능합니다. 40개 퀀트 모델 + 7-Layer Risk Defense의 산출 방식.",
  alternates: { canonical: "/methodology" },
};

const WRAP: CSSProperties = {
  minHeight: "100vh",
  background: "var(--pq-ink, #050505)",
  color: "var(--pq-ivory, #F5F0E8)",
};
const INNER = "mx-auto w-full max-w-3xl px-5 py-16 sm:px-6 sm:py-24";
const EYEBROW: CSSProperties = {
  fontFamily: "var(--font-mono), monospace",
  fontSize: "var(--pq-text-eyebrow)",
  textTransform: "uppercase",
  letterSpacing: "0.22em",
  color: "var(--pq-bronze, #B8956A)",
};
const CARD: CSSProperties = {
  border: "0.5px solid var(--pq-ivory-line, rgba(245,240,232,0.14))",
  background: "var(--pq-card-veil, rgba(255,255,255,0.02))",
  borderRadius: 3,
  padding: "18px 20px",
};
const H2: CSSProperties = {
  fontFamily: "var(--font-display), Georgia, serif",
  fontWeight: 500,
  fontSize: "var(--pq-text-h3)",
  lineHeight: 1.15,
  letterSpacing: "-0.01em",
};
const BODY: CSSProperties = {
  fontFamily: "var(--font-serif), Georgia, serif",
  fontSize: "var(--pq-text-body)",
  lineHeight: 1.65,
  color: "rgba(245,240,232,0.74)",
};
const BODY_SM: CSSProperties = {
  ...BODY,
  fontSize: "var(--pq-text-body-sm)",
  color: "rgba(245,240,232,0.62)",
};

const DATA_SOURCES: { name: string; role: string }[] = [
  { name: "FMP (Financial Modeling Prep)", role: "시세 · 재무제표 · 과거 가격 (라이선스)" },
  { name: "SEC EDGAR", role: "미국 공시 원문 (공개)" },
  { name: "FRED", role: "거시 지표 · 금리 · 환율 (공개, 美 연준)" },
];

export default function PublicMethodologyPage() {
  return (
    <main style={WRAP}>
      <div className={INNER}>
        {/* Top bar */}
        <div className="mb-12 flex items-center justify-between">
          <Link href="/" style={{ ...EYEBROW, textDecoration: "none" }} aria-label="PivoxQuant home">
            PIVOXQUANT
          </Link>
          <Link
            href="/"
            style={{
              fontFamily: "var(--font-mono), monospace",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.14em",
              color: "rgba(245,240,232,0.55)",
              textDecoration: "none",
            }}
          >
            ← Home
          </Link>
        </div>

        {/* Header */}
        <header className="space-y-4">
          <div style={EYEBROW}>방법론 · 투명성 · METHODOLOGY</div>
          <h1 style={{ ...H2, fontSize: "var(--pq-text-h1)" }}>모든 수치의 출처와 산출 방법</h1>
          <p style={{ ...BODY, maxWidth: 620 }}>
            PivoxQuant이 보여주는 모든 숫자는{" "}
            <strong style={{ color: "var(--pq-ivory)" }}>
              공개·라이선스 데이터와 공개된 학술 공식
            </strong>
            으로 재현할 수 있습니다. 가중치 등 일부 파라미터를 제외하면 방법론은 블랙박스가
            아닙니다.
          </p>
          <p style={{ ...BODY_SM, maxWidth: 620 }}>
            Every figure can be re-derived from public, licensed data (FMP, SEC EDGAR, FRED) and
            published formulas. The methodology is not a black box.
          </p>
        </header>

        {/* Stat strip */}
        <div className="mt-14 flex flex-wrap gap-x-12 gap-y-6">
          <Stat value="40" suffix="모델" label="QUANT MODELS · 39 ACTIVE" />
          <Stat value="7" suffix="레이어" label="RISK DEFENSE LAYERS" />
          <Stat value="3" suffix="출처" label="PUBLIC DATA SOURCES" />
        </div>

        {/* Data sources */}
        <section className="mt-16 space-y-5">
          <div style={EYEBROW}>데이터 출처 · DATA SOURCES</div>
          <p style={{ ...BODY, maxWidth: 620 }}>
            모든 분석은 아래 공개·라이선스 데이터 위에서만 계산됩니다. 연결된 브로커가 없으면
            어떤 브로커도 출처로 표기하지 않습니다.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {DATA_SOURCES.map((src) => (
              <div key={src.name} style={CARD}>
                <div
                  style={{
                    fontFamily: "var(--font-display), Georgia, serif",
                    fontSize: "var(--pq-text-callout)",
                    fontWeight: 500,
                    color: "var(--pq-bronze, #B8956A)",
                  }}
                >
                  {src.name}
                </div>
                <p style={{ ...BODY_SM, marginTop: 6 }}>{src.role}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Engine overview */}
        <section className="mt-16 space-y-5">
          <div style={EYEBROW}>엔진 · ENGINE</div>
          <h2 style={H2}>40개 퀀트 모델 · 7-Layer Risk Defense</h2>
          <p style={{ ...BODY, maxWidth: 620 }}>
            엔진은 가치·품질·모멘텀·변동성 등 학술적으로 검증된 팩터 군을 4-pillar 구조로 조합한{" "}
            <strong style={{ color: "var(--pq-ivory)" }}>40개 모델</strong>(39개 활성)을 제공합니다.
            각 모델은 공개된 학술 공식에 근거하며, 산출된 신호는{" "}
            <strong style={{ color: "var(--pq-ivory)" }}>POSITIVE / NEGATIVE / NEUTRAL</strong>의
            관찰 라벨로만 표시됩니다 — 매수·매도 권유가 아닙니다.
          </p>
          <p style={{ ...BODY, maxWidth: 620 }}>
            7-Layer Risk Defense는 집중도·변동성·상관·하방위험 등을 단계적으로 점검하는 리스크
            관측 레이어입니다. 머신이 데이터를 읽고, 최종 판단은 이용자 본인이 합니다.
          </p>
        </section>

        {/* Disclaimer */}
        <section className="mt-16" style={{ ...CARD, borderColor: "rgba(184,149,106,0.28)" }}>
          <p style={BODY_SM}>
            본 서비스는 정보 제공 도구이며 투자자문업·유사투자자문업에 해당하지 않습니다. 제공되는
            모든 정보는 특정 종목의 매수·매도·보유를 권유하거나 추천하지 않으며, 투자 판단과 그
            결과의 책임은 전적으로 이용자 본인에게 있습니다. 과거 성과는 미래 수익을 보장하지
            않습니다.
          </p>
        </section>
      </div>
    </main>
  );
}

function Stat({ value, suffix, label }: { value: string; suffix?: string; label: string }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span
          style={{
            fontFamily: "var(--font-mono), monospace",
            fontSize: "var(--pq-text-hero-num)",
            fontWeight: 500,
            color: "var(--pq-ivory, #F5F0E8)",
            letterSpacing: "-0.02em",
          }}
        >
          {value}
        </span>
        {suffix && (
          <span
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              fontSize: "var(--pq-text-body-sm)",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            {suffix}
          </span>
        )}
      </div>
      <div
        style={{
          fontFamily: "var(--font-mono), monospace",
          fontSize: "var(--pq-text-eyebrow-sm)",
          textTransform: "uppercase",
          letterSpacing: "0.18em",
          color: "rgba(245,240,232,0.45)",
          marginTop: 6,
        }}
      >
        {label}
      </div>
    </div>
  );
}
