"use client";

import { motion } from "framer-motion";

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      whileHover={{ rotate: [0, -5, 5, 0], transition: { duration: 0.5 } }}
    >
      {/* Background */}
      <defs>
        <linearGradient id="logo-grad" x1="0" y1="0" x2="40" y2="40">
          <stop offset="0%" stopColor="#3b8bff" />
          <stop offset="100%" stopColor="#00d4ff" />
        </linearGradient>
        <linearGradient id="arrow-grad" x1="10" y1="30" x2="30" y2="10">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#ffffff" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="10" fill="url(#logo-grad)" />
      {/* Chart line going up */}
      <path
        d="M8 28 L14 22 L20 25 L26 16 L32 12"
        stroke="url(#arrow-grad)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Arrow head */}
      <path
        d="M29 11 L33 11 L33 15"
        stroke="white"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {/* Subtle glow dot at peak */}
      <circle cx="32" cy="12" r="2" fill="white" opacity="0.8" />
    </motion.svg>
  );
}
