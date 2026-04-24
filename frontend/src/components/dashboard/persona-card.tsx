"use client";

/**
 * <PersonaCard /> — Layer 1 identity surface.
 *
 * Paper-styled card pitched between the top strip and the This Morning
 * dossier paper. Renders:
 *
 *   Declared persona   (from InvestmentProfile onboarding)
 *   One-line identity  (tagline from PERSONA_TAGLINES)
 *   Sparkline          (12-week rolling persona-score trend)
 *   Drift indicator    (30d vs 90d persona divergence)
 *   Re-classify CTA    (opens mini 5-question modal)
 *
 * Pure presentation + data wiring. No writes beyond a "re-classify later"
 * stub that pushes to /api/profile/questionnaire — which already exists
 * on the backend. Falls back to the 20-question onboarding flow on non-
 * 200 responses.
 *
 * Legal: contains no BUY/SELL/HOLD, no "recommend" language.
 */

import * as React from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import { ArrowUpRight, X } from "lucide-react";
import {
  usePersona,
  PERSONA_LABELS,
  PERSONA_TAGLINES,
  type PersonaId,
} from "@/lib/cfo/hooks";
import {
  getPersonaGlyph,
  normalizedPersonaId,
} from "@/components/home/persona-glyph";
import { useFocusTrap } from "@/lib/useFocusTrap";

interface Props {
  /** Rendered inline (no paper shell). Defaults to false → renders
   *  inside an ivory paper-like panel. */
  bare?: boolean;
  className?: string;
}

export function PersonaCard({ bare = false, className = "" }: Props) {
  const { data, isLoading } = usePersona();
  const [miniOpen, setMiniOpen] = React.useState(false);

  const declared = data?.declared;
  const observed30 = data?.observed?.window_30d;
  const observed90 = data?.observed?.window_90d;
  const drift = data?.drift ?? 0;

  const declaredLabel =
    (declared && PERSONA_LABELS[declared.persona as PersonaId]) ?? "Your CFO";
  const declaredTag =
    (declared && PERSONA_TAGLINES[declared.persona as PersonaId]) ??
    "Identity calibrating.";
  const glyphId = normalizedPersonaId(declared?.persona);
  const glyph = getPersonaGlyph(glyphId);

  const wrapperClass = bare
    ? `pq-cfo-persona-card ${className}`
    : `pq-cfo-persona-card pq-cfo-persona-card--paper ${className}`;

  return (
    <section
      className={wrapperClass}
      aria-label="Living CFO persona card"
      style={
        bare
          ? undefined
          : {
              background: "#F5F0E8",
              color: "#1a1612",
              padding: "24px 28px",
              borderRadius: 2,
              boxShadow:
                "0 1px 2px rgba(184,149,106,0.12), 0 18px 36px -22px rgba(0,0,0,0.5)",
              borderTop: "0.5px solid rgba(184,149,106,0.55)",
            }
      }
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div
            className="text-[9.5px] uppercase tracking-[0.26em] flex items-center gap-1.5"
            style={{ color: "#B8956A" }}
          >
            <span
              aria-hidden
              className="font-mono"
              style={{ fontSize: 12, lineHeight: 1 }}
            >
              {glyph}
            </span>
            <span>Layer 1 · Identity · You, observed</span>
          </div>
          <h2
            className="mt-1.5 font-serif text-2xl md:text-3xl"
            style={{ color: "#1a1612", letterSpacing: "-0.01em" }}
          >
            {isLoading ? "…" : declaredLabel}
          </h2>
          <p
            className="mt-1.5 font-serif text-[13px] max-w-lg"
            style={{ color: "rgba(26,22,18,0.72)" }}
          >
            {declaredTag}
          </p>
        </div>

        <button
          type="button"
          onClick={() => setMiniOpen(true)}
          className="shrink-0 inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.22em] px-3 py-1.5 border rounded-[2px] transition-colors"
          style={{
            borderColor: "rgba(139,111,71,0.45)",
            color: "#6F5636",
            background: "rgba(245,240,232,0.5)",
          }}
        >
          Re-classify
          <ArrowUpRight className="h-3 w-3" />
        </button>
      </div>

      {/* Sparkline + drift */}
      <div className="mt-5 grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-5 items-end">
        <Sparkline points={data?.sparkline ?? []} />
        <div className="text-right">
          <div
            className="text-[9.5px] uppercase tracking-[0.22em]"
            style={{ color: "#B8956A" }}
          >
            Drift · declared vs 30d
          </div>
          <div
            className="mt-1 font-mono tabular-nums text-2xl"
            style={{ color: drift > 20 ? "#a35b3b" : "#1a1612" }}
          >
            {isLoading ? "…" : `${drift}`}
          </div>
          <div className="text-[10px]" style={{ color: "rgba(26,22,18,0.55)" }}>
            {drift > 20
              ? "Material drift detected."
              : drift > 10
                ? "Slight drift."
                : "In sync."}
          </div>
        </div>
      </div>

      {/* Rolling window comparison */}
      <div
        className="mt-4 pt-4 grid grid-cols-3 gap-3 text-[11px]"
        style={{ borderTop: "0.5px solid rgba(139,111,71,0.2)" }}
      >
        <WindowStat label="30d observed" p={observed30} />
        <WindowStat label="60d observed" p={data?.observed?.window_60d} />
        <WindowStat label="90d observed" p={observed90} />
      </div>

      <AnimatePresence>
        {miniOpen && <ReclassifyMini onClose={() => setMiniOpen(false)} />}
      </AnimatePresence>
    </section>
  );
}

function WindowStat({
  label,
  p,
}: {
  label: string;
  p:
    | {
        persona: PersonaId;
        score: number;
      }
    | undefined;
}) {
  return (
    <div>
      <div
        className="text-[9.5px] uppercase tracking-[0.22em]"
        style={{ color: "#B8956A" }}
      >
        {label}
      </div>
      <div
        className="mt-1 font-serif text-[15px]"
        style={{ color: "#1a1612" }}
      >
        {p ? PERSONA_LABELS[p.persona] : "—"}
      </div>
      <div
        className="mt-0.5 font-mono tabular-nums text-[11px]"
        style={{ color: "rgba(26,22,18,0.6)" }}
      >
        {p ? p.score.toFixed(0) : "—"}
      </div>
    </div>
  );
}

/* ── Sparkline (inline SVG, no deps) ── */
function Sparkline({
  points,
  width = 260,
  height = 52,
}: {
  points: { week: string; score: number }[];
  width?: number;
  height?: number;
}) {
  if (!points.length) {
    return (
      <div
        aria-hidden
        style={{
          height,
          background:
            "repeating-linear-gradient(0deg, rgba(139,111,71,0.08) 0, rgba(139,111,71,0.08) 1px, transparent 1px, transparent 6px)",
        }}
      />
    );
  }
  const pad = 2;
  const min = Math.min(...points.map((p) => p.score));
  const max = Math.max(...points.map((p) => p.score));
  const range = Math.max(1, max - min);
  const step = (width - pad * 2) / Math.max(1, points.length - 1);
  const y = (v: number) =>
    height - pad - ((v - min) / range) * (height - pad * 2);

  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${pad + i * step},${y(p.score)}`)
    .join(" ");

  // Fill area
  const last = pad + (points.length - 1) * step;
  const areaD = `${d} L ${last},${height} L ${pad},${height} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      role="img"
      aria-label="Persona score — 12 week trend"
      preserveAspectRatio="none"
    >
      <path d={areaD} fill="rgba(139,111,71,0.12)" />
      <path
        d={d}
        fill="none"
        stroke="#B8956A"
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {points.map((p, i) => (
        <circle
          key={p.week}
          cx={pad + i * step}
          cy={y(p.score)}
          r={i === points.length - 1 ? 2.5 : 1.2}
          fill={i === points.length - 1 ? "#6F5636" : "#B8956A"}
        />
      ))}
    </svg>
  );
}

/* ── Re-classify mini modal — 5 rapid questions, local-only echo. ── */
function ReclassifyMini({ onClose }: { onClose: () => void }) {
  const dialogRef = useFocusTrap<HTMLDivElement>(true);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Re-classify persona"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
    >
      <motion.div
        ref={dialogRef}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        initial={{ y: 8, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 8, opacity: 0 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md bg-[var(--pq-ink)] border border-[rgba(245,240,232,0.12)] rounded-[2px] p-6"
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="text-[10px] tracking-[0.26em] uppercase text-[var(--pq-bronze)]">
              Quick re-classify · 5 questions
            </div>
            <h3 className="mt-1 font-serif text-lg text-[var(--pq-ivory)]">
              Refresh your CFO profile
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[rgba(245,240,232,0.5)] hover:text-[var(--pq-ivory)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <p className="text-[13px] text-[rgba(245,240,232,0.65)] font-serif leading-relaxed">
          The full 20-question assessment is on the onboarding page. The
          rapid 5-question mini is a 2026 Q3 shipment — until then, retake
          the full profile in ~4 minutes.
        </p>

        <div className="mt-5 flex gap-2">
          <Link
            href="/onboarding"
            className="pq-ink-btn-bronze flex-1 text-center"
            onClick={onClose}
          >
            Retake full profile
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="pq-ink-btn-ghost flex-1"
          >
            Cancel
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default PersonaCard;
