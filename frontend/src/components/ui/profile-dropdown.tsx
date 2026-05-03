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
import { User, Settings, CreditCard, Keyboard, HelpCircle, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ModalShell } from "@/components/ui/modal-shell";
import { cn } from "@/lib/utils";

type Tier = "Free" | "Pro" | "Premium";

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
  const [open, setOpen] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  // Mock: Observer until billing resolved
  const tier: Tier = "Free";

  const displayName = user?.name || "Guest";
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
          aria-label="Profile menu"
          aria-haspopup="menu"
          aria-expanded={open}
          className="flex h-10 w-10 items-center justify-center rounded-full transition-colors hover:bg-[rgba(139,111,71,0.08)]"
        >
          <span
            className="flex h-8 w-8 items-center justify-center rounded-full font-mono text-[11px] font-semibold"
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
            style={{ background: "#0E0E0E", border: "0.5px solid rgba(245,240,232,0.12)" }}
            role="menu"
          >
            {/* Identity block */}
            <div
              className="px-4 py-4"
              style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
            >
              <div
                className="text-[15px]"
                style={{
                  fontFamily: "var(--font-serif), serif",
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
                  className="inline-flex items-center rounded px-2 py-0.5 text-[10px]"
                  style={{
                    border: "0.5px solid var(--pq-bronze)",
                    color: "var(--pq-bronze)",
                    letterSpacing: "0.2em",
                    textTransform: "uppercase",
                    fontFamily: "var(--font-mono), monospace",
                  }}
                >
                  {tier}
                </span>
              </div>
            </div>

            {/* Menu items */}
            <nav className="py-1.5">
              <MenuLink href="/profile" icon={<User className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                My Profile
              </MenuLink>
              <MenuLink href="/settings" icon={<Settings className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                Settings
              </MenuLink>
              <MenuLink href="/pricing" icon={<CreditCard className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                Billing
              </MenuLink>
              <MenuButton
                icon={<Keyboard className="h-4 w-4" />}
                onClick={() => {
                  setOpen(false);
                  setShowShortcuts(true);
                }}
              >
                Keyboard shortcuts
              </MenuButton>
              <MenuLink href="/docs" icon={<HelpCircle className="h-4 w-4" />} onNavigate={() => setOpen(false)}>
                Help &amp; Docs
              </MenuLink>
            </nav>

            {/* Sign out */}
            <div style={{ borderTop: "0.5px solid var(--pq-hairline)" }} className="py-1.5">
              <button
                type="button"
                role="menuitem"
                onClick={handleSignOut}
                className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors hover:bg-[rgba(139,111,71,0.08)]"
                style={{ color: "var(--pq-bronze)" }}
              >
                <LogOut className="h-4 w-4" />
                Sign out
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
        "flex items-center gap-3 px-4 py-2 text-sm transition-colors hover:bg-[rgba(139,111,71,0.08)]",
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
      className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm transition-colors hover:bg-[rgba(139,111,71,0.08)]"
      style={{ color: "var(--pq-ivory)" }}
    >
      <span style={{ color: "var(--pq-muted)" }}>{icon}</span>
      {children}
    </button>
  );
}

/* ── shortcuts modal ────────────────────────────────── */

function ShortcutsModal({ onClose }: { onClose: () => void }) {
  const rows: Array<[string, string]> = [
    ["Open search palette", "⌘ K"],
    ["Go to Home", "G then H"],
    ["Go to Portfolio", "G then P"],
    ["Go to Watchlist", "G then W"],
    ["Close modal", "Esc"],
    ["Navigate list", "↑ ↓"],
    ["Select", "Enter"],
  ];

  return (
    <ModalShell onClose={onClose} ariaLabel="Keyboard shortcuts">
      <div
        className="w-full max-w-md overflow-hidden rounded-2xl shadow-[0_24px_60px_-20px_rgba(10,10,10,0.35)]"
        style={{ background: "#0E0E0E", border: "0.5px solid rgba(245,240,232,0.12)" }}
      >
        <div
          className="px-5 py-4"
          style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
        >
          <div
            className="text-[10px] uppercase"
            style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
          >
            Reference
          </div>
          <div
            className="mt-0.5 text-xl"
            style={{ fontFamily: "var(--font-serif), serif", color: "var(--pq-ivory)" }}
          >
            Keyboard shortcuts
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
            Close
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
