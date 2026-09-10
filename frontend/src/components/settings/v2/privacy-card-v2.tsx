"use client";

/**
 * <PrivacyCardV2 />
 *
 * Section E of /settings v2 — Privacy (Cookie consent + Data export + Danger zone).
 * Mirror of settings-v2 mockup §889 ("E · Privacy · PIPA · GDPR").
 *
 * Three surfaces stacked:
 *   - E1 Cookie consent (4 categories — Strictly necessary always-on, Analytics,
 *     Performance, Marketing). Persisted to localStorage (GAP-C — backend
 *     `consent_log` table not yet present).
 *   - E2 Data export (full JSON download + per-dataset CSV downloads).
 *     2026-05-15: GAP-X resolved — backend `/api/profile/export` IS
 *     declared (routes/profile.py:1172) and covers positions + watchlist
 *     + trades + alerts + consent state per PIPA §35 ① "complete personal
 *     data record" requirement. settings/page.tsx export handler
 *     now calls /api/profile/export (was /api/agent/export, subset only).
 *   - E3 Danger zone (Sign out + Delete account). GAP-J resolved: account
 *     deletion now opens the self-service <DeleteAccountModal /> (30-day
 *     soft-delete default + immediate hard-delete) instead of a mailto link.
 *
 * Host wires `useAuth().logout` (sign-out). Account deletion is self-contained.
 *
 * Legal: persona vocabulary only. PIPA · 30-day purge phrasing matches mockup.
 */

import * as React from "react";
import { DeleteAccountModal } from "@/components/account/delete-account-modal";

const ERROR_COLOR = "var(--pq-error, #d18888)";
const ERROR_BORDER = "rgba(209,136,136,0.18)";
const ERROR_LINK_BORDER = "rgba(209,136,136,0.30)";

const COOKIE_LS_KEY = "pq_cookie_consent_v2";

/** Shared bronze-outline pill for every CSV download button (E2b/E2c). */
const CSV_BUTTON_STYLE: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  padding: "10px 18px",
  background: "transparent",
  color: "var(--pq-ivory, #f5f0e8)",
  fontSize: "var(--pq-text-eyebrow)",
  letterSpacing: "0.18em",
  borderRadius: 2,
  border: "1px solid var(--pq-bronze)",
  cursor: "pointer",
};

type CookieCategory = "necessary" | "analytics" | "performance" | "marketing";
type CookieState = Record<CookieCategory, boolean>;

const DEFAULT_COOKIES: CookieState = {
  necessary: true, // always on, no toggle
  analytics: true,
  performance: true,
  marketing: false,
};

const COOKIE_ROWS: Array<{
  id: CookieCategory;
  label: string;
  help: string;
  alwaysOn?: boolean;
}> = [
  {
    id: "necessary",
    label: "Strictly necessary",
    help: "Auth session, CSRF, locale. Required for sign-in.",
    alwaysOn: true,
  },
  {
    id: "analytics",
    label: "Analytics",
    help: "Anonymized page-view counts. Self-hosted.",
  },
  {
    id: "performance",
    label: "Performance",
    help: "Web Vitals · LCP / CLS / INP — for engineering.",
  },
  {
    id: "marketing",
    label: "Marketing",
    help: "Off by default. We do not use ad-tech cookies.",
  },
];

function readCookies(): CookieState {
  if (typeof window === "undefined") return DEFAULT_COOKIES;
  try {
    const raw = window.localStorage.getItem(COOKIE_LS_KEY);
    if (!raw) return DEFAULT_COOKIES;
    const parsed = JSON.parse(raw) as Partial<CookieState>;
    return {
      necessary: true,
      analytics: parsed.analytics ?? DEFAULT_COOKIES.analytics,
      performance: parsed.performance ?? DEFAULT_COOKIES.performance,
      marketing: parsed.marketing ?? DEFAULT_COOKIES.marketing,
    };
  } catch {
    return DEFAULT_COOKIES;
  }
}

function writeCookies(state: CookieState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(COOKIE_LS_KEY, JSON.stringify(state));
  } catch {
    /* quota/disabled — silently degrade */
  }
}

function PrivacyToggle({
  on,
  onChange,
  ariaLabel,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      onClick={() => onChange(!on)}
      style={{
        position: "relative",
        display: "inline-block",
        width: 36,
        height: 20,
        background: on ? "var(--pq-bronze)" : "rgba(245,240,232,0.10)",
        borderRadius: 999,
        transition: "background 200ms",
        flexShrink: 0,
        border: "none",
        cursor: "pointer",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 3,
          left: 3,
          width: 14,
          height: 14,
          background: "var(--pq-ivory)",
          borderRadius: 999,
          transition: "transform 200ms",
          transform: on ? "translateX(16px)" : "translateX(0)",
        }}
      />
    </button>
  );
}

/**
 * CSV datasets a user can download.
 *   - trades / positions / watchlist / journal / pulse → raw stored fields.
 *   - capital_gains / capital_gains_summary → 해외주식 양도소득세 참고용 추정
 *     (FIFO realised P&L + trade-date FX; KRW blank when FX unavailable).
 */
export type CsvDataset =
  | "trades"
  | "positions"
  | "watchlist"
  | "capital_gains"
  | "capital_gains_summary"
  | "journal"
  | "pulse";

interface Props {
  /** Last export metadata, for the E2 row. */
  lastExport?: { at: string; size?: string };
  onRequestExport?: () => void;
  /** Download a single dataset as CSV (raw stored fields, instant). */
  onExportCsv?: (dataset: CsvDataset) => void;
  /** Download ALL datasets as one multi-sheet .xlsx workbook. */
  onExportXlsx?: () => void;
  onSignOut?: () => void;
  signingOut?: boolean;
}

export function PrivacyCardV2({
  lastExport,
  onRequestExport,
  onExportCsv,
  onExportXlsx,
  onSignOut,
  signingOut,
}: Props) {
  const [cookies, setCookies] = React.useState<CookieState>(DEFAULT_COOKIES);
  const [showDelete, setShowDelete] = React.useState(false);

  React.useEffect(() => {
    setCookies(readCookies());
  }, []);

  const setCookie = (id: CookieCategory, next: boolean) => {
    setCookies((prev) => {
      const updated: CookieState = { ...prev, [id]: next, necessary: true };
      writeCookies(updated);
      return updated;
    });
  };

  return (
    // 2026-05-15 (bug-hunter Wave 4 P2 #4 sibling): same root cause as
    // subscription-card-v2.tsx — duplicate `id="section-e"` (both here
    // and on outer page-v2.tsx wrapper) broke AnchorRail sidebar
    // scroll. Outer keeps the id; inner drops it.
    <section
      style={{ scrollMarginTop: 96 }}
      aria-label="Privacy"
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          marginBottom: 16,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            E · Privacy · PIPA · GDPR
          </div>
          <div
            className="font-display"
            style={{
              fontWeight: 500,
              fontSize: "var(--pq-text-h3)",
              lineHeight: 1.15,
              letterSpacing: "-0.02em",
              color: "var(--pq-ivory)",
            }}
          >
            Your data is{" "}
            <span style={{ color: "var(--pq-bronze)" }}>
              yours.
            </span>
          </div>
        </div>
        <a
          href="/privacy"
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.18em",
            color: "var(--pq-bronze)",
            borderBottom: "1px solid rgba(184,149,106,0.15)",
            paddingBottom: 2,
            textDecoration: "none",
          }}
        >
          Privacy policy ›
        </a>
      </div>

      {/* E1 + E2 split */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 12,
          marginBottom: 12,
        }}
        className="pq-privacy-grid"
      >
        {/* E1 — Cookie consent */}
        <div
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--pq-ivory-line)",
            borderRadius: 4,
            padding: 24,
            position: "relative",
          }}
        >
          <span
            className="font-mono uppercase"
            style={{
              position: "absolute",
              top: 14,
              right: 14,
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              color: "var(--pq-ivory-dim)",
            }}
          >
            E1 · Consent
          </span>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 16,
            }}
          >
            Cookie consent · Granular
          </div>

          {COOKIE_ROWS.map((row, idx) => (
            <div
              key={row.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 14,
                padding: "14px 0",
                borderTop:
                  idx === 0
                    ? undefined
                    : "1px solid var(--pq-ivory-line)",
                paddingTop: idx === 0 ? 0 : 14,
                paddingBottom: idx === COOKIE_ROWS.length - 1 ? 0 : 14,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  className="font-serif"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    color: "var(--pq-ivory)",
                  }}
                >
                  {row.label}
                </div>
                <div
                  className="font-serif"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    color: "var(--pq-ivory-dim)",
                    marginTop: 2,
                  }}
                >
                  {row.help}
                </div>
              </div>
              {row.alwaysOn ? (
                <span
                  className="font-mono uppercase"
                  style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    fontSize: "var(--pq-text-eyebrow)",
                    letterSpacing: "0.18em",
                    border: "1px solid rgba(184,149,106,0.15)",
                    color: "var(--pq-bronze)",
                    borderRadius: 2,
                  }}
                >
                  Always on
                </span>
              ) : (
                <PrivacyToggle
                  on={cookies[row.id]}
                  onChange={(next) => setCookie(row.id, next)}
                  ariaLabel={row.label}
                />
              )}
            </div>
          ))}
        </div>

        {/* E2 — Data export */}
        <div
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid var(--pq-ivory-line)",
            borderRadius: 4,
            padding: 24,
            position: "relative",
          }}
        >
          <span
            className="font-mono uppercase"
            style={{
              position: "absolute",
              top: 14,
              right: 14,
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              color: "var(--pq-ivory-dim)",
            }}
          >
            E2 · Export
          </span>
          <div
            className="font-mono uppercase"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.22em",
              color: "var(--pq-bronze)",
              marginBottom: 16,
            }}
          >
            Data export · PIPA Art. 35
          </div>

          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-body)",
              lineHeight: 1.55,
              color: "var(--pq-ivory-strong)",
              marginBottom: 20,
            }}
          >
            Download a portable JSON copy of your account: positions,
            watchlist, persona snapshots, pulse history, and delivered
            artifact metadata.
          </p>

          {lastExport ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 14,
                padding: "0 0 14px",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  className="font-serif"
                  style={{
                    fontSize: "var(--pq-text-body)",
                    color: "var(--pq-ivory)",
                  }}
                >
                  Last export
                </div>
                <div
                  className="font-mono"
                  style={{
                    fontVariantNumeric: "tabular-nums",
                    fontSize: "var(--pq-text-body)",
                    color: "var(--pq-ivory-dim)",
                    marginTop: 2,
                  }}
                >
                  {lastExport.at}
                  {lastExport.size ? <> · {lastExport.size}</> : null}
                </div>
              </div>
            </div>
          ) : null}

          <button
            type="button"
            onClick={onRequestExport}
            className="font-mono uppercase"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 22px",
              background: "var(--pq-bronze)",
              color: "var(--pq-ink, #050505)",
              fontSize: "var(--pq-text-eyebrow)",
              letterSpacing: "0.2em",
              borderRadius: 2,
              border: "none",
              cursor: "pointer",
              marginTop: 12,
            }}
          >
            Download full export (JSON) →
          </button>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-caption)",
              color: "var(--pq-ivory-dim)",
              marginTop: 12,
            }}
          >
            Instant download. No email, no wait — the file is generated and
            saved to your device immediately.
          </p>

          {/* E2b — CSV (spreadsheet) downloads: raw stored fields only. */}
          <div
            style={{
              marginTop: 24,
              paddingTop: 20,
              borderTop: "1px solid var(--pq-ivory-line)",
            }}
          >
            <div
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.22em",
                color: "var(--pq-ivory-dim)",
                marginBottom: 12,
              }}
            >
              CSV · Spreadsheet
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-caption)",
                color: "var(--pq-ivory-dim)",
                marginBottom: 14,
              }}
            >
              Download a single table as CSV — opens cleanly in Excel or Google
              Sheets. Your raw records only, exactly as stored.
            </p>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 10,
              }}
            >
              {([
                ["trades", "거래내역 · Trades"],
                ["positions", "보유종목 · Positions"],
                ["watchlist", "관심종목 · Watchlist"],
                ["journal", "기록 · Journal"],
                ["pulse", "주간 기록 · Pulse"],
              ] as const).map(([dataset, label]) => (
                <button
                  key={dataset}
                  type="button"
                  onClick={() => onExportCsv?.(dataset)}
                  className="font-mono uppercase"
                  style={CSV_BUTTON_STYLE}
                >
                  {label} ↓
                </button>
              ))}
            </div>

            {/* E2b-xlsx — one click downloads every table as ONE multi-sheet
                .xlsx workbook (보유종목 / 거래내역 / 매매일지 / 주간펄스 …). Same
                raw-fact columns as the CSVs; nothing computed beyond the tax
                sheets. */}
            <div style={{ marginTop: 16 }}>
              <button
                type="button"
                onClick={() => onExportXlsx?.()}
                className="font-mono uppercase"
                style={CSV_BUTTON_STYLE}
              >
                전체 데이터 · Excel (.xlsx) ↓
              </button>
            </div>

            {/* E2c — 해외주식 양도소득세 (참고용 추정). Computed from your own
                trades via FIFO matching + trade-date FX. NOT advice — a
                calculation record only; KRW left blank where FX is
                unavailable (never fabricated). */}
            <div style={{ marginTop: 22 }}>
              <div
                className="font-mono uppercase"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  letterSpacing: "0.22em",
                  color: "var(--pq-ivory-dim)",
                  marginBottom: 10,
                }}
              >
                해외주식 양도소득세 · Capital gains
              </div>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 10,
                }}
              >
                {([
                  ["capital_gains", "양도세 내역 · Lots"],
                  ["capital_gains_summary", "양도세 요약 · Yearly"],
                ] as const).map(([dataset, label]) => (
                  <button
                    key={dataset}
                    type="button"
                    onClick={() => onExportCsv?.(dataset)}
                    className="font-mono uppercase"
                    style={CSV_BUTTON_STYLE}
                  >
                    {label} ↓
                  </button>
                ))}
              </div>
              <p
                className="font-serif"
                style={{
                  fontSize: "var(--pq-text-caption)",
                  color: "var(--pq-ivory-faint)",
                  marginTop: 10,
                  lineHeight: 1.55,
                }}
              >
                참고용 추정치이며 세무대리·세무자문이 아닙니다. FIFO 실현손익을
                거래일 환율(FMP 종가)로 환산 — 국세청 매매기준율과 차이가 날 수
                있고, 환율 결손분은 빈칸으로 둡니다. 한국 일반주식은 대주주 외
                비과세입니다. 실제 신고는 홈택스·세무사 확인이 필요하며, 신고
                책임은 본인에게 있습니다.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* E3 — Danger zone */}
      <div
        style={{
          background: "rgba(255,255,255,0.02)",
          border: `1px solid ${ERROR_BORDER}`,
          borderRadius: 4,
          padding: 24,
          position: "relative",
        }}
      >
        <span
          className="font-mono uppercase"
          style={{
            position: "absolute",
            top: 14,
            right: 14,
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.2em",
            color: ERROR_COLOR,
          }}
        >
          E3 · Danger zone
        </span>
        <div
          className="font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            letterSpacing: "0.22em",
            color: ERROR_COLOR,
            marginBottom: 16,
          }}
        >
          Account deletion · PIPA Art. 36
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 24,
          }}
          className="pq-danger-grid"
        >
          <div>
            <div
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-quote)",
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
                marginBottom: 12,
                letterSpacing: "-0.02em",
              }}
            >
              Sign out
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.55,
                color: "var(--pq-ivory-strong)",
                marginBottom: 16,
              }}
            >
              Ends this browser session. Your data is preserved.
            </p>
            <button
              type="button"
              onClick={onSignOut}
              disabled={signingOut}
              className="font-mono uppercase"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "11px 20px",
                background: "transparent",
                color: "var(--pq-bronze)",
                border: "1px solid var(--pq-bronze)",
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.2em",
                borderRadius: 2,
                cursor: signingOut ? "not-allowed" : "pointer",
                opacity: signingOut ? 0.5 : 1,
              }}
            >
              {signingOut ? "Signing out…" : "Sign out →"}
            </button>
          </div>

          <div>
            <div
              className="font-display"
              style={{
                fontWeight: 500,
                fontSize: "var(--pq-text-quote)",
                lineHeight: 1.2,
                color: "var(--pq-ivory)",
                marginBottom: 12,
                letterSpacing: "-0.02em",
              }}
            >
              Delete account
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-body)",
                lineHeight: 1.55,
                color: "var(--pq-ivory-strong)",
                marginBottom: 16,
              }}
            >
              Permanent. Removes positions, watchlists, persona snapshots,
              and delivered artifacts. PIPA · 30-day purge after request.
            </p>
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="font-mono uppercase"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                letterSpacing: "0.18em",
                color: ERROR_COLOR,
                borderBottom: `1px solid ${ERROR_LINK_BORDER}`,
                paddingBottom: 2,
                background: "transparent",
                border: "none",
                borderBottomStyle: "solid",
                cursor: "pointer",
              }}
            >
              Contact support to delete
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        @media (max-width: 1023px) {
          :global(.pq-privacy-grid),
          :global(.pq-danger-grid) {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>

      {showDelete ? (
        <DeleteAccountModal onClose={() => setShowDelete(false)} />
      ) : null}
    </section>
  );
}

export default PrivacyCardV2;
