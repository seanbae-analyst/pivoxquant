"use client";

/**
 * CommandPalette — terminal Cmd+K fuzzy launcher.
 *
 * Global palette mounted by the dashboard layout. Features:
 *   - Cmd/Ctrl+K opens; Esc closes.
 *   - Arrow Up/Down navigation; Enter triggers.
 *   - Fuzzy search across three sources:
 *       1. Pages        — static list of 13 dashboard routes.
 *       2. Tickers      — /api/search?q=... debounced live lookup.
 *       3. Actions      — imperative commands (add position, connect, etc).
 *
 * Legal: result labels are observation-only (no BUY/SELL/HOLD / recommend).
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { SEARCH } from "@/lib/endpoints";
import { useFocusTrap } from "@/lib/useFocusTrap";

export interface PaletteAction {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

interface Page {
  id: string;
  label: string;
  hint: string;
  path: string;
}

const PAGES: Page[] = [
  { id: "p-home",      label: "Home",       hint: "Terminal overview",      path: "/home" },
  { id: "p-portfolio", label: "Portfolio",  hint: "Positions & analytics",  path: "/portfolio" },
  { id: "p-watchlist", label: "Watchlist",  hint: "Observed symbols",       path: "/watchlist" },
  { id: "p-signals",   label: "Signals",    hint: "Signal stream",          path: "/signals" },
  { id: "p-risk",      label: "Risk",       hint: "7-Layer Defense",        path: "/risk" },
  { id: "p-discover",  label: "Discover",   hint: "Universe scan",          path: "/discover" },
  { id: "p-market",    label: "Market",     hint: "Indexes & macro",        path: "/market" },
  { id: "p-alerts",    label: "Alerts",     hint: "Notification log",       path: "/alerts" },
  { id: "p-reports",   label: "Reports",    hint: "Dossier archive",        path: "/reports" },
  { id: "p-ai",        label: "AI Chat",    hint: "AI Assistant",           path: "/ai-chat" },
  { id: "p-companion", label: "Companion",  hint: "Personal journal",       path: "/companion" },
  { id: "p-growth",    label: "Growth",     hint: "Progress tracking",      path: "/growth" },
  { id: "p-settings",  label: "Settings",   hint: "Account & broker",       path: "/settings" },
];

interface TickerResult {
  ticker: string;
  name: string;
  market?: string;
  type?: string;
}

interface SearchResponse {
  results?: TickerResult[];
  items?: TickerResult[];
}

export interface CommandPaletteProps {
  /** Extra imperative actions — caller can inject page-local commands. */
  extraActions?: PaletteAction[];
}

export function CommandPalette({ extraActions = [] }: CommandPaletteProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [tickers, setTickers] = useState<TickerResult[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useFocusTrap<HTMLDivElement>(open);

  // Cmd/Ctrl+K toggle + ESC close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 0);
    } else {
      setQuery("");
      setTickers([]);
    }
  }, [open]);

  // Body scroll lock while palette is open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Debounced live ticker search
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setTickers([]);
      return;
    }
    const ac = new AbortController();
    const id = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await fetch(
          `${SEARCH}?q=${encodeURIComponent(q)}&limit=10`,
          { credentials: "include", signal: ac.signal },
        );
        if (!r.ok) throw new Error(String(r.status));
        const j: SearchResponse = await r.json();
        const items = j.results ?? j.items ?? [];
        setTickers(items);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setTickers([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => {
      ac.abort();
      clearTimeout(id);
    };
  }, [query]);

  const actions = useMemo<PaletteAction[]>(
    () => [
      {
        id: "a-add-position",
        label: "Add Position",
        hint: "Record a new holding",
        run: () => router.push("/portfolio?modal=add"),
      },
      {
        id: "a-connect-alpaca",
        label: "Connect Alpaca",
        hint: "US broker (paper)",
        run: () => router.push("/settings?section=broker"),
      },
      {
        id: "a-connect-kis",
        label: "Connect KIS",
        hint: "KR broker (read-only)",
        run: () => router.push("/settings?section=broker"),
      },
      {
        id: "a-weekly-memo",
        label: "Open Weekly Memo",
        hint: "Latest dossier",
        run: () => router.push("/reports"),
      },
      {
        id: "a-logout",
        label: "Sign out",
        hint: "End session",
        run: async () => {
          try {
            await fetch("/api/auth/logout", {
              method: "POST",
              credentials: "include",
            });
          } finally {
            router.push("/login");
          }
        },
      },
      ...extraActions,
    ],
    [router, extraActions],
  );

  if (!open) return null;

  return (
    <div
      ref={dialogRef}
      className="fixed inset-0 z-[90]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      tabIndex={-1}
      onMouseDown={(e) => {
        // Dismiss when clicking the scrim
        if (e.target === e.currentTarget) setOpen(false);
      }}
      style={{
        background: "rgba(0,0,0,0.72)",
        backdropFilter: "blur(4px)",
        WebkitBackdropFilter: "blur(4px)",
        paddingTop: "10vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
      }}
    >
      <div
        style={{
          width: "min(640px, 92vw)",
          background: "#0B0E14",
          border: "1px solid #1A1F2E",
          boxShadow:
            "0 32px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(184,149,106,0.08)",
          overflow: "hidden",
        }}
      >
        <Command
          label="PivoxQuant command palette"
          shouldFilter={true}
          loop
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "12px 14px",
              borderBottom: "1px solid #1A1F2E",
            }}
          >
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9.5,
                letterSpacing: "0.24em",
                color: "#B8956A",
              }}
            >
              ⌘K
            </span>
            <Command.Input
              ref={inputRef}
              value={query}
              onValueChange={setQuery}
              placeholder="Jump to a page, ticker, or action…"
              className="font-mono"
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "rgba(245,240,232,0.95)",
                fontSize: 13,
                padding: "6px 0",
              }}
            />
            <span
              className="font-mono uppercase"
              style={{
                fontSize: 9,
                letterSpacing: "0.22em",
                color: "rgba(245,240,232,0.35)",
              }}
            >
              ESC
            </span>
          </div>

          <Command.List
            style={{
              maxHeight: 440,
              overflowY: "auto",
              padding: 6,
            }}
          >
            <Command.Empty
              style={{
                padding: "18px 14px",
                fontSize: 11,
                color: "rgba(245,240,232,0.4)",
                fontFamily: "var(--font-mono), monospace",
              }}
            >
              {loading ? "Searching…" : "No matches."}
            </Command.Empty>

            <Command.Group heading="Pages">
              {PAGES.map((p) => (
                <Command.Item
                  key={p.id}
                  value={`${p.label} ${p.hint} ${p.path}`}
                  onSelect={() => {
                    router.push(p.path);
                    setOpen(false);
                  }}
                  className="pq-palette-item"
                >
                  <span
                    className="font-mono"
                    style={{ color: "rgba(245,240,232,0.92)" }}
                  >
                    {p.label}
                  </span>
                  <span
                    className="font-mono uppercase ml-auto"
                    style={{
                      fontSize: 9,
                      letterSpacing: "0.22em",
                      color: "rgba(245,240,232,0.4)",
                    }}
                  >
                    {p.hint}
                  </span>
                </Command.Item>
              ))}
            </Command.Group>

            {tickers.length > 0 && (
              <Command.Group heading="Tickers">
                {tickers.map((t) => (
                  <Command.Item
                    key={`t-${t.ticker}`}
                    value={`${t.ticker} ${t.name}`}
                    onSelect={() => {
                      router.push(`/detail/${encodeURIComponent(t.ticker)}`);
                      setOpen(false);
                    }}
                    className="pq-palette-item"
                  >
                    <span
                      className="font-mono"
                      style={{
                        color: "#B8956A",
                        minWidth: 78,
                        letterSpacing: "0.04em",
                      }}
                    >
                      {t.ticker}
                    </span>
                    <span
                      style={{
                        color: "rgba(245,240,232,0.85)",
                        fontSize: 12,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {t.name}
                    </span>
                    {t.market && (
                      <span
                        className="font-mono uppercase ml-auto"
                        style={{
                          fontSize: 9,
                          letterSpacing: "0.22em",
                          color: "rgba(245,240,232,0.35)",
                        }}
                      >
                        {t.market}
                      </span>
                    )}
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            <Command.Group heading="Actions">
              {actions.map((a) => (
                <Command.Item
                  key={a.id}
                  value={`${a.label} ${a.hint ?? ""}`}
                  onSelect={() => {
                    a.run();
                    setOpen(false);
                  }}
                  className="pq-palette-item"
                >
                  <span
                    className="font-mono"
                    style={{ color: "rgba(245,240,232,0.92)" }}
                  >
                    {a.label}
                  </span>
                  {a.hint && (
                    <span
                      className="font-mono uppercase ml-auto"
                      style={{
                        fontSize: 9,
                        letterSpacing: "0.22em",
                        color: "rgba(245,240,232,0.4)",
                      }}
                    >
                      {a.hint}
                    </span>
                  )}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>

          <div
            style={{
              borderTop: "1px solid #1A1F2E",
              padding: "8px 14px",
              display: "flex",
              gap: 12,
              fontFamily: "var(--font-mono), monospace",
              fontSize: 9,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color: "rgba(245,240,232,0.35)",
            }}
          >
            <span>↑↓ navigate</span>
            <span>↵ select</span>
            <span>esc close</span>
          </div>
        </Command>
      </div>

    </div>
  );
}

export default CommandPalette;
