"use client";

import { motion } from "motion/react";
import Image from "next/image";
import Link from "next/link";

export function Hero() {
  return (
    <section className="relative min-h-[100dvh] flex items-center justify-center overflow-hidden">
      {/* Background: logo image as full hero backdrop */}
      <div className="absolute inset-0">
        <Image
          src="/logo-hero.jpeg"
          alt=""
          fill
          className="object-cover object-center"
          style={{
            maskImage: "radial-gradient(ellipse 80% 70% at 50% 45%, black 20%, transparent 75%)",
            WebkitMaskImage: "radial-gradient(ellipse 80% 70% at 50% 45%, black 20%, transparent 75%)",
            opacity: 0.35,
          }}
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-b from-[#09090b]/80 via-[#09090b]/30 to-[#09090b]" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#09090b]/60 via-transparent to-[#09090b]/60" />
      </div>
      <div className="absolute inset-0 grid-pattern opacity-30" />

      <div className="relative z-10 max-w-5xl mx-auto px-6 pt-32 pb-20 text-center">

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
          className="inline-flex items-center gap-2 glass-surface rounded-full px-4 py-1.5 mb-8"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[12px] text-zinc-400 tracking-wide">
            AI Quant Advisor &mdash; Now in Beta
          </span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-[clamp(2.5rem,6vw,4.5rem)] font-bold leading-[1.1] tracking-tight mb-6"
        >
          Stop guessing.
          <br />
          <span className="text-glow-cyan" style={{ color: "#22d3ee" }}>
            Trade with data.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="text-[clamp(1rem,2vw,1.25rem)] text-zinc-400 max-w-xl mx-auto mb-10 leading-relaxed"
        >
          15+ quant indicators and AI analyze your portfolio in real-time.
          <br className="hidden sm:block" />
          The next-generation personal investment platform.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <Link
            href="/login"
            className="bg-white text-zinc-900 font-medium px-8 py-3 rounded-full hover:bg-zinc-200 transition-all duration-300 hover:scale-[1.03] text-[15px]"
          >
            Start for Free
          </Link>
          <a
            href="#products"
            className="border border-zinc-700 text-zinc-300 font-medium px-8 py-3 rounded-full hover:border-zinc-500 hover:text-white transition-all duration-300 text-[15px]"
          >
            Explore Products
          </a>
        </motion.div>

        {/* Dashboard mockup */}
        <motion.div
          initial={{ opacity: 0, y: 60, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 1, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="relative mt-20 mx-auto max-w-4xl"
        >
          <div className="bezel-card">
            <div className="bezel-card-inner !p-0 overflow-hidden">
              <div className="bg-[#111113] p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full bg-emerald-500" />
                    <span className="text-[13px] text-zinc-400">Portfolio Dashboard</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] text-zinc-500 font-mono">2026.04.07</span>
                    <div className="w-6 h-6 rounded-full bg-zinc-800" />
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: "Total Assets", value: "$127,450", change: "+12.4%" },
                    { label: "Daily P&L", value: "+$1,280", change: "+1.01%" },
                    { label: "Win Rate", value: "73.2%", change: "+5.1%" },
                    { label: "Sharpe Ratio", value: "2.14", change: "+0.3" },
                  ].map((m) => (
                    <div key={m.label} className="bg-zinc-900/60 border border-zinc-800/60 rounded-xl p-4">
                      <p className="text-[11px] text-zinc-500 mb-1">{m.label}</p>
                      <p className="text-[18px] font-semibold text-white">{m.value}</p>
                      <p className="text-[11px] text-emerald-400 mt-1">{m.change}</p>
                    </div>
                  ))}
                </div>

                <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-xl p-4 h-40 flex items-end gap-[3px]">
                  {Array.from({ length: 48 }).map((_, i) => {
                    const h = 20 + Math.sin(i * 0.3) * 30 + Math.random() * 20;
                    return (
                      <div
                        key={i}
                        className="flex-1 rounded-t"
                        style={{
                          height: `${h}%`,
                          background: h > 50 ? "rgba(34,211,238,0.5)" : "rgba(34,211,238,0.2)",
                        }}
                      />
                    );
                  })}
                </div>

                <div className="space-y-2">
                  {[
                    { ticker: "AAPL", name: "Apple Inc.", signal: "BUY", score: 87, pnl: "+8.2%" },
                    { ticker: "NVDA", name: "NVIDIA Corp.", signal: "HOLD", score: 72, pnl: "+24.1%" },
                    { ticker: "TSLA", name: "Tesla Inc.", signal: "BUY", score: 81, pnl: "+3.7%" },
                  ].map((pos) => (
                    <div key={pos.ticker} className="flex items-center justify-between bg-zinc-900/30 border border-zinc-800/30 rounded-lg px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center text-[10px] font-mono text-zinc-400">
                          {pos.ticker.slice(0, 2)}
                        </div>
                        <div>
                          <p className="text-[13px] font-medium text-white">{pos.ticker}</p>
                          <p className="text-[11px] text-zinc-500">{pos.name}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                          pos.signal === "BUY"
                            ? "bg-emerald-500/10 text-emerald-400"
                            : "bg-amber-500/10 text-amber-400"
                        }`}>
                          {pos.signal}
                        </span>
                        <span className="text-[12px] font-mono text-zinc-400">{pos.score}</span>
                        <span className="text-[13px] font-medium text-emerald-400">{pos.pnl}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="absolute -inset-4 rounded-3xl bg-cyan-500/[0.03] blur-3xl -z-10" />
        </motion.div>
      </div>
    </section>
  );
}
