"use client";

/**
 * TopNav — PivoxQuant global top navigation with mega dropdowns.
 * ---------------------------------------------------------------
 * Polish target: Apple HIG + Linear.app + Vercel.com.
 *  • Sticky; shrinks 20% + backdrop blur intensifies after 20px scroll.
 *  • 5 menus: Living CFO / Personas / Signature / Pricing / Docs.
 *  • Mega dropdown: 3-col grid, icon + title + one-line description.
 *  • Vantablack bg, bronze hairline, gradient bronze underline on hover.
 *  • motion/react stagger 0.04s, cubic-bezier(0.16, 1, 0.3, 1).
 *  • ESC + click-outside close.
 *  • FilmGrain overlay at 0.025 opacity inside dropdown panels.
 *  • A11y: aria-haspopup, aria-expanded, focus-visible rings.
 *  • Mobile: hides desktop menu, shows hamburger that opens MobileDrawer.
 *
 * This replaces the inline <nav> inside legacy landing-page.tsx for the
 * new slim landing and for all /features/* pages.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import {
  ArrowRight,
  BarChart3,
  Bookmark,
  Brain,
  Briefcase,
  CircuitBoard,
  Compass,
  FileText,
  Gavel,
  Globe2,
  Layers,
  LineChart,
  Menu,
  Receipt,
  Shield,
  Sparkles,
  Target,
  Users,
  type LucideIcon,
} from "lucide-react";
import { FilmGrain } from "./film-grain";
import MobileDrawer from "./mobile-drawer";
import { useAuth } from "@/lib/auth";

/* ───────────────────────── types ───────────────────────── */

export type NavItem = {
  label: string;
  href: string;
  description: string;
  icon: LucideIcon;
};

export type NavGroup = {
  key: string;
  label: string;
  items: NavItem[];
  footnote?: string;
};

/* ───────────────────────── data ───────────────────────── */

export const NAV_GROUPS: readonly NavGroup[] = [
  {
    key: "living-cfo",
    label: "Living CFO",
    footnote: "The architecture of your personal research desk.",
    items: [
      {
        label: "3-Layer Architecture",
        href: "/features/engine#three-layers",
        description: "Identity · Learning · Artifact. The three strata.",
        icon: Layers,
      },
      {
        label: "Living CFO Loop",
        href: "/features/engine#loop",
        description: "The six-step cycle from onboarding to self-audit.",
        icon: CircuitBoard,
      },
      {
        label: "40-Model Engine",
        href: "/features/engine",
        description: "Quant, risk, and AI models feeding every artifact.",
        icon: Brain,
      },
      {
        label: "Feature Explorer",
        href: "/features/explorer",
        description: "All 17 research artifacts, opened one at a time.",
        icon: Compass,
      },
    ],
  },
  {
    key: "personas",
    label: "Personas",
    footnote: "Eight investor identities. One desk that speaks them all.",
    items: [
      {
        label: "8 CFO Personas",
        href: "/features/personas",
        description: "Growth, Value, Balanced, Income, Quant, and more.",
        icon: Users,
      },
      {
        label: "Sample Reports",
        href: "/features/reports",
        description: "Weekly Memo, Earnings Pre-Brief, Risk Board deck.",
        icon: FileText,
      },
      {
        label: "Dashboard Preview",
        href: "/features/dashboard",
        description: "The research terminal — equity, signals, ledger.",
        icon: LineChart,
      },
      {
        label: "Archetype Quiz",
        href: "/features/personas#archetype",
        description: "20 questions. One honest portrait of how you invest.",
        icon: Target,
      },
    ],
  },
  {
    key: "signature",
    label: "Signature",
    footnote: "The four signature workflows that define the desk.",
    items: [
      {
        label: "Pre-Trade Checklist",
        href: "/features/pre-trade",
        description: "Seven gates before any position change.",
        icon: Shield,
      },
      {
        label: "Korea × US Desk",
        href: "/features/global-desk",
        description: "One pane. KRW and USD. KIS and FMP.",
        icon: Globe2,
      },
      {
        label: "Journal Companion",
        href: "/companion",
        description: "A private thinking partner. Closed beta.",
        icon: Bookmark,
      },
      {
        label: "The Deposition",
        href: "/features/pre-trade#deposition",
        description: "Your own trade, cross-examined — on the record.",
        icon: Gavel,
      },
    ],
  },
  {
    key: "pricing",
    label: "Pricing",
    footnote: "Four tiers. We are never paid when you trade.",
    items: [
      {
        label: "Four Tiers",
        href: "/#pricing",
        description: "Free, Pro, Premium — priced in KRW.",
        icon: Receipt,
      },
      {
        label: "Founding Lifetime",
        href: "/#pricing",
        description: "200 seats. Locked for the life of the product.",
        icon: Sparkles,
      },
      {
        label: "Compare Plans",
        href: "/pricing",
        description: "Full side-by-side of every artifact and module.",
        icon: BarChart3,
      },
      {
        label: "For Teams",
        href: "/pricing#teams",
        description: "Research desks, family offices, private trusts.",
        icon: Briefcase,
      },
    ],
  },
  {
    key: "docs",
    label: "Docs",
    footnote: "Terms, privacy, and the non-advisory boundary.",
    items: [
      {
        label: "FAQ",
        href: "/#faq",
        description: "How observation differs from advice. Plainly.",
        icon: FileText,
      },
      {
        label: "Terms of Service",
        href: "/terms",
        description: "The agreement between you and the desk.",
        icon: Gavel,
      },
      {
        label: "Privacy Policy",
        href: "/privacy",
        description: "What we store, for how long, and why.",
        icon: Shield,
      },
      {
        label: "Contact",
        href: "mailto:hello@pivoxquant.com",
        description: "hello@pivoxquant.com — real humans, promptly.",
        icon: Compass,
      },
    ],
  },
] as const;

/* ───────────────────────── motion ───────────────────────── */

const EASE = [0.16, 1, 0.3, 1] as const;

const panelVariants: Variants = {
  hidden: { opacity: 0, y: -6, scale: 0.985 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.28, ease: EASE },
  },
  exit: {
    opacity: 0,
    y: -4,
    scale: 0.99,
    transition: { duration: 0.18, ease: EASE },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.32, delay: 0.04 * i, ease: EASE },
  }),
};

/* ───────────────────────── component ───────────────────────── */

export default function TopNav() {
  const { user } = useAuth();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [scrolled, setScrolled] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const reduce = useReducedMotion();
  const pathname = usePathname();
  const rootRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [lastPathname, setLastPathname] = useState(pathname);

  // Scroll shrink/opacity
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Close on route change — compute during render so we don't queue a
  // cascade of setStates from inside an effect. Tracking the previous
  // pathname in state (rather than a ref) keeps us inside React's
  // render-phase rules.
  if (pathname !== lastPathname) {
    setLastPathname(pathname);
    if (activeKey !== null) setActiveKey(null);
    if (drawerOpen) setDrawerOpen(false);
  }

  // ESC closes mega dropdown
  useEffect(() => {
    if (!activeKey) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setActiveKey(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [activeKey]);

  // Click outside closes
  useEffect(() => {
    if (!activeKey) return;
    const onClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setActiveKey(null);
      }
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [activeKey]);

  const clearCloseTimer = useCallback(() => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }, []);

  const scheduleClose = useCallback(() => {
    clearCloseTimer();
    closeTimer.current = setTimeout(() => setActiveKey(null), 120);
  }, [clearCloseTimer]);

  const openGroup = useCallback(
    (key: string) => {
      clearCloseTimer();
      setActiveKey(key);
    },
    [clearCloseTimer]
  );

  const activeGroup = useMemo(
    () => NAV_GROUPS.find((g) => g.key === activeKey) ?? null,
    [activeKey]
  );

  // Body scroll lock when drawer open
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (drawerOpen) {
      const prev = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = prev;
      };
    }
  }, [drawerOpen]);

  const navHeight = scrolled ? 56 : 68;

  return (
    <>
      <div
        ref={rootRef}
        onMouseLeave={scheduleClose}
        className="fixed inset-x-0 top-0 z-50"
        style={{
          // Preserve layout height under the fixed nav for anchor targets.
          pointerEvents: "none",
        }}
      >
        <header
          className="pointer-events-auto transition-all duration-300 ease-out"
          style={{
            backgroundColor: scrolled
              ? "rgba(8,8,8,0.82)"
              : "rgba(8,8,8,0.55)",
            backdropFilter: scrolled ? "blur(18px) saturate(140%)" : "blur(10px)",
            WebkitBackdropFilter: scrolled
              ? "blur(18px) saturate(140%)"
              : "blur(10px)",
            borderBottom: scrolled
              ? "0.5pt solid rgba(184,149,106,0.18)"
              : "0.5pt solid rgba(245,240,232,0.06)",
            transition:
              "background-color 280ms cubic-bezier(0.16,1,0.3,1), border-color 280ms ease",
          }}
        >
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8"
               style={{ height: navHeight, transition: "height 280ms cubic-bezier(0.16,1,0.3,1)" }}>
            {/* Brand */}
            <Link
              href="/"
              className="group flex items-baseline gap-3"
              onMouseEnter={() => setActiveKey(null)}
            >
              <span
                className="font-serif"
                style={{
                  color: "var(--pq-ivory)",
                  letterSpacing: "0.22em",
                  fontSize: scrolled ? "12px" : "13px",
                  fontWeight: 500,
                  textTransform: "uppercase",
                  transition: "font-size 280ms cubic-bezier(0.16,1,0.3,1)",
                }}
              >
                PIVOXQUANT
              </span>
              <span
                aria-hidden
                className="hidden font-serif italic md:inline"
                style={{
                  color: "rgba(184,149,106,0.75)",
                  fontSize: "12px",
                  letterSpacing: "0.08em",
                }}
              >
                · Living CFO
              </span>
            </Link>

            {/* Desktop menu */}
            <nav
              aria-label="Primary"
              className="hidden items-center gap-1 lg:flex"
            >
              {NAV_GROUPS.map((group) => {
                const isOpen = activeKey === group.key;
                return (
                  <div
                    key={group.key}
                    onMouseEnter={() => openGroup(group.key)}
                    className="relative"
                  >
                    <button
                      type="button"
                      aria-haspopup="menu"
                      aria-expanded={isOpen}
                      onClick={() => setActiveKey(isOpen ? null : group.key)}
                      onFocus={() => openGroup(group.key)}
                      className="group relative inline-flex h-9 items-center gap-1.5 px-3 font-serif text-[14px] transition-colors duration-300"
                      style={{
                        color: isOpen
                          ? "var(--pq-ivory)"
                          : "rgba(245,240,232,0.68)",
                        letterSpacing: "0.02em",
                      }}
                    >
                      <span>{group.label}</span>
                      <span
                        aria-hidden
                        className="inline-block transition-transform duration-300"
                        style={{
                          transform: isOpen
                            ? "translateY(1px) rotate(180deg)"
                            : "translateY(0) rotate(0)",
                          color: "var(--pq-bronze)",
                          fontSize: "8px",
                          lineHeight: 1,
                        }}
                      >
                        ▾
                      </span>
                      {/* Bronze gradient underline on hover/open */}
                      <span
                        aria-hidden
                        className="pointer-events-none absolute inset-x-2 bottom-1 h-px origin-center transition-transform duration-300"
                        style={{
                          background:
                            "linear-gradient(90deg, transparent 0%, rgba(184,149,106,0.6) 50%, transparent 100%)",
                          transform: isOpen ? "scaleX(1)" : "scaleX(0)",
                        }}
                      />
                    </button>
                  </div>
                );
              })}
            </nav>

            {/* Right cluster */}
            <div className="flex items-center gap-2">
              <Link
                href={user ? "/home" : "/login"}
                className="hidden font-serif text-[14px] transition-colors lg:inline-block"
                style={{
                  color: "rgba(245,240,232,0.68)",
                  letterSpacing: "0.02em",
                  padding: "8px 12px",
                }}
              >
                {user ? (user.name?.trim() ? user.name : "Go to desk") : "Log in"}
              </Link>
              <Link
                href={user ? "/home" : "/signup"}
                className="group relative inline-flex items-center gap-2 overflow-hidden rounded-full px-4 font-serif text-[14px] transition-transform duration-200 active:scale-[0.98]"
                style={{
                  // WCAG 2.5.5 AA — 44x44 minimum tap target. Was 36 (failed
                  // mobile guideline + Apple HIG). Padding/letter-spacing
                  // unchanged so visual presence stays nav-grade restrained.
                  height: 44,
                  backgroundColor: "var(--pq-bronze)",
                  color: "var(--pq-ink)",
                  letterSpacing: "0.02em",
                  fontWeight: 500,
                  boxShadow:
                    "0 1px 0 rgba(255,240,220,0.22) inset, 0 0 0 0.5pt rgba(184,149,106,0.65)",
                }}
              >
                <span className="relative z-10">{user ? "Open desk" : "Meet your CFO"}</span>
                <ArrowRight
                  className="relative z-10 h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-0.5"
                  aria-hidden
                />
                {/* Bronze shimmer */}
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                  style={{
                    background:
                      "linear-gradient(110deg, transparent 40%, rgba(255,240,220,0.35) 50%, transparent 60%)",
                  }}
                />
              </Link>

              {/* Mobile hamburger */}
              <button
                type="button"
                aria-label="Open menu"
                aria-expanded={drawerOpen}
                onClick={() => setDrawerOpen(true)}
                className="ml-1 inline-flex h-10 w-10 items-center justify-center rounded-sm lg:hidden"
                style={{ color: "var(--pq-ivory)" }}
              >
                <Menu className="h-5 w-5" aria-hidden />
              </button>
            </div>
          </div>

          {/* Mega dropdown panel */}
          <AnimatePresence mode="wait">
            {activeGroup && !reduce && (
              <motion.div
                key={activeGroup.key}
                role="menu"
                aria-label={`${activeGroup.label} menu`}
                variants={panelVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                onMouseEnter={clearCloseTimer}
                onMouseLeave={scheduleClose}
                className="pointer-events-auto overflow-hidden"
                style={{
                  backgroundColor: "rgba(6,6,6,0.94)",
                  backdropFilter: "blur(24px) saturate(130%)",
                  WebkitBackdropFilter: "blur(24px) saturate(130%)",
                  borderBottom: "0.5pt solid rgba(184,149,106,0.22)",
                }}
              >
                <div className="relative mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
                  <FilmGrain opacity={0.025} blendMode="soft-light" />
                  {/* Bronze gradient hairline top */}
                  <div
                    aria-hidden
                    className="pointer-events-none absolute inset-x-0 top-0 h-px"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent 0%, rgba(184,149,106,0.55) 50%, transparent 100%)",
                    }}
                  />

                  <div className="grid grid-cols-1 gap-10 md:grid-cols-[260px_1fr]">
                    {/* Left: eyebrow + footnote */}
                    <div>
                      <div className="mb-3 inline-flex items-center gap-2.5">
                        <span
                          aria-hidden
                          className="h-px w-6"
                          style={{ backgroundColor: "rgba(184,149,106,0.7)" }}
                        />
                        <span
                          className="font-serif uppercase"
                          style={{
                            color: "var(--pq-bronze)",
                            fontSize: "12px",
                            letterSpacing: "0.22em",
                          }}
                        >
                          {activeGroup.label}
                        </span>
                      </div>
                      <p
                        className="font-serif italic"
                        style={{
                          color: "rgba(245,240,232,0.78)",
                          fontSize: "15px",
                          lineHeight: 1.55,
                          maxWidth: 240,
                        }}
                      >
                        {activeGroup.footnote}
                      </p>
                    </div>

                    {/* Right: items grid */}
                    <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                      {activeGroup.items.map((item, i) => (
                        <motion.div
                          key={item.href}
                          custom={i}
                          variants={itemVariants}
                          initial="hidden"
                          animate="visible"
                        >
                          <Link
                            href={item.href}
                            onClick={() => setActiveKey(null)}
                            aria-current={
                              pathname === item.href.split("#")[0]
                                ? "page"
                                : undefined
                            }
                            className="group relative flex items-start gap-3.5 rounded-sm p-4 transition-colors duration-300"
                            style={{
                              border: "0.5px solid transparent",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.backgroundColor =
                                "rgba(184,149,106,0.06)";
                              e.currentTarget.style.borderColor =
                                "rgba(184,149,106,0.22)";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.backgroundColor =
                                "transparent";
                              e.currentTarget.style.borderColor = "transparent";
                            }}
                          >
                            <span
                              className="mt-0.5 flex h-9 w-9 flex-none items-center justify-center rounded-sm"
                              style={{
                                backgroundColor: "rgba(184,149,106,0.1)",
                                border: "0.5px solid rgba(184,149,106,0.26)",
                                color: "var(--pq-bronze)",
                              }}
                            >
                              <item.icon className="h-4 w-4" aria-hidden />
                            </span>
                            <div className="min-w-0">
                              <div
                                className="mb-1 flex items-center gap-1.5 font-serif"
                                style={{
                                  color: "var(--pq-ivory)",
                                  fontSize: "14px",
                                  letterSpacing: "0",
                                  fontWeight: 500,
                                }}
                              >
                                {item.label}
                                <ArrowRight
                                  className="h-3 w-3 -translate-x-1 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100"
                                  style={{ color: "var(--pq-bronze)" }}
                                  aria-hidden
                                />
                              </div>
                              <p
                                className="font-serif"
                                style={{
                                  color: "rgba(245,240,232,0.58)",
                                  fontSize: "14px",
                                  lineHeight: 1.5,
                                }}
                              >
                                {item.description}
                              </p>
                            </div>
                          </Link>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </header>
      </div>

      {/* No spacer — TopNav is position:fixed and overlays the first section.
          Feature pages that don't start with a full-bleed hero should add
          their own pt-20/pt-24 to their top container. */}

      {/* Mobile drawer */}
      <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} groups={NAV_GROUPS} />
    </>
  );
}
