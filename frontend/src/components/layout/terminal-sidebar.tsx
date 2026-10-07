"use client";

/**
 * TerminalSidebar — full-height Vantablack navigation rail.
 *
 * 2026-08-31: the nav is now the whole product. The 19→3 fold of
 * 2026-06-15 kept every demoted surface alive behind "More" and a hidden
 * list; this pass deletes them instead of hiding them. What is left is
 * the behavioural loop (멈춤 → 기록 → 거울) plus the account:
 *   거울 / 멈춤 / 기록 / Portfolio / Settings   (Profile · Persona removed 2026-09-12)
 *
 * 2026-09-13: one flat list in loop order. The "More" group had two items
 * left after the 09-12 removals and split 기록 away from 멈춤 and 거울 — the
 * three words the landing page teaches as one loop. Below the nav sits
 * <SidebarRecordCard /> — the user's own record (30-day pause counts,
 * seven-day rhythm, three latest entries), so the rail's lower 70% carries
 * the product's one real asset instead of empty ink.
 *
 * There is no hidden list any more — an item in this file is a page that
 * exists, and every page that exists is in this file.
 *
 * Visual language: ink column, bronze left-edge accent on the active
 * item, Korean labels (no uppercase / wide tracking — spaced-out Hangul reads
 * as broken).
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Briefcase,
  Settings as SettingsIcon,
  NotebookPen,
  Gavel,
  Contrast,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { SidebarRecordCard } from "./sidebar-record-card";

export type TerminalSidebarKey =
  | "mirror"
  | "portfolio"
  | "pre-trade"
  | "journal"
  | "settings";

type Item = {
  key: TerminalSidebarKey;
  label: string;
  href: string;
  icon: LucideIcon;
};

// One list, loop order: 거울 (home) → 멈춤 → 기록, then the two loanword
// screens. The behavioural loop IS the product.
//
// Naming rule: Korean throughout. 멈춤 / 기록 / 거울 are the words the landing
// page and all six emails teach the reader; a nav that said "Pre-Trade"
// taught a second vocabulary for the same three screens. 포트폴리오 / 설정
// were English ("Portfolio" / "Settings") until 2026-10-07 (CEO "영문 라벨도
// 한글로") — now they match bottom-nav.tsx.
//
// Labels stay literal (no t()) — same reason bottom-nav.tsx gives: a missing
// locale key must never be able to blank the navigation.
const ALL_ITEMS: Item[] = [
  { key: "mirror", label: "거울", href: "/mirror", icon: Contrast },
  { key: "pre-trade", label: "멈춤", href: "/pre-trade", icon: Gavel },
  { key: "journal", label: "기록", href: "/journal", icon: NotebookPen },
  { key: "portfolio", label: "포트폴리오", href: "/portfolio", icon: Briefcase },
  { key: "settings", label: "설정", href: "/settings", icon: SettingsIcon },
];

function keyFromPath(pathname: string | null): TerminalSidebarKey | null {
  if (!pathname) return null;
  // Longest-prefix match so "/portfolio/123" lights 포트폴리오.
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
      <nav className="flex-1 overflow-y-auto" aria-label="주 메뉴">
        <ul className="space-y-0.5 px-3" aria-label="페이지">
          {ALL_ITEMS.map((item) => (
            <SidebarLink
              key={item.key}
              item={item}
              isActive={resolvedActive === item.key}
            />
          ))}
        </ul>

        {/* The record — what only this product holds. Sits in the scroll
            body, not the footer, so a long list on a short viewport scrolls
            instead of overlapping the mode label. */}
        <SidebarRecordCard />
      </nav>

      {/* Footer meta — FINDING-040: "v1.0 · Paper" was ambiguous ("paper"
          as document? paper trade?). Spell out the mode so the observation-
          only posture is unmistakable. */}
      <div className="px-6 pb-6 pt-4">
        <span
          className="block font-mono"
          style={{
            fontSize: "var(--pq-text-kicker)",
            color: "var(--pq-ivory-dim)",
          }}
          title="관찰 전용 — 증권사 주문 기능이 꺼져 있습니다"
        >
          v1.0 · 관찰 전용
        </span>
      </div>
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
        className="flex items-center gap-2.5 rounded-sm font-serif transition-colors"
        style={{
          padding: "10px 14px",
          fontSize: "var(--pq-text-body)",
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
