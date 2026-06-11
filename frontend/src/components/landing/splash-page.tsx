"use client";

/**
 * SplashPage — Page 0 of the PivoxQuant flip landing.
 *
 * CEO brief (2026-04-23):
 *   "첫 페이지에 다 검은 여백에 우리 사이트 왼쪽위에 있는 것
 *    그 문구만 넣고"
 *
 * Implementation:
 *   - Full-bleed Vantablack (#050505) canvas.
 *   - Single PIVOXQUANT wordmark, centered, in the editorial
 *     silver-matte treatment used throughout the site.
 *   - Subtle radial spotlight (ivory @ 3%) and a gentle breath
 *     pulse (4s ease-in-out) — both disabled under
 *     `prefers-reduced-motion`.
 *   - Serif/italic scroll hint at the bottom, bronze @ 40%.
 *
 * Input handlers (wheel / Space / ArrowDown / ArrowUp) are owned
 * by <FlipLandingShell/>. This component is purely presentational.
 *
 * Palette guardrail: ONLY Vantablack / Bronze / Ivory tokens.
 */

import { ChevronDown } from "lucide-react";
import { useT } from "@/lib/locale";

export default function SplashPage() {
  const t = useT();
  return (
    <div
      className="pq-splash"
      role="region"
      aria-label={t("landing.splash.ariaLabel")}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: "100dvh",
        backgroundColor: "var(--pq-ink, #050505)",
        color: "var(--pq-ivory, #F5F0E8)",
        overflow: "hidden",
      }}
    >
      {/* Centered spotlight — ivory @ 3%, 80% radius */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background:
            "radial-gradient(ellipse 80% 80% at 50% 50%, rgba(245,240,232,0.03) 0%, rgba(245,240,232,0.012) 40%, transparent 75%)",
        }}
      />

      {/* Wordmark — reuses .pq-silver-matte and adds a breath pulse
         via the scoped .pq-splash-wordmark class (globals.css). */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 24px",
        }}
      >
        <span
          className="pq-splash-wordmark font-serif"
          style={{
            // Matches the landing header wordmark (top-left) — same font
            // family, weight, tracking, casing. Only the size is scaled up
            // since this is the full-viewport cover treatment.
            // v3 token: --pq-text-display = clamp(3rem, 7vw, 6rem).
            fontSize: "var(--pq-text-display)",
            letterSpacing: "0.22em",
            lineHeight: 1,
            fontWeight: 500,
            textTransform: "uppercase",
            textAlign: "center",
            color: "var(--pq-ivory)",
          }}
        >
          PIVOXQUANT
        </span>
      </div>

      {/* Scroll hint — bronze @ 40%, editorial italic, chevron */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: "clamp(28px, 5vh, 56px)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "8px",
          pointerEvents: "none",
        }}
      >
        <ChevronDown
          className="pq-splash-chevron"
          strokeWidth={1.2}
          style={{
            width: "18px",
            height: "18px",
            color: "rgba(var(--pq-bronze-wash-rgb), 0.55)",
          }}
          aria-hidden="true"
        />
        <span
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.24em",
            textTransform: "uppercase",
            color: "rgba(var(--pq-bronze-wash-rgb), 0.40)",
            fontStyle: "italic",
          }}
        >
          {t("landing.splash.scrollHint")}
        </span>
      </div>
    </div>
  );
}
