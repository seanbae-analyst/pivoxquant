"use client";

/**
 * DisclaimerBand — legal-compliance band for the Journal Companion.
 *
 * Variants:
 *   - "session-start" — large, fullscreen-scale banner shown on first
 *      entry; ack'd once and remembered via localStorage.
 *   - "inline"        — small bronze-italic strip under each agent
 *      message. Must be visible without scroll on mobile.
 *   - "legal-modal"   — long-form text (Korean + English) for a
 *      settings/legal drawer. No auto-dismiss.
 *
 * Palette: Vantablack #050505 / Bronze #B8956A / Ivory #F5F0E8.
 * Tone: "Not investment advice. Your record, your decision."
 */

import { useMemo } from "react";
import { ShieldCheck } from "lucide-react";

type Variant = "session-start" | "inline" | "legal-modal";

interface DisclaimerBandProps {
  variant: Variant;
  onAcknowledge?: () => void;
  className?: string;
}

/** Content — single source of truth for all three variants. */
const CONTENT = {
  inline: {
    en: "Not investment advice. Your record, your decision.",
    ko: "투자 자문이 아닙니다. 당신의 기록, 당신의 결정입니다.",
  },
  session: {
    titleEn: "A companion, not an advisor.",
    titleKo: "조언자가 아닌 동반자.",
    bodyEn:
      "This companion reflects your own journal — what you wrote, what patterns recur. It will not recommend trades, predict prices, or guarantee outcomes. Three principles: Remember · Mirror · Question.",
    bodyKo:
      "이 동반자는 당신이 쓴 기록을 비추는 거울입니다. 매수/매도 권유도, 가격 예측도, 수익 보장도 하지 않습니다. 세 가지 원칙: 기억 · 반영 · 질문.",
    cta: "I understand · 확인",
  },
  legal: {
    en: "The Personal Journal Companion is an experimental reflective tool operating under Closed Beta. It does not constitute investment advice under the Financial Investment Services and Capital Markets Act (자본시장법) of the Republic of Korea, and is not a substitute for licensed financial guidance. The service declines to produce buy/sell recommendations, price predictions, or performance guarantees. All investment decisions are your own. Logs may be reviewed for safety and compliance; personally identifying information is minimized and handled per our Privacy Policy.",
    ko: "Personal Journal Companion은 Closed Beta 단계의 실험적 회고 도구입니다. 자본시장법상 투자자문에 해당하지 않으며, 공인 투자자문의 대체가 아닙니다. 특정 종목의 매수·매도 권유, 가격 예측, 수익 보장은 제공하지 않습니다. 모든 투자 판단의 책임은 이용자 본인에게 있습니다. 안전 및 컴플라이언스를 위해 로그가 검토될 수 있으며, 개인정보는 최소 수집 원칙에 따라 처리되고 개인정보처리방침의 적용을 받습니다.",
  },
} as const;

export function DisclaimerBand({ variant, onAcknowledge, className }: DisclaimerBandProps) {
  const wrapperStyle = useMemo<React.CSSProperties>(() => {
    if (variant === "session-start") {
      return {
        background: "rgba(247, 245, 239, 0.04)",
        border: "0.5px solid rgba(184, 149, 106, 0.35)",
        color: "var(--pq-ivory)",
      };
    }
    if (variant === "legal-modal") {
      return {
        background: "rgba(10, 10, 10, 0.9)",
        border: "0.5px solid rgba(245, 240, 232, 0.12)",
        color: "var(--pq-ivory)",
      };
    }
    // inline
    return {
      borderTop: "0.5px solid rgba(184, 149, 106, 0.24)",
      color: "rgba(184, 149, 106, 0.85)",
    };
  }, [variant]);

  if (variant === "inline") {
    return (
      <div
        className={["mt-2.5 pt-2", className ?? ""].join(" ")}
        style={wrapperStyle}
        role="note"
      >
        <p
          className="font-serif italic"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.01em",
            lineHeight: 1.5,
            margin: 0,
          }}
        >
          {CONTENT.inline.en}
          <span className="mx-1.5" aria-hidden style={{ color: "rgba(184,149,106,0.4)" }}>·</span>
          {CONTENT.inline.ko}
        </p>
      </div>
    );
  }

  if (variant === "legal-modal") {
    return (
      <div
        className={["rounded-sm p-5 md:p-6", className ?? ""].join(" ")}
        style={wrapperStyle}
        role="region"
        aria-label="Journal Companion legal disclosure"
      >
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck
            className="h-3.5 w-3.5"
            strokeWidth={1.5}
            style={{ color: "var(--pq-bronze)" }}
            aria-hidden
          />
          <span
            className="font-serif uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
            }}
          >
            Legal · 법적 고지
          </span>
        </div>
        <p
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.65,
            color: "rgba(245,240,232,0.78)",
          }}
        >
          {CONTENT.legal.ko}
        </p>
        <p
          className="mt-3 font-serif italic"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.55)",
          }}
        >
          {CONTENT.legal.en}
        </p>
      </div>
    );
  }

  // session-start
  return (
    <div
      className={["rounded-sm p-6 md:p-8", className ?? ""].join(" ")}
      style={wrapperStyle}
      role="dialog"
      aria-label="Journal Companion session disclosure"
      aria-modal="false"
    >
      <div className="mb-4 flex items-center gap-2">
        <span
          aria-hidden
          className="h-px w-7"
          style={{ background: "rgba(184,149,106,0.7)" }}
        />
        <span
          className="font-serif uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: "var(--pq-bronze)",
          }}
        >
          Closed Beta · Reflective Only
        </span>
      </div>
      <h2
        className="font-serif"
        style={{
          fontSize: "clamp(20px, 2.6vw, 26px)",
          lineHeight: 1.15,
          letterSpacing: "-0.01em",
          fontWeight: 500,
          color: "var(--pq-ivory)",
          margin: 0,
        }}
      >
        {CONTENT.session.titleEn}
      </h2>
      <p
        className="mt-2 font-serif italic"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.5,
          color: "rgba(184,149,106,0.85)",
        }}
      >
        {CONTENT.session.titleKo}
      </p>
      <p
        className="mt-5 font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.7,
          color: "rgba(245,240,232,0.75)",
        }}
      >
        {CONTENT.session.bodyEn}
      </p>
      <p
        className="mt-2 font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.7,
          color: "rgba(245,240,232,0.55)",
        }}
      >
        {CONTENT.session.bodyKo}
      </p>
      {onAcknowledge && (
        <button
          type="button"
          onClick={onAcknowledge}
          className="mt-6 inline-flex items-center gap-2 rounded-sm px-5 py-2.5 font-serif uppercase transition-colors"
          style={{
            background: "var(--pq-bronze)",
            color: "var(--pq-ink)",
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
          }}
        >
          {CONTENT.session.cta}
        </button>
      )}
    </div>
  );
}

export default DisclaimerBand;
