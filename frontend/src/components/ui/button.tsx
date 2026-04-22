"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/* ──────────────────────────────────────────────────────────────
   <Button /> — PivoxQuant Editorial Button
   Vantablack / Ivory / Bronze. No gradient, no glow, no pill.
   Pattern adapted from 21st.dev editorial/minimal CTA category.
   (21st.dev list renders client-side so the WebFetch preview is
   empty — palette + motion below mirror the inspected DOM pattern
   already used on the landing page's final CTA block.)

   Variants:
     primary   — ink fill, ivory text. Dominant.
     secondary — ink outline, ink text, ivory-fill on hover.
     ghost     — transparent, ink text, bronze underline reveal
                 (reuses .pq-cta-underline keyframes from globals.css).

   Sizes: sm / md / lg. All share .pq-btn base (focus ring, disabled).
   ────────────────────────────────────────────────────────────── */

const buttonVariants = cva("pq-btn", {
  variants: {
    variant: {
      primary: [
        "bg-[var(--pq-ink)] text-[var(--pq-ivory)]",
        "border border-[var(--pq-ink)]",
        "hover:bg-[var(--pq-bronze)] hover:border-[var(--pq-bronze)] hover:text-[var(--pq-ink)]",
        "active:bg-[var(--pq-bronze-deep)] active:border-[var(--pq-bronze-deep)]",
      ].join(" "),
      secondary: [
        "bg-transparent text-[var(--pq-ink)]",
        "border border-[var(--pq-ink)]",
        "hover:bg-[var(--pq-ink)] hover:text-[var(--pq-ivory)]",
        "active:bg-[var(--pq-bronze-deep)] active:text-[var(--pq-ivory)] active:border-[var(--pq-bronze-deep)]",
      ].join(" "),
      ghost: [
        "pq-cta-underline bg-transparent text-[var(--pq-ink)]",
        "border border-transparent",
        "hover:text-[var(--pq-bronze)]",
      ].join(" "),
    },
    size: {
      sm: "h-8 px-3 text-[11.5px]",
      md: "h-10 px-5 text-[12.5px]",
      lg: "h-12 px-7 text-[13.5px]",
    },
    block: {
      true: "w-full",
      false: "",
    },
  },
  defaultVariants: {
    variant: "primary",
    size: "md",
    block: false,
  },
});

export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

type ButtonBaseProps = {
  loading?: boolean;
  iconLeft?: React.ReactNode;
  iconRight?: React.ReactNode;
};

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants>,
    ButtonBaseProps {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      block,
      loading = false,
      iconLeft,
      iconRight,
      disabled,
      children,
      type = "button",
      ...rest
    },
    ref,
  ) => {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        className={cn(buttonVariants({ variant, size, block }), className)}
        {...rest}
      >
        {loading ? (
          <Spinner />
        ) : (
          iconLeft && <span className="-ml-0.5 inline-flex">{iconLeft}</span>
        )}
        <span>{children}</span>
        {!loading && iconRight && (
          <span className="-mr-0.5 inline-flex">{iconRight}</span>
        )}
      </button>
    );
  },
);
Button.displayName = "Button";

/* Minimal inline spinner — avoids bundling an SVG icon lib. */
function Spinner() {
  return (
    <span
      aria-hidden
      className="inline-block h-3.5 w-3.5 animate-spin rounded-full border border-current border-r-transparent"
    />
  );
}

export { buttonVariants };
