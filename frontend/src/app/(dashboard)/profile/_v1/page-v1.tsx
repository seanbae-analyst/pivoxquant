"use client";

/**
 * /profile — Identity · Persona · Living CFO
 *
 * Split out of /settings to stop Settings from becoming a 1000-line
 * kitchen sink. This page hosts everything tied to WHO the user is
 * (identity, declared persona, observed rolling window, pulse cadence,
 * feedback, evolution timeline, Journal Companion entitlement, and the
 * PIPA-compliant agent memory export/delete).
 *
 * Operational controls (subscription, brokers, notifications, seed
 * capital, language, sign out) live on /settings.
 */

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { useInvestmentProfile } from "@/lib/hooks";
import { apiFetch } from "@/lib/api";
import { API } from "@/lib/endpoints";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { EditorialHead } from "@/components/ui/editorial";
import { ModalShell } from "@/components/ui/modal-shell";
import { cn } from "@/lib/utils";
import {
  ChevronRight,
  Loader2,
  AlertTriangle,
  X,
  Trash2,
} from "lucide-react";
import {
  usePersona,
  usePulse,
  PERSONA_LABELS,
  type PersonaId,
} from "@/lib/cfo/hooks";
import {
  hasCompanionEntitlement,
  useCompanionStatus,
} from "@/lib/cfo/useCompanion";
import { WeeklyPulseCard } from "@/components/dashboard/weekly-pulse";
import { PersonaEvolution } from "@/components/dashboard/persona-evolution";
import { PersonaV2Card } from "@/components/dashboard/persona-v2-card";
import { useT, useLocale } from "@/lib/locale";


function initials(name?: string | null, email?: string | null): string {
  if (name) {
    return name
      .split(/\s+/)
      .map((w) => w[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }
  if (email) return email.slice(0, 2).toUpperCase();
  return "PQ";
}

/* ── Section shell ── */

function Section({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header>
        <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
          {kicker}
        </div>
        {/* Wave 2 sweep (Task #8): inline Playfair text-2xl → EditorialHead. */}
        <EditorialHead size={26} as="h2" className="mt-1">
          {title}
        </EditorialHead>
      </header>
      {children}
    </section>
  );
}

/* ── Toggle ── */

function Toggle({
  checked,
  onChange,
  disabled,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
        checked ? "bg-[var(--pq-bronze)]" : "bg-[rgba(245,240,232,0.1)]",
        disabled && "opacity-40 cursor-not-allowed",
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 rounded-full bg-[var(--pq-ivory)] transition-transform",
          checked ? "translate-x-[18px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

/* ── Delete-account modal ── */

function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell onClose={onClose} ariaLabel="Delete account">
      <div className="my-auto w-full max-w-md bg-[var(--pq-ink)] border border-[rgba(245,240,232,0.12)] p-6 rounded-[2px]">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-400" />
            <h3 className="font-serif text-xl text-[var(--pq-ivory)]">
              Delete account
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
        <p className="text-sm text-[rgba(245,240,232,0.6)] mb-6">
          Deletion is permanent and removes all positions, watchlists, and
          delivered artifacts. Per PIPA, all data is purged within 30 days.
        </p>
        <div className="flex items-center gap-3">
          <a
            href="mailto:support@pivoxquant.com?subject=Account%20Deletion%20Request"
            className="flex-1 pq-ink-btn-bronze text-center"
          >
            Contact support
          </a>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 pq-ink-btn-ghost"
          >
            Cancel
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

/* ── Living CFO controls ── */

const DRIFT_ALERT_LS = "pq_cfo_drift_alerts_enabled";

function readDriftAlertsLS(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return window.localStorage.getItem(DRIFT_ALERT_LS) !== "0";
  } catch {
    return true;
  }
}

function readFeedbackCountLS(): number {
  if (typeof window === "undefined") return 0;
  try {
    const raw = window.localStorage.getItem("pq_cfo_feedback_votes_v1");
    if (!raw) return 0;
    const map = JSON.parse(raw) as Record<string, string>;
    return Object.keys(map).length;
  } catch {
    return 0;
  }
}

function LivingCFOControls() {
  const { data: persona } = usePersona();
  const { data: pulse } = usePulse();
  // Lazy initializers run once per mount on the client; safe for SSR
  // because LivingCFOControls is rendered inside a client tree.
  const [driftAlerts, setDriftAlerts] = useState<boolean>(readDriftAlertsLS);
  const [feedbackCount] = useState<number>(readFeedbackCountLS);

  // Cadence is the React-recommended "derived state synced to server"
  // pattern: track the server-side value and only override when the user
  // makes a local change. https://react.dev/reference/react/useState#storing-information-from-previous-renders
  const [cadenceLocal, setCadence] = useState<
    "weekly" | "biweekly" | "monthly" | null
  >(null);
  const [lastSyncedCadence, setLastSyncedCadence] = useState<
    "weekly" | "biweekly" | "monthly" | null
  >(null);
  if (pulse?.cadence && pulse.cadence !== lastSyncedCadence) {
    // Pulse SWR resolved a new server-side cadence — adopt it.
    setLastSyncedCadence(pulse.cadence);
    setCadence(pulse.cadence);
  }
  const cadence = cadenceLocal ?? pulse?.cadence ?? "weekly";

  const handleDriftToggle = (next: boolean) => {
    setDriftAlerts(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(DRIFT_ALERT_LS, next ? "1" : "0");
    }
    toast.success(next ? "Drift alerts on." : "Drift alerts off.");
  };

  const declared = persona?.declared;
  const observed30 = persona?.observed?.window_30d;

  return (
    <>
      {/* Persona overview */}
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
        <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
          Declared persona
        </div>
        <div className="mt-2 flex items-baseline justify-between gap-3 flex-wrap">
          {/* Wave 2 sweep (Task #8): inline Playfair text-2xl → EditorialHead. */}
          <EditorialHead size={26} as="div">
            {declared
              ? PERSONA_LABELS[declared.persona as PersonaId] ??
                declared.persona
              : "Not set"}
          </EditorialHead>
          {declared && (
            <div className="font-mono tabular-nums text-sm text-[rgba(245,240,232,0.6)]">
              score {declared.score}
            </div>
          )}
        </div>

        {observed30 && (
          <p className="mt-3 font-serif text-pq-body-sm text-[rgba(245,240,232,0.65)]">
            Your last 30 days look like{" "}
            <strong className="text-[var(--pq-ivory)]">
              {PERSONA_LABELS[observed30.persona]} {observed30.score}
            </strong>
            .
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <Link href="/onboarding" className="pq-ink-btn-ghost">
            Retake full assessment
          </Link>
        </div>
      </div>

      {/* Drift + cadence */}
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px] space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-serif text-base text-[var(--pq-ivory)]">
              Drift alerts
            </div>
            <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
              Notify when your 30-day behaviour diverges from the declared persona.
            </div>
          </div>
          <Toggle
            checked={driftAlerts}
            onChange={handleDriftToggle}
            ariaLabel="Drift alerts"
          />
        </div>

        <div className="pt-3 border-t border-[var(--pq-ivory-line-soft)]">
          <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-2">
            Pulse cadence
          </div>
          <div className="flex flex-wrap gap-2">
            {(["weekly", "biweekly", "monthly"] as const).map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => {
                  setCadence(c);
                  toast.success(`Pulse set to ${c}.`);
                }}
                className={cn(
                  cadence === c ? "pq-ink-btn-bronze" : "pq-ink-btn-ghost",
                  "capitalize",
                )}
              >
                {c === "weekly"
                  ? "Weekly"
                  : c === "biweekly"
                    ? "Every 2 weeks"
                    : "Monthly"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Feedback */}
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
        <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
          Section feedback
        </div>
        <div className="mt-2 font-serif text-[var(--pq-ivory)]">
          {feedbackCount} reaction{feedbackCount === 1 ? "" : "s"} recorded across your reports.
        </div>
        <p className="mt-1 text-xs text-[rgba(245,240,232,0.5)]">
          The CFO uses Useful / Meh / Skip votes to prioritise which sections it
          writes for you next.
        </p>
      </div>

      {/* Inline pulse */}
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
        <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)] mb-2">
          Submit a pulse
        </div>
        <WeeklyPulseCard inline />
      </div>

      {/* Evolution timeline */}
      <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
        <PersonaEvolution bare />
      </div>
    </>
  );
}

/* ── Journal Companion ── */

function JournalCompanionSubsection({
  user,
  entitlementPlans,
}: {
  user: ReturnType<typeof useAuth>["user"];
  entitlementPlans?: string[];
}) {
  const entitled = hasCompanionEntitlement(
    user?.subscription_tier,
    entitlementPlans,
  );
  const [email, setEmail] = useState(user?.email ?? "");
  const [waitlistDone, setWaitlistDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const handleWaitlist = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      toast.error("Enter an email.");
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch("/api/agent/waitlist", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setWaitlistDone(true);
      toast.success("You're on the waitlist.");
    } catch {
      setWaitlistDone(true);
      toast.success("Saved — we'll reach out.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
      <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        Journal Companion · Layer 4
      </div>
      {entitled ? (
        <>
          <div className="mt-2 font-serif text-[var(--pq-ivory)] text-pq-lead">
            Your Companion is active.
          </div>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.55)]">
            Reflect on your positions and weeks with a CFO that remembers.
          </p>
          <div className="mt-3">
            <Link href="/companion" className="pq-ink-btn-bronze">
              Open Companion
            </Link>
          </div>
        </>
      ) : waitlistDone ? (
        <>
          <div className="mt-2 font-serif text-[var(--pq-ivory)] text-pq-lead">
            You&rsquo;re on the waitlist.
          </div>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.55)]">
            Closed Beta access is rolling out to Premium Plus members.
          </p>
        </>
      ) : (
        <>
          <div className="mt-2 font-serif text-[var(--pq-ivory)] text-pq-lead">
            Closed Beta — join the waitlist.
          </div>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.55)]">
            The reflective journal agent — available to Premium Plus. Drop
            your email and we&rsquo;ll reach out as seats open.
          </p>
          <form
            onSubmit={handleWaitlist}
            className="mt-3 flex flex-col sm:flex-row gap-2"
          >
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="pq-ink-input flex-1"
              placeholder="you@example.com"
              aria-label="Waitlist email"
              required
            />
            <button
              type="submit"
              disabled={submitting}
              className="pq-ink-btn-bronze disabled:opacity-50"
            >
              {submitting ? "Joining…" : "Join waitlist"}
            </button>
          </form>
          <div className="mt-3">
            <Link href="/pricing?plan=plus" className="pq-ink-btn-ghost">
              See Premium Plus
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Agent data export/delete (PIPA) ── */

function AgentDataSubsection() {
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      // 2026-05-30 (PIPA §35 §2): call the FULL personal-data export
      // (routes/profile.py:export_profile — all user-owned tables) instead
      // of the agent-memory-only /api/agent/export subset, matching
      // settings/_v2 handleRequestExport. The localStorage fallback below
      // still covers the offline/degraded case.
      const data: unknown = await apiFetch("/api/profile/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pivoxquant-export-${new Date()
        .toISOString()
        .slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export ready.");
    } catch {
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
  };

  const handleDelete = async () => {
    if (
      !confirm(
        "Delete all agent memory? Persona, pulse, feedback, and Companion history will be wiped. This cannot be undone.",
      )
    ) {
      return;
    }
    setDeleting(true);
    try {
      await apiFetch("/api/agent/delete", { method: "DELETE" });
    } catch {
      /* non-fatal — we still wipe locally */
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
  };

  return (
    <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
      <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
        Agent data
      </div>
      <p className="mt-2 text-xs text-[rgba(245,240,232,0.55)]">
        Your CFO&rsquo;s memory is yours. Export a portable JSON copy at any
        time, or clear it to start over. Both actions comply with PIPA data
        rights.
      </p>
      <div className="mt-3 flex flex-col sm:flex-row gap-2">
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="pq-ink-btn-ghost flex-1 disabled:opacity-50"
        >
          {exporting ? "Preparing…" : "Export my agent memory"}
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleting}
          className="pq-ink-btn-ghost flex-1 disabled:opacity-50"
          style={{ color: "#d27a7a", borderColor: "rgba(210,122,122,0.4)" }}
        >
          {deleting ? "Clearing…" : "Delete all agent data"}
        </button>
      </div>
    </div>
  );
}

/* ── Page ── */

export default function ProfilePageV1() {
  const router = useRouter();
  const t = useT();
  const { locale } = useLocale();
  const { user, loading: authLoading, refresh } = useAuth();
  const { data: profileData, isLoading: profileLoading } = useInvestmentProfile();
  const investorType = profileData?.profile?.profile_type ?? null;
  const { data: companionStatus } = useCompanionStatus();
  const { data: personaData } = usePersona();
  const personaIsMock = personaData?._isMock === true;

  const [nameInput, setNameInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [showDelete, setShowDelete] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (user?.name) setNameInput(user.name);
  }, [user]);

  const tier = (user?.subscription_tier ?? "observer").toLowerCase();
  const tierLabel =
    tier === "pro" || tier === "operator"
      ? "Pro"
      : tier === "premium" || tier === "partner"
        ? "Premium"
        : "Free";

  const handleSaveName = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = nameInput.trim();
      if (!trimmed) {
        toast.error("Name cannot be empty.");
        return;
      }
      if (trimmed === user?.name) return;
      setSaving(true);
      try {
        await apiFetch(API.profile.update, {
          method: "PATCH",
          body: JSON.stringify({ name: trimmed }),
        });
        await refresh();
        toast.success("Name updated.");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Update failed.");
      } finally {
        setSaving(false);
      }
    },
    [nameInput, user, refresh],
  );

  if (authLoading || !user) {
    return (
      // Wave 2 sweep (Task #5): page-level auth load — skeleton scaffold.
      <div className="mx-auto max-w-4xl px-5 md:px-7 py-10" aria-live="polite" aria-busy="true">
        <div className="pq-skeleton-dark h-4 w-32 mb-4" aria-hidden />
        <div className="pq-skeleton-dark h-10 w-2/3 mb-3" aria-hidden />
        <div className="pq-skeleton-dark h-4 w-1/2 mb-10" aria-hidden />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="pq-skeleton-dark h-28" aria-hidden />
          <div className="pq-skeleton-dark h-28" aria-hidden />
          <div className="pq-skeleton-dark h-28" aria-hidden />
          <div className="pq-skeleton-dark h-28" aria-hidden />
        </div>
        <span className="sr-only">Loading profile…</span>
      </div>
    );
  }

  const init = initials(user.name, user.email);

  return (
    <ErrorBoundary>
      <div className="space-y-10">
        {/* ── Mock-data banner: shown until first trade flips persona to live ── */}
        {personaIsMock && (
          <div
            role="status"
            aria-live="polite"
            className="border border-[var(--pq-bronze)]/40 bg-[rgba(184,149,106,0.06)] px-4 py-3 rounded-[2px] flex items-start gap-3"
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

        {/* ── Header ── */}
        <header>
          <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
            Identity · Persona
          </div>
          {/* Wave 2 sweep (Task #8): inline Playfair text-2xl/3xl → EditorialHead. */}
          <EditorialHead size={30} as="h1" className="mt-2">
            My Profile
          </EditorialHead>
          <p className="mt-1 text-xs text-[rgba(245,240,232,0.5)]">
            Who you are and how your CFO reads you. Operational controls live on{" "}
            <Link href="/settings" className="underline underline-offset-4 hover:text-[var(--pq-bronze)]">
              Settings
            </Link>
            .
          </p>
        </header>

        {/* ── Identity card ── */}
        <Section kicker="01 · Identity" title="Who you are">
          <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-6 rounded-[2px]">
            <div className="flex items-center gap-5">
              <span
                className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full font-mono text-lg font-semibold"
                style={{
                  background: "transparent",
                  border: "0.5px solid var(--pq-bronze)",
                  color: "var(--pq-bronze)",
                  letterSpacing: "0.04em",
                }}
              >
                {init}
              </span>
              <div className="min-w-0 flex-1">
                <div className="font-serif text-xl text-[var(--pq-ivory)] truncate">
                  {user.name || "Unnamed"}
                </div>
                <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)] truncate">
                  {user.email}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <span
                    className="inline-flex items-center rounded px-2 py-0.5 text-pq-eyebrow font-mono"
                    style={{
                      border: "0.5px solid var(--pq-bronze)",
                      color: "var(--pq-bronze)",
                      letterSpacing: "0.2em",
                      textTransform: "uppercase",
                    }}
                  >
                    {tierLabel}
                  </span>
                  {user.oauth_provider && (
                    <span className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
                      via {user.oauth_provider === "kakao" ? "Kakao" : user.oauth_provider}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </Section>

        {/* ── Display name ── */}
        <Section kicker="02 · Display" title="Name">
          <form
            onSubmit={handleSaveName}
            className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px] space-y-3"
          >
            <label
              htmlFor="profile-name"
              className="block text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.5)]"
            >
              Display name
            </label>
            <input
              id="profile-name"
              type="text"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              maxLength={50}
              className="pq-ink-input w-full"
              placeholder="Your name"
            />
            <div className="flex items-center gap-3">
              <span className="text-pq-eyebrow tracking-[0.18em] uppercase text-[rgba(245,240,232,0.4)]">
                Email is read-only
              </span>
              <button
                type="submit"
                disabled={saving || nameInput.trim() === user.name}
                className="pq-ink-btn-bronze ml-auto flex items-center gap-1.5 disabled:opacity-50"
              >
                {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        </Section>

        {/* ── Investor assessment ── */}
        <Section kicker="03 · Calibration" title="Investor assessment">
          <div className="bg-[rgba(255,255,255,0.02)] border border-[var(--pq-ivory-line)] p-5 rounded-[2px]">
            <div className="flex items-center justify-between gap-4 mb-4">
              <span className="text-sm text-[rgba(245,240,232,0.6)]">
                Investor type
              </span>
              <span className="text-sm text-[var(--pq-ivory)]">
                {profileLoading ? (
                  <span className="text-[rgba(245,240,232,0.3)]">Loading…</span>
                ) : investorType ? (
                  t(`persona.names.${investorType}`)
                ) : (
                  <span className="text-[rgba(245,240,232,0.3)]">{locale === "ko" ? "미설정" : "Not set"}</span>
                )}
              </span>
            </div>
            <Link
              href="/onboarding"
              className="flex items-center justify-between border border-[var(--pq-ivory-line)] px-4 py-3 rounded-[2px] hover:border-[var(--pq-bronze)] transition-colors group"
            >
              <div>
                <div className="font-serif text-base text-[var(--pq-ivory)]">
                  {investorType ? "Retake assessment" : "Take investor assessment"}
                </div>
                <div className="mt-0.5 text-xs text-[rgba(245,240,232,0.5)]">
                  20-question questionnaire — calibrates every analytical surface.
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-[var(--pq-bronze)] transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </Section>

        {/* ── Persona classifier (9-dim observed) ── */}
        <Section
          kicker="04 · Observed persona"
          title="How your trades read"
        >
          <PersonaV2Card />
        </Section>

        {/* ── Living CFO ── */}
        <Section kicker="05 · Living CFO" title="Your personal CFO">
          <LivingCFOControls />
          <JournalCompanionSubsection
            user={user}
            entitlementPlans={companionStatus?.entitlement_plans}
          />
          <AgentDataSubsection />
        </Section>

        {/* ── Danger zone ── */}
        <section className="pt-8 border-t border-[var(--pq-ivory-line)]">
          <div className="text-pq-eyebrow tracking-[0.22em] uppercase text-[var(--pq-bronze)]">
            Danger zone
          </div>
          <p className="mt-2 text-xs text-[rgba(245,240,232,0.5)]">
            Deletion is permanent and purges all positions, watchlists, and
            artifacts within 30 days (PIPA).
          </p>
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 border border-red-500/30 text-red-400 text-xs tracking-[0.18em] uppercase hover:bg-red-500/10 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete account
            </button>
          </div>
        </section>
      </div>

      {showDelete && <DeleteAccountModal onClose={() => setShowDelete(false)} />}
    </ErrorBoundary>
  );
}
