import { ImageResponse } from "next/og";

export const runtime = "edge";

export const alt = "PivoxQuant — 사기 전에 멈추고, 나중에 되비춘다";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * Default OG image for the site.
 * Renders the PivoxQuant wordmark on a Vantablack canvas with a warm-gold accent.
 * Vantablack Luxe palette — no purple/violet gradients (THE LILA BAN).
 *
 * ⚠️ 2026-09-02: this card used to read "AI Quant Research Tool for serious
 * investors / 40 quant models. 7-layer risk defense. / AI · Quant · Risk".
 * `services/quant/` was deleted 2026-08-31 and `services/ai/` on 2026-09-01,
 * so the true count of quant models is 0 and of risk layers is 0. This is the
 * image every KakaoTalk / LinkedIn / Slack link preview renders — a hard,
 * checkable number that was false is the worst possible thing to put there
 * (표시광고법 §3 부당표시). Copy now states only what the three shipping
 * screens do. If you add a number here, measure it first.
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
              background: "#B8956A",
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
            사기 전에 멈추고,
            <br />
            <span style={{ color: "#B8956A" }}>나중에 되비춘다.</span>
          </span>
          <span
            style={{
              fontSize: 32,
              fontWeight: 400,
              color: "rgba(250,250,250,0.66)",
              maxWidth: 900,
            }}
          >
            멈춤 · 기록 · 거울. 종목을 골라주지 않습니다. 한국 + 미국 주식.
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
          <span>투자 권유 아님 · 정보 제공 전용</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
