"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState, useRef } from "react";

/* ── Page Transition Wrapper ── */
export function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

/* ── Stagger Container + Item ── */
export function StaggerContainer({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.06 } },
      }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 16, scale: 0.97 },
        visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35 } },
      }}
    >
      {children}
    </motion.div>
  );
}

/* ── Counting Number Animation ── */
export function CountUp({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  duration = 1.2,
  className,
}: {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(0);
  const prevValue = useRef(0);

  useEffect(() => {
    const start = prevValue.current;
    const end = value;
    const startTime = performance.now();
    const dur = duration * 1000;

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / dur, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(start + (end - start) * eased);
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
    prevValue.current = end;
  }, [value, duration]);

  const formatted = display.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return (
    <span className={className}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}

/* ── Live Price Ticker (green/red flash) ── */
export function PriceTick({
  value,
  prevValue,
  className,
}: {
  value: number;
  prevValue?: number;
  className?: string;
}) {
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (prevValue === undefined) return;
    if (value > prevValue) setFlash("up");
    else if (value < prevValue) setFlash("down");
    const t = setTimeout(() => setFlash(null), 800);
    return () => clearTimeout(t);
  }, [value, prevValue]);

  return (
    <motion.span
      className={`${className} transition-colors duration-300 ${
        flash === "up"
          ? "text-success bg-success/10"
          : flash === "down"
            ? "text-destructive bg-destructive/10"
            : ""
      }`}
      animate={flash ? { scale: [1, 1.05, 1] } : {}}
      transition={{ duration: 0.3 }}
    >
      {value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
    </motion.span>
  );
}

/* ── Pulse Dot (live indicator) ── */
export function PulseDot({ color = "bg-success" }: { color?: string }) {
  return (
    <span className="relative flex h-2 w-2">
      <span
        className={`absolute inline-flex h-full w-full animate-ping rounded-full ${color} opacity-75`}
      />
      <span className={`relative inline-flex h-2 w-2 rounded-full ${color}`} />
    </span>
  );
}

/* ── Shimmer Loading Skeleton ── */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-gradient-to-r from-muted via-muted/50 to-muted bg-[length:200%_100%] ${className ?? "h-4 w-full"}`}
    />
  );
}

/* ── Card Hover Glow ── */
export function GlowCard({
  children,
  className,
  onClick,
}: {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <motion.div
      className={`relative overflow-hidden rounded-xl border border-border bg-card transition-all ${className}`}
      whileHover={{
        borderColor: "rgba(59, 139, 255, 0.3)",
        boxShadow: "0 0 30px rgba(59, 139, 255, 0.08)",
        y: -2,
      }}
      whileTap={onClick ? { scale: 0.98 } : {}}
      onClick={onClick}
      style={{ cursor: onClick ? "pointer" : "default" }}
    >
      {children}
    </motion.div>
  );
}
