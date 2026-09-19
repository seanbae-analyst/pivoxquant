/**
 * <FxAttribution /> — required source credit for the USD/KRW rate.
 *
 * Why
 * ---
 * `services/fx_service.py` resolves USD/KRW through KIS → FMP →
 * `https://open.er-api.com/v6/latest/USD`. exchangerate-api.com's free terms
 * say: "We require attribution on the pages you're using these rates with."
 * The frontend carried zero attribution as of 2026-09-19, so every page that
 * converted with that rate was in breach. The provider that actually served
 * a given response is not visible to the client, so the credit is
 * unconditional on any screen that uses the rate.
 *
 * The anchor markup and label are the provider's own required wording and
 * must not be reworded:
 *   <a href="https://www.exchangerate-api.com">Rates By Exchange Rate API</a>
 *
 * Where
 * -----
 * Mount it on every screen that converts with the rate. Today that is
 * `/portfolio` alone — `useFxRate()` has exactly one consumer
 * (grep 2026-09-19), and the cost-basis weight / sector mix math there is
 * cross-currency. Add a mount here, not a second copy of the markup, when a
 * second screen starts converting.
 *
 * Design v3: mono footnote tier, `--pq-*` tokens only, no italic.
 */

import * as React from "react";

export function FxAttribution({ style }: { style?: React.CSSProperties }) {
  return (
    <p
      className="font-mono"
      data-testid="fx-attribution"
      style={{
        fontSize: "var(--pq-text-eyebrow)",
        letterSpacing: "0.14em",
        color: "var(--pq-ivory-dim)",
        margin: 0,
        ...style,
      }}
    >
      <a
        href="https://www.exchangerate-api.com"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          color: "var(--pq-ivory-dim)",
          textDecoration: "underline",
          textUnderlineOffset: 3,
        }}
      >
        Rates By Exchange Rate API
      </a>
    </p>
  );
}

export default FxAttribution;
