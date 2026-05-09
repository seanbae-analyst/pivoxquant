"use client";

/**
 * MobileDrawer — full-screen slide-in menu for TopNav on <lg screens.
 * ----------------------------------------------------------------------
 *  • Slides from right, 400ms cubic-bezier(0.16,1,0.3,1).
 *  • Five accordion groups. Serif caps headers. Tap to expand.
 *  • Sub-items: ivory text, bronze chevron, lucide icon.
 *  • Locks body scroll. Respects safe-area-inset-bottom for sticky CTA.
 *  • ESC + backdrop tap close.
 *  • Reduced-motion: instant open/close, fade only.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { Variants } from "motion/react";
import { ArrowRight, ChevronDown, X } from "lucide-react";
import type { NavGroup } from "./top-nav";
import { useFocusTrap } from "@/lib/useFocusTrap";

const EASE = [0.16, 1, 0.3, 1] as const;

const backdropVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.24, ease: EASE } },
  exit: { opacity: 0, transition: { duration: 0.18, ease: EASE } },
};

const panelVariants: Variants = {
  hidden: { x: "100%" },
  visible: { x: 0, transition: { duration: 0.4, ease: EASE } },
  exit: { x: "100%", transition: { duration: 0.3, ease: EASE } },
};

export default function MobileDrawer({
  open,
  onClose,
  groups,
}: {
  open: boolean;
  onClose: () => void;
  groups: readonly NavGroup[];
}) {
  const reduce = useReducedMotion();
  const [expanded, setExpanded] = useState<string | null>(null);
  const panelRef = useFocusTrap<HTMLElement>(open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Body scroll lock while drawer open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="drawer-backdrop"
            variants={reduce ? undefined : backdropVariants}
            initial={reduce ? { opacity: 1 } : "hidden"}
            animate={reduce ? { opacity: 1 } : "visible"}
            exit={reduce ? { opacity: 0 } : "exit"}
            onClick={onClose}
            aria-hidden
            className="fixed inset-0 z-[60]"
            style={{
              backgroundColor: "rgba(0,0,0,0.55)",
              backdropFilter: "blur(8px)",
              WebkitBackdropFilter: "blur(8px)",
            }}
          />

          {/* Panel */}
          <motion.aside
            key="drawer-panel"
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label="Menu"
            tabIndex={-1}
            variants={reduce ? undefined : panelVariants}
            initial={reduce ? false : "hidden"}
            animate="visible"
            exit="exit"
            className="fixed inset-y-0 right-0 z-[61] flex w-full max-w-[420px] flex-col"
            style={{
              backgroundColor: "#060606",
              borderLeft: "0.5pt solid rgba(184,149,106,0.2)",
              paddingTop: "calc(env(safe-area-inset-top, 0px) + 8px)",
              paddingBottom: "env(safe-area-inset-bottom, 0px)",
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4">
              <span
                className="font-serif"
                style={{
                  color: "var(--pq-ivory)",
                  letterSpacing: "0.22em",
                  fontSize: "12px",
                  textTransform: "uppercase",
                  fontWeight: 500,
                }}
              >
                PIVOXQUANT
              </span>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close menu"
                className="inline-flex h-10 w-10 items-center justify-center rounded-sm"
                style={{ color: "var(--pq-ivory)" }}
              >
                <X className="h-5 w-5" aria-hidden />
              </button>
            </div>

            {/* Groups (accordion) */}
            <nav className="flex-1 overflow-y-auto px-2 pb-6">
              {groups.map((group) => {
                const isOpen = expanded === group.key;
                return (
                  <div key={group.key} className="border-b border-white/5 last:border-b-0">
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded((k) => (k === group.key ? null : group.key))
                      }
                      aria-expanded={isOpen}
                      aria-controls={`drawer-group-${group.key}`}
                      className="flex w-full items-center justify-between px-3 py-5"
                    >
                      <span
                        className="font-serif"
                        style={{
                          color: isOpen ? "var(--pq-ivory)" : "rgba(245,240,232,0.85)",
                          fontSize: "24px",
                          letterSpacing: "-0.01em",
                          fontWeight: 500,
                        }}
                      >
                        {group.label}
                      </span>
                      <ChevronDown
                        className="h-4 w-4 transition-transform duration-300"
                        style={{
                          color: "var(--pq-bronze)",
                          transform: isOpen ? "rotate(180deg)" : "rotate(0)",
                        }}
                        aria-hidden
                      />
                    </button>

                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          id={`drawer-group-${group.key}`}
                          key="content"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{
                            height: "auto",
                            opacity: 1,
                            transition: { duration: 0.3, ease: EASE },
                          }}
                          exit={{
                            height: 0,
                            opacity: 0,
                            transition: { duration: 0.22, ease: EASE },
                          }}
                          className="overflow-hidden"
                        >
                          <div className="pb-3">
                            {group.items.map((item) => (
                              <Link
                                key={item.href}
                                href={item.href}
                                onClick={onClose}
                                className="flex items-center gap-3 rounded-sm px-3 py-3 transition-colors active:bg-white/5"
                              >
                                <span
                                  className="flex h-8 w-8 flex-none items-center justify-center rounded-sm"
                                  style={{
                                    backgroundColor: "rgba(184,149,106,0.1)",
                                    border: "0.5px solid rgba(184,149,106,0.26)",
                                    color: "var(--pq-bronze)",
                                  }}
                                >
                                  <item.icon className="h-3.5 w-3.5" aria-hidden />
                                </span>
                                <div className="min-w-0 flex-1">
                                  <div
                                    className="font-serif"
                                    style={{
                                      color: "var(--pq-ivory)",
                                      fontSize: "15px",
                                      fontWeight: 500,
                                    }}
                                  >
                                    {item.label}
                                  </div>
                                  <div
                                    className="font-serif"
                                    style={{
                                      color: "rgba(245,240,232,0.55)",
                                      fontSize: "12px",
                                      lineHeight: 1.45,
                                    }}
                                  >
                                    {item.description}
                                  </div>
                                </div>
                                <ArrowRight
                                  className="h-3.5 w-3.5 flex-none"
                                  style={{ color: "var(--pq-bronze)" }}
                                  aria-hidden
                                />
                              </Link>
                            ))}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}

              {/* Log in */}
              <Link
                href="/login"
                onClick={onClose}
                className="mt-4 inline-block px-3 py-3 font-serif"
                style={{
                  color: "rgba(245,240,232,0.72)",
                  fontSize: "14px",
                  letterSpacing: "0.02em",
                }}
              >
                Log in →
              </Link>
            </nav>

            {/* Sticky CTA */}
            <div
              className="px-5 pt-3"
              style={{
                borderTop: "0.5pt solid rgba(184,149,106,0.18)",
                paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 16px)",
              }}
            >
              <Link
                href="/signup"
                onClick={onClose}
                className="flex h-12 w-full items-center justify-center gap-2 rounded-[2px] font-serif transition-transform active:scale-[0.98]"
                style={{
                  backgroundColor: "var(--pq-bronze)",
                  color: "var(--pq-ink)",
                  fontSize: "14px",
                  letterSpacing: "0.02em",
                  fontWeight: 500,
                }}
              >
                Meet your CFO
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Link>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
