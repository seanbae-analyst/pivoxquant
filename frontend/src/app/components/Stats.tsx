"use client";

import { motion } from "motion/react";

const stats = [
  { value: "15+", label: "Quant Indicators", description: "Technical, fundamental, sentiment" },
  { value: "73%", label: "Avg Signal Win Rate", description: "Backtested & validated" },
  { value: "2.1", label: "Sharpe Ratio", description: "Risk-adjusted excess returns" },
  { value: "<50ms", label: "Signal Latency", description: "Real-time data processing" },
];

export function Stats() {
  return (
    <section id="stats" className="relative py-32 px-6 overflow-hidden">
      <hr className="landing-divider absolute top-0 left-6 right-6" />

      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="text-center mb-20"
        >
          <p className="text-[13px] text-amber-400 tracking-wider uppercase mb-3">Performance</p>
          <h2 className="text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight">
            The numbers speak for themselves
          </h2>
        </motion.div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-40px" }}
              transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
              className="text-center"
            >
              <p className="text-[clamp(2.5rem,5vw,3.5rem)] font-bold tracking-tight text-white mb-2">
                {stat.value}
              </p>
              <p className="text-[15px] font-medium text-zinc-300 mb-1">{stat.label}</p>
              <p className="text-[12px] text-zinc-500">{stat.description}</p>
            </motion.div>
          ))}
        </div>
      </div>

      <hr className="landing-divider absolute bottom-0 left-6 right-6" />
    </section>
  );
}
