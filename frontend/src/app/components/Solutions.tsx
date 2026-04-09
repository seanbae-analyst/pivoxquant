"use client";

import { motion } from "motion/react";

const steps = [
  {
    number: "01",
    title: "Profile Your Style",
    description: "Answer 8 quick questions to map your investment style. From conservative to aggressive, we match you with the optimal quant profile.",
    accent: "#22d3ee",
  },
  {
    number: "02",
    title: "AI + Quant Signals",
    description: "15+ technical, fundamental, and sentiment indicators are scored together. Claude AI translates the data into plain-language insights.",
    accent: "#34d399",
  },
  {
    number: "03",
    title: "Automated Execution",
    description: "Signals trigger automatic entries and exits. TP/SL targets, position sizing, and risk limits are all handled for you.",
    accent: "#fbbf24",
  },
  {
    number: "04",
    title: "Real-time Monitoring",
    description: "Track portfolio performance live. Get instant alerts when market regimes shift, and receive strategy adjustments on the fly.",
    accent: "#f472b6",
  },
];

export function Solutions() {
  return (
    <section id="solutions" className="relative py-32 px-6">
      <div className="absolute inset-0 grid-pattern opacity-50" />

      <div className="relative max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="text-center mb-20"
        >
          <p className="text-[13px] text-emerald-400 tracking-wider uppercase mb-3">How it works</p>
          <h2 className="text-[clamp(2rem,4vw,3rem)] font-bold tracking-tight leading-tight">
            Smart investing in 4 steps
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-6">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.6, delay: i * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="group relative"
            >
              <div className="bg-[var(--ld-surface)] border border-[var(--ld-border)] rounded-2xl p-8 h-full transition-all duration-500 hover:border-[var(--ld-border-light)] hover:shadow-[0_20px_60px_rgba(0,0,0,0.3)]" style={{ transitionTimingFunction: "cubic-bezier(0.16,1,0.3,1)" }}>
                <span
                  className="text-[48px] font-bold leading-none block mb-6"
                  style={{ color: step.accent, opacity: 0.15 }}
                >
                  {step.number}
                </span>
                <h3 className="text-[20px] font-semibold text-white mb-3">
                  {step.title}
                </h3>
                <p className="text-[14px] text-zinc-400 leading-relaxed">
                  {step.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
