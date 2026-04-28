"use client";

/**
 * <TodayHero /> — cinematic "Today, for your CFO" opener.
 *
 * Sits at the top of /home, above the ticker and persona card, and is
 * NOT sticky — it scrolls away with the rest of the page. Pulls the
 * same polish language as the landing HeroAurora + FilmGrain + CTA
 * ink-bleed so the dashboard reads as the same piece of software.
 *
 * Composition
 *   • Vantablack canvas + bronze aurora radial (reused HeroAurora)
 *   • Fine film grain at 0.05 opacity
 *   • Editorial header: ISO date · Week N · KST clock
 *   • Serif italic headline (persona-specific, one per 8 personas)
 *   • Subtitle with the real display name + today's brief title
 *   • Primary CTA: "Read this morning's brief →" (bronze ink-bleed)
 *   • Secondary CTA: "Ask your CFO →" (ghost variant, /companion)
 *   • Right-aligned mini sparkline (portfolio 5-day equity)
 *   • Bottom bronze hairline that slowly pulses
 *
 * Data dependencies — all degrade silently when the endpoint is missing:
 *   • usePersona (declared persona → headline dictionary)
 *   • useAuth   (display name)
 *   • /api/brief/today (morning brief title or insight)
 *   • /api/portfolio/history?period=5d (sparkline)
 *
 * Legal: no BUY/SELL/HOLD, no "recommend". Headlines are observational.
 * Animations respect `prefers-reduced-motion`.
 */

import * as React from "react";
import Link from "next/link";
import useSWR from "swr";
import { motion, useReducedMotion } from "motion/react";

import { HeroAurora } from "@/components/landing/hero-aurora";
import { FilmGrain } from "@/components/landing/film-grain";
import { CtaInkBleed } from "@/components/landing/cta-ink-bleed";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";
import { usePersona, PERSONA_LABELS, type PersonaId } from "@/lib/cfo/hooks";
import {
  getPersonaGlyph,
  normalizedPersonaId,
  type NormalizedPersonaId,
} from "./persona-glyph";

/* ═══════════ Persona-specific headlines (8 variants) ═══════════ */

const HEADLINES: Record<NormalizedPersonaId, string> = {
  growth: "Momentum leaders this morning.",
  value: "What the market mispriced overnight.",
  balanced: "A steady read on the opening tape.",
  income: "Payers holding their ground.",
  quant: "Signal, before the noise.",
  speculator: "Where the tape is restless today.",
  daytrader: "The first ninety minutes, charted.",
  beginner: "One thing worth learning today.",
};

const EYEBROW_SUFFIX: Record<NormalizedPersonaId, string> = {
  growth: "compounders in view",
  value: "mispricings, observed",
  balanced: "portfolio equilibrium",
  income: "yield stability",
  quant: "signal / noise",
  speculator: "dislocations",
  daytrader: "session open",
  beginner: "learn by watching",
};

/* ═══════════ Data shapes ═══════════ */

interface BriefToday {
  available?: boolean;
  brief?: { title?: string; insight?: string; summary?: string };
}

interface HistoryPoint {
  date?: string;
  nav?: number;
  total_value?: number;
  equity?: number;
}

interface HistoryResponse {
  history?: HistoryPoint[];
  series?: HistoryPoint[];
  points?: HistoryPoint[];
}

const fetcher = <T,>(url: string) => apiFetch<T>(url);

/* ═══════════ Date / week helpers ═══════════ */

function fmtIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function isoWeek(d: Date): number {
  // ISO week number — Monday = 1.
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

function fmtKstClock(d: Date): string {
  try {
    return d.toLocaleTimeString("en-GB", {
      timeZone: "Asia/Seoul",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return d.toTimeString().slice(0, 5);
  }
}

/* ═══════════ Mini sparkline — pure inline SVG ═══════════ */

function MiniSparkline({
  points,
  width = 140,
  height = 40,
}: {
  points: number[];
  width?: number;
  height?: number;
}) {
  if (points.length < 2) {
    return (
      <div
        aria-hidden
        className="w-[140px] h-[40px]"
        style={{
          background:
            "repeating-linear-gradient(0deg, rgba(184,149,106,0.10) 0, rgba(184,149,106,0.10) 1px, transparent 1px, transparent 6px)",
        }}
      />
    );
  }
  const pad = 2;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = Math.max(1e-6, max - min);
  const step = (width - pad * 2) / (points.length - 1);
  const y = (v: number) =>
    height - pad - ((v - min) / range) * (height - pad * 2);
  const d = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${pad + i * step},${y(p)}`)
    .join(" ");
  const last = pad + (points.length - 1) * step;
  const areaD = `${d} L ${last},${height} L ${pad},${height} Z`;
  const up = points[points.length - 1] >= points[0];
  const stroke = up ? "#B8956A" : "rgba(245,240,232,0.55)";
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label="Portfolio — 5 day trend"
    >
      <path d={areaD} fill="rgba(184,149,106,0.10)" />
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={1.25}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle
        cx={pad + (points.length - 1) * step}
        cy={y(points[points.length - 1])}
        r={2.5}
        fill={stroke}
      />
    </svg>
  );
}

/* ═══════════ Component ═══════════ */

export function TodayHero() {
  const { user } = useAuth();
  const { data: persona } = usePersona();
  const reduceMotion = useReducedMotion();

  const { data: brief } = useSWR<BriefToday>(
    API.market.morningBriefToday,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000, errorRetryCount: 1 },
  );

  const { data: history } = useSWR<HistoryResponse>(
    API.portfolio.history("5d"),
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000, errorRetryCount: 1 },
  );

  /* ── Live clock (1-min tick; enough for a KST display) ── */
  const [now, setNow] = React.useState<Date>(() => new Date());
  React.useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  const declaredPersonaRaw = persona?.declared?.persona as PersonaId | undefined;
  const declaredPersona = normalizedPersonaId(
    declaredPersonaRaw,
    user?.onboarding_completed === false ? "beginner" : "balanced",
  );
  const headline = HEADLINES[declaredPersona];
  const eyebrowSuffix = EYEBROW_SUFFIX[declaredPersona];
  const glyph = getPersonaGlyph(declaredPersona);

  const displayName = user?.name?.split(" ")[0] || "Observer";

  const briefTitle =
    brief?.available !== false
      ? brief?.brief?.title ||
        brief?.brief?.insight ||
        brief?.brief?.summary ||
        null
      : null;

  /* ── Sparkline extraction. History response shape varies, so be
        tolerant: accept `history`, `series`, or `points`; on each
        point prefer `nav`, then `total_value`, then `equity`. ── */
  const sparkPoints = React.useMemo<number[]>(() => {
    const rows: HistoryPoint[] =
      history?.history ?? history?.series ?? history?.points ?? [];
    return rows
      .map((p) => p.nav ?? p.total_value ?? p.equity ?? null)
      .filter((n): n is number => typeof n === "number" && Number.isFinite(n))
      .slice(-24);
  }, [history]);

  const isoDate = fmtIso(now);
  const weekNo = isoWeek(now);
  const kst = fmtKstClock(now);

  const personaLabel =
    (declaredPersonaRaw && PERSONA_LABELS[declaredPersonaRaw]) ?? "Your CFO";

  /* ── Reveal cascade — drives both motion/react and CSS fallback ── */
  const stageAnim = (delay: number) =>
    reduceMotion
      ? {}
      : {
          initial: { opacity: 0, y: 14 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] as const },
        };

  return (
    <section
      aria-label={`Today, for ${personaLabel}`}
      className="pq-today-hero relative overflow-hidden rounded-[3px]"
      style={{
        background: "var(--pq-ink, #050505)",
        border: "0.5px solid rgba(184,149,106,0.22)",
        boxShadow:
          "0 0 0 1px rgba(184,149,106,0.06), 0 18px 56px -20px rgba(0,0,0,0.9)",
      }}
    >
      {/* Aurora layer — bronze sunrise below headline */}
      <div className="absolute inset-0" aria-hidden>
        <HeroAurora />
      </div>
      {/* Grain — slightly stronger than landing default */}
      <FilmGrain opacity={0.05} blendMode="overlay" />

      <div className="relative z-10 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 md:gap-10 px-5 sm:px-8 md:px-10 py-8 md:py-11">
        {/* ── Left column: eyebrow + headline + sub + CTAs ── */}
        <div className="min-w-0">
          <motion.div
            {...stageAnim(0.0)}
            className="flex items-center gap-2 font-mono uppercase text-[9.5px] tracking-[0.26em]"
            style={{ color: "var(--pq-bronze)" }}
          >
            <span aria-hidden>{glyph}</span>
            <span>{isoDate}</span>
            <span aria-hidden style={{ opacity: 0.5 }}>·</span>
            <span>Week {weekNo}</span>
            <span aria-hidden style={{ opacity: 0.5 }}>·</span>
            <span className="hidden sm:inline">{kst} KST</span>
            <span className="hidden md:inline" style={{ opacity: 0.5 }}>·</span>
            <span className="hidden md:inline">{eyebrowSuffix}</span>
          </motion.div>

          <motion.h1
            {...stageAnim(0.08)}
            className="mt-4 max-w-[620px]"
            style={{
              fontFamily: "var(--font-serif), 'Source Serif 4', Georgia, serif",
              fontStyle: "italic",
              fontWeight: 400,
              fontSize: "clamp(28px, 4.4vw, 46px)",
              lineHeight: 1.08,
              letterSpacing: "-0.01em",
              color: "var(--pq-ivory)",
            }}
          >
            {headline}
          </motion.h1>

          <motion.p
            {...stageAnim(0.16)}
            className="mt-3 max-w-[560px] text-[14px] leading-relaxed"
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              color: "rgba(245,240,232,0.68)",
            }}
          >
            Good morning, <span style={{ color: "var(--pq-ivory)" }}>{displayName}</span>.
            {briefTitle ? (
              <>
                {" "}Your brief leads with{" "}
                <span style={{ color: "var(--pq-ivory)" }}>
                  &ldquo;{truncate(briefTitle, 80)}&rdquo;
                </span>
                .
              </>
            ) : (
              <> Your {personaLabel.toLowerCase()} is watching the tape.</>
            )}
          </motion.p>

          <motion.div
            {...stageAnim(0.24)}
            className="mt-6 flex flex-wrap items-center gap-2.5"
          >
            <CtaInkBleed href="/morning-brief" variant="bronze">
              Read this morning&rsquo;s brief
              <span aria-hidden style={{ marginLeft: 2 }}>→</span>
            </CtaInkBleed>
            <CtaInkBleed href="/companion" variant="ghost">
              Ask your CFO
              <span aria-hidden style={{ marginLeft: 2 }}>→</span>
            </CtaInkBleed>
          </motion.div>
        </div>

        {/* ── Right column: persona badge + sparkline ── */}
        <motion.div
          {...stageAnim(0.32)}
          className="md:text-right flex md:flex-col items-center md:items-end justify-between md:justify-start gap-3 md:gap-4 shrink-0"
        >
          <div>
            <div
              className="font-mono uppercase text-[9.5px] tracking-[0.24em]"
              style={{ color: "var(--pq-bronze)" }}
            >
              Portfolio · 5d
            </div>
            <div className="mt-2 flex md:justify-end">
              <MiniSparkline points={sparkPoints} />
            </div>
          </div>
          <div className="md:mt-auto text-right">
            <div
              className="font-mono uppercase text-[9.5px] tracking-[0.24em]"
              style={{ color: "var(--pq-bronze)" }}
            >
              Persona
            </div>
            <div
              className="mt-1 font-serif text-[13px]"
              style={{ color: "var(--pq-ivory)" }}
            >
              {personaLabel}
            </div>
          </div>
        </motion.div>
      </div>

      {/* Bottom hairline pulse */}
      <div
        aria-hidden
        className="pq-today-hairline"
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 1,
          background:
            "linear-gradient(90deg, transparent 0%, rgba(184,149,106,0.55) 50%, transparent 100%)",
        }}
      />
    </section>
  );
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1).trimEnd() + "…";
}

export default TodayHero;
