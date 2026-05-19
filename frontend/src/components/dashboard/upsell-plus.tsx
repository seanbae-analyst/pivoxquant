"use client";

/**
 * <UpsellPlus /> — Premium Plus Founding-Lifetime strip.
 *
 * Rendered only for Free and Pro users. Hidden entirely when the
 * user already holds a `premium_plus` or `founding_lifetime` tier,
 * or when the Companion backend explicitly reports the feature as
 * disabled (defensive: no point advertising a locked flagship).
 *
 * Copy is observational — "is rolling out" / "join the waitlist" —
 * never "buy" / "you should". The countdown ("X of 200 remaining")
 * is mocked on the client with a stable derived number so the
 * strip doesn't flicker between renders.
 */

import * as React from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import { PQ_EASE, PQ_DUR_SLOW } from "@/lib/motion";
import { Sparkles, ArrowUpRight } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { hasCompanionEntitlement, useCompanionStatus } from "@/lib/cfo/useCompanion";

/** Mock — stable for the session.
 *  Seat count 183 / 200. Kept in a module-level const so it never
 *  mutates during a session. Backed by a real endpoint in a later
 *  release (see `/api/agent/status` extension plan). */
const FOUNDING_TOTAL = 200;
const FOUNDING_CLAIMED = 17; // 183 remaining
const FOUNDING_REMAINING = FOUNDING_TOTAL - FOUNDING_CLAIMED;

export function UpsellPlus() {
  const { user } = useAuth();
  const { data: status } = useCompanionStatus();
  const reduceMotion = useReducedMotion();

  const entitled = hasCompanionEntitlement(
    user?.subscription_tier,
    status?.entitlement_plans,
  );

  // Already on Plus+, or the feature is fully disabled → render nothing.
  if (entitled) return null;
  if (status && status.enabled === false && status.phase !== "closed_beta") {
    // still show during closed_beta — waitlist has value then.
    return null;
  }

  const progressPct = (FOUNDING_CLAIMED / FOUNDING_TOTAL) * 100;

  return (
    <motion.aside
      aria-label="Premium Plus founding seats"
      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
      animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: PQ_DUR_SLOW, ease: PQ_EASE }}
      className="pq-upsell-plus relative overflow-hidden rounded-[3px]"
      style={{
        background:
          "linear-gradient(96deg, rgba(10,10,10,0.92) 0%, rgba(20,14,8,0.92) 100%)",
        border: "0.5px solid rgba(184,149,106,0.28)",
        boxShadow:
          "0 0 0 1px rgba(184,149,106,0.10), 0 18px 56px -20px rgba(0,0,0,0.9)",
      }}
    >
      {/* soft aurora stripe, decorative */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 18% 50%, rgba(184,149,106,0.18) 0%, transparent 60%)",
          mixBlendMode: "screen",
        }}
      />

      <div className="relative flex flex-col sm:flex-row items-start sm:items-center gap-4 p-5 md:p-6">
        <span
          className="inline-flex items-center justify-center h-9 w-9 rounded-[2px] shrink-0"
          style={{
            background: "rgba(184,149,106,0.12)",
            border: "0.5px solid rgba(184,149,106,0.35)",
            color: "var(--pq-bronze)",
          }}
          aria-hidden
        >
          <Sparkles className="h-4 w-4" />
        </span>

        <div className="flex-1 min-w-0">
          <div
            className="font-mono uppercase text-pq-caption tracking-[0.26em]"
            style={{ color: "var(--pq-bronze)" }}
          >
            Living CFO · Layer 4 · Closed Beta
          </div>
          <p
            className="mt-1 font-serif text-pq-lead leading-snug"
            style={{ color: "var(--pq-ivory)", letterSpacing: "-0.005em" }}
          >
            Personal Journal Companion is rolling out to Premium Plus.
          </p>
          <div className="mt-3 flex items-center gap-3">
            <div
              className="relative h-[3px] flex-1 max-w-[240px] overflow-hidden"
              style={{ background: "var(--pq-ivory-line)" }}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={FOUNDING_TOTAL}
              aria-valuenow={FOUNDING_CLAIMED}
              aria-label="Founding seats claimed"
            >
              <motion.div
                className="absolute inset-y-0 left-0"
                initial={reduceMotion ? { width: `${progressPct}%` } : { width: 0 }}
                animate={{ width: `${progressPct}%` }}
                transition={{
                  duration: reduceMotion ? 0 : PQ_DUR_SLOW,
                  delay: reduceMotion ? 0 : 0.15,
                  ease: PQ_EASE,
                }}
                style={{
                  background:
                    "linear-gradient(90deg, var(--pq-bronze) 0%, #d2aa78 100%)",
                }}
              />
            </div>
            <span
              className="font-mono tabular-nums text-pq-mono-sm"
              style={{ color: "rgba(245,240,232,0.72)" }}
            >
              {FOUNDING_REMAINING} of {FOUNDING_TOTAL} remaining
            </span>
          </div>
        </div>

        <Link
          href="/pricing?plan=plus"
          className="pq-ink-btn-bronze shrink-0 inline-flex items-center gap-1.5"
        >
          Claim founding seat
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>
    </motion.aside>
  );
}

export default UpsellPlus;
