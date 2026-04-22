"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

/* ──────────────────────────────────────────────────────────────
   <PQCta /> — Editorial link-style CTA.
   Mirrors the "bronze-underline reveal" pattern used on the
   landing page final CTA block (reuses globals.css .pq-cta-underline).

   Pattern parent: 21st.dev "editorial minimal link CTA" category —
   e.g. tokens listed at https://21st.dev/community/components.
   (Client-rendered preview, so no direct fetch; palette + motion
   below replicate the inspected behavior.)

   Usage:
     <PQCta href="/pricing">View membership tiers</PQCta>
     <PQCta as="button" onClick={…}>Skip</PQCta>
   ────────────────────────────────────────────────────────────── */

type CommonProps = {
  children: React.ReactNode;
  className?: string;
  tone?: "ink" | "ivory";
  withArrow?: boolean;
};

type AsLink = CommonProps & {
  href: string;
  as?: "link";
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
};

type AsButton = CommonProps & {
  as: "button";
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  href?: never;
};

export type PQCtaProps = AsLink | AsButton;

export function PQCta(props: PQCtaProps) {
  const {
    children,
    className,
    tone = "ink",
    withArrow = true,
  } = props;

  const content = (
    <>
      <span>{children}</span>
      {withArrow && (
        <ArrowUpRight
          className="ml-1.5 inline-block h-[14px] w-[14px] -translate-y-px"
          strokeWidth={1.25}
          aria-hidden
        />
      )}
    </>
  );

  const base = cn(
    "pq-cta-underline inline-flex items-center font-serif text-[12.5px] tracking-[0.04em]",
    "transition-colors duration-200",
    tone === "ivory"
      ? "text-[var(--pq-ivory)] hover:text-[var(--pq-bronze-light)]"
      : "text-[var(--pq-ink)] hover:text-[var(--pq-bronze)]",
    className,
  );

  if (props.as === "button") {
    return (
      <button
        type={props.type ?? "button"}
        onClick={props.onClick}
        disabled={props.disabled}
        className={base}
      >
        {content}
      </button>
    );
  }

  return (
    <Link href={props.href} onClick={props.onClick} className={base}>
      {content}
    </Link>
  );
}
