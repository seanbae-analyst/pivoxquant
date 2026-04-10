"use client";

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "motion/react";
import { Logo } from "@/components/ui/logo";

const navItems = [
  { label: "Products", href: "#products" },
  { label: "Features", href: "#solutions" },
  { label: "Performance", href: "#stats" },
];

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex justify-center px-4 pt-4">
      <motion.nav
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="bg-white/90 backdrop-blur-lg border border-slate-200 shadow-sm rounded-full px-6 py-3 flex items-center gap-8 max-w-3xl w-full"
      >
        <Link href="/" className="flex items-center shrink-0">
          <Logo size={32} />
        </Link>

        <div className="hidden md:flex items-center gap-6 flex-1 justify-center">
          {navItems.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-[13px] text-slate-500 hover:text-slate-900 transition-colors duration-300"
            >
              {item.label}
            </a>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3 shrink-0">
          <Link
            href="/login"
            className="text-[13px] text-slate-500 hover:text-slate-900 transition-colors duration-300"
          >
            Sign In
          </Link>
          <Link
            href="/login"
            className="text-[13px] font-medium bg-emerald-600 text-white px-5 py-1.5 rounded-full hover:bg-emerald-700 transition-all duration-300"
          >
            Get Started
          </Link>
        </div>

        <button
          className="md:hidden ml-auto text-slate-500 hover:text-slate-900 transition-colors"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Menu"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            {mobileOpen ? (
              <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            ) : (
              <path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </motion.nav>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-[72px] left-4 right-4 bg-white/95 backdrop-blur-lg border border-slate-200 shadow-lg rounded-2xl p-6 flex flex-col gap-4 z-50"
          >
            {navItems.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className="text-[15px] text-slate-600 hover:text-slate-900 transition-colors"
              >
                {item.label}
              </a>
            ))}
            <hr className="landing-divider my-2" />
            <Link href="/login" className="text-[15px] text-slate-600 hover:text-slate-900 transition-colors">
              Sign In
            </Link>
            <Link
              href="/login"
              className="text-[14px] font-medium bg-emerald-600 text-white px-5 py-2.5 rounded-full text-center hover:bg-emerald-700 transition-all"
            >
              Get Started
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
