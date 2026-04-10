"use client";

import { motion } from "motion/react";
import Link from "next/link";

export function CTA() {
  return (
    <section className="landing-section-dark relative py-40 px-6 overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-emerald-500/[0.08] blur-[150px]" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="relative max-w-3xl mx-auto text-center"
      >
        <h2 className="text-[clamp(2rem,5vw,3.5rem)] font-bold tracking-tight leading-[1.1] mb-6 text-white">
          Done guessing.
          <br />
          Start knowing.
        </h2>
        <p className="text-[17px] text-slate-400 max-w-lg mx-auto mb-10 leading-relaxed">
          Get started with StockPilot today and experience data-driven investing.
          No credit card required.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/login"
            className="bg-emerald-500 text-white font-medium px-10 py-3.5 rounded-full hover:bg-emerald-400 transition-all duration-300 hover:scale-[1.03] text-[15px]"
          >
            Start for Free
          </Link>
          <Link
            href="#products"
            className="border border-slate-600 text-slate-300 font-medium px-10 py-3.5 rounded-full hover:border-slate-400 hover:text-white transition-all duration-300 text-[15px]"
          >
            Learn More
          </Link>
        </div>
        <div className="mt-12 flex items-center justify-center gap-8 text-slate-500 text-[13px]">
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Free Trial
          </span>
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            No Credit Card
          </span>
          <span className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Instant Access
          </span>
        </div>
      </motion.div>
    </section>
  );
}
