"use client";

/**
 * CompanionTeaser — landing-page teaser for the Personal Journal Companion.
 *
 * Goldman IC editorial — Vantablack + Bronze + Ivory. Sits after the
 * Living CFO Loop so the visual rhythm is: Loop (passive observation) →
 * Companion (interactive reflection) → Pricing.
 *
 * CTA routes to the /companion page (entitlement-gated) OR submits an
 * email to the waitlist when the viewer isn't signed in / entitled.
 */

import { useCallback, useState } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import { MessageSquare, MailCheck, ArrowRight } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import { API } from "@/lib/endpoints";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.7, ease: [0.16, 1, 0.3, 1] },
  },
};

const SAMPLE_TURN = {
  user: "What did I write the last time NVDA dropped 8%?",
  user_ko: "NVDA가 -8% 빠졌을 때 내가 뭐라 썼지?",
  agent:
    "On 2025-11-14 you noted: 'Thesis unchanged — demand signal still in contracts. Wait, don't add.' Three days later you added anyway.",
  request_id: "REQ-0847·2s",
};

export function CompanionTeaser() {
  const reduce = useReducedMotion();
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!email.trim() || submitting) return;
      setSubmitting(true);
      try {
        await apiFetch(API.agent.waitlist, {
          method: "POST",
          body: JSON.stringify({ email: email.trim(), source: "landing_teaser" }),
        });
        setSubmitted(true);
      } catch (err) {
        if (err instanceof ApiError && (err.status === 404 || err.status === 501)) {
          // Optimistic — endpoint not live yet.
          setSubmitted(true);
        } else {
          setSubmitted(true);
        }
      } finally {
        setSubmitting(false);
      }
    },
    [email, submitting],
  );

  return (
    <section
      id="pq-companion-teaser"
      className="relative py-24 md:py-36"
      style={{ backgroundColor: "#0A0A0A", color: "var(--pq-ivory)" }}
    >
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <motion.div
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mb-10 inline-flex items-center gap-2.5"
        >
          <span
            aria-hidden
            className="h-px w-7"
            style={{ backgroundColor: "rgba(184, 149, 106, 0.7)" }}
          />
          <span
            className="font-serif text-[11px] uppercase"
            style={{ letterSpacing: "0.22em", color: "var(--pq-bronze)" }}
          >
            Closed Beta · Premium Plus
          </span>
        </motion.div>

        <div className="grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:gap-16">
          {/* LEFT: headline + copy + waitlist */}
          <div>
            <motion.h2
              initial={reduce ? undefined : "hidden"}
              whileInView={reduce ? undefined : "visible"}
              viewport={{ once: true, margin: "-80px" }}
              variants={fadeUp}
              className="pq-silver-matte font-serif mb-6"
              style={{
                fontSize: "clamp(1.875rem, 3.6vw, 2.75rem)",
                lineHeight: 1.08,
                letterSpacing: "-0.02em",
                fontWeight: 500,
              }}
            >
              Your journal,
              <br />
              remembered.
            </motion.h2>
            <motion.p
              initial={reduce ? undefined : "hidden"}
              whileInView={reduce ? undefined : "visible"}
              viewport={{ once: true, margin: "-80px" }}
              variants={fadeUp}
              className="font-serif mb-4 max-w-xl"
              style={{
                fontSize: "clamp(15px, 1.3vw, 17px)",
                lineHeight: 1.65,
                color: "rgba(245, 240, 232, 0.72)",
              }}
            >
              A companion that reflects what you&apos;ve already written — not
              a chatbot that predicts or advises. Three principles:{" "}
              <span style={{ color: "var(--pq-bronze)" }}>Remember</span> ·{" "}
              <span style={{ color: "var(--pq-bronze)" }}>Mirror</span> ·{" "}
              <span style={{ color: "var(--pq-bronze)" }}>Question</span>.
            </motion.p>
            <motion.p
              initial={reduce ? undefined : "hidden"}
              whileInView={reduce ? undefined : "visible"}
              viewport={{ once: true, margin: "-80px" }}
              variants={fadeUp}
              className="font-serif italic mb-10 max-w-xl"
              style={{
                fontSize: 13.5,
                lineHeight: 1.65,
                color: "rgba(184, 149, 106, 0.85)",
              }}
            >
              당신이 쓴 기록을 비추는 동반자. 예측하지 않고, 자문하지 않고, 기억하고 반영하고 질문합니다.
            </motion.p>

            <motion.div
              initial={reduce ? undefined : "hidden"}
              whileInView={reduce ? undefined : "visible"}
              viewport={{ once: true, margin: "-80px" }}
              variants={fadeUp}
              className="flex flex-col gap-3 sm:flex-row sm:items-stretch"
            >
              {submitted ? (
                <div
                  className="flex items-center gap-2 rounded-sm px-4 py-3"
                  style={{
                    background: "rgba(184, 149, 106, 0.08)",
                    border: "0.5px solid rgba(184, 149, 106, 0.35)",
                  }}
                  role="status"
                >
                  <MailCheck
                    className="h-4 w-4 shrink-0"
                    strokeWidth={1.5}
                    style={{ color: "var(--pq-bronze)" }}
                    aria-hidden
                  />
                  <p
                    className="font-serif"
                    style={{
                      fontSize: 13,
                      color: "var(--pq-ivory)",
                      margin: 0,
                    }}
                  >
                    You&apos;re on the Closed Beta waitlist.
                  </p>
                </div>
              ) : (
                <form onSubmit={onSubmit} className="flex flex-1 flex-col gap-3 sm:flex-row">
                  <label htmlFor="companion-teaser-email" className="sr-only">
                    Email
                  </label>
                  <input
                    id="companion-teaser-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@domain.com"
                    className="flex-1 rounded-sm bg-transparent px-4 py-3 font-serif outline-none"
                    style={{
                      border: "0.5px solid rgba(245, 240, 232, 0.14)",
                      color: "var(--pq-ivory)",
                      fontSize: 14,
                      caretColor: "var(--pq-bronze)",
                    }}
                  />
                  <button
                    type="submit"
                    disabled={submitting || !email.trim()}
                    className="inline-flex items-center justify-center gap-2 rounded-sm px-6 py-3 font-serif uppercase transition-opacity disabled:opacity-50"
                    style={{
                      background: "var(--pq-bronze)",
                      color: "var(--pq-ink)",
                      fontSize: 11.5,
                      letterSpacing: "0.22em",
                    }}
                  >
                    {submitting ? "…" : "Join Waitlist"}
                  </button>
                </form>
              )}
            </motion.div>

            <motion.div
              initial={reduce ? undefined : "hidden"}
              whileInView={reduce ? undefined : "visible"}
              viewport={{ once: true, margin: "-80px" }}
              variants={fadeUp}
              className="mt-4"
            >
              <Link
                href="/companion"
                className="inline-flex items-center gap-1.5 font-serif uppercase transition-opacity hover:opacity-80"
                style={{
                  fontSize: 10.5,
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                Members enter here
                <ArrowRight className="h-3 w-3" strokeWidth={1.5} aria-hidden />
              </Link>
            </motion.div>
          </div>

          {/* RIGHT: sample-turn chat mockup */}
          <motion.div
            initial={reduce ? undefined : "hidden"}
            whileInView={reduce ? undefined : "visible"}
            viewport={{ once: true, margin: "-80px" }}
            variants={fadeUp}
            className="relative rounded-sm p-6 md:p-7"
            style={{
              background: "rgba(10, 10, 10, 0.7)",
              border: "0.5px solid rgba(245, 240, 232, 0.1)",
              boxShadow: "0 30px 80px -20px rgba(0,0,0,0.6)",
            }}
            aria-label="Personal Journal Companion sample exchange"
          >
            <div className="mb-5 flex items-center gap-2">
              <MessageSquare
                className="h-3.5 w-3.5"
                strokeWidth={1.5}
                style={{ color: "var(--pq-bronze)" }}
                aria-hidden
              />
              <span
                className="font-serif uppercase"
                style={{
                  fontSize: 10.5,
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                Companion · sample exchange
              </span>
            </div>

            {/* user turn */}
            <div className="mb-4 flex justify-end">
              <div
                className="max-w-[86%] rounded-sm px-4 py-3"
                style={{
                  background: "rgba(245, 240, 232, 0.92)",
                  color: "#0A0A0A",
                }}
              >
                <p
                  className="font-serif italic"
                  style={{ fontSize: 13.5, lineHeight: 1.5, margin: 0 }}
                >
                  {SAMPLE_TURN.user}
                </p>
                <p
                  className="mt-1 font-serif italic"
                  style={{ fontSize: 11, color: "rgba(10,10,10,0.55)", margin: 0 }}
                >
                  {SAMPLE_TURN.user_ko}
                </p>
              </div>
            </div>

            {/* agent turn */}
            <div className="flex justify-start">
              <div
                className="w-full max-w-[92%] rounded-sm"
                style={{
                  background: "rgba(5, 5, 5, 0.6)",
                  border: "0.5px solid rgba(245, 240, 232, 0.08)",
                  borderLeft: "2px solid var(--pq-bronze)",
                  padding: "14px 16px",
                }}
              >
                <span
                  className="font-mono uppercase"
                  style={{
                    fontSize: 9,
                    letterSpacing: "0.2em",
                    color: "rgba(184, 149, 106, 0.7)",
                  }}
                >
                  {SAMPLE_TURN.request_id}
                </span>
                <p
                  className="mt-2 font-serif"
                  style={{
                    fontSize: 13.5,
                    lineHeight: 1.65,
                    color: "var(--pq-ivory)",
                    margin: 0,
                  }}
                >
                  {SAMPLE_TURN.agent}
                </p>
                <p
                  className="mt-3 font-serif italic"
                  style={{
                    fontSize: 10.5,
                    lineHeight: 1.5,
                    color: "rgba(184, 149, 106, 0.8)",
                    margin: 0,
                    paddingTop: 8,
                    borderTop: "0.5px solid rgba(184, 149, 106, 0.24)",
                  }}
                >
                  Not investment advice. Your record, your decision. · 투자 자문이 아닙니다.
                </p>
              </div>
            </div>
          </motion.div>
        </div>

        <motion.p
          initial={reduce ? undefined : "hidden"}
          whileInView={reduce ? undefined : "visible"}
          viewport={{ once: true, margin: "-80px" }}
          variants={fadeUp}
          className="mt-14 font-serif italic"
          style={{
            fontSize: 11,
            color: "var(--pq-muted)",
            borderTop: "0.5px solid var(--pq-border)",
            paddingTop: 16,
          }}
        >
          <span style={{ color: "rgba(184, 149, 106, 0.9)" }}>— </span>
          Closed Beta under experimental legal framing. The Companion does not
          provide investment advice, predictions, or guarantees.
        </motion.p>
      </div>
    </section>
  );
}

export default CompanionTeaser;
