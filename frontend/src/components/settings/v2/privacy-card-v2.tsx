"use client";

/**
 * <PrivacyCardV2 />
 *
 * Section E of /settings v2 — Privacy (Cookie consent + Data export + Danger zone).
 * Mirror of settings-v2 mockup §889 ("C · Privacy · PIPA · GDPR").
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
    label: "필수",
    help: "로그인 세션, CSRF, 언어 설정. 로그인에 꼭 필요합니다.",
    alwaysOn: true,
  },
  {
    id: "analytics",
    label: "분석",
    help: "익명 처리한 페이지 조회 수. 자체 서버에서만 집계합니다.",
  },
  {
    id: "performance",
    label: "성능",
    help: "Web Vitals · LCP / CLS / INP — 속도 개선용입니다.",
  },
  {
    id: "marketing",
    label: "마케팅",
    help: "기본으로 꺼져 있습니다. 광고 추적 쿠키는 쓰지 않습니다.",
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
 *   - trades / positions / journal / pulse → raw stored fields.
 *   - capital_gains / capital_gains_summary → 해외주식 양도소득세 참고용 추정
 *     (FIFO realised P&L + trade-date FX; KRW blank when FX unavailable).
 * The backend also accepts "watchlist"; the UI no longer offers it.
 */
export type CsvDataset =
  | "trades"
  | "positions"
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
    // a since-removed sibling card — duplicate `id="section-e"` (both here
    // and on outer page-v2.tsx wrapper) broke AnchorRail sidebar
    // scroll. Outer keeps the id; inner drops it.
    <section
      style={{ scrollMarginTop: 96 }}
      aria-label="개인정보"
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
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              color: "var(--pq-bronze)",
              marginBottom: 8,
            }}
          >
            개인정보 · 개인정보보호법 · GDPR
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
            당신의 데이터는{" "}
            <span style={{ color: "var(--pq-bronze)" }}>
              당신의 것.
            </span>
          </div>
        </div>
        <a
          href="/privacy"
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: "var(--pq-bronze)",
            borderBottom: "1px solid rgba(184,149,106,0.15)",
            paddingBottom: 2,
            textDecoration: "none",
          }}
        >
          개인정보처리방침 ›
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
            className="font-mono"
            style={{
              position: "absolute",
              top: 14,
              right: 14,
              fontSize: "var(--pq-text-eyebrow)",
              color: "var(--pq-ivory-dim)",
            }}
          >
            동의
          </span>
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              color: "var(--pq-bronze)",
              marginBottom: 16,
            }}
          >
            쿠키 동의 · 항목별
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
                  className="font-mono"
                  style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    fontSize: "var(--pq-text-eyebrow)",
                    border: "1px solid rgba(184,149,106,0.15)",
                    color: "var(--pq-bronze)",
                    borderRadius: 2,
                  }}
                >
                  항상 켜짐
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
            className="font-mono"
            style={{
              position: "absolute",
              top: 14,
              right: 14,
              fontSize: "var(--pq-text-eyebrow)",
              color: "var(--pq-ivory-dim)",
            }}
          >
            내보내기
          </span>
          <div
            className="font-mono"
            style={{
              fontSize: "var(--pq-text-eyebrow)",
              color: "var(--pq-bronze)",
              marginBottom: 16,
            }}
          >
            데이터 내보내기 · 개인정보보호법 제35조
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
            계정에 저장된 모든 것을 JSON 파일 하나로 받습니다. 보유 종목,
            거래, 멈춤 기록, 메모, 주간 기록, 페르소나 스냅숏이 담깁니다.
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
                  마지막 내보내기
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
            className="font-mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 22px",
              background: "var(--pq-bronze)",
              color: "var(--pq-ink, #050505)",
              fontSize: "var(--pq-text-eyebrow)",
              borderRadius: 2,
              border: "none",
              cursor: "pointer",
              marginTop: 12,
            }}
          >
            전체 내보내기 (JSON) →
          </button>
          <p
            className="font-serif"
            style={{
              fontSize: "var(--pq-text-caption)",
              color: "var(--pq-ivory-dim)",
              marginTop: 12,
            }}
          >
            바로 내려받습니다. 메일을 기다릴 필요 없이 파일이 곧장 이
            기기에 저장됩니다.
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
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: "var(--pq-ivory-dim)",
                marginBottom: 12,
              }}
            >
              CSV · 스프레드시트
            </div>
            <p
              className="font-serif"
              style={{
                fontSize: "var(--pq-text-caption)",
                color: "var(--pq-ivory-dim)",
                marginBottom: 14,
              }}
            >
              표 하나를 CSV로 받습니다. Excel이나 Google Sheets에서 바로
              열립니다. 저장된 기록 그대로이며, 가공하지 않습니다.
            </p>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 10,
              }}
            >
              {([
                ["trades", "거래내역"],
                ["positions", "보유종목"],
                // No "watchlist" button (2026-09-29): /watchlist is gone, so
                // offering its CSV advertised a feature nobody can use. The
                // backend still exports legacy rows in the JSON / .xlsx copy
                // (PIPA §35 full record) — only the button is gone.
                ["journal", "기록"],
                ["pulse", "주간 기록"],
              ] as const).map(([dataset, label]) => (
                <button
                  key={dataset}
                  type="button"
                  onClick={() => onExportCsv?.(dataset)}
                  className="font-mono"
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
                className="font-mono"
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
                className="font-mono"
                style={{
                  fontSize: "var(--pq-text-eyebrow)",
                  color: "var(--pq-ivory-dim)",
                  marginBottom: 10,
                }}
              >
                해외주식 양도소득세
              </div>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 10,
                }}
              >
                {([
                  ["capital_gains", "양도세 내역"],
                  ["capital_gains_summary", "양도세 연도별 요약"],
                ] as const).map(([dataset, label]) => (
                  <button
                    key={dataset}
                    type="button"
                    onClick={() => onExportCsv?.(dataset)}
                    className="font-mono"
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
          className="font-mono"
          style={{
            position: "absolute",
            top: 14,
            right: 14,
            fontSize: "var(--pq-text-eyebrow)",
            color: ERROR_COLOR,
          }}
        >
          계정 삭제
        </span>
        <div
          className="font-mono"
          style={{
            fontSize: "var(--pq-text-eyebrow)",
            color: ERROR_COLOR,
            marginBottom: 16,
          }}
        >
          회원 탈퇴 · 개인정보보호법 제36조
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
              로그아웃
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
              이 브라우저에서 로그아웃합니다. 데이터는 그대로 남습니다.
            </p>
            <button
              type="button"
              onClick={onSignOut}
              disabled={signingOut}
              className="font-mono"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "11px 20px",
                background: "transparent",
                color: "var(--pq-bronze)",
                border: "1px solid var(--pq-bronze)",
                fontSize: "var(--pq-text-eyebrow)",
                borderRadius: 2,
                cursor: signingOut ? "not-allowed" : "pointer",
                opacity: signingOut ? 0.5 : 1,
              }}
            >
              {signingOut ? "로그아웃 중…" : "로그아웃 →"}
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
              계정 삭제
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
              되돌릴 수 없습니다. 보유 종목, 거래, 멈춤 기록, 주간 기록 답변,
              페르소나 이력을 지웁니다. 요청하고 30일이 지나면 완전히 파기합니다(개인정보보호법).
            </p>
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="font-mono"
              style={{
                fontSize: "var(--pq-text-eyebrow)",
                color: ERROR_COLOR,
                borderBottom: `1px solid ${ERROR_LINK_BORDER}`,
                paddingBottom: 2,
                background: "transparent",
                border: "none",
                borderBottomStyle: "solid",
                cursor: "pointer",
              }}
            >
              계정 삭제 →
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
