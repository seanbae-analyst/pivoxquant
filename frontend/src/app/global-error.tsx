"use client";

import Link from "next/link";

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
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          background: "#ffffff",
          color: "#0f172a",
          fontFamily:
            'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
          WebkitFontSmoothing: "antialiased",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "420px",
            padding: "32px",
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: "16px",
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
            textAlign: "center",
          }}
        >
          {/* Logo mark — Vantablack + Warm Gold accent */}
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "16px",
              background: "#050505",
              border: "1px solid #E2B96F",
              margin: "0 auto 24px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#ffffff"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 9v2m0 4h.01M4.93 19h14.14a2 2 0 001.73-3L13.73 4a2 2 0 00-3.46 0L3.2 16a2 2 0 001.73 3z" />
            </svg>
          </div>

          <h1
            style={{
              fontSize: "22px",
              fontWeight: 700,
              margin: "0 0 8px",
              color: "#0f172a",
            }}
          >
            Application error
          </h1>
          <p
            style={{
              fontSize: "14px",
              color: "#475569",
              margin: "0 0 24px",
              lineHeight: 1.5,
            }}
          >
            PivoxQuant ran into a critical error and could not recover. Please
            refresh the page — your data is safe on the server.
          </p>

          {isProduction ? (
            error.digest ? (
              <p
                style={{
                  fontSize: "11px",
                  fontFamily:
                    'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
                  color: "#94a3b8",
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
                fontFamily:
                  'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
                color: "#475569",
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
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

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              alignItems: "center",
            }}
          >
            <button
              type="button"
              onClick={() => reset()}
              style={{
                width: "100%",
                padding: "10px 20px",
                borderRadius: "9999px",
                border: "none",
                background:
                  "linear-gradient(135deg, #7c3aed, #3b82f6, #ec4899)",
                color: "#ffffff",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Try again
            </button>
            <Link
              href="/"
              style={{
                width: "100%",
                padding: "10px 20px",
                borderRadius: "9999px",
                border: "1px solid #e2e8f0",
                background: "#ffffff",
                color: "#334155",
                fontSize: "14px",
                fontWeight: 600,
                textDecoration: "none",
                boxSizing: "border-box",
              }}
            >
              Go home
            </Link>
          </div>

          <p
            style={{
              fontSize: "11px",
              color: "#94a3b8",
              marginTop: "24px",
              lineHeight: 1.5,
            }}
          >
            PivoxQuant does not lose data on errors. All positions and settings
            are saved on the server.
          </p>
        </div>
      </body>
    </html>
  );
}
