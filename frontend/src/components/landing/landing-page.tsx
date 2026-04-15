"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import {
  TrendingUp,
  BarChart3,
  Shield,
  Brain,
  User,
  Search,
  FlaskConical,
  Menu,
  X,
  ArrowRight,
  Check,
  ChevronRight,
  Star,
  Activity,
  Home,
  Target,
  Bell,
  Settings,
  Clock,
} from "lucide-react";

/* ──────────────────────────────────────────────
   Animation variants
   ────────────────────────────────────────────── */

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] } },
};

const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.1 } },
};

const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] } },
};

/* ──────────────────────────────────────────────
   Feature data
   ────────────────────────────────────────────── */

const features = [
  {
    icon: BarChart3,
    title: "Quant Scoring",
    description:
      "25 technical + 13 fundamental indicators score every stock 0-100. Data-driven decisions, not gut feelings.",
    href: "/features/quant-scoring",
  },
  {
    icon: Brain,
    title: "AI Assistant",
    description:
      "Claude AI explains your portfolio in plain language. Get personalized insights and actionable insights.",
    href: "/features/ai-assistant",
  },
  {
    icon: Shield,
    title: "Risk Defense",
    description:
      "7-layer protection system: VaR, correlation limits, VIX hedge, sector caps, drawdown guards, and more.",
    href: "/features/risk-defense",
  },
  {
    icon: User,
    title: "Smart Profiles",
    description:
      "8 investor types with customized strategies. Your risk tolerance shapes every analysis.",
    href: "/features/profiles",
  },
  {
    icon: Search,
    title: "CAN SLIM Screener",
    description:
      "William O'Neil's systematic 7-factor stock selection method. Find tomorrow's leaders before the crowd.",
    href: "/features/canslim",
  },
  {
    icon: FlaskConical,
    title: "Paper Trading",
    description:
      "Test strategies risk-free with real market data. Validate before you commit real capital.",
    href: "/features/paper-trading",
  },
];

const stats = [
  { value: "58+", label: "Quant Models" },
  { value: "7-Layer", label: "Risk Defense" },
  { value: "US + KR", label: "Markets" },
  { value: "-52%", label: "MDD vs Buy & Hold" },
];

const steps = [
  {
    step: "01",
    title: "Sign Up & Profile",
    description:
      "Answer 20 questions about your investing style. Get matched to one of 8 investor types with customized parameters.",
  },
  {
    step: "02",
    title: "Connect Portfolio",
    description:
      "Link your Alpaca account (US) or KIS account (Korea), or add positions manually. We support both markets.",
  },
  {
    step: "03",
    title: "AI Protects & Grows",
    description:
      "58 quant models analyze continuously. 7 layers defend your capital. AI assists you through every decision.",
  },
];

const pricingPlans = [
  {
    name: "Free",
    price: "0",
    currency: "",
    period: "",
    description: "Get started with essential tools",
    features: [
      "5 stock analysis per day",
      "Basic quant scoring",
      "1 investor profile",
      "Paper trading",
      "Community access",
    ],
    cta: "Get Started Free",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "9,900",
    currency: "\u20a9",
    period: "/mo",
    description: "For serious individual investors",
    originalPrice: "14,900",
    features: [
      "Unlimited stock analysis",
      "Full 58-model scoring",
      "7-layer risk defense",
      "AI Assistant conversations",
      "CAN SLIM screener",
      "Real-time alerts",
      "US + KR markets",
    ],
    cta: "Start Pro Trial",
    highlighted: true,
  },
  {
    name: "Premium",
    price: "19,900",
    currency: "\u20a9",
    period: "/mo",
    description: "Institutional-grade tools for power users",
    features: [
      "Everything in Pro",
      "Auto-trading (Alpaca + KIS)",
      "Advanced backtesting",
      "Custom quant models",
      "Priority AI assistant",
      "API access",
      "Dedicated support",
    ],
    cta: "Start Premium Trial",
    highlighted: false,
  },
];

const footerLinks = {
  Product: [
    { label: "Features", href: "#features" },
    { label: "Pricing", href: "#pricing" },
    { label: "Paper Trading", href: "/features/paper-trading" },
  ],
  Company: [
    { label: "Contact", href: "mailto:seanbae1521@gmail.com" },
  ],
  Legal: [
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
    { label: "Disclaimer", href: "/terms" },
  ],
};

/* ──────────────────────────────────────────────
   Equity curve SVG
   ────────────────────────────────────────────── */

function MiniEquityCurve() {
  return (
    <svg viewBox="0 0 200 60" className="w-full h-12" preserveAspectRatio="none">
      <defs>
        <linearGradient id="curveGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 45 C20 42, 30 38, 50 35 C70 32, 80 28, 100 30 C120 32, 130 20, 150 15 C170 10, 180 12, 200 8"
        fill="none"
        stroke="#8b5cf6"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M0 45 C20 42, 30 38, 50 35 C70 32, 80 28, 100 30 C120 32, 130 20, 150 15 C170 10, 180 12, 200 8 L200 60 L0 60 Z"
        fill="url(#curveGrad)"
      />
    </svg>
  );
}

/* ──────────────────────────────────────────────
   Dashboard equity curve (full width section)
   ────────────────────────────────────────────── */

function DashboardEquityCurve() {
  return (
    <svg viewBox="0 0 500 120" className="w-full h-full" preserveAspectRatio="none">
      <defs>
        <linearGradient id="dashCurve" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10"
        fill="none"
        stroke="#8b5cf6"
        strokeWidth="2"
      />
      <path
        d="M0 90 C30 88, 50 80, 80 75 C110 70, 130 65, 160 58 C190 51, 210 55, 240 48 C270 41, 290 38, 320 32 C350 26, 370 30, 400 22 C430 14, 460 18, 500 10 L500 120 L0 120 Z"
        fill="url(#dashCurve)"
      />
    </svg>
  );
}

/* ══════════════════════════════════════════════
   MAIN COMPONENT
   ══════════════════════════════════════════════ */

export default function LandingPage() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const prefersReduced = useReducedMotion();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // If user prefers reduced motion, skip framer variants
  const motionProps = (v: Variants) =>
    prefersReduced
      ? {}
      : {
          initial: "hidden" as const,
          whileInView: "visible" as const,
          viewport: { once: true, margin: "-60px" },
          variants: v,
        };

  return (
    <div className="min-h-screen bg-white text-slate-900 overflow-x-hidden">
      {/* ─── 1. NAVIGATION ─── */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled
            ? "bg-white/80 backdrop-blur-xl border-b border-slate-100 shadow-sm"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-primary-gradient flex items-center justify-center">
                <TrendingUp className="w-4.5 h-4.5 text-white" />
              </div>
              <span className="text-lg font-bold text-slate-900">
                Stock<span className="gradient-text">Pilot</span>
              </span>
            </Link>

            {/* Desktop Nav */}
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                Features
              </a>
              <a href="#how-it-works" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                How It Works
              </a>
              <a href="#pricing" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                Pricing
              </a>
              <a href="#resources" className="text-sm text-slate-500 hover:text-slate-900 transition-colors">
                Resources
              </a>
            </div>

            {/* Desktop CTA */}
            <div className="hidden md:flex items-center gap-3">
              <Link
                href="/login"
                className="text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center px-5 py-2 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
              >
                Get Started Free
              </Link>
            </div>

            {/* Mobile hamburger */}
            <button
              className="md:hidden flex h-11 w-11 items-center justify-center rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="md:hidden bg-white border-b border-slate-100 shadow-lg"
          >
            <div className="px-4 py-4 space-y-1">
              <a href="#features" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                Features
              </a>
              <a href="#how-it-works" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                How It Works
              </a>
              <a href="#pricing" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                Pricing
              </a>
              <a href="#resources" className="block text-sm text-slate-600 hover:text-slate-900 py-3" onClick={() => setMobileMenuOpen(false)}>
                Resources
              </a>
              <hr className="border-slate-100" />
              <Link href="/login" className="block text-sm font-medium text-slate-600 py-3">
                Sign In
              </Link>
              <Link
                href="/signup"
                className="block text-center px-5 py-2.5 rounded-full bg-slate-900 text-white text-sm font-semibold"
              >
                Get Started Free
              </Link>
            </div>
          </motion.div>
        )}
      </nav>

      {/* ─── 2. HERO SECTION ─── */}
      <section className="relative pt-28 pb-20 md:pt-36 md:pb-28 overflow-hidden">
        {/* Background decorations */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full bg-violet-100/40 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-[500px] h-[500px] rounded-full bg-blue-100/30 blur-3xl" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-pink-50/40 blur-3xl" />
        </div>

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            {/* Left: Text */}
            <motion.div {...motionProps(staggerContainer)} className="max-w-xl">
              {/* Eyebrow badge */}
              <motion.div variants={fadeUp} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-50 border border-violet-100 mb-6">
                <span className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
                <span className="text-xs font-medium text-violet-700">AI Quant Platform &mdash; Now in Beta</span>
              </motion.div>

              {/* Headline */}
              <motion.h1 variants={fadeUp} className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold leading-[1.1] tracking-tight text-slate-900 mb-6">
                Smarter investing, powered by{" "}
                <span className="gradient-text">AI + Quant.</span>
              </motion.h1>

              {/* Subtitle */}
              <motion.p variants={fadeUp} className="text-lg text-slate-500 leading-relaxed mb-8">
                58 quant models. 7-layer risk defense. US + Korea markets. The only platform
                that protects your portfolio while growing it.
              </motion.p>

              {/* CTAs */}
              <motion.div variants={fadeUp} className="flex flex-wrap gap-3 mb-6">
                <Link
                  href="/signup"
                  className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
                >
                  Start Free
                  <ArrowRight className="w-4 h-4" />
                </Link>
                <Link
                  href="/simulator/what-if"
                  className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-gradient-to-r from-violet-600 via-blue-500 to-pink-500 text-white text-sm font-semibold shadow-lg shadow-violet-500/25 hover:shadow-xl hover:shadow-violet-500/30 transition-all active:scale-[0.97]"
                >
                  <Clock className="w-4 h-4" />
                  타임머신 체험하기
                </Link>
                <a
                  href="#dashboard-preview"
                  className="inline-flex items-center gap-2 px-7 py-3 rounded-full border border-slate-200 text-slate-700 text-sm font-semibold hover:bg-slate-50 transition-all active:scale-[0.97]"
                >
                  View Demo
                </a>
              </motion.div>

              {/* Trust line */}
              <motion.p variants={fadeUp} className="text-xs text-slate-400">
                No credit card required &middot; Free during beta
              </motion.p>
            </motion.div>

            {/* Right: Dashboard preview card */}
            <motion.div {...motionProps(scaleIn)} className="relative">
              {/* Main card */}
              <div className="glass-panel rounded-2xl p-6 relative">
                {/* Header */}
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <p className="text-xs text-slate-400 mb-0.5">Portfolio Value</p>
                    <p className="text-2xl font-bold text-slate-900 tabular-nums">$127,450</p>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-100">
                    <Shield className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-xs font-semibold text-emerald-700">Risk: 85</span>
                  </div>
                </div>

                {/* Equity curve */}
                <div className="mb-5 rounded-lg bg-slate-50/80 p-3">
                  <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-2">Equity Curve (6M)</p>
                  <MiniEquityCurve />
                </div>

                {/* Signal items */}
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-white border border-slate-100">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-[11px] font-bold text-slate-700">
                        AAPL
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-800">Apple Inc.</p>
                        <p className="text-xs text-slate-400">Technology</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">POSITIVE</span>
                      <span className="text-xs font-mono font-bold text-slate-700">78</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-white border border-slate-100">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-[11px] font-bold text-slate-700">
                        NVDA
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-slate-800">NVIDIA Corp.</p>
                        <p className="text-xs text-slate-400">Semiconductors</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded">NEUTRAL</span>
                      <span className="text-xs font-mono font-bold text-slate-700">52</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Floating cards */}
              <motion.div
                animate={prefersReduced ? {} : { y: [0, -6, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                className="absolute -top-4 -right-4 lg:-right-8 glass-panel rounded-xl px-4 py-2.5 shadow-lg"
              >
                <p className="text-[11px] text-slate-400">MDD Reduced</p>
                <p className="text-lg font-bold text-emerald-600">-52%</p>
              </motion.div>

              <motion.div
                animate={prefersReduced ? {} : { y: [0, -6, 0] }}
                transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut", delay: 1 }}
                className="absolute -bottom-3 -left-3 lg:-left-6 glass-panel rounded-xl px-4 py-2.5 shadow-lg"
              >
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <p className="text-xs font-semibold text-slate-700">58 Models Active</p>
                </div>
              </motion.div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ─── 3. STATS BAR ─── */}
      <section className="bg-slate-900 py-12 md:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12"
          >
            {stats.map((stat) => (
              <motion.div key={stat.label} variants={fadeUp} className="text-center">
                <p className="text-3xl md:text-4xl font-bold text-white mb-1">{stat.value}</p>
                <p className="text-sm text-slate-400">{stat.label}</p>
              </motion.div>
            ))}
          </motion.div>
          <p className="text-xs text-slate-400 text-center mt-4 max-w-2xl mx-auto">
            Based on backtested portfolio simulation. Past performance does not guarantee future results. All figures are hypothetical.
          </p>
        </div>
      </section>

      {/* ─── 4. FEATURES GRID ─── */}
      <section id="features" className="py-20 md:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="text-center max-w-2xl mx-auto mb-16">
            <p className="text-sm font-semibold text-violet-600 mb-3 uppercase tracking-wider">Features</p>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Everything you need to invest smarter
            </h2>
            <p className="text-lg text-slate-500">
              Institutional-grade quantitative analysis tools, now accessible to every investor.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={feature.title}
                  variants={fadeUp}
                  className="sp-card rounded-2xl p-6 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center mb-4 group-hover:bg-primary-gradient transition-colors duration-300">
                    <Icon className="w-5 h-5 text-violet-600 group-hover:text-white transition-colors duration-300" />
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 mb-2">{feature.title}</h3>
                  <p className="text-sm text-slate-500 leading-relaxed mb-4">{feature.description}</p>
                  <Link
                    href={feature.href}
                    className="inline-flex items-center gap-1 text-sm font-medium text-violet-600 group-hover:gap-2 transition-all"
                  >
                    Learn more <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* ─── 5. DASHBOARD PREVIEW (full width) ─── */}
      <section id="dashboard-preview" className="py-20 md:py-28 bg-slate-50/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="text-center max-w-2xl mx-auto mb-12">
            <p className="text-sm font-semibold text-violet-600 mb-3 uppercase tracking-wider">Dashboard</p>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Your portfolio command center
            </h2>
            <p className="text-lg text-slate-500">
              Every metric, signal, and analysis in one unified view.
            </p>
          </motion.div>

          <motion.div {...motionProps(scaleIn)} className="relative">
            {/* Browser frame */}
            <div className="rounded-xl overflow-hidden border border-slate-200 shadow-2xl bg-white">
              {/* Browser chrome */}
              <div className="flex items-center gap-2 px-4 py-3 bg-slate-100 border-b border-slate-200">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-amber-400" />
                  <div className="w-3 h-3 rounded-full bg-emerald-400" />
                </div>
                <div className="flex-1 flex items-center gap-2 ml-4">
                  <div className="flex items-center gap-2 px-3 py-1 rounded-md bg-white border border-slate-200 text-xs text-slate-400 flex-1 max-w-md">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                    app.pivoxquant.com/home
                  </div>
                </div>
              </div>

              {/* Dashboard body */}
              <div className="flex min-h-[400px] md:min-h-[480px]">
                {/* Sidebar */}
                <div className="hidden md:flex flex-col w-52 border-r border-slate-100 bg-white p-4">
                  <div className="flex items-center gap-2 mb-8">
                    <div className="w-7 h-7 rounded-lg bg-primary-gradient flex items-center justify-center">
                      <TrendingUp className="w-3.5 h-3.5 text-white" />
                    </div>
                    <span className="text-sm font-bold">PivoxQuant</span>
                  </div>
                  <nav className="space-y-1">
                    {[
                      { icon: Home, label: "Home", active: true },
                      { icon: Activity, label: "Market", active: false },
                      { icon: Target, label: "Signals", active: false },
                      { icon: Shield, label: "Risk", active: false },
                      { icon: Brain, label: "AI Assistant", active: false },
                      { icon: Bell, label: "Alerts", active: false },
                      { icon: Settings, label: "Settings", active: false },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm ${
                          item.active
                            ? "bg-violet-50 text-violet-700 font-medium"
                            : "text-slate-400 hover:text-slate-600"
                        }`}
                      >
                        <item.icon className="w-4 h-4" />
                        {item.label}
                      </div>
                    ))}
                  </nav>
                </div>

                {/* Main content */}
                <div className="flex-1 p-5 md:p-6">
                  {/* Metric cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                    <div className="rounded-xl border border-slate-100 p-4 bg-white">
                      <p className="text-xs text-slate-400 mb-1">Portfolio Value</p>
                      <p className="text-xl font-bold text-slate-900 tabular-nums">$127,450</p>
                      <p className="text-xs text-emerald-600 font-medium mt-1">+12.4% all time</p>
                    </div>
                    <div className="rounded-xl border border-slate-100 p-4 bg-white">
                      <p className="text-xs text-slate-400 mb-1">Risk Score</p>
                      <div className="flex items-baseline gap-2">
                        <p className="text-xl font-bold text-slate-900">85</p>
                        <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">SAFE</span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">7 layers active</p>
                    </div>
                    <div className="rounded-xl border border-slate-100 p-4 bg-white">
                      <p className="text-xs text-slate-400 mb-1">Active Signals</p>
                      <p className="text-xl font-bold text-slate-900">14</p>
                      <p className="text-xs text-violet-600 font-medium mt-1">3 new today</p>
                    </div>
                  </div>

                  {/* Chart area */}
                  <div className="rounded-xl border border-slate-100 p-4 bg-white mb-6">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-semibold text-slate-700">Portfolio Performance</p>
                      <div className="flex gap-1">
                        {["1W", "1M", "3M", "6M", "1Y"].map((t) => (
                          <span
                            key={t}
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              t === "6M" ? "bg-violet-50 text-violet-700" : "text-slate-400"
                            }`}
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="h-28">
                      <DashboardEquityCurve />
                    </div>
                  </div>

                  {/* Signal list */}
                  <div className="rounded-xl border border-slate-100 bg-white">
                    <div className="px-4 py-3 border-b border-slate-50">
                      <p className="text-sm font-semibold text-slate-700">Recent Signals</p>
                    </div>
                    {[
                      { ticker: "AAPL", name: "Apple", signal: "POSITIVE", score: 78, change: "+1.2%" },
                      { ticker: "MSFT", name: "Microsoft", signal: "POSITIVE", score: 82, change: "+0.8%" },
                      { ticker: "NVDA", name: "NVIDIA", signal: "NEUTRAL", score: 52, change: "-0.3%" },
                    ].map((item) => (
                      <div key={item.ticker} className="flex items-center justify-between px-4 py-2.5 border-b border-slate-50 last:border-0">
                        <div className="flex items-center gap-3">
                          <div className="w-7 h-7 rounded-md bg-slate-100 flex items-center justify-center text-[10px] font-bold text-slate-600">
                            {item.ticker.slice(0, 2)}
                          </div>
                          <div>
                            <p className="text-xs font-semibold text-slate-700">{item.ticker}</p>
                            <p className="text-[10px] text-slate-400">{item.name}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] font-medium text-slate-500">{item.change}</span>
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                              item.signal === "POSITIVE"
                                ? "text-emerald-600 bg-emerald-50"
                                : "text-amber-600 bg-amber-50"
                            }`}
                          >
                            {item.score}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 6. HOW IT WORKS ─── */}
      <section id="how-it-works" className="py-20 md:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="text-center max-w-2xl mx-auto mb-16">
            <p className="text-sm font-semibold text-violet-600 mb-3 uppercase tracking-wider">How It Works</p>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Get started in three simple steps
            </h2>
            <p className="text-lg text-slate-500">
              From sign-up to AI-powered portfolio management in under 5 minutes.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12"
          >
            {steps.map((step, i) => (
              <motion.div key={step.step} variants={fadeUp} className="relative">
                {/* Connection line */}
                {i < steps.length - 1 && (
                  <div className="hidden md:block absolute top-8 left-[calc(50%+40px)] right-[calc(-50%+40px)] h-px bg-slate-200" />
                )}
                <div className="text-center">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-violet-50 border border-violet-100 mb-5">
                    <span className="text-xl font-bold gradient-text">{step.step}</span>
                  </div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-2">{step.title}</h3>
                  <p className="text-sm text-slate-500 leading-relaxed max-w-xs mx-auto">{step.description}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── 7. PRICING ─── */}
      <section id="pricing" className="py-20 md:py-28 bg-slate-50/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div {...motionProps(fadeUp)} className="text-center max-w-2xl mx-auto mb-16">
            <p className="text-sm font-semibold text-violet-600 mb-3 uppercase tracking-wider">Pricing</p>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Simple, transparent pricing
            </h2>
            <p className="text-lg text-slate-500">
              Start free. Upgrade when you need more power.
            </p>
          </motion.div>

          <motion.div
            {...motionProps(staggerContainer)}
            className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto"
          >
            {pricingPlans.map((plan) => (
              <motion.div
                key={plan.name}
                variants={fadeUp}
                className={`rounded-2xl p-6 md:p-8 ${
                  plan.highlighted
                    ? "bg-slate-900 text-white ring-2 ring-slate-900 relative"
                    : "bg-white border border-slate-200"
                }`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary-gradient text-white text-xs font-semibold">
                    Most Popular
                  </div>
                )}

                <div className="mb-6">
                  <h3 className={`text-lg font-semibold mb-1 ${plan.highlighted ? "text-white" : "text-slate-900"}`}>
                    {plan.name}
                  </h3>
                  <p className={`text-sm mb-4 ${plan.highlighted ? "text-slate-400" : "text-slate-500"}`}>
                    {plan.description}
                  </p>
                  <div className="flex items-baseline gap-1">
                    <span className={`text-4xl font-bold ${plan.highlighted ? "text-white" : "text-slate-900"}`}>
                      {plan.currency}{plan.price}
                    </span>
                    {plan.period && (
                      <span className={`text-sm ${plan.highlighted ? "text-slate-400" : "text-slate-500"}`}>
                        {plan.period}
                      </span>
                    )}
                  </div>
                  {plan.originalPrice && (
                    <p className="text-xs text-violet-400 mt-1.5">
                      Introductory price &mdash; normally {plan.currency}{plan.originalPrice}/mo
                    </p>
                  )}
                </div>

                <ul className="space-y-3 mb-8">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5">
                      <Check className={`w-4 h-4 mt-0.5 shrink-0 ${plan.highlighted ? "text-violet-400" : "text-violet-500"}`} />
                      <span className={`text-sm ${plan.highlighted ? "text-slate-300" : "text-slate-600"}`}>
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>

                <Link
                  href="/signup"
                  className={`block text-center w-full px-5 py-2.5 rounded-full text-sm font-semibold transition-all active:scale-[0.97] ${
                    plan.highlighted
                      ? "bg-white text-slate-900 hover:bg-slate-100"
                      : "bg-slate-900 text-white hover:bg-slate-800"
                  }`}
                >
                  {plan.cta}
                </Link>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ─── 8. TESTIMONIAL / QUOTE ─── */}
      <section className="bg-slate-900 py-20 md:py-28">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div {...motionProps(fadeUp)}>
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-white/10 mb-6">
              <Star className="w-6 h-6 text-violet-400" />
            </div>
            <blockquote className="text-2xl md:text-3xl font-semibold text-white leading-snug mb-6">
              &ldquo;The only platform that manages both US and Korean stocks with institutional-grade risk management.&rdquo;
            </blockquote>
            <div className="flex items-center justify-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary-gradient flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-white" />
              </div>
              <div className="text-left">
                <p className="text-sm font-semibold text-white">PivoxQuant Team</p>
                <p className="text-xs text-slate-400">Built for investors, by investors</p>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 9. FINAL CTA ─── */}
      <section className="py-20 md:py-28 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-1/4 w-[500px] h-[500px] rounded-full bg-violet-50/60 blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] rounded-full bg-blue-50/40 blur-3xl" />
        </div>
        <div className="relative max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.div {...motionProps(fadeUp)}>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Start protecting your portfolio today.
            </h2>
            <p className="text-lg text-slate-500 mb-8 max-w-xl mx-auto">
              Join investors who trust AI + Quant models to manage risk and find opportunities across US and Korean markets.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href="/signup"
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-all active:scale-[0.97]"
              >
                Get Started Free
                <ArrowRight className="w-4 h-4" />
              </Link>
              <a
                href="mailto:seanbae1521@gmail.com"
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-full border border-slate-200 text-slate-700 text-sm font-semibold hover:bg-slate-50 transition-all active:scale-[0.97]"
              >
                Contact Sales
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ─── 10. FOOTER ─── */}
      <footer className="border-t border-slate-100 bg-white py-12 md:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
            {/* Brand */}
            <div className="col-span-2">
              <Link href="/" className="flex items-center gap-2.5 mb-4">
                <div className="w-8 h-8 rounded-lg bg-primary-gradient flex items-center justify-center">
                  <TrendingUp className="w-4.5 h-4.5 text-white" />
                </div>
                <span className="text-lg font-bold text-slate-900">
                  Stock<span className="gradient-text">Pilot</span>
                </span>
              </Link>
              <p className="text-sm text-slate-400 leading-relaxed max-w-xs">
                AI-powered quantitative investment platform for smarter, safer investing.
              </p>
            </div>

            {/* Links */}
            {Object.entries(footerLinks).map(([title, links]) => (
              <div key={title}>
                <h4 className="text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3">{title}</h4>
                <ul className="space-y-2">
                  {links.map((link) => (
                    <li key={link.label}>
                      <a href={link.href} className="text-sm text-slate-400 hover:text-slate-600 transition-colors">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom bar */}
          <div className="pt-8 border-t border-slate-100">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <p className="text-xs text-slate-400">
                &copy; {new Date().getFullYear()} PivoxQuant. All rights reserved.
              </p>
              <a
                href="mailto:seanbae1521@gmail.com"
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
              >
                seanbae1521@gmail.com
              </a>
            </div>

            {/* Disclaimer */}
            <p className="text-[10px] text-slate-300 mt-6 text-center leading-relaxed max-w-3xl mx-auto">
              Past performance does not guarantee future results. PivoxQuant provides analytical tools, not investment advice.
              All investing involves risk. Please consult a qualified financial advisor before making investment decisions.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
