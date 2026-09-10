"use client";

/**
 * TerminalSidebar — full-height Vantablack navigation rail.
 *
 * 2026-08-31: the nav is now the whole product. The 19→3 fold of
 * 2026-06-15 kept every demoted surface alive behind "More" and a hidden
 * list; this pass deletes them instead of hiding them. What is left is
 * the behavioural loop (멈춤 → 기록 → 거울) plus the account:
 *   PRIMARY · Mirror / Portfolio / Pre-Trade
 *   MORE    · Journal / Profile · Persona / Settings
 *
 * There is no hidden list any more — an item in this file is a page that
 * exists, and every page that exists is in this file.
 *
 * Visual language: ink column, bronze left-edge accent on the active
 * item, editorial uppercase labels with generous spacing. Group labels
 * use the bronze tint at 55% with a hairline divider directly under.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Briefcase,
  Settings as SettingsIcon,
  NotebookPen,
  UserCircle,
  Gavel,
  Contrast,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type TerminalSidebarKey =
  | "mirror"
  | "portfolio"
  | "pre-trade"
  | "journal"
  | "profile"
  | "settings";

type Item = {
  key: TerminalSidebarKey;
  label: string;
  href: string;
  icon: LucideIcon;
};

// PRIMARY — the 3 doors. The behavioural loop IS the product
// (멈춤 → 기록 → 거울).
//
// Naming rule: the product's OWN vocabulary is Korean, the generic app
// shell stays English. 멈춤 / 기록 / 거울 are the words the landing page and
// all six emails teach the reader; a nav that said "Pre-Trade" taught a
// second vocabulary for the same three screens. Portfolio / Profile /
// Settings are loanwords in Korean product UI already and carry no such
// duty, so they keep the terminal tone.
//
// Labels stay literal (no t()) — same reason bottom-nav.tsx gives: a missing
// locale key must never be able to blank the navigation.
const PRIMARY: Item[] = [
  { key: "mirror", label: "거울", href: "/mirror", icon: Contrast },
  { key: "portfolio", label: "Portfolio", href: "/portfolio", icon: Briefcase },
  { key: "pre-trade", label: "멈춤", href: "/pre-trade", icon: Gavel },
];

// MORE — the record's own surfaces plus the account.
const MORE: Item[] = [
  { key: "journal", label: "기록", href: "/journal", icon: NotebookPen },
  { key: "profile", label: "Profile · Persona", href: "/profile", icon: UserCircle },
  { key: "settings", label: "Settings", href: "/settings", icon: SettingsIcon },
];

const ALL_ITEMS: Item[] = [...PRIMARY, ...MORE];

function keyFromPath(pathname: string | null): TerminalSidebarKey | null {
  if (!pathname) return null;
  // Longest-prefix match so "/portfolio/123" lights Portfolio.
  const match = ALL_ITEMS.slice()
    .sort((a, b) => b.href.length - a.href.length)
    .find((it) => pathname === it.href || pathname.startsWith(it.href + "/"));
  return match?.key ?? null;
}

export function TerminalSidebar({
  active,
}: {
  active?: TerminalSidebarKey;
  /** Reserved for future layouts; currently fixed to "rail". */
  variant?: "rail";
}) {
  const pathname = usePathname();
  const resolvedActive = active ?? keyFromPath(pathname);

  return (
    <div className="flex h-full flex-col">
      {/* Brand mark — FINDING-030: canonical wordmark is italic Playfair
          Display mixed-case "PivoxQuant" (splash + landing + market all use
          this form). The sidebar previously rendered roman uppercase
          "PIVOXQUANT", a competing second treatment. Now unified. */}
      <div className="px-6 pt-7 pb-6">
        <span
          className="font-serif"
          style={{
            fontSize: "var(--pq-text-h6)",
            letterSpacing: "0.01em",
            color: "var(--pq-ivory)",
            fontWeight: 500,
          }}
        >
          PivoxQuant
        </span>
      </div>

      {/* Scrollable nav body */}
      <nav className="flex-1 overflow-y-auto" aria-label="Primary">
        {/* The 3 doors — Mirror / Portfolio / Pre-Trade */}
        <ul className="space-y-0.5 px-3" aria-label="Primary doors">
          {PRIMARY.map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>

        <GroupHeader label="More" />
        <ul className="space-y-0.5 px-3 pb-4" aria-label="More">
          {MORE.map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>
      </nav>

      {/* Footer meta — FINDING-040: "v1.0 · Paper" was ambiguous ("paper"
          as document? paper trade?). Spell out the mode so the observation-
          only posture is unmistakable. */}
      <div className="px-6 pb-6 pt-4">
        <span
          className="block font-mono uppercase"
          style={{
            fontSize: "var(--pq-text-kicker)",
            letterSpacing: "0.22em",
            color: "var(--pq-ivory-dim)",
          }}
          title="Paper mode — broker orders disabled, observation only"
        >
          v1.0 · Paper mode (observation only)
        </span>
      </div>
    </div>
  );
}

function GroupHeader({ label }: { label: string }) {
  return (
    <div className="px-3 mt-6 mb-2" aria-hidden="true">
      <span
        className="font-serif uppercase"
        style={{
          fontSize: "var(--pq-text-eyebrow)",
          letterSpacing: "0.22em",
          color: "rgba(184, 149, 106, 0.78)",  /* 0.55 = 2.84:1; bronze needs ≥0.76 on #050505 */
          display: "block",
          paddingLeft: "14px",
        }}
      >
        {label}
      </span>
      <div
        className="mt-1 h-px"
        style={{ backgroundColor: "var(--pq-ivory-line)" }}
      />
    </div>
  );
}

function SidebarLink({ item, isActive }: { item: Item; isActive: boolean }) {
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={item.href}
        aria-current={isActive ? "page" : undefined}
        className="flex items-center gap-2.5 rounded-sm font-serif uppercase transition-colors"
        style={{
          padding: "10px 14px",
          fontSize: "var(--pq-text-body)",
          letterSpacing: "0.2em",
          color: isActive ? "var(--pq-ivory)" : "rgba(245,240,232,0.5)",
          backgroundColor: isActive ? "rgba(247,245,239,0.06)" : "transparent",
          borderLeft: isActive
            ? "3px solid var(--pq-bronze)"
            : "3px solid transparent",
        }}
      >
        <Icon
          className="h-3.5 w-3.5 shrink-0"
          strokeWidth={1.5}
          style={{
            color: isActive ? "var(--pq-bronze)" : "rgba(245,240,232,0.5)",
          }}
        />
        {item.label}
      </Link>
    </li>
  );
}
