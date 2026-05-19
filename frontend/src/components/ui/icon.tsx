import type { ComponentType, SVGProps } from "react";

/**
 * <Icon /> — standardized lucide-react wrapper for the Wave 2 sweep.
 *
 * Background
 * ──────────
 * Across ~30+ surfaces we ship lucide icons at ad-hoc sizes (h-3, h-3.5,
 * h-4, w-[14px], etc.) and ad-hoc stroke widths (1, 1.25, 1.5, 2). The
 * result is visible weight drift between cards and breakpoints. This
 * wrapper locks the four legal sizes and a single default strokeWidth so
 * downstream sites can migrate via codemod (Wave 2 Track D).
 *
 * Sizes
 *   xs  = 12px   (chip metadata / inline note)
 *   sm  = 16px   (button glyph / table cell affordance — DEFAULT)
 *   md  = 20px   (card header / section affordance)
 *   lg  = 24px   (toolbar / mobile bottom-nav)
 *
 * Stroke
 *   default 1.5  — matches the v3 editorial hairline weight. Bumping to 2
 *   should be a deliberate per-callsite decision (e.g. dense KPI tiles
 *   where 1.5 reads anemic against a heavy mono number).
 *
 * Usage
 *   import { ArrowUpRight } from "lucide-react";
 *   <Icon as={ArrowUpRight} size="sm" />
 *
 *   // Pass-through className still works for color/opacity:
 *   <Icon as={Bell} size="md" className="text-[var(--pq-bronze)]" />
 */

const SIZE_PX = {
  xs: 12,
  sm: 16,
  md: 20,
  lg: 24,
} as const;

export type IconSize = keyof typeof SIZE_PX;

// lucide-react icons accept the standard SVG prop surface plus `size` and
// `strokeWidth` as numbers. Typed as the SVG superset so any lucide icon
// (which exports as ComponentType<LucideProps>) is structurally assignable.
type LucideLike = ComponentType<
  SVGProps<SVGSVGElement> & {
    size?: number | string;
    strokeWidth?: number | string;
  }
>;

export interface IconProps
  extends Omit<SVGProps<SVGSVGElement>, "size" | "strokeWidth"> {
  /** The lucide icon component, e.g. `ArrowUpRight`. */
  as: LucideLike;
  /** Standardized pixel size token. Default: `sm` (16px). */
  size?: IconSize;
  /** Stroke weight override. Default: 1.5 (v3 editorial hairline). */
  strokeWidth?: number;
}

export function Icon({
  as: Component,
  size = "sm",
  strokeWidth = 1.5,
  "aria-hidden": ariaHidden = true,
  ...rest
}: IconProps) {
  const px = SIZE_PX[size];
  return (
    <Component
      size={px}
      strokeWidth={strokeWidth}
      aria-hidden={ariaHidden}
      {...rest}
    />
  );
}
