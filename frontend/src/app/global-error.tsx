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
          color: "#F7F5EF",
          fontFamily:
            '"Source Serif 4", Georgia, "Times New Roman", serif',
          WebkitFontSmoothing: "antialiased",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "420px",
            padding: "40px 32px",
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(247,245,239,0.1)",
            borderRadius: "2px",
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
              fontSize: "10px",
              letterSpacing: "0.22em",
              textTransform: "uppercase",
              color: "#B8956A",
              marginBottom: "16px",
            }}
          >
            Critical error
          </div>

          <h1
            style={{
              fontStyle: "italic",
              fontSize: "clamp(1.5rem, 4vw, 2rem)",
              fontWeight: 500,
              margin: "0 0 16px",
              color: "#F7F5EF",
              lineHeight: 1.1,
            }}
          >
            The observation went dark.
          </h1>

          <p
            style={{
              fontSize: "14px",
              color: "rgba(247,245,239,0.55)",
              margin: "0 0 24px",
              lineHeight: 1.6,
            }}
          >
            A critical error occurred. Reload to reconnect to the desk. Your
            data is safe on the server.
          </p>

          {isProduction ? (
            error.digest ? (
              <p
                style={{
                  fontSize: "11px",
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                  color: "rgba(247,245,239,0.3)",
                  margin: "0 0 24px",
                }}
              >
                ref: {error.digest}
              </p>
            ) : null
          ) : (
            <pre
              style={{
                fontSize: "11px",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                color: "rgba(247,245,239,0.5)",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(247,245,239,0.08)",
                borderRadius: "2px",
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
              border: "1px solid #B8956A",
              borderRadius: "2px",
              background: "transparent",
              color: "#B8956A",
              fontSize: "11px",
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Reload
          </button>

          <p
            style={{
              fontSize: "11px",
              color: "rgba(247,245,239,0.25)",
              marginTop: "24px",
              lineHeight: 1.5,
            }}
          >
            PivoxQuant · Observational research only
          </p>
        </div>
      </body>
    </html>
  );
}
