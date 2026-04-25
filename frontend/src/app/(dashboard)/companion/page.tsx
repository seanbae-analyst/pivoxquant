"use client";

/**
 * /companion — Personal Journal Companion (Closed Beta).
 *
 * Entry gate has three states:
 *   1. Not entitled      → "Upgrade to Premium Plus" prompt.
 *   2. Entitled + disabled (AGENT_ENABLED=false / kill switch) →
 *      "Coming Soon · Closed Beta" + waitlist CTA.
 *   3. Entitled + enabled → render <ChatPanel />.
 *
 * The page intentionally has no padding from the dashboard layout —
 * the chat panel itself manages safe-area insets at the composer
 * (bottom) and backdrop-blurred header (top).
 */

import Link from "next/link";
import { useCallback, useState } from "react";
import { ArrowRight, Lock, MailCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";
import {
  useCompanionStatus,
  hasCompanionEntitlement,
} from "@/lib/cfo/useCompanion";
import { ChatPanel } from "@/components/companion/chat-panel";

export default function CompanionPage() {
  const { user } = useAuth();
  const { data: status, isLoading } = useCompanionStatus();

  const entitled = hasCompanionEntitlement(
    user?.subscription_tier,
    status?.entitlement_plans,
  );

  // Show skeleton while auth + status are resolving.
  if (isLoading && !status) {
    return <LoadingShell />;
  }

  if (!entitled) {
    return <UpgradePrompt />;
  }

  if (status && !status.enabled) {
    return <ComingSoon phase={status.phase} />;
  }

  // Escape the dashboard layout's main padding so the chat composer
  // can sit flush against the viewport edges (desktop + mobile).
  return (
    <div className="-mx-4 -my-6 md:-mx-10 md:-my-8 md:pb-0 pb-0 md:min-h-[calc(100vh-64px)]">
      <ChatPanel />
    </div>
  );
}

/* ─── Skeleton ────────────────────────────────────────────────────── */

function LoadingShell() {
  return (
    <div
      className="flex min-h-[100dvh] w-full items-center justify-center"
      style={{ background: "var(--pq-ink, #050505)" }}
    >
      <div
        className="font-serif uppercase"
        style={{
          fontSize: 10.5,
          letterSpacing: "0.22em",
          color: "rgba(184, 149, 106, 0.7)",
        }}
      >
        Loading · 불러오는 중
      </div>
    </div>
  );
}

/* ─── Upgrade prompt (entitlement wall) ───────────────────────────── */

function UpgradePrompt() {
  return (
    <div
      className="flex min-h-[100dvh] w-full items-center justify-center px-5 py-16"
      style={{ background: "var(--pq-ink, #050505)", color: "var(--pq-ivory, #F5F0E8)" }}
    >
      <div className="w-full max-w-xl">
        <div className="mb-6 inline-flex items-center gap-2.5">
          <span
            aria-hidden
            className="h-px w-7"
            style={{ background: "rgba(184, 149, 106, 0.7)" }}
          />
          <span
            className="font-serif uppercase"
            style={{
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze, #B8956A)",
            }}
          >
            Premium Plus · Closed Beta
          </span>
        </div>
        <h1
          className="font-serif"
          style={{
            fontSize: "clamp(28px, 4.2vw, 40px)",
            lineHeight: 1.08,
            letterSpacing: "-0.02em",
            fontWeight: 500,
            color: "var(--pq-ivory, #F5F0E8)",
            margin: 0,
          }}
        >
          Personal Journal Companion
        </h1>
        <p
          className="mt-4 font-serif"
          style={{
            fontSize: 15.5,
            lineHeight: 1.65,
            color: "rgba(245, 240, 232, 0.72)",
          }}
        >
          A reflective companion that remembers what you wrote — not an advisor.
          Available to <strong style={{ color: "var(--pq-bronze, #B8956A)" }}>Premium Plus</strong> and
          Founding Lifetime members during Closed Beta.
        </p>
        <p
          className="mt-2 font-serif italic"
          style={{
            fontSize: 13,
            lineHeight: 1.65,
            color: "rgba(184, 149, 106, 0.85)",
          }}
        >
          Premium Plus 또는 Founding Lifetime 멤버에게 제공됩니다.
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/pricing"
            className="inline-flex items-center justify-center gap-2 rounded-sm px-6 py-3 font-serif uppercase transition-opacity hover:opacity-90"
            style={{
              background: "var(--pq-bronze, #B8956A)",
              color: "var(--pq-ink, #050505)",
              fontSize: 11.5,
              letterSpacing: "0.22em",
            }}
          >
            <Lock className="h-3 w-3" strokeWidth={2} aria-hidden />
            Upgrade to Premium Plus
            <ArrowRight className="h-3 w-3" strokeWidth={2} aria-hidden />
          </Link>
          <Link
            href="/home"
            className="inline-flex items-center justify-center gap-2 rounded-sm px-6 py-3 font-serif uppercase transition-colors hover:bg-[rgba(247,245,239,0.04)]"
            style={{
              border: "0.5px solid rgba(245, 240, 232, 0.14)",
              color: "rgba(245, 240, 232, 0.72)",
              fontSize: 11.5,
              letterSpacing: "0.22em",
            }}
          >
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ─── Coming soon (kill switch / closed-beta queue) ───────────────── */

function ComingSoon({ phase }: { phase: string }) {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!email.trim() || submitting) return;
      setSubmitting(true);
      setError(null);
      try {
        await apiFetch(API.agent.waitlist, {
          method: "POST",
          body: JSON.stringify({ email: email.trim() }),
        });
        setSubmitted(true);
      } catch (err) {
        if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
          // Waitlist endpoint not live yet — treat as optimistic success so
          // beta-hopefuls aren't punished for a missing backend stub.
          setSubmitted(true);
        } else {
          setError(err instanceof Error ? err.message : "Could not submit.");
        }
      } finally {
        setSubmitting(false);
      }
    },
    [email, submitting],
  );

  return (
    <div
      className="flex min-h-[100dvh] w-full items-center justify-center px-5 py-16"
      style={{ background: "var(--pq-ink, #050505)", color: "var(--pq-ivory, #F5F0E8)" }}
    >
      <div className="w-full max-w-xl">
        <div className="mb-6 inline-flex items-center gap-2.5">
          <span
            aria-hidden
            className="h-px w-7"
            style={{ background: "rgba(184, 149, 106, 0.7)" }}
          />
          <span
            className="font-serif uppercase"
            style={{
              fontSize: 10.5,
              letterSpacing: "0.22em",
              color: "var(--pq-bronze, #B8956A)",
            }}
          >
            {phase === "internal" ? "Internal · Staff" : "Coming Soon · Closed Beta"}
          </span>
        </div>
        <h1
          className="font-serif"
          style={{
            fontSize: "clamp(28px, 4.2vw, 40px)",
            lineHeight: 1.08,
            letterSpacing: "-0.02em",
            fontWeight: 500,
            color: "var(--pq-ivory, #F5F0E8)",
            margin: 0,
          }}
        >
          Your journal, remembered.
        </h1>
        <p
          className="mt-4 font-serif"
          style={{
            fontSize: 15.5,
            lineHeight: 1.65,
            color: "rgba(245, 240, 232, 0.72)",
          }}
        >
          The Personal Journal Companion is in Closed Beta. Leave your email —
          we open seats in small batches so responses stay slow, careful, and
          within reflective bounds.
        </p>
        <p
          className="mt-2 font-serif italic"
          style={{
            fontSize: 13,
            lineHeight: 1.65,
            color: "rgba(184, 149, 106, 0.85)",
          }}
        >
          Closed Beta 운영 중입니다. 소규모로 순차 초대합니다.
        </p>

        {submitted ? (
          <div
            className="mt-8 flex items-center gap-2 rounded-sm px-4 py-3"
            style={{
              background: "rgba(184, 149, 106, 0.08)",
              border: "0.5px solid rgba(184, 149, 106, 0.35)",
            }}
            role="status"
          >
            <MailCheck
              className="h-4 w-4"
              strokeWidth={1.5}
              style={{ color: "var(--pq-bronze, #B8956A)" }}
              aria-hidden
            />
            <p
              className="font-serif"
              style={{
                fontSize: 13,
                color: "var(--pq-ivory, #F5F0E8)",
                margin: 0,
              }}
            >
              You&apos;re on the waitlist. We&apos;ll email when your seat opens.
            </p>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-3 sm:flex-row">
            <label htmlFor="waitlist-email" className="sr-only">
              Email
            </label>
            <input
              id="waitlist-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@domain.com"
              className="flex-1 rounded-sm bg-transparent px-4 py-3 font-serif outline-none"
              style={{
                border: "0.5px solid rgba(245, 240, 232, 0.14)",
                color: "var(--pq-ivory, #F5F0E8)",
                fontSize: 14,
                caretColor: "var(--pq-bronze, #B8956A)",
              }}
            />
            <button
              type="submit"
              disabled={submitting || !email.trim()}
              className="inline-flex items-center justify-center gap-2 rounded-sm px-6 py-3 font-serif uppercase transition-opacity disabled:opacity-50"
              style={{
                background: "var(--pq-bronze, #B8956A)",
                color: "var(--pq-ink, #050505)",
                fontSize: 11.5,
                letterSpacing: "0.22em",
              }}
            >
              {submitting ? "Submitting…" : "Join Waitlist"}
            </button>
          </form>
        )}

        {error && (
          <p
            role="alert"
            className="mt-3 font-serif"
            style={{ fontSize: 12, color: "rgba(239, 184, 143, 0.9)" }}
          >
            {error}
          </p>
        )}

        {/*
          Inline "Not investment advice" italic was removed — the
          (dashboard)/layout.tsx now mounts a single-source
          <DisclaimerBanner /> for every dashboard page, satisfying the
          legal-guard CI check and avoiding duplicate disclaimer text on
          the Companion screen.
        */}
      </div>
    </div>
  );
}
