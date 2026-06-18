"use client";

/**
 * ProfileDropdown — Avatar + Bronze-accent dropdown with tier chip.
 *
 * Tier visual: Bronze outline + uppercase tracking. Compliance-safe labels.
 * Sign-out is Bronze-accent and separated by a hairline divider.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { User, Settings, Keyboard, HelpCircle, LifeBuoy, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ModalShell } from "@/components/ui/modal-shell";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/locale";

type Tier = "Free" | "Pro" | "Premium" | "Founding";

// Mirror tier-gate.tsx::TIER_LEVEL — surface raw subscription_tier values
// from /api/auth/me (founding_lifetime / premium_plus) as their canonical
// chip label rather than collapsing everything unknown to "Free".
const TIER_LABELS: Record<string, Tier> = {
  free: "Free",
  Free: "Free",
  pro: "Pro",
  Pro: "Pro",
  premium: "Premium",
  Premium: "Premium",
  premium_plus: "Premium",
  founding_lifetime: "Founding",
};

function initials(name?: string, email?: string): string {
  if (name) {
    return name
      .split(/\s+/)
      .map((w) => w[0] ?? "")
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }
  if (email) return email.slice(0, 2).toUpperCase();
  return "PQ";
}

export function ProfileDropdown() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const t = useT();
  const [open, setOpen] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  // Bug #12 (wave 3b): use the real subscription_tier from /api/auth/me
  // instead of the placeholder "Free". The DB value can be free/pro/premium
  // (Stripe webhooks) or founding_lifetime/premium_plus (DEV_FOUNDING_EMAILS
  // / DEV_PREMIUM_EMAILS env-var overrides via services/serializers.py).
  // P1 fix: founding_lifetime users used to fall through the strict equality
  // check and render as "Free" — surface the canonical label instead.
  const tierRaw = user?.subscription_tier;
  const tier: Tier = (tierRaw && TIER_LABELS[tierRaw]) || "Free";

  const displayName = user?.name || t("profileMenu.guest");
  const displayEmail = user?.email || "—";
  const init = initials(displayName, displayEmail);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        setShowShortcuts(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEsc);
    };
  }, []);

  async function handleSignOut() {
    setOpen(false);
    try {
      await logout();
    } finally {
      router.push("/");
    }
  }

  return (
    <>
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setOpen((p) => !p)}
          aria-label={t("profileMenu.ariaLabel")}
          aria-haspopup="menu"
          aria-expanded={open}
          /* 2026-05-17 wave C-3 P2: h-10/w-10 (40px) below Apple HIG 44px tap-target.
             Bump to h-11/w-11 so profile avatar is reliably tappable on mobile. */
          className="flex h-11 w-11 items-center justify-center rounded-full transition-colors hover:bg-[rgba(var(--pq-bronze-wash-rgb),0.08)]"
        >
          <span
            className="flex h-8 w-8 items-center justify-center rounded-full font-mono text-pq-mono-sm font-semibold"
            style={{
              background: "transparent",
              border: "0.5px solid var(--pq-bronze)",
              color: "var(--pq-bronze)",
              letterSpacing: "0.04em",
            }}
          >
            {init}
          </span>
        </button>

        {open && (
          <div
            className="absolute right-0 top-full z-[100] mt-2 w-[260px] overflow-hidden rounded-xl shadow-[0_16px_48px_-16px_rgba(10,10,10,0.3)]"
            style={{ background: "color-mix(in srgb, var(--pq-ivory) 4%, var(--pq-ink))", border: "0.5px solid rgba(245,240,232,0.12)" }}
            role="menu"
          >
            {/* Identity block */}
            <div
              className="px-4 py-4"
              style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
            >
              <div
                className="text-pq-lead font-serif"
                style={{
                  color: "var(--pq-ivory)",
                }}
              >
                {displayName}
              </div>
              <div
                className="mt-0.5 truncate text-xs"
                style={{ color: "var(--pq-muted)" }}
              >
                {displayEmail}
              </div>
              <div className="mt-3">
                <span
                  className="inline-flex items-center rounded px-2 py-0.5 text-pq-eyebrow font-mono"
                  style={{
                    border: "0.5px solid var(--pq-bronze)",
                    color: "var(--pq-bronze)",
                    letterSpacing: "0.2em",
                    textTransform: "uppercase",
                  }}
                >
                  {tier}
                </span>
              </div>
            </div>

            {/* Menu items */}
            <nav className="py-1.5">
              <MenuLink href="/profile" icon={<User className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                {t("profileMenu.myProfile")}
              </MenuLink>
              <MenuLink href="/settings" icon={<Settings className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                {t("profileMenu.settings")}
              </MenuLink>
              {/* Billing 진입점 제거 (DECISIONS.md ✅확정 2026-05-30: 무료 Stage 0).
                  /pricing 은 next.config.ts 307 redirect → /home. i18n 키
                  (profileMenu.billing) 는 보존 — Stage 1 부활 시 이 링크만 복원. */}
              <MenuButton
                icon={<Keyboard className="h-4 w-4" />}
                onClick={() => {
                  setOpen(false);
                  setShowShortcuts(true);
                }}
              >
                {t("profileMenu.keyboardShortcuts")}
              </MenuButton>
              <MenuLink href="/support" icon={<LifeBuoy className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                고객지원
              </MenuLink>
              <MenuLink href="/docs" icon={<HelpCircle className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                {t("profileMenu.helpDocs")}
              </MenuLink>
            </nav>

            {/* Sign out */}
            <div style={{ borderTop: "0.5px solid var(--pq-hairline)" }} className="py-1.5">
              <button
                type="button"
                role="menuitem"
                onClick={handleSignOut}
                className="flex min-h-[44px] w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors hover:bg-[rgba(var(--pq-bronze-wash-rgb),0.08)]"
                style={{ color: "var(--pq-bronze)" }}
              >
                <LogOut className="h-4 w-4" />
                {t("profileMenu.signOut")}
              </button>
            </div>
          </div>
        )}
      </div>

      {showShortcuts && <ShortcutsModal onClose={() => setShowShortcuts(false)} />}
    </>
  );
}

/* ── menu atoms ─────────────────────────────────────── */

function MenuLink({
  href,
  icon,
  children,
  onNavigate,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  onNavigate: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      role="menuitem"
      className={cn(
        "flex min-h-[44px] items-center gap-3 px-4 py-2 text-sm transition-colors hover:bg-[rgba(var(--pq-bronze-wash-rgb),0.08)]",
      )}
      style={{ color: "var(--pq-ivory)" }}
    >
      <span style={{ color: "var(--pq-muted)" }}>{icon}</span>
      {children}
    </Link>
  );
}

function MenuButton({
  icon,
  children,
  onClick,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className="flex min-h-[44px] w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors hover:bg-[rgba(var(--pq-bronze-wash-rgb),0.08)]"
      style={{ color: "var(--pq-ivory)" }}
    >
      <span style={{ color: "var(--pq-muted)" }}>{icon}</span>
      {children}
    </button>
  );
}

/* ── shortcuts modal ────────────────────────────────── */

function ShortcutsModal({ onClose }: { onClose: () => void }) {
  const t = useT();
  const rows: Array<[string, string]> = [
    [t("profileMenu.shortcuts.openSearch"), "⌘ K"],
    [t("profileMenu.shortcuts.goHome"), "G then H"],
    [t("profileMenu.shortcuts.goPortfolio"), "G then P"],
    [t("profileMenu.shortcuts.goWatchlist"), "G then W"],
    [t("profileMenu.shortcuts.closeModal"), "Esc"],
    [t("profileMenu.shortcuts.navList"), "↑ ↓"],
    [t("profileMenu.shortcuts.select"), "Enter"],
  ];

  return (
    <ModalShell onClose={onClose} ariaLabel={t("profileMenu.shortcutsModalTitle")}>
      {/* v3 modal-shell exception per project_design_v3.md — rounded-2xl is intentional on modal/dialog shells (CTAs inside remain rounded-sm). */}
      <div
        className="w-full max-w-md overflow-hidden rounded-2xl shadow-[0_24px_60px_-20px_rgba(10,10,10,0.35)]"
        style={{ background: "color-mix(in srgb, var(--pq-ivory) 4%, var(--pq-ink))", border: "0.5px solid rgba(245,240,232,0.12)" }}
      >
        <div
          className="px-5 py-4"
          style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
        >
          <div
            className="text-pq-eyebrow uppercase"
            style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
          >
            {t("profileMenu.shortcutsKicker")}
          </div>
          <div
            className="mt-0.5 text-xl font-serif"
            style={{ color: "var(--pq-ivory)" }}
          >
            {t("profileMenu.shortcutsModalTitle")}
          </div>
        </div>
        <div className="divide-y" style={{ borderColor: "var(--pq-hairline-soft)" }}>
          {rows.map(([label, keys]) => (
            <div
              key={label}
              className="flex items-center justify-between px-5 py-3"
              style={{ borderBottom: "0.5px solid var(--pq-hairline-soft)" }}
            >
              <span className="text-sm" style={{ color: "var(--pq-ivory)" }}>{label}</span>
              <kbd
                className="rounded px-2 py-0.5 font-mono text-xs"
                style={{ border: "0.5px solid var(--pq-hairline)", color: "var(--pq-bronze)" }}
              >
                {keys}
              </kbd>
            </div>
          ))}
        </div>
        <div className="px-5 py-3 text-right">
          <button
            type="button"
            onClick={onClose}
            className="text-xs uppercase underline underline-offset-4"
            style={{ letterSpacing: "0.18em", color: "var(--pq-bronze)" }}
          >
            {t("profileMenu.close")}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
