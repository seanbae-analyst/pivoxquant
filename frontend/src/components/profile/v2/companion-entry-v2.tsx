"use client";

/**
 * <CompanionEntryV2 />
 *
 * Block 7 of /profile v2 — Companion entry (5-col card).
 * Mirror of profile-v2 mockup §707 ("07 · Companion · Layer 4").
 *
 * Three states:
 *   - entitled (Premium Plus): "Your Companion is active." + "Open Companion" CTA.
 *   - waitlistDone: confirmation that the user is on the waitlist.
 *   - default: editorial waitlist invitation + email confirm + 2 CTAs.
 *
 * Pure presentational — host wires `onJoinWaitlist` (apiFetch /api/agent/waitlist)
 * and `entitled` derived from useCompanionStatus + hasCompanionEntitlement.
 *
 * Legal: persona vocabulary only. No advice/recommend strings.
 */

import * as React from "react";
import Link from "next/link";

interface Props {
  entitled?: boolean;
  /** Email shown in the confirmation copy. Falls back to support@pivoxquant.com per mockup. */
  email?: string | null;
  waitlistDone?: boolean;
  submitting?: boolean;
  onJoinWaitlist?: (email: string) => void;
}

export function CompanionEntryV2({
  entitled = false,
  email,
  waitlistDone = false,
  submitting = false,
  onJoinWaitlist,
}: Props) {
  const [draftEmail, setDraftEmail] = React.useState<string>(email ?? "");

  React.useEffect(() => {
    if (email) setDraftEmail(email);
  }, [email]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onJoinWaitlist && draftEmail.trim()) {
      onJoinWaitlist(draftEmail.trim());
    }
  };

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(245,240,232,0.08)",
        borderRadius: 4,
        padding: 24,
        position: "relative",
        height: "100%",
      }}
    >
      <span
        className="font-mono uppercase"
        style={{
          position: "absolute",
          top: 14,
          right: 14,
          fontSize: 12,
          letterSpacing: "0.2em",
          color: "rgba(245,240,232,0.55)",
        }}
      >
        Closed Beta
      </span>

      <div
        className="font-mono uppercase"
        style={{
          fontSize: 12,
          letterSpacing: "0.22em",
          color: "var(--pq-bronze)",
          marginBottom: 12,
        }}
      >
        07 · Companion · Layer 4
      </div>

      <div
        className="font-display"
        style={{
          fontWeight: 500,
          fontSize: 24,
          lineHeight: 1.15,
          letterSpacing: "-0.02em",
          color: "var(--pq-ivory)",
          marginBottom: 12,
        }}
      >
        A CFO that{" "}
        <span style={{ color: "var(--pq-bronze)", fontStyle: "italic" }}>
          remembers.
        </span>
      </div>

      <p
        className="font-serif"
        style={{
          fontSize: 14,
          lineHeight: 1.55,
          color: "rgba(245,240,232,0.82)",
          marginBottom: 20,
        }}
      >
        The reflective journal agent — Premium Plus. Reflect on positions and
        weeks with a companion that reads your archive and pulses, then asks the
        next question.
      </p>

      {entitled ? (
        <>
          <div
            style={{
              borderTop: "1px solid rgba(245,240,232,0.08)",
              paddingTop: 14,
              marginBottom: 14,
            }}
          >
            <div
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.22em",
                color: "rgba(245,240,232,0.55)",
                marginBottom: 8,
              }}
            >
              Your Companion is active
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: 14,
                color: "rgba(245,240,232,0.65)",
              }}
            >
              Open the reflective journal to review your archive and submit a
              new pulse.
            </p>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            <Link
              href="/companion"
              className="font-mono uppercase"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "12px 22px",
                background: "var(--pq-bronze)",
                color: "var(--pq-ink, #050505)",
                fontSize: 12,
                letterSpacing: "0.2em",
                borderRadius: 2,
                textDecoration: "none",
              }}
            >
              Open Companion →
            </Link>
          </div>
        </>
      ) : waitlistDone ? (
        <>
          <div
            style={{
              borderTop: "1px solid rgba(245,240,232,0.08)",
              paddingTop: 14,
            }}
          >
            <div
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.22em",
                color: "rgba(245,240,232,0.55)",
                marginBottom: 8,
              }}
            >
              YOU ARE ON THE WAITLIST
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: 14,
                color: "rgba(245,240,232,0.65)",
              }}
            >
              Seats roll out to Premium Plus members. We&rsquo;ll reach out at{" "}
              {email ? (
                <span
                  className="font-mono"
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    color: "rgba(245,240,232,0.82)",
                  }}
                >
                  {email}
                </span>
              ) : (
                "your email"
              )}
              .
            </p>
          </div>
        </>
      ) : (
        <>
          <div
            style={{
              borderTop: "1px solid rgba(245,240,232,0.08)",
              paddingTop: 14,
              marginBottom: 14,
            }}
          >
            <div
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.22em",
                color: "rgba(245,240,232,0.55)",
                marginBottom: 8,
              }}
            >
              Closed Beta — join the waitlist
            </div>
            <form
              onSubmit={handleSubmit}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <input
                type="email"
                value={draftEmail}
                onChange={(e) => setDraftEmail(e.target.value)}
                placeholder="you@example.com"
                aria-label="Waitlist email"
                required
                style={{
                  width: "100%",
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(245,240,232,0.14)",
                  borderRadius: 2,
                  padding: "10px 12px",
                  color: "var(--pq-ivory)",
                  fontSize: 14,
                  letterSpacing: "-0.01em",
                }}
              className="font-mono" />
              <button
                type="submit"
                disabled={submitting}
                className="font-mono uppercase"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "12px 22px",
                  background: "var(--pq-bronze)",
                  color: "var(--pq-ink, #050505)",
                  fontSize: 12,
                  letterSpacing: "0.2em",
                  borderRadius: 2,
                  border: "none",
                  cursor: submitting ? "not-allowed" : "pointer",
                  opacity: submitting ? 0.5 : 1,
                  justifyContent: "center",
                }}
              >
                {submitting ? "Joining…" : "Join the waitlist →"}
              </button>
            </form>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            <Link
              href="/pricing?plan=plus"
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.18em",
                color: "var(--pq-bronze)",
                borderBottom: "1px solid rgba(184,149,106,0.35)",
                paddingBottom: 2,
                textDecoration: "none",
              }}
            >
              See Premium Plus →
            </Link>
            <Link
              href="/companion#sample"
              className="font-mono uppercase"
              style={{
                fontSize: 12,
                letterSpacing: "0.18em",
                color: "rgba(245,240,232,0.55)",
                borderBottom: "1px solid rgba(245,240,232,0.14)",
                paddingBottom: 2,
                textDecoration: "none",
              }}
            >
              Sample memo
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

export default CompanionEntryV2;
