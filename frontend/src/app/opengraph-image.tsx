import { ImageResponse } from "next/og";

export const runtime = "edge";

export const alt = "PivoxQuant — AI Quant Advisor";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * Default OG image for the site.
 * Renders the PivoxQuant wordmark on a Vantablack canvas with a warm-gold accent.
 * Vantablack Luxe palette — no purple/violet gradients (THE LILA BAN).
 */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px 80px",
          background:
            "radial-gradient(120% 80% at 0% 0%, #1a1408 0%, #050505 60%) #050505",
          color: "#FAFAFA",
          fontFamily:
            'Geist, "Pretendard Variable", -apple-system, system-ui, sans-serif',
        }}
      >
        {/* Top — wordmark + warm gold dot */}
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 9999,
              background: "#E2B96F",
              boxShadow: "0 0 24px rgba(226,185,111,0.55)",
            }}
          />
          <span
            style={{
              fontSize: 36,
              fontWeight: 600,
              letterSpacing: -0.5,
              color: "#FAFAFA",
            }}
          >
            PivoxQuant
          </span>
        </div>

        {/* Middle — headline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <span
            style={{
              fontSize: 88,
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: -2,
              color: "#FAFAFA",
              maxWidth: 900,
            }}
          >
            AI Quant Advisor
            <br />
            <span style={{ color: "#E2B96F" }}>for serious investors</span>
          </span>
          <span
            style={{
              fontSize: 32,
              fontWeight: 400,
              color: "rgba(250,250,250,0.66)",
              maxWidth: 900,
            }}
          >
            58 quant models. 7-layer risk defense. US + Korean equities.
          </span>
        </div>

        {/* Bottom — meta */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 22,
            color: "rgba(250,250,250,0.5)",
            borderTop: "1px solid rgba(250,250,250,0.12)",
            paddingTop: 28,
          }}
        >
          <span>pivoxquant.com</span>
          <span>AI · Quant · Risk</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
