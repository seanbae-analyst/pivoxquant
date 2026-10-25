"use client";

/**
 * Global error boundary.
 *
 * Handles errors thrown in the root layout itself. Because this replaces the
 * root layout when active, it must declare its own <html> and <body> tags and
 * cannot rely on fonts/providers/global styles from the layout tree.
 *
 * Keep styles inline so this still renders if `globals.css` failed to load.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const isProduction = process.env.NODE_ENV === "production";

  return (
    <html lang="ko">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          background: "#050505",
          color: "#F5F0E8",
          // Pretendard only (2026-10-11 refresh: one typeface). This page
          // renders outside the app tree, so it cannot use the CSS tokens.
          fontFamily:
            '"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif',
          WebkitFontSmoothing: "antialiased",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "420px",
            padding: "40px 32px",
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(245,240,232,0.1)",
            borderRadius: "14px",
            textAlign: "center",
          }}
        >
          {/* Warm-gold accent mark */}
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "9999px",
              background: "#B8956A",
              margin: "0 auto 28px",
            }}
          />

          <div
            style={{
              fontSize: "13px",
              fontWeight: 500,
              letterSpacing: "0.01em",
              color: "#B8956A",
              marginBottom: "12px",
            }}
          >
            화면을 열지 못했어요
          </div>

          <h1
            style={{
              fontSize: "clamp(1.5rem, 4vw, 2rem)",
              fontWeight: 500,
              margin: "0 0 16px",
              color: "#F5F0E8",
              lineHeight: 1.1,
            }}
          >
            잠깐 문제가 생겼어요.
          </h1>

          <p
            style={{
              fontSize: "14px",
              color: "var(--pq-ivory-dim)",
              margin: "0 0 24px",
              lineHeight: 1.6,
            }}
          >
            남긴 기록은 그대로예요. 새로고침해 주세요.
          </p>

          {isProduction ? (
            error.digest ? (
              <p
                style={{
                  fontSize: "11px",
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                  color: "rgba(245,240,232,0.3)",
                  margin: "0 0 24px",
                }}
              >
                참조 번호 {error.digest}
              </p>
            ) : null
          ) : (
            <pre
              style={{
                fontSize: "11px",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                color: "var(--pq-ivory-faint)",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(245,240,232,0.08)",
                borderRadius: "10px",
                padding: "12px",
                margin: "0 0 24px",
                maxHeight: "128px",
                overflow: "auto",
                textAlign: "left",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {error.message || "Unknown error"}
            </pre>
          )}

          <button
            type="button"
            onClick={() => reset()}
            style={{
              display: "block",
              width: "100%",
              padding: "10px 20px",
              border: 0,
              borderRadius: "10px",
              background: "#B8956A",
              color: "#050505",
              fontSize: "14px",
              letterSpacing: "0.01em",
              fontWeight: 600,
              minHeight: "44px",
              cursor: "pointer",
            }}
          >
            새로고침
          </button>

          <p
            style={{
              fontSize: "11px",
              color: "rgba(245,240,232,0.25)",
              marginTop: "24px",
              lineHeight: 1.5,
            }}
          >
            Pivox<span style={{ color: "rgba(184,149,106,0.5)" }}>Quant</span>
          </p>
        </div>
      </body>
    </html>
  );
}
