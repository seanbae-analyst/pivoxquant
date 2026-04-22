"use client";

/**
 * Rolling VaR 30-day line chart — hand-crafted inline SVG.
 * Mock data, single stroke, hairline axis, tabular-nums labels.
 */

function mockSeries(): number[] {
  // deterministic wobble around -2.0% to -2.5%
  const base = -2.1;
  const pts: number[] = [];
  for (let i = 0; i < 30; i++) {
    const wobble = Math.sin(i / 3.2) * 0.35 + Math.cos(i / 5.1) * 0.2;
    pts.push(base + wobble);
  }
  return pts;
}

export function RollingVarChart() {
  const series = mockSeries();
  const n = series.length;

  const width = 520;
  const height = 160;
  const pad = { t: 14, r: 16, b: 22, l: 40 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;

  const min = Math.min(...series) - 0.3;
  const max = Math.max(...series) + 0.3;
  const xOf = (i: number) => pad.l + (i / (n - 1)) * innerW;
  const yOf = (v: number) => pad.t + ((max - v) / (max - min)) * innerH;

  const linePath = series
    .map((v, i) => `${i === 0 ? "M" : "L"}${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`)
    .join(" ");

  const gridY = [max, (max + min) / 2, min];

  return (
    <section aria-labelledby="rolling-var-heading" className="mt-6">
      <header className="mb-3 border-t border-slate-200 pt-4">
        <h2
          id="rolling-var-heading"
          className="font-serif italic text-xl text-slate-900"
        >
          Rolling 30-Day VaR
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Daily 95% Value-at-Risk, last 30 sessions (mock).
        </p>
      </header>

      <div className="w-full overflow-x-auto">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="block max-w-full"
          role="img"
          aria-label="Rolling 30-day VaR line chart"
        >
          {/* y grid */}
          {gridY.map((v, i) => (
            <g key={`g-${i}`}>
              <line
                x1={pad.l}
                x2={width - pad.r}
                y1={yOf(v)}
                y2={yOf(v)}
                stroke="#E5E0D6"
                strokeWidth={1}
                strokeDasharray={i === 1 ? "2 3" : undefined}
              />
              <text
                x={pad.l - 6}
                y={yOf(v) + 3}
                textAnchor="end"
                className="fill-slate-400"
                style={{
                  fontSize: 10,
                  fontFamily: "var(--font-mono, ui-monospace)",
                }}
              >
                {v.toFixed(2)}%
              </text>
            </g>
          ))}

          {/* x axis baseline */}
          <line
            x1={pad.l}
            x2={width - pad.r}
            y1={height - pad.b}
            y2={height - pad.b}
            stroke="#3a2d1f"
            strokeWidth={1}
          />

          {/* data line — bronze */}
          <path
            d={linePath}
            fill="none"
            stroke="#8B6F47"
            strokeWidth={1.5}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {/* endpoint dot */}
          <circle
            cx={xOf(n - 1)}
            cy={yOf(series[n - 1])}
            r={3}
            fill="#8B6F47"
          />

          {/* x labels */}
          <text
            x={pad.l}
            y={height - 6}
            textAnchor="start"
            className="fill-slate-400"
            style={{ fontSize: 10, fontFamily: "var(--font-mono, ui-monospace)" }}
          >
            D-29
          </text>
          <text
            x={width - pad.r}
            y={height - 6}
            textAnchor="end"
            className="fill-slate-400"
            style={{ fontSize: 10, fontFamily: "var(--font-mono, ui-monospace)" }}
          >
            today
          </text>
        </svg>
      </div>
    </section>
  );
}
