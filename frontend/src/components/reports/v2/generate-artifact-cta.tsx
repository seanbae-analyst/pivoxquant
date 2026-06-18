"use client";

/**
 * <GenerateArtifactCta /> — 3 horizontal request tiles. On click the
 * tile POSTs to `generateArtifact()` and surfaces a toast-style status
 * line. The unified endpoint is SYNCHRONOUS — status "ready" on resolve
 * means the artifact is already in the archive (the SPEC-era job-queue
 * shape never shipped).
 *
 * Tier gating: Earnings Pre-Brief / Risk Board are Pro-only. Brag Card
 * is free-tier.
 *
 * Source: design-mockups/reports-v2/SPEC.md §4 (+ 2026-06-11 resolution
 * note: the old "Risk Note" free-text tile posted type "risk_report",
 * which never existed in the backend dispatch → 400 on every click. The
 * tile now runs the existing Pro `risk_board` deck, which already carries
 * the advertised VaR / drawdown / tail-risk / sector-exposure content.
 * The free-text memo concept is dropped pending counsel review — a
 * personalized free-text AI answer is 투자자문-adjacent).
 *
 * Legal: pure desk metaphor — no banned vocabulary. Description text
 * is reviewed copy, no recommend/advice tokens.
 */

import * as React from "react";
import Link from "next/link";
import { Lock } from "lucide-react";
import { toast } from "sonner";
import { useSWRConfig } from "swr";
import {
  generateArtifact,
  useArtifacts,
  type GenerateArtifactBody,
} from "@/lib/hooks";
import { API } from "@/lib/endpoints";
import type { ArtifactType } from "@/lib/types";
import type { Tier } from "./artifact-kind-card";

const TIER_RANK: Record<Tier, number> = { free: 0, pro: 1, premium: 2 };
function hasAccess(userTier: Tier, required: Tier): boolean {
  return TIER_RANK[userTier] >= TIER_RANK[required];
}

interface RequestTile {
  /** Display name (Playfair 20 ivory). */
  displayName: string;
  /** Mono dim sub-line. */
  subLine: string;
  /** Source Serif 13 description. */
  description: string;
  /** Bronze CTA label. */
  ctaLabel: string;
  /** Backend artifact type to generate. */
  type: ArtifactType;
  /** Optional ticker prompt — when present we ask for input. */
  needsTicker?: boolean;
  /** Minimum tier. */
  minTier: Tier;
}

/** status:"empty" reason enums → display copy (observational, no advice). */
const EMPTY_COPY: Record<string, string> = {
  no_positions: "Your book is empty — add a position first.",
  no_trades: "No trades on record for this period yet.",
  not_in_portfolio: "That ticker isn't in your book or watchlist.",
  no_upcoming_earnings: "No upcoming earnings date on file for that ticker.",
};
const EMPTY_FALLBACK = "Nothing to draft for this period yet.";

const TILES: RequestTile[] = [
  {
    displayName: "Brag Card",
    subLine: "Current quarter · 3 trades, 1 chart",
    description:
      "Compose a quarter-to-date brag card — what worked, in language that fits a one-on-one.",
    ctaLabel: "Generate now ›",
    type: "monthly_brag",
    minTier: "free",
  },
  {
    displayName: "Earnings Pre-Brief",
    subLine: "Per ticker · 24h before print",
    description:
      "Queue a pre-brief on the next earnings date for a ticker in your book or watchlist.",
    ctaLabel: "Queue pre-brief ›",
    type: "earnings_prebrief",
    needsTicker: true,
    minTier: "pro",
  },
  {
    // 2026-06-11: was the "Risk Note" free-text tile posting the
    // never-built "risk_report" type (dead on click — 400 before any
    // tier gate). Re-pointed at the existing risk_board deck.
    displayName: "Risk Board",
    subLine: "Current book · 8-page deck",
    description:
      "Run the risk deck on your current book — VaR, max drawdown, tail ratio, sector concentration, the 7-layer check.",
    ctaLabel: "Run the board ›",
    type: "risk_board",
    minTier: "pro",
  },
];

interface Props {
  tier: Tier;
}

interface TileState {
  status: "idle" | "queueing" | "queued" | "done" | "error";
  message?: string;
}

export function GenerateArtifactCta({ tier }: Props) {
  const [states, setStates] = React.useState<Record<string, TileState>>({});
  const [inputs, setInputs] = React.useState<Record<string, string>>({});
  const { mutate: globalMutate } = useSWRConfig();

  // P0-3 (2026-05-20 ux-flow fix): the old flow ended at "Queued · ETA ~Ns"
  // and never closed the loop — no completion feedback, no scroll to the
  // result. We now (a) revalidate the shared artifacts cache after queueing,
  // (b) watch for a NEW artifact of the queued tile's type to appear, and
  // (c) when it lands, toast + scroll the just-out card into view so the
  // "aha" moment completes.
  //
  // BUG (2026-05-20 frontend bug-hunt) fixes:
  //   Fix 1 — key drift: this tile read `limit:999` (key
  //     `/api/artifacts/list?limit=999`) but <LivingCFOStatusBar/> +
  //     <ArtifactQueue/> read `/api/artifacts/list` (no limit). mutating only
  //     our key left the badge/queue stale. We now mutate ALL keys that start
  //     with `/api/artifacts/list` via the SWR global mutate key-matcher so
  //     every consumer of the artifact archive revalidates together.
  //   Fix 2 — premature "done": completion was a raw count delta keyed off a
  //     baseline captured at click time, which was 0 before SWR resolved →
  //     the very first SWR resolve (0→N) tripped a false success toast before
  //     any job ran. We now snapshot the set of existing artifact ids at
  //     queue time and only resolve a tile when a NEW id of its matching type
  //     appears.
  //   Fix 3 — fan-out false completion: a single +1 used to resolve EVERY
  //     pending tile. Identity matching by artifact `type` resolves only the
  //     tile whose artifact actually landed.
  //
  // We keep the page's `limit:999` read shape for the full archive snapshot
  // (so identity matching sees every row), but invalidation is key-prefix
  // wide so no consumer is left stale.
  const { artifacts } = useArtifacts({
    type: "all",
    since: "all",
    limit: 999,
  });

  // Revalidate every SWR cache entry whose key targets the artifacts list,
  // regardless of query-string (limit / type / since). Closes the
  // key-drift staleness between this CTA, the status bar, and the queue.
  const revalidateAllArtifacts = React.useCallback(() => {
    void globalMutate(
      (key) => typeof key === "string" && key.startsWith(API.artifacts.list),
      undefined,
      { revalidate: true },
    );
  }, [globalMutate]);

  // Tiles currently waiting on a backend job. For each we record the artifact
  // type it produces and the set of artifact ids that already existed when it
  // was queued — a NEW id of that type means this specific tile completed.
  const pendingRef = React.useRef<
    Record<
      string,
      { type: ArtifactType; label: string; knownIds: Set<number> }
    >
  >({});

  // Poll the artifacts list a few times after a queue so the async job result
  // surfaces without waiting for the next 30s SWR dedupe window.
  const pollTimers = React.useRef<ReturnType<typeof setTimeout>[]>([]);
  React.useEffect(() => {
    const timers = pollTimers.current;
    return () => {
      timers.forEach(clearTimeout);
    };
  }, []);

  const scrollToLatest = React.useCallback(() => {
    if (typeof document === "undefined") return;
    const el = document.getElementById("latest-heading");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, []);

  // Completion detection by artifact identity: when a NEW artifact whose
  // `type` matches a pending tile appears in the archive, resolve only that
  // tile. No count-delta heuristic → no premature toast (Fix 2) and no
  // cross-tile fan-out (Fix 3).
  React.useEffect(() => {
    const pendingKeys = Object.keys(pendingRef.current);
    if (pendingKeys.length === 0) return;

    let resolvedLabel: string | null = null;
    for (const key of pendingKeys) {
      const entry = pendingRef.current[key];
      const fresh = artifacts.find(
        (a) => a.type === entry.type && !entry.knownIds.has(a.id),
      );
      if (fresh) {
        resolvedLabel = entry.label;
        delete pendingRef.current[key];
        setStates((s) => ({
          ...s,
          [key]: { status: "done", message: "Ready · in your archive ↑" },
        }));
      }
    }
    if (resolvedLabel) {
      toast.success(`${resolvedLabel} is ready`, {
        description: "Drafted by AI · review it in the archive above.",
      });
      scrollToLatest();
    }
  }, [artifacts, scrollToLatest]);

  const handleGenerate = React.useCallback(
    async (tile: RequestTile) => {
      const inputValue = inputs[tile.type]?.trim() ?? "";
      const body: GenerateArtifactBody = { type: tile.type };
      if (tile.needsTicker) {
        if (!inputValue) {
          setStates((s) => ({
            ...s,
            [tile.type]: {
              status: "error",
              message: "Enter a ticker first.",
            },
          }));
          return;
        }
        body.ticker = inputValue.toUpperCase();
      }
      setStates((s) => ({
        ...s,
        [tile.type]: { status: "queueing" },
      }));
      try {
        const r = await generateArtifact(body);
        // 2026-06-11: handle the REAL (synchronous) response shape. The old
        // code read an ETA field from a job-queue contract that never
        // shipped → "ETA ~undefineds" copy, and an `empty` response left the
        // tile stuck on "Drafting…" forever.
        if (r.status === "ready") {
          // The artifact row already exists — resolve immediately.
          setStates((s) => ({
            ...s,
            [tile.type]: {
              status: "done",
              message: "Ready · in your archive ↑",
            },
          }));
          toast.success(`${tile.displayName} is ready`, {
            description: "Drafted by AI · review it in the archive above.",
          });
          revalidateAllArtifacts();
          scrollToLatest();
          return;
        }
        if (r.status === "empty") {
          // Nothing to draft (new book / no trades / unknown ticker) — a
          // terminal outcome, not a pending job.
          setStates((s) => ({
            ...s,
            [tile.type]: {
              status: "error",
              message:
                (r.reason && EMPTY_COPY[r.reason]) || EMPTY_FALLBACK,
            },
          }));
          return;
        }
        // Fallback — unknown/future async status: keep the identity-watch
        // path. Register this tile as awaiting completion. Snapshot the
        // artifact ids that exist right now so a NEW id of this tile's type
        // is what resolves it (identity match, not count delta).
        setStates((s) => ({
          ...s,
          [tile.type]: {
            status: "queued",
            message: "Queued · drafting now",
          },
        }));
        pendingRef.current[tile.type] = {
          type: tile.type,
          label: tile.displayName,
          knownIds: new Set(artifacts.map((a) => a.id)),
        };
        toast(`${tile.displayName} queued`, {
          description:
            "The desk is drafting it — it'll appear in the archive above.",
        });
        // Revalidate every artifacts-list cache key a few times so the async
        // job's output surfaces promptly across this CTA, the status bar, and
        // the queue; the identity-watch effect closes the loop.
        [8_000, 16_000, 28_000].forEach((delay) => {
          pollTimers.current.push(
            setTimeout(() => {
              revalidateAllArtifacts();
            }, delay),
          );
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Backend offline";
        setStates((s) => ({
          ...s,
          [tile.type]: {
            status: "error",
            message: msg.includes("404")
              ? "Coming soon — backend pending."
              : msg,
          },
        }));
      }
    },
    [inputs, artifacts, revalidateAllArtifacts, scrollToLatest],
  );

  return (
    <section
      aria-labelledby="ask-heading"
      style={{ marginTop: "clamp(48px, 8vw, 80px)" }}
    >
      <h2
        id="ask-heading"
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: "clamp(26px, 3.4vw, 40px)",
          lineHeight: 1.1,
          color: "var(--pq-ivory, #F5F0E8)",
          margin: "0 0 12px",
        }}
      >
        Ask the desk.
      </h2>
      <p
        className="font-serif"
        style={{
          fontSize: "var(--pq-text-body)",
          lineHeight: 1.6,
          color: "rgba(245,240,232,0.7)",
          margin: "0 0 24px",
          maxWidth: 620,
        }}
      >
        Three on-demand artifacts. Drafted by AI, reviewed by you before the file
        ever leaves the archive.
      </p>

      {/* BUG Fix 4 (2026-05-20): the previous `md:!grid-cols-1` was inverted —
          Tailwind `md:` is min-width 768px (mobile-first), so it forced ONE
          column on desktop while the inline `repeat(3, …)` stayed 3-up on
          mobile (<768px) → 375px overflow. Switched to the proven max-width
          `<style jsx>` collapse used by home/_v2/page-v2.tsx: 3-up desktop,
          1-up mobile. */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
        }}
        className="pq-artifact-cta-grid"
      >
        {TILES.map((tile) => {
          const locked = !hasAccess(tier, tile.minTier);
          const state = states[tile.type] ?? { status: "idle" as const };
          return (
            <div
              key={tile.type + tile.displayName}
              style={{
                border:
                  "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
                borderRadius: 4,
                padding: 24,
                background: "rgba(255,255,255,0.02)",
                position: "relative",
                opacity: locked ? 0.7 : 1,
              }}
            >
              {locked && (
                <div
                  aria-hidden="true"
                  style={{ position: "absolute", top: 14, right: 14 }}
                >
                  <Lock
                    className="h-3.5 w-3.5"
                    style={{ color: "var(--pq-bronze, #B8956A)" }}
                  />
                </div>
              )}

              {/* 종목명 main pattern */}
              <h3
                className="font-display"
                style={{
                  fontWeight: 500,
                  fontSize: "var(--pq-text-h4)",
                  color: "var(--pq-ivory, #F5F0E8)",
                  margin: 0,
                  lineHeight: 1.2,
                }}
              >
                {tile.displayName}
              </h3>
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.18em",
                  color: "rgba(245,240,232,0.45)",
                  marginTop: 4,
                }}
              >
                {tile.subLine}
              </div>

              <p
                className="font-serif"
                style={{
                  fontSize: "var(--pq-text-body)",
                  lineHeight: 1.55,
                  color: "rgba(245,240,232,0.7)",
                  margin: "14px 0 16px",
                }}
              >
                {tile.description}
              </p>

              {tile.needsTicker && !locked && (
                <input
                  type="text"
                  value={inputs[tile.type] ?? ""}
                  onChange={(e) =>
                    setInputs((s) => ({ ...s, [tile.type]: e.target.value }))
                  }
                  placeholder="AAPL"
                  aria-label={`Ticker symbol for ${tile.displayName}`}
                  className="font-mono pq-input-noom-xs"
                  style={{
                    width: "100%",
                    background: "rgba(0,0,0,0.3)",
                    border:
                      "1px solid var(--pq-hairline-ink, var(--pq-ivory-line))",
                    borderRadius: 2,
                    color: "var(--pq-ivory, #F5F0E8)",
                    padding: "8px 10px",
                    marginBottom: 12,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                  }}
                />
              )}

              {locked ? (
                <Link
                  href="/pricing"
                  className="pq-ink-btn-bronze inline-flex"
                  style={{ fontSize: "var(--pq-text-eyebrow)", letterSpacing: "0.18em" }}
                >
                  Upgrade to {tile.minTier}
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => handleGenerate(tile)}
                  disabled={state.status === "queueing"}
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.18em",
                    color: "var(--pq-bronze, #B8956A)",
                    background: "transparent",
                    border: "none",
                    borderBottom:
                      "1px solid var(--pq-bronze-15, rgba(184,149,106,0.15))",
                    paddingBottom: 2,
                    cursor:
                      state.status === "queueing" ? "wait" : "pointer",
                  }}
                >
                  {state.status === "queueing"
                    ? "Queueing…"
                    : state.status === "queued"
                      ? "Drafting…"
                      : state.status === "done"
                        ? "Generate again ›"
                        : tile.ctaLabel}
                </button>
              )}

              {state.status !== "idle" && (
                <div
                  aria-live="polite"
                  className="font-mono uppercase"
                  style={{
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.18em",
                    color:
                      state.status === "error"
                        ? "var(--pq-negative, #d18888)"
                        : state.status === "done"
                          ? "var(--pq-positive)"
                          : "rgba(245,240,232,0.55)",
                    marginTop: 12,
                  }}
                >
                  {state.message}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Mobile collapse: 3-up desktop → 1-up under 768px (mobile-first
          375px no longer overflows). Mirrors home/_v2/page-v2.tsx. */}
      <style jsx>{`
        @media (max-width: 767px) {
          .pq-artifact-cta-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </section>
  );
}

export default GenerateArtifactCta;
