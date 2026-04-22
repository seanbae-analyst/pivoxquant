"use client";

import { DisclaimerBanner } from "@/components/ui/disclaimer-banner";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { TerminalSidebar } from "@/components/layout/terminal-sidebar";

/* ──────────────────────────────────────────────────────────────
   /home — PivoxQuant Research Terminal

   Pixel-replicate of the landing page's Dashboard Preview section
   (components/landing/landing-page.tsx, lines 3011–3295). Ivory
   outer canvas, one dominant Vantablack Terminal card with its own
   internal sidebar rail + 3-stat bento + Bronze equity curve +
   observations table + footer.

   Copy follows PivoxQuant legal constraints: POSITIVE/NEGATIVE/
   NEUTRAL only — no BUY/SELL/HOLD/recommend/advice language.
   DisclaimerBanner rendered directly under the Terminal.
   ────────────────────────────────────────────────────────────── */

/* ── Equity curve — direct port of DashboardEquityCurve from landing ── */

function TerminalEquityCurve() {
  return (
    <svg
      viewBox="0 0 500 120"
      className="w-full h-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="Equity observation curve"
    >
      <defs>
        <linearGradient id="pqHomeCurve" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8B6F47" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#8B6F47" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[30, 60, 90].map((y) => (
        <line
          key={y}
          x1={0}
          y1={y}
          x2={500}
          y2={y}
          stroke="#F5F0E8"
          strokeOpacity={0.06}
          strokeWidth={0.5}
        />
      ))}
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10 L500 120 L0 120 Z"
        fill="url(#pqHomeCurve)"
      />
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10"
        fill="none"
        stroke="#8B6F47"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Page ── */

const STATS = [
  { label: "Portfolio Value", value: "$127,450", sub: "+12.4% all-time" },
  { label: "Risk Board", value: "85", sub: "7 signals observed" },
  { label: "Artifacts Ready", value: "14", sub: "3 new this week" },
] as const;

const PERIODS = ["1M", "3M", "6M", "1Y", "ALL"] as const;

const OBSERVATIONS = [
  { ticker: "AAPL", name: "Apple", signal: "POSITIVE", change: "+1.24%" },
  { ticker: "MSFT", name: "Microsoft", signal: "POSITIVE", change: "+0.82%" },
  { ticker: "NVDA", name: "NVIDIA", signal: "NEUTRAL", change: "−0.34%" },
] as const;

export default function HomePage() {
  return (
    <ErrorBoundary>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-10">
        {/* ── Terminal card ── */}
        <div
          className="rounded-sm overflow-hidden"
          style={{
            backgroundColor: "var(--pq-ink)",
            border: "0.5pt solid rgba(10,10,10,0.15)",
            boxShadow: "0 40px 80px -40px rgba(10,10,10,0.4)",
          }}
        >
          {/* Chrome bar */}
          <div
            className="flex items-center justify-between px-5 py-3"
            style={{ borderBottom: "0.5pt solid rgba(245,240,232,0.08)" }}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: "var(--pq-bronze)" }}
              />
              <span
                className="font-serif text-[10.5px] uppercase"
                style={{
                  letterSpacing: "0.22em",
                  color: "var(--pq-bronze)",
                }}
              >
                PivoxQuant · Monday Brief
              </span>
            </div>
            <span
              className="font-mono tabular-nums text-[11px]"
              style={{ color: "rgba(245,240,232,0.5)" }}
            >
              07:00 KST
            </span>
          </div>

          {/* Body — 2-column */}
          <div className="flex min-h-[800px]">
            <TerminalSidebar active="home" />

            {/* ── Main content ── */}
            <main className="flex-1 p-5 md:p-8">
              {/* 3-stat bento */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                {STATS.map((m) => (
                  <div
                    key={m.label}
                    className="rounded-sm"
                    style={{
                      backgroundColor: "rgba(255,255,255,0.02)",
                      border: "0.5pt solid rgba(245,240,232,0.08)",
                      padding: "18px 22px",
                    }}
                  >
                    <p
                      className="font-serif uppercase mb-2 text-[9.5px]"
                      style={{
                        letterSpacing: "0.22em",
                        color: "var(--pq-bronze)",
                      }}
                    >
                      {m.label}
                    </p>
                    <p
                      className="pq-home-stat mb-1.5"
                      style={{
                        color: "var(--pq-ivory)",
                      }}
                    >
                      {m.value}
                    </p>
                    <p
                      className="font-serif text-[11px]"
                      style={{ color: "rgba(245,240,232,0.55)" }}
                    >
                      {m.sub}
                    </p>
                  </div>
                ))}
              </div>

              {/* Equity chart */}
              <div
                className="mb-6"
                style={{
                  backgroundColor: "rgba(255,255,255,0.015)",
                  borderTop: "0.5pt solid rgba(245,240,232,0.08)",
                  borderBottom: "0.5pt solid rgba(245,240,232,0.08)",
                  padding: "20px 4px",
                }}
              >
                <div className="flex items-center justify-between mb-4 px-2">
                  <span
                    className="font-serif uppercase text-[9.5px]"
                    style={{
                      letterSpacing: "0.22em",
                      color: "var(--pq-bronze)",
                    }}
                  >
                    Equity · Observation
                  </span>
                  <div className="flex gap-1">
                    {PERIODS.map((t) => {
                      const active = t === "6M";
                      return (
                        <span
                          key={t}
                          className="font-mono tabular-nums text-[10px]"
                          style={{
                            padding: "2px 8px",
                            borderRadius: "2px",
                            border: active
                              ? "1px solid var(--pq-bronze)"
                              : "1px solid transparent",
                            color: active
                              ? "var(--pq-bronze)"
                              : "rgba(245,240,232,0.5)",
                            letterSpacing: "0.05em",
                          }}
                        >
                          {t}
                        </span>
                      );
                    })}
                  </div>
                </div>
                <div className="h-[200px]">
                  <TerminalEquityCurve />
                </div>
              </div>

              {/* Observations table */}
              <div>
                <p
                  className="font-serif uppercase text-[9.5px] mb-3"
                  style={{
                    letterSpacing: "0.22em",
                    color: "var(--pq-bronze)",
                  }}
                >
                  This Week&rsquo;s Observations
                </p>
                <table
                  className="w-full"
                  style={{ tableLayout: "fixed", borderCollapse: "collapse" }}
                >
                  <colgroup>
                    <col style={{ width: "35%" }} />
                    <col style={{ width: "10%" }} />
                    <col style={{ width: "35%" }} />
                    <col style={{ width: "20%" }} />
                  </colgroup>
                  <tbody>
                    {OBSERVATIONS.map((row) => {
                      const isPos = row.signal === "POSITIVE";
                      const changeUp = row.change.startsWith("+");
                      return (
                        <tr
                          key={row.ticker}
                          style={{
                            borderBottom:
                              "0.5pt solid rgba(245,240,232,0.06)",
                          }}
                        >
                          <td
                            className="font-serif text-[13px] py-3"
                            style={{ color: "var(--pq-ivory)" }}
                          >
                            {row.name}
                          </td>
                          <td
                            className="font-mono tabular-nums text-[11px] py-3"
                            style={{ color: "rgba(245,240,232,0.5)" }}
                          >
                            {row.ticker}
                          </td>
                          <td
                            className="font-mono tabular-nums text-[11.5px] py-3 text-right pr-6"
                            style={{
                              color: changeUp
                                ? "#7db487"
                                : "rgba(245,240,232,0.6)",
                            }}
                          >
                            {row.change}
                          </td>
                          <td className="py-3 text-right">
                            <span
                              className="font-mono uppercase inline-block"
                              style={{
                                fontSize: "9px",
                                letterSpacing: "0.18em",
                                padding: "2px 10px",
                                borderRadius: "2px",
                                color: isPos
                                  ? "#7db487"
                                  : "rgba(245,240,232,0.55)",
                                border: isPos
                                  ? "1px solid rgba(125,180,135,0.4)"
                                  : "1px solid rgba(245,240,232,0.2)",
                              }}
                            >
                              {row.signal}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Footer */}
              <p
                className="mt-5 font-serif italic"
                style={{
                  fontSize: "11px",
                  color: "rgba(245,240,232,0.5)",
                }}
              >
                Observational signals. Not investment advice.
              </p>
            </main>
          </div>
        </div>

        {/* Legally required disclaimer banner — rendered outside Terminal card */}
        <div className="mt-8">
          <DisclaimerBanner type="signal" />
        </div>
      </div>
    </ErrorBoundary>
  );
}
