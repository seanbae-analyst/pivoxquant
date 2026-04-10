"use client";

import { motion } from "motion/react";

const features = [
  {
    title: "Quant Analysis Engine",
    description: "Combines 15+ technical, fundamental, and sentiment indicators into a multi-factor scoring system for every position.",
    tags: ["RSI", "MACD", "Bollinger", "PER", "PBR"],
    accent: "#22d3ee",
    span: "md:col-span-2",
  },
  {
    title: "Auto Trading",
    description: "Signal-driven automated entries and exits via Alpaca (US) and KIS (KR) broker integrations.",
    tags: ["TP/SL", "Position Sizing", "Risk Limits"],
    accent: "#34d399",
    span: "md:col-span-1",
  },
  {
    title: "AI Insights",
    description: "Claude AI delivers SWOT analysis, market commentary, portfolio coaching, and a morning brief in real-time.",
    tags: ["SWOT", "Coaching", "Morning Brief"],
    accent: "#fbbf24",
    span: "md:col-span-1",
  },
  {
    title: "Regime Detection & Adaptive Trading",
    description: "Automatically detects market regimes (bull, bear, choppy) and adjusts trading parameters in real-time. Built-in VIX strategy, StatArb, and momentum models.",
    tags: ["Regime Detection", "VIX Strategy", "StatArb", "Mean Reversion"],
    accent: "#22d3ee",
    span: "md:col-span-2",
  },
];

export function Products() {
  return (
    <section id="products" className="relative py-32 px-6 bg-[#f1f5f9]">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mb-16"
        >
          <p className="text-[13px] text-emerald-600 tracking-wider uppercase mb-3">Products</p>
          <h2 className="text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight leading-tight mb-4">
            All-in-one platform for
            <br />
            data-driven investing
          </h2>
          <p className="text-slate-500 text-[17px] max-w-xl leading-relaxed">
            From complex quant analysis to automated execution, everything you need in a single platform.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-4">
          {features.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
              className={`bezel-card group ${feature.span}`}
            >
              <div className="bezel-card-inner flex flex-col justify-between min-h-[220px]">
                <div>
                  <div
                    className="w-2 h-2 rounded-full mb-5"
                    style={{ background: feature.accent }}
                  />
                  <h3 className="text-[20px] font-semibold text-slate-900 mb-3">
                    {feature.title}
                  </h3>
                  <p className="text-[14px] text-slate-500 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 mt-6">
                  {feature.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-[11px] px-2.5 py-1 rounded-full border border-slate-200 text-slate-500 bg-white"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
