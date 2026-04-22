"use client";

/**
 * Correlation heatmap — 10x10 mock, inline SVG.
 * Diagonal is 1.0, off-diagonal is pseudo-random but deterministic.
 * Bronze ink scales darker with absolute correlation.
 */

const TICKERS = [
  "AAPL",
  "MSFT",
  "GOOG",
  "AMZN",
  "NVDA",
  "005930",
  "000660",
  "035420",
  "TSLA",
  "META",
];

/** deterministic pseudo-corr — stable across renders */
function mockCorr(i: number, j: number): number {
  if (i === j) return 1;
  const seed = (i * 31 + j * 17 + 7) % 100;
  // range [0.2, 0.85]
  return 0.2 + (seed / 100) * 0.65;
}

export function CorrelationHeatmap() {
  const n = TICKERS.length;
  const cell = 30;
  const labelGap = 56;
  const size = labelGap + n * cell + 8;

  return (
    <section aria-labelledby="corr-heatmap-heading" className="mt-6">
      <header className="mb-3 border-t border-slate-200 pt-4">
        <h2
          id="corr-heatmap-heading"
          className="font-serif italic text-xl text-slate-900"
        >
          Correlation Matrix
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Pairwise correlation across top holdings (mock).
        </p>
      </header>
      <div className="overflow-x-auto">
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="block"
          role="img"
          aria-label="Correlation heatmap"
        >
          {/* column labels */}
          {TICKERS.map((t, j) => (
            <text
              key={`col-${t}`}
              x={labelGap + j * cell + cell / 2}
              y={labelGap - 8}
              textAnchor="middle"
              className="fill-slate-500"
              style={{ fontSize: 9, fontFamily: "var(--font-mono, ui-monospace)" }}
            >
              {t.length > 5 ? t.slice(0, 4) : t}
            </text>
          ))}
          {/* row labels */}
          {TICKERS.map((t, i) => (
            <text
              key={`row-${t}`}
              x={labelGap - 6}
              y={labelGap + i * cell + cell / 2 + 3}
              textAnchor="end"
              className="fill-slate-500"
              style={{ fontSize: 9, fontFamily: "var(--font-mono, ui-monospace)" }}
            >
              {t.length > 5 ? t.slice(0, 4) : t}
            </text>
          ))}
          {/* cells */}
          {TICKERS.map((_, i) =>
            TICKERS.map((__, j) => {
              const c = mockCorr(i, j);
              // Bronze scale: lighter at low corr, darker at high corr
              const opacity = 0.12 + c * 0.75;
              return (
                <g key={`cell-${i}-${j}`}>
                  <rect
                    x={labelGap + j * cell}
                    y={labelGap + i * cell}
                    width={cell - 1}
                    height={cell - 1}
                    fill="#8B6F47"
                    fillOpacity={opacity}
                  />
                  <text
                    x={labelGap + j * cell + cell / 2}
                    y={labelGap + i * cell + cell / 2 + 3}
                    textAnchor="middle"
                    style={{
                      fontSize: 8,
                      fontFamily: "var(--font-mono, ui-monospace)",
                      fill: c > 0.6 ? "#FAF8F3" : "#3a2d1f",
                    }}
                  >
                    {c.toFixed(2)}
                  </text>
                </g>
              );
            }),
          )}
        </svg>
      </div>
      <p className="mt-2 text-[11px] text-slate-400">
        Darker bronze indicates higher correlation. Informational signal only.
      </p>
    </section>
  );
}
