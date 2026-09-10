"use client";

/**
 * TopNav — PivoxQuant global top navigation with mega dropdowns.
 * ---------------------------------------------------------------
 * Polish target: Apple HIG + Linear.app + Vercel.com.
 *  • Sticky; shrinks 20% + backdrop blur intensifies after 20px scroll.
 *  • 1 menu: Docs. (Living CFO / Personas / Signature were removed with
 *    the /features/* pages they advertised — see NAV_GROUPS below.)
 *    (Pricing menu removed 2026-05-30 — free Stage 0 launch.)
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
import { PQ_EASE, PQ_DUR_BASE, PQ_DUR_FAST } from "@/lib/motion";
import {
  ArrowRight,
  Compass,
  FileText,
  Gavel,
  Menu,
  Shield,
  type LucideIcon,
} from "lucide-react";
import { FilmGrain } from "./film-grain";
import MobileDrawer from "./mobile-drawer";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/locale";

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
  // The Living Mirror / Personas / Signature groups are gone with the
  // /features/* pages they advertised. A marketing menu that sells screens
  // the product no longer has is worse than no menu.
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

const panelVariants: Variants = {
  hidden: { opacity: 0, y: -6, scale: 0.985 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: PQ_DUR_BASE, ease: PQ_EASE },
  },
  exit: {
    opacity: 0,
    y: -4,
    scale: 0.99,
    transition: { duration: PQ_DUR_FAST, ease: PQ_EASE },
  },
};

// Inner content variants — used when switching between dropdowns while the
// outer panel stays mounted. Fast crossfade prevents the ghosting / faded
// trail that occurs when re-keying the entire AnimatePresence wrapper on
// rapid hover (E2E P1 #16-19).
const contentVariants: Variants = {
  hidden: { opacity: 0, y: 2 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: PQ_DUR_FAST, ease: PQ_EASE },
  },
  exit: {
    opacity: 0,
    y: -2,
    // 0.08s intentionally sub-100ms — ghost-prevention guard (W7.1 #16-19).
    // DO NOT raise to PQ_DUR_MICRO; test nav-dropdown-singleton.test.tsx
    // asserts duration: 0.08 to prevent faded-trail regression.
    transition: { duration: 0.08, ease: PQ_EASE },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: PQ_DUR_BASE, delay: 0.04 * i, ease: PQ_EASE },
  }),
};

/* ───────────────────────── component ───────────────────────── */

export default function TopNav() {
  const t = useT();
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
              : "0.5pt solid var(--pq-ivory-line-soft)",
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
              {/* FINDING-030: canonical wordmark — italic Playfair Display,
                  mixed-case "PivoxQuant" (unified across splash / sidebar /
                  market masthead). Was roman uppercase "PIVOXQUANT". */}
              <span
                className="font-serif"
                style={{
                  color: "var(--pq-ivory)",
                  letterSpacing: "0.01em",
                  fontSize: scrolled ? "15px" : "16px",
                  fontWeight: 500,
                  transition: "font-size 280ms cubic-bezier(0.16,1,0.3,1)",
                }}
              >
                PivoxQuant
              </span>
              <span
                aria-hidden
                className="hidden font-serif md:inline"
                style={{
                  color: "rgba(184,149,106,0.80)",
                  fontSize: "var(--pq-text-eyebrow)",
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
                      className="group relative inline-flex h-9 items-center gap-1.5 px-3 font-serif text-pq-body transition-colors duration-300"
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
                          fontSize: "var(--pq-text-mono-sm)",
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
              {/* FINDING-MOB-002 (design-audit-20260514): the "Log in"
                  link was a 38px tap target — below WCAG 2.5.5's 44px
                  minimum. inline-flex + min-height:44 lifts it to spec
                  without changing the visual padding rhythm. */}
              <Link
                href={user ? "/mirror" : "/login"}
                className="hidden items-center font-serif text-pq-body transition-colors lg:inline-flex"
                style={{
                  color: "rgba(245,240,232,0.68)",
                  letterSpacing: "0.02em",
                  minHeight: 44,
                  padding: "8px 12px",
                }}
              >
                {user ? (user.name?.trim() ? user.name : t("landing.topNav.goToDesk")) : t("landing.topNav.loginLink")}
              </Link>
              <Link
                href={user ? "/mirror" : "/signup"}
                className="group relative inline-flex items-center gap-2 overflow-hidden rounded-sm px-4 font-serif text-pq-body transition-transform duration-200 active:scale-[0.98]"
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
                <span className="relative z-10">{user ? t("landing.topNav.openDesk") : t("landing.topNav.meetCfo")}</span>
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
              {/* FINDING-LAND-007 (design-audit-20260514): 40px
                  (h-10 w-10) is below the 44px WCAG 2.5.5 minimum touch
                  target. Bumped to h-11 w-11 (44px). */}
              <button
                type="button"
                aria-label={t("landing.topNav.openMenu")}
                aria-expanded={drawerOpen}
                onClick={() => setDrawerOpen(true)}
                className="ml-1 inline-flex h-11 w-11 items-center justify-center rounded-sm lg:hidden"
                style={{ color: "var(--pq-ivory)" }}
              >
                <Menu className="h-5 w-5" aria-hidden />
              </button>
            </div>
          </div>

          {/*
            Mega dropdown panel.
            ---------------------------------------------------------------
            Singleton architecture (E2E P1 #16-19 fix):
            The OUTER panel mounts once when any group becomes active and
            stays mounted while the user hovers between groups. Only the
            INNER content swaps (keyed by activeKey) via a fast crossfade.
            This prevents the "ghost trail" where the previous dropdown's
            faded content remained visible during rapid Living CFO →
            Personas → Signature → Pricing → Docs hover sequences.

            Background opacity bumped 0.94 → 0.985 + solid base layer so
            hero text (e.g. "investor language") never bleeds through the
            backdrop blur on Pricing dropdown hover.
          */}
          <AnimatePresence mode="wait">
            {activeGroup && !reduce && (
              <motion.div
                key="nav-mega-panel"
                role="menu"
                aria-label={`${activeGroup.label} menu`}
                data-active-key={activeGroup.key}
                variants={panelVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
                onMouseEnter={clearCloseTimer}
                onMouseLeave={scheduleClose}
                className="pointer-events-auto overflow-hidden"
                style={{
                  // Solid base layer guarantees zero bleed-through behind
                  // the translucent layer + backdrop blur.
                  backgroundColor: "rgba(6,6,6,0.985)",
                  backdropFilter: "blur(28px) saturate(140%)",
                  WebkitBackdropFilter: "blur(28px) saturate(140%)",
                  borderBottom: "0.5pt solid rgba(184,149,106,0.22)",
                  // Lift above hero content stacking context.
                  position: "relative",
                  zIndex: 1,
                }}
              >
                {/* Opaque solid backstop — sits behind blur so hero text
                    cannot bleed through even at low device blur fidelity. */}
                <div
                  aria-hidden
                  className="absolute inset-0"
                  style={{
                    backgroundColor: "var(--pq-ink, #060606)",
                    opacity: 0.96,
                    pointerEvents: "none",
                  }}
                />
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

                  {/*
                    Inner content swap. mode="wait" + ultra-short crossfade
                    (180ms in / 80ms out) keeps a single content tree on
                    screen at any moment — no overlapping ghost layers.
                  */}
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                      key={activeGroup.key}
                      variants={contentVariants}
                      initial="hidden"
                      animate="visible"
                      exit="exit"
                      className="grid grid-cols-1 gap-10 md:grid-cols-[260px_1fr]"
                    >
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
                              fontSize: "var(--pq-text-eyebrow)",
                              letterSpacing: "0.22em",
                            }}
                          >
                            {activeGroup.label}
                          </span>
                        </div>
                        <p
                          className="font-serif"
                          style={{
                            color: "var(--pq-ivory-soft)",
                            fontSize: "var(--pq-text-lead)",
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
                                    fontSize: "var(--pq-text-body)",
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
                                    fontSize: "var(--pq-text-body)",
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
                    </motion.div>
                  </AnimatePresence>
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
