"use client";

/**
 * <ArtifactQueue /> — "Today's Artifacts" card.
 *
 * Four rows, one per artifact category, each with its own micro-status:
 *   1. Today's Morning Brief     — delivered time + read-state
 *   2. Current Portfolio Journal — last entry date
 *   3. Next Weekly Memo          — day-of-week + countdown
 *   4. Journal Companion         — last conversation or Closed-Beta lock
 *
 * Ivory-on-ink dossier styling. Each row hover lifts a bronze glow and
 * reveals an "open →" affordance. Rendered inside the Dossier Desk.
 *
 * Observational only. No predictive/recommendation language.
 */

import * as React from "react";
import Link from "next/link";
import useSWR from "swr";
import { ArrowUpRight, Lock, Check, Clock, FileText, BookHeart } from "lucide-react";

import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { API } from "@/lib/endpoints";
import { useArtifacts } from "@/lib/hooks";
import {
  useCompanionStatus,
  hasCompanionEntitlement,
  useCompanionHistory,
} from "@/lib/cfo/useCompanion";

// BriefToday shape removed 2026-04-29 — Morning Brief backend deprecated.

const fetcher = <T,>(url: string) => apiFetch<T>(url);

/* ── Countdown helpers ── */

function nextMondayKst(ref: Date): Date {
  // 07:00 KST on the next Monday, returned as an absolute Date.
  // 07:00 KST ≡ 22:00 UTC the day before.
  const d = new Date(ref.getTime());
  d.setUTCSeconds(0, 0);
  const dayUtc = d.getUTCDay(); // 0=Sun..6=Sat
  // target weekday in UTC that corresponds to Monday 07:00 KST is Sunday 22:00 UTC.
  const deltaDays = (7 + 0 - dayUtc) % 7; // 0 = Sunday
  const nextSundayUtc = new Date(d.getTime());
  nextSundayUtc.setUTCDate(d.getUTCDate() + deltaDays);
  nextSundayUtc.setUTCHours(22, 0, 0, 0);
  if (nextSundayUtc.getTime() <= ref.getTime()) {
    nextSundayUtc.setUTCDate(nextSundayUtc.getUTCDate() + 7);
  }
  return nextSundayUtc;
}

function relativeFuture(to: Date, from: Date): string {
  const ms = to.getTime() - from.getTime();
  if (ms <= 0) return "imminent";
  const d = Math.floor(ms / 86_400_000);
  const h = Math.floor((ms % 86_400_000) / 3_600_000);
  if (d >= 1) return `${d}d ${h}h`;
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return `${h}h ${m}m`;
}

function relativePast(iso: string, from: Date): string {
  const ms = from.getTime() - new Date(iso).getTime();
  if (ms < 60_000) return "just now";
  const m = Math.floor(ms / 60_000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

/* ─────────────────────────────────────────────────────────────── */

interface QueueRow {
  id: string;
  label: string;
  title: string;
  meta: string;
  href: string;
  locked?: boolean;
  Icon: React.ComponentType<{ className?: string }>;
  /** Optional state pill: pre-computed short label (e.g. "Read", "Draft"). */
  state?: { kind: "ready" | "waiting" | "locked" | "done"; text: string };
}

export function ArtifactQueue() {
  const { user } = useAuth();
  const [now, setNow] = React.useState<Date>(() => new Date());
  React.useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  // Morning Brief SWR call removed 2026-04-29 — backend deprecated.
  void fetcher;

  // "Portfolio Journal" is represented today by the Weekly Memo artifact
  // archive — pull the latest row of any type.
  //
  // BUG-8 FIX 3: key unified with <LivingCFOStatusBar/> (both now call
  // useArtifacts({type:"all", since:"all"})) so SWR dedupes them to a
  // single /api/artifacts request. Previously this used
  // `{since:"90d", limit:5}` → separate cache key → two concurrent
  // requests on /home mount. We only consume `artifacts[0]` here, and
  // the full-archive response is already small (user-scoped), so the
  // extra rows are negligible bytes.
  const { artifacts } = useArtifacts({ type: "all", since: "all" });

  const { data: companionStatus } = useCompanionStatus();
  const { messages } = useCompanionHistory();

  const companionEntitled = hasCompanionEntitlement(
    user?.subscription_tier,
    companionStatus?.entitlement_plans,
  );

  /* ── Row 1 (Morning Brief) — REMOVED 2026-04-29.
   * Morning Brief artifact stream deprecated. The first row now leads with
   * Portfolio Journal so this surface continues to render four rows when
   * the companion is included; otherwise three. ── */

  /* ── Row 2: Portfolio Journal (= last artifact overall) ── */
  const lastArtifact = artifacts[0];
  const journalRow: QueueRow = {
    id: "journal",
    label: "Portfolio Journal",
    title: lastArtifact?.title || "No entry yet",
    meta: lastArtifact
      ? `Last entry ${relativePast(lastArtifact.sent_at, now)}`
      : "Your first journal will appear after Monday's memo.",
    href: "/reports",
    Icon: FileText,
    state: lastArtifact
      ? { kind: "done", text: "Logged" }
      : { kind: "waiting", text: "Pending" },
  };

  /* ── Row 3: Next Weekly Memo countdown ── */
  const nextMonday = nextMondayKst(now);
  const memoDay = nextMonday.toLocaleDateString("en-US", {
    weekday: "long",
    timeZone: "Asia/Seoul",
  });
  const memoRow: QueueRow = {
    id: "memo",
    label: "Next Weekly Memo",
    title: `${memoDay} · 07:00 KST`,
    meta: `In ${relativeFuture(nextMonday, now)}`,
    href: "/reports",
    Icon: Clock,
    state: { kind: "waiting", text: "Queued" },
  };

  /* ── Row 4: Companion (beta-gated) ── */
  const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
  const lastCompanionTs = lastUserMsg?.ts;
  const companionRow: QueueRow = {
    id: "companion",
    label: "Journal Companion",
    title: lastCompanionTs
      ? truncate(lastUserMsg!.text, 60)
      : companionEntitled
        ? "Open a reflection"
        : "Closed Beta",
    meta: lastCompanionTs
      ? `Last chat ${relativePast(new Date(lastCompanionTs).toISOString(), now)}`
      : companionEntitled
        ? "Reflect on this week's moves."
        : "Premium Plus — join the waitlist.",
    href: companionEntitled ? "/companion" : "/pricing?plan=plus",
    Icon: BookHeart,
    locked: !companionEntitled,
    state: companionEntitled
      ? lastCompanionTs
        ? { kind: "done", text: "Active" }
        : { kind: "ready", text: "Open" }
      : { kind: "locked", text: "Locked" },
  };

  const rows: QueueRow[] = [journalRow, memoRow, companionRow];

  return (
    <section
      aria-label="Today's artifact queue"
      className="pq-artifact-queue"
      style={{
        background: "rgba(10,10,10,0.6)",
        border: "0.5px solid rgba(184,149,106,0.22)",
        borderRadius: 3,
        padding: "18px 18px 10px",
        boxShadow:
          "0 0 0 1px rgba(184,149,106,0.10), 0 16px 48px -20px rgba(0,0,0,0.85)",
      }}
    >
      <header className="flex items-baseline justify-between gap-3 mb-2">
        <div>
          <div
            className="font-mono uppercase text-[9.5px] tracking-[0.26em]"
            style={{ color: "var(--pq-bronze)" }}
          >
            Today · Artifact Queue
          </div>
          <h3
            className="mt-1 font-serif text-[17px]"
            style={{ color: "var(--pq-ivory)" }}
          >
            The four things your CFO is producing
          </h3>
        </div>
      </header>

      <ul className="divide-y divide-[rgba(245,240,232,0.06)]">
        {rows.map((row) => (
          <ArtifactRow key={row.id} row={row} />
        ))}
      </ul>
    </section>
  );
}

function ArtifactRow({ row }: { row: QueueRow }) {
  const { label, title, meta, href, locked, Icon, state } = row;
  const stateColor =
    state?.kind === "done"
      ? "#7db487"
      : state?.kind === "ready"
        ? "var(--pq-bronze)"
        : state?.kind === "locked"
          ? "rgba(245,240,232,0.35)"
          : "rgba(245,240,232,0.45)";

  return (
    <li>
      <Link
        href={href}
        className="group flex items-center gap-3 py-3 transition-colors hover:bg-[rgba(184,149,106,0.06)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(184,149,106,0.4)] rounded-[2px]"
        aria-label={`${label} — ${title}`}
      >
        <span
          className="flex items-center justify-center shrink-0 h-8 w-8 rounded-[2px]"
          style={{
            background: "rgba(184,149,106,0.08)",
            border: "0.5px solid rgba(184,149,106,0.22)",
            color: "var(--pq-bronze)",
          }}
          aria-hidden
        >
          {locked ? (
            <Lock className="h-3.5 w-3.5" />
          ) : (
            <Icon className="h-3.5 w-3.5" />
          )}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="font-mono uppercase text-[9.5px] tracking-[0.24em]"
              style={{ color: "var(--pq-bronze)" }}
            >
              {label}
            </span>
            {state && (
              <span
                className="font-mono uppercase text-[9px] tracking-[0.22em] px-1.5 py-[1px] rounded-[2px]"
                style={{
                  color: stateColor,
                  background: "rgba(245,240,232,0.03)",
                  border: `0.5px solid ${
                    state.kind === "done"
                      ? "rgba(125,180,135,0.35)"
                      : "rgba(184,149,106,0.22)"
                  }`,
                }}
              >
                {state.kind === "done" && (
                  <Check className="inline h-2.5 w-2.5 mr-1 -translate-y-[0.5px]" />
                )}
                {state.text}
              </span>
            )}
          </div>
          <div
            className="mt-0.5 font-serif text-[14px] leading-tight truncate"
            style={{ color: "var(--pq-ivory)" }}
          >
            {title}
          </div>
          <div
            className="mt-0.5 text-[11.5px]"
            style={{ color: "rgba(245,240,232,0.55)" }}
          >
            {meta}
          </div>
        </div>

        <span
          className="shrink-0 inline-flex items-center gap-1 font-mono uppercase text-[9px] tracking-[0.22em] opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: "var(--pq-bronze)" }}
        >
          open
          <ArrowUpRight className="h-3 w-3" />
        </span>
      </Link>
    </li>
  );
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1).trimEnd() + "…";
}

export default ArtifactQueue;
