"use client";

import Image from "next/image";

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <Image
      src="/logo-hero.jpeg"
      alt="StockPilot"
      width={size}
      height={size}
      className="object-cover rounded-lg"
      priority
    />
  );
}
