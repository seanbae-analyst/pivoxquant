/**
 * /sample-reports — index of all 18 PDF design previews (public, no auth).
 *
 * Lightweight grid linking to each /sample-reports/[slug] route.
 * Use this to walk the entire report family without logging in.
 */

import Link from "next/link";

const REPORTS: { slug: string; title: string; tier: string; cadence: string; pages: number }[] = [
  { slug: "weekly-memo", title: "Weekly Memo", tier: "Free", cadence: "Weekly", pages: 1 },
  { slug: "morning-brief-plus", title: "Morning Brief Plus", tier: "Free", cadence: "Daily", pages: 1 },
  { slug: "brag-card", title: "Brag Card", tier: "Free", cadence: "Monthly", pages: 1 },
  { slug: "earnings-prebrief", title: "Earnings Pre-Brief", tier: "Pro", cadence: "Per-event", pages: 2 },
  { slug: "risk-board", title: "Risk Board", tier: "Pro", cadence: "Weekly", pages: 2 },
  { slug: "quarterly-self-report", title: "Quarterly Self Report", tier: "Pro", cadence: "Quarterly", pages: 2 },
  { slug: "self-audit", title: "Self Audit", tier: "Pro", cadence: "On-demand", pages: 2 },
  { slug: "dd-checklist", title: "DD Checklist", tier: "Pro", cadence: "On-demand", pages: 2 },
  { slug: "dividend-income", title: "Dividend Income", tier: "Pro", cadence: "Monthly", pages: 1 },
  { slug: "insider-mirror", title: "Insider Mirror", tier: "Pro", cadence: "Weekly", pages: 2 },
  { slug: "sp500-backtest", title: "S&P 500 Backtest", tier: "Pro", cadence: "On-demand", pages: 2 },
  { slug: "portfolio-segment", title: "Portfolio Segment", tier: "Pro", cadence: "Monthly", pages: 2 },
  { slug: "capital-allocation", title: "Capital Allocation", tier: "Premium", cadence: "Quarterly", pages: 4 },
  { slug: "credit-rating", title: "Credit Rating", tier: "Premium", cadence: "Quarterly", pages: 3 },
  { slug: "burn-rate", title: "Burn Rate", tier: "Premium", cadence: "Monthly", pages: 2 },
  { slug: "monthly-finance", title: "Monthly Finance", tier: "Premium", cadence: "Monthly", pages: 4 },
  { slug: "kpi-dashboard", title: "KPI Dashboard", tier: "Premium", cadence: "Monthly", pages: 3 },
  { slug: "year-end-letter", title: "Year-End Letter", tier: "Premium", cadence: "Annual", pages: 5 },
];

export const metadata = {
  title: "Sample Reports · PivoxQuant",
};

export default function SampleReportsIndexPage() {
  return (
    <main
      style={{
        fontFamily: "var(--font-serif), Georgia, serif",
        background: "#ececec",
        minHeight: "100vh",
        padding: "48px 24px",
      }}
    >
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        <div
          style={{
            fontFamily: "var(--font-mono, Inter), system-ui",
            fontSize: 11,
            letterSpacing: "2px",
            textTransform: "uppercase",
            color: "#6b6b6b",
          }}
        >
          PivoxQuant · Design Preview
        </div>
        <h1
          style={{
            fontSize: 48,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            margin: "12px 0 6px",
          }}
        >
          18 PDF Reports
        </h1>
        <p style={{ color: "#5a5a5a", maxWidth: 560, lineHeight: 1.55 }}>
          Click any tile to preview the print-ready design. Use Cmd/Ctrl+P inside
          a preview to save as A4 PDF. Sample data is hard-coded.
        </p>

        <div
          style={{
            marginTop: 32,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 16,
          }}
        >
          {REPORTS.map((r, i) => (
            <Link
              key={r.slug}
              href={`/sample-reports/${r.slug}`}
              style={{
                display: "block",
                background: "#fff",
                padding: 18,
                border: "1px solid #e2e0d8",
                borderRadius: 0,
                textDecoration: "none",
                color: "#0e0e0e",
                transition: "border-color 150ms",
              }}
            >
              <div
                style={{
                  fontFamily: "var(--font-mono, Inter), system-ui",
                  fontSize: 9,
                  letterSpacing: "1.6px",
                  textTransform: "uppercase",
                  color: "#8a8a8a",
                }}
              >
                {String(i + 1).padStart(2, "0")} · {r.tier} · {r.cadence}
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 500,
                  letterSpacing: "-0.012em",
                  marginTop: 8,
                }}
              >
                {r.title}
              </div>
              <div
                style={{
                  marginTop: 14,
                  fontFamily: "var(--font-mono, Inter), system-ui",
                  fontSize: 10,
                  color: "#8a8a8a",
                  letterSpacing: "0.5px",
                }}
              >
                {r.pages} {r.pages === 1 ? "page" : "pages"}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
