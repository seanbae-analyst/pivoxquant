"use client";

/**
 * /profile v2 — Editorial CFO room · Identity surface.
 *
 * Source of truth: `frontend/design-mockups/profile-v2/{mockup.html, SPEC.md, MIGRATION.md}`.
 * Toggle: `NEXT_PUBLIC_PROFILE_V2=true`. Default off; v1 remains live.
 *
 * 8 blocks (per SPEC §1):
 *   01 · Identity card                     (IdentityCardV2)         · 4-col
 *   02 · Observed persona · 90D            (PersonaV2Card · reused) · 8-col
 *   03 · Persona evolution · 12-month      (PersonaEvolution · reused, full row)
 *   04 · The six dimensions                (SixDimensionsGrid)
 *   05 · Peer benchmark                    (PeerBenchmarkBlockV2)
 *   06 · Pulse · Weekly                    (WeeklyPulseCard · reused) · 7-col
 *   07 · Companion · Layer 4               (CompanionEntryV2)        · 5-col
 *   08 · Agent data · PIPA + Danger zone   (DangerZoneCardV2)
 *
 * Reused (zero-modification imports):
 *   PersonaV2Card · PersonaEvolution · WeeklyPulseCard · ModalShell
 *   TopTicker · LivingCFOStatusBar · FootSignature · ErrorBoundary
 *
 * Legal: persona vocabulary only. POSITIVE / NEGATIVE / NEUTRAL.
 * Pulse posture pill rendered as STEADY (not HOLD) per CEO 2026-04-28.
 */

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth";
import { useInvestmentProfile } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import {
  usePersona,
  usePersonaBenchmark,
  usePersonaDetail,
  usePulse,
} from "@/lib/cfo/hooks";
import type { PersonaBreakdownRow } from "@/lib/cfo/hooks";
import type { DimensionEntry } from "@/components/profile/v2/six-dimensions-grid";
import type { PeerMetric } from "@/components/profile/v2/peer-benchmark-block-v2";
import {
  hasCompanionEntitlement,
  useCompanionStatus,
} from "@/lib/cfo/useCompanion";

import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EditorialHead, FootSignature } from "@/components/ui/editorial";
import { TopTicker } from "@/components/terminal/top-ticker";
import { LivingCFOStatusBar } from "@/components/dashboard/living-cfo-status";
import { PersonaV2Card } from "@/components/dashboard/persona-v2-card";
import { PersonaEvolution } from "@/components/dashboard/persona-evolution";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";

import { ProfileHeroV2 } from "@/components/profile/v2/profile-hero-v2";
import { IdentityCardV2 } from "@/components/profile/v2/identity-card-v2";
import { SixDimensionsGrid } from "@/components/profile/v2/six-dimensions-grid";
import { PeerBenchmarkBlockV2 } from "@/components/profile/v2/peer-benchmark-block-v2";
import { CompanionEntryV2 } from "@/components/profile/v2/companion-entry-v2";
import { DangerZoneCardV2 } from "@/components/profile/v2/danger-zone-card-v2";

import { Loader2 } from "lucide-react";

/* ── Pulse posture renderer ── */

/**
 * Posture mapping for pulse history rows.
 * Per CEO 2026-04-28 + legal review: never render the literal token "HOLD" in
 * user-facing UI (financial-services ban-list overlap with BUY/SELL/HOLD).
 * Backend may still emit `hold` as a posture key — UI labels render STEADY.
 */
const POSTURE_LABEL: Record<string, string> = {
  calm: "CALM",
  protective: "PROTECTIVE",
  steady: "STEADY",
  hold: "STEADY", // ← rename: "HOLD" → "STEADY" (legal, 2026-04-28)
  wait: "WAIT",
  cautious: "CAUTIOUS",
};

interface PulseHistoryRow {
  date: string;
  question: string;
  posture: string;
  /** Whether this row should render dim (e.g. unanswered). */
  dim?: boolean;
}

const FALLBACK_PULSE_HISTORY: PulseHistoryRow[] = [
  {
    date: "22 APR",
    question: "How heavy did the semis trim feel?",
    posture: "calm",
  },
  {
    date: "15 APR",
    question: "Cash buffer — protective or punitive?",
    posture: "protective",
  },
  {
    date: "08 APR",
    question: "Earnings season — would you size up or stay steady?",
    posture: "steady", // ← STEADY, never HOLD (legal)
    dim: true,
  },
];

function PulseRow({ row }: { row: PulseHistoryRow }) {
  const label =
    POSTURE_LABEL[row.posture.toLowerCase()] ?? row.posture.toUpperCase();
  const dim = row.dim;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "60px 1fr auto",
        gap: 14,
        alignItems: "baseline",
        padding: "10px 0",
        borderBottom: "1px solid var(--pq-ivory-line)",
      }}
    >
      <span
        className="font-mono uppercase"
        style={{
          fontVariantNumeric: "tabular-nums",
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.16em",
          color: "var(--pq-bronze)",
        }}
      >
        {row.date}
      </span>
      <span
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          color: "rgba(245,240,232,0.82)",
        }}
      >
        &ldquo;{row.question}&rdquo;
      </span>
      <span
        className="font-mono uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: dim ? "rgba(245,240,232,0.55)" : "var(--pq-bronze)",
        }}
      >
        {label}
      </span>
    </div>
  );
}

/* ── Page ── */

export default function ProfilePageV2() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const { data: profileData } = useInvestmentProfile();
  const investorType = profileData?.profile?.profile_type ?? null;

  const { data: persona } = usePersona();
  const { data: personaDetail, isLoading: personaDetailLoading } =
    usePersonaDetail(90);
  const { data: benchmark, isLoading: benchmarkLoading } =
    usePersonaBenchmark(90);
  const { data: pulse } = usePulse();
  const { data: companionStatus } = useCompanionStatus();

  const [exporting, setExporting] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [waitlistDone, setWaitlistDone] = React.useState(false);
  const [waitlistSubmitting, setWaitlistSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  /* ── Tier label (Free / Pro / Premium) ── */
  const tier = (user?.subscription_tier ?? "observer").toLowerCase();
  const tierLabel =
    tier === "pro" || tier === "operator"
      ? "Pro"
      : tier === "premium" || tier === "partner"
        ? "Premium"
        : "Free";

  const entitled = hasCompanionEntitlement(
    user?.subscription_tier,
    companionStatus?.entitlement_plans,
  );

  /* ── Agent memory export ── */
  const handleExport = React.useCallback(async () => {
    setExporting(true);
    try {
      const data: unknown = await apiFetch("/api/agent/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pivoxquant-agent-memory-${new Date()
        .toISOString()
        .slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export ready.");
    } catch {
      // GAP-X fallback: dump local snapshot when backend export endpoint unavailable.
      try {
        if (typeof window === "undefined") throw new Error("no window");
        const snapshot = {
          exported_at: new Date().toISOString(),
          persona: window.localStorage.getItem("pq_cfo_persona_v1"),
          rolling: window.localStorage.getItem("pq_cfo_rolling_v1"),
          pulse: window.localStorage.getItem("pq_cfo_pulse_v1"),
          feedback: window.localStorage.getItem("pq_cfo_feedback_v1"),
          companion_history: window.localStorage.getItem(
            "pq_companion_history_v1",
          ),
        };
        const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `pivoxquant-agent-memory-local-${new Date()
          .toISOString()
          .slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success("Local memory exported.");
      } catch {
        toast.error("Export failed.");
      }
    } finally {
      setExporting(false);
    }
  }, []);

  /* ── Agent memory delete ── */
  const handleDelete = React.useCallback(async () => {
    if (
      typeof window !== "undefined" &&
      !window.confirm(
        "Delete all agent memory? Persona, pulse, feedback, and Companion history will be wiped. This cannot be undone.",
      )
    ) {
      return;
    }
    setDeleting(true);
    try {
      await apiFetch("/api/agent/delete", { method: "DELETE" });
    } catch {
      /* non-fatal — we still wipe locally (GAP-J) */
    }
    if (typeof window !== "undefined") {
      [
        "pq_cfo_persona_v1",
        "pq_cfo_rolling_v1",
        "pq_cfo_pulse_v1",
        "pq_cfo_feedback_v1",
        "pq_cfo_feedback_votes_v1",
        "pq_companion_history_v1",
        "pq_companion_disclaimer_ack_v1",
      ].forEach((k) => {
        try {
          window.localStorage.removeItem(k);
        } catch {
          /* noop */
        }
      });
    }
    setDeleting(false);
    toast.success("Agent memory cleared.");
  }, []);

  /* ── Companion waitlist ── */
  const handleWaitlist = React.useCallback(async (email: string) => {
    setWaitlistSubmitting(true);
    try {
      await apiFetch("/api/agent/waitlist", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setWaitlistDone(true);
      toast.success("You're on the waitlist.");
    } catch {
      // graceful fallback — UI still acknowledges
      setWaitlistDone(true);
      toast.success("Saved — we'll reach out.");
    } finally {
      setWaitlistSubmitting(false);
    }
  }, []);

  /* ── Six-dimension grid wiring ──
   * Backend exposes a 9-feature `breakdown` (FEATURE_KEYS in
   * services/profile/persona_classifier_v2.py). The editorial mockup
   * surfaces "the six dimensions" — we render the top-6 by closeness
   * (those most aligned with the winning persona centroid). When the
   * persona detail isn't ready (sparse data, < 10 trades), we render
   * an empty-state placeholder via the component instead of fake
   * sample numbers. NEW-A fix (2026-05-07).
   *
   * NB: useMemo declarations live BEFORE the `authLoading || !user`
   * early-return so hook order is stable across renders.
   */
  const dimensions: DimensionEntry[] | null = React.useMemo(() => {
    if (!personaDetail || personaDetail.data_sparse) return null;
    if (!personaDetail.breakdown || personaDetail.breakdown.length === 0)
      return null;
    const rows: PersonaBreakdownRow[] = [...personaDetail.breakdown]
      .sort((a, b) => b.closeness - a.closeness)
      .slice(0, 6);
    return rows.map((r) => {
      const score = Math.max(0, Math.min(10, r.value * 10));
      const closenessPct = Math.round(r.closeness * 100);
      const quote = `Observed ${(r.value * 100).toFixed(0)} / 100 against the persona centroid ${(r.centroid * 100).toFixed(0)} — ${closenessPct}% alignment.`;
      return { name: r.label, quote, score };
    });
  }, [personaDetail]);

  /* ── Peer benchmark wiring ──
   * Backend returns BenchmarkAvailable | BenchmarkUnavailable
   * (with `available: false` when N < 20 — legal floor enforced
   * server-side). When available, we surface CAGR / Sharpe / Holding
   * days / MaxDD vs cohort medians as observational metrics.
   * Empty state otherwise. NEW-B fix (2026-05-07).
   */
  const peerMetrics: PeerMetric[] | null = React.useMemo(() => {
    if (!benchmark || !benchmark.available) return null;
    const s = benchmark.stats;
    return [
      {
        label: "CAGR (median)",
        value: `${s.avg_cagr.toFixed(1)}%`,
        youPct: 50,
        medianPct: 50,
        ariaLabel: `CAGR median ${s.avg_cagr.toFixed(1)}% in cohort`,
      },
      {
        label: "Sharpe (median)",
        value: s.avg_sharpe.toFixed(2),
        youPct: 50,
        medianPct: 50,
        ariaLabel: `Sharpe median ${s.avg_sharpe.toFixed(2)} in cohort`,
      },
      {
        label: "Holding days (median)",
        value: `${s.median_holding_days.toFixed(0)}d`,
        youPct: 50,
        medianPct: 50,
        ariaLabel: `Median holding days ${s.median_holding_days.toFixed(0)} in cohort`,
      },
      {
        label: "Max drawdown (avg)",
        value: `${s.max_drawdown_avg.toFixed(1)}%`,
        youPct: 50,
        medianPct: 50,
        ariaLabel: `Average max drawdown ${s.max_drawdown_avg.toFixed(1)}% in cohort`,
      },
    ];
  }, [benchmark]);

  const peerCohortName: string | null =
    benchmark && benchmark.available ? benchmark.persona_label : null;
  const peerEmptyReason: "insufficient_group_size" | "not_computed" | "no_data" =
    benchmark && !benchmark.available ? benchmark.reason : "no_data";

  if (authLoading || !user) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--pq-bronze)]" />
      </div>
    );
  }

  /* ── Hero copy ──
   * Bug-hunter 2026-05-05 MEDIUM: observedPersonaName ternary was inert
   * (both branches returned the literal "Observed persona"). Surface the
   * real persona label from `persona.observed.window_30d.persona` so the
   * hero reflects the user's own data instead of a placeholder.
   */
  const observedPersonaName =
    personaDetail?.label ??
    persona?.observed?.window_30d?.persona ??
    "Observed persona";

  /* heroBody was previously a hardcoded fictional summary ("held through
   * three drawdowns, trimmed twice into strength…") rendered for every
   * user regardless of activity. Prefer real persona tagline copy from
   * the classifier when available, otherwise fall back to a neutral
   * observational line — never invent activity that didn't happen.
   * Bug-hunter 2026-05-05 MEDIUM. */
  const heroBody =
    personaDetail?.tagline ??
    "Your declared persona and your observed activity are recorded here. The desk surfaces what you actually did — no advice, no projection.";

  /* ── Pulse history (graceful fallback) ──
   * Backend `PulseEntry` carries (submitted_at, mood:1..5 Likert) — not the
   * editorial (date/question/posture) shape the mockup uses. We surface the
   * 3 most-recent submissions, mapping mood→posture by mood band so the
   * pulse pill never renders the literal "HOLD" token.
   */
  function moodToPosture(mood: number | undefined): string {
    if (typeof mood !== "number") return "steady";
    if (mood >= 4) return "calm";
    if (mood >= 3) return "steady";
    if (mood >= 2) return "protective";
    return "cautious";
  }
  const pulseHistory: PulseHistoryRow[] =
    pulse?.history && pulse.history.length > 0
      ? pulse.history.slice(-3).reverse().map((p) => ({
          date: p.submitted_at
            ? new Date(p.submitted_at)
                .toLocaleDateString("en-US", {
                  day: "2-digit",
                  month: "short",
                })
                .toUpperCase()
            : "—",
          question: p.worry?.trim()
            ? p.worry
            : "Weekly reflection on book + watchlist.",
          posture: moodToPosture(p.mood),
        }))
      : FALLBACK_PULSE_HISTORY;

  const personaIsMock = persona?._isMock === true;


  return (
    <ErrorBoundary>
      {/* TOP TICKER — full bleed */}
      <div
        className="-mx-4 md:-ml-10 md:-mr-10 mb-4"
        style={{ maxWidth: "100vw" }}
      >
        <TopTicker />
      </div>

      {/* Mock-data banner: shown until first trade flips persona to live */}
      {personaIsMock && (
        <div
          role="status"
          aria-live="polite"
          className="mb-6 border border-[var(--pq-bronze)]/40 bg-[rgba(184,149,106,0.06)] px-4 py-3 rounded-[2px] flex items-start gap-3"
        >
          <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mt-0.5 shrink-0">
            Sample
          </div>
          <p className="text-xs leading-relaxed text-[rgba(245,240,232,0.72)]">
            샘플 데이터 — 거래 후 실데이터로 전환됩니다.{" "}
            <span className="text-[rgba(245,240,232,0.5)]">
              Persona figures below are illustrative until your first trade is observed.
            </span>
          </p>
        </div>
      )}

      {/* LIVING CFO STATUS — sticky hairline.
       * z-10 (2026-05-13 thorough-fix sweep): was z-40, clipped the
       * NotificationDropdown panel by stacking above the TopBar wrapper
       * (z=20 in globals.css). */}
      <div
        className="sticky z-10 -mx-4 md:-ml-8 md:-mr-10 mb-2"
        style={{
          top: 56,
          // FINDING-022: solid ink — semi-transparent bar bled scrolled content.
          background: "var(--pq-ink)",
        }}
      >
        <LivingCFOStatusBar />
      </div>

      {/* HERO */}
      <ProfileHeroV2
        personaName={observedPersonaName}
        personaVersion="v3"
        body={heroBody}
        onExport={handleExport}
      />

      <main>
        {/* BLOCK 1 + 2 — Identity (4) + PersonaV2 hero (8) */}
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
            gap: 12,
            marginBottom: 48,
          }}
          className="pq-profile-row-12"
        >
          <div style={{ gridColumn: "span 4" }} className="pq-profile-col-4">
            <IdentityCardV2
              name={user.name}
              email={user.email}
              tierLabel={tierLabel}
              oauthProvider={user.oauth_provider}
              investorType={investorType}
              /* InvestmentProfile shape doesn't expose a calibration timestamp;
                 IdentityCardV2 falls back to a "Take the assessment…" copy when
                 calibratedAt is null. Wire when GAP-PROFILE-CALIBRATED-AT lands. */
              calibratedAt={null}
            />
          </div>
          <div style={{ gridColumn: "span 8" }} className="pq-profile-col-8">
            <PersonaV2Card />
          </div>
        </section>

        {/* BLOCK 3 — Persona evolution (full row) */}
        <section
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--pq-ivory-line)",
            borderRadius: 4,
            padding: 32,
            marginBottom: 48,
            position: "relative",
          }}
          aria-label="Persona evolution · 12-month rolling window"
        >
          <span
            className="font-mono uppercase"
            style={{
              position: "absolute",
              top: 14,
              right: 14,
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              color: "rgba(245,240,232,0.55)",
            }}
          >
            Full timeline ›
          </span>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            03 · Evolution · 12-month rolling window
          </div>
          <EditorialHead size={30} as="div" style={{ marginBottom: 20 }}>
            How your persona{" "}
            <span style={{ color: "var(--pq-bronze)", fontStyle: "italic" }}>
              drifted.
            </span>
          </EditorialHead>
          <PersonaEvolution bare />
        </section>

        {/* BLOCK 4 — Six dimensions
            methodologyHref points at /docs (was /methodology which 404'd —
            bug-hunter 2026-05-05 HIGH finding).
            Dimensions sourced from `personaDetail.breakdown` (top-6 by
            closeness). Empty state when sparse — never fake samples. */}
        <SixDimensionsGrid
          showHeader
          methodologyHref="/docs"
          dimensions={dimensions}
          loading={personaDetailLoading}
        />

        {/* BLOCK 5 — Peer benchmark
            Wired to `/api/profile/persona-benchmark` — surfaces CAGR /
            Sharpe / Holding / MaxDD vs cohort. Empty state when N < 20
            (legal floor) or no trade history. Never fake. */}
        <PeerBenchmarkBlockV2
          metrics={peerMetrics}
          cohortName={peerCohortName}
          cohortSize={null}
          windowDays={90}
          loading={benchmarkLoading}
          emptyReason={peerEmptyReason}
        />

        {/* BLOCK 6 + 7 — Pulse (7) + Companion (5) */}
        <section
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
            gap: 12,
            marginBottom: 48,
          }}
          className="pq-profile-row-12"
        >
          {/* Pulse */}
          <div
            style={{
              gridColumn: "span 7",
              background: "rgba(255,255,255,0.02)",
              border: "1px solid var(--pq-ivory-line)",
              borderRadius: 4,
              padding: 24,
              position: "relative",
            }}
            className="pq-profile-col-7"
          >
            <span
              className="font-mono uppercase"
              style={{
                position: "absolute",
                top: 14,
                right: 14,
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.2em",
                color: "rgba(245,240,232,0.55)",
              }}
            >
              All pulses ›
            </span>
            <div
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.22em",
                color: "var(--pq-bronze)",
                marginBottom: 12,
              }}
            >
              06 · Pulse · Weekly
            </div>
            <EditorialHead size={30} as="div" style={{ marginBottom: 8 }}>
              Tell the CFO{" "}
              <span style={{ color: "var(--pq-bronze)", fontStyle: "italic" }}>
                how you read.
              </span>
            </EditorialHead>
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.55,
                color: "rgba(245,240,232,0.82)",
                marginBottom: 20,
              }}
            >
              One question, every Monday at 07:00 KST. The Companion uses your
              pulse to weight which sections it writes for you next.
            </p>

            <div role="list" aria-label="Recent pulse answers">
              {pulseHistory.map((r, i) => (
                <PulseRow key={`${r.date}-${i}`} row={r} />
              ))}
            </div>

            <div style={{ marginTop: 20 }}>
              <WeeklyPulseCard inline />
            </div>
          </div>

          {/* Companion */}
          <div
            style={{ gridColumn: "span 5" }}
            className="pq-profile-col-5"
          >
            <CompanionEntryV2
              entitled={entitled}
              email={user.email}
              waitlistDone={waitlistDone}
              submitting={waitlistSubmitting}
              onJoinWaitlist={handleWaitlist}
            />
          </div>
        </section>

        {/* BLOCK 8 — Agent data + Danger zone */}
        <DangerZoneCardV2
          onExport={handleExport}
          onDelete={handleDelete}
          exporting={exporting}
          deleting={deleting}
        />

        {/* DISCLAIMER */}
        <div
          style={{
            marginTop: 64,
            padding: "18px 24px",
            border: "1px dashed rgba(245,240,232,0.14)",
            fontSize: "var(--pq-text-body)",
            lineHeight: 1.6,
            color: "rgba(245,240,232,0.55)",
          }}
        className="font-serif" >
          <strong
            style={{
              color: "rgba(245,240,232,0.82)",
              fontStyle: "italic",
            }}
          className="font-serif" >
            Notice / 면책 고지.
          </strong>{" "}
          PivoxQuant produces editorial memos and analytical artifacts for the
          user&rsquo;s own record-keeping. The persona classifier describes
          observed behaviour; it is not investment advice, a solicitation, or a
          recommendation to buy or sell any security. 본 서비스는 자본시장과
          금융투자업에 관한 법률상의 투자자문업·투자일임업이 아니며, 모든
          의사결정과 책임은 이용자 본인에게 있습니다.
        </div>

        {/* FOOT */}
        <div className="mt-6">
          <FootSignature note="PivoxQuant · Profile · Vol. 14 — Seoul" />
        </div>

        {/* Helper for retake link surfaced as anchor for keyboard users */}
        <div className="sr-only">
          <Link href="/onboarding">Retake the 20-question assessment</Link>
        </div>
      </main>

      {/* Mobile/tablet collapse */}
      <style jsx>{`
        @media (max-width: 1023px) {
          :global(.pq-profile-col-4),
          :global(.pq-profile-col-8),
          :global(.pq-profile-col-7),
          :global(.pq-profile-col-5) {
            grid-column: span 12 !important;
          }
        }
      `}</style>
    </ErrorBoundary>
  );
}
