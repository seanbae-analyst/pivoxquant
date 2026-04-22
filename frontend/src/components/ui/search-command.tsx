"use client";

/**
 * SearchCommandMenu — Cmd+K command palette.
 *
 * Sections: Stocks / Pages / Recent.
 * Keyboard: ↑↓ navigate, Enter select, Esc close.
 * Fires a custom window event `pq:search:open` that top-bar listens to,
 * so any button on any page can trigger it.
 *
 * Legal: result labels use "observe" / "view" / "open" only — no buy/sell/recommend.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X, TrendingUp, LayoutGrid, Clock, CornerDownLeft } from "lucide-react";
import { ModalShell } from "@/components/ui/modal-shell";
import { cn } from "@/lib/utils";

type StockItem = { kind: "stock"; ticker: string; name: string; market: string };
type PageItem = { kind: "page"; label: string; path: string; hint?: string };
type RecentItem = { kind: "recent"; label: string; path: string };
export type CommandItem = StockItem | PageItem | RecentItem;

const STOCKS: StockItem[] = [
  { kind: "stock", ticker: "AAPL", name: "Apple Inc.", market: "NASDAQ" },
  { kind: "stock", ticker: "MSFT", name: "Microsoft Corp.", market: "NASDAQ" },
  { kind: "stock", ticker: "NVDA", name: "NVIDIA Corp.", market: "NASDAQ" },
  { kind: "stock", ticker: "GOOGL", name: "Alphabet Inc. Class A", market: "NASDAQ" },
  { kind: "stock", ticker: "META", name: "Meta Platforms Inc.", market: "NASDAQ" },
  { kind: "stock", ticker: "TSLA", name: "Tesla Inc.", market: "NASDAQ" },
  { kind: "stock", ticker: "SPY", name: "SPDR S&P 500 ETF Trust", market: "NYSE ARCA" },
  { kind: "stock", ticker: "QQQ", name: "Invesco QQQ Trust", market: "NASDAQ" },
  { kind: "stock", ticker: "005930.KS", name: "Samsung Electronics", market: "KRX" },
  { kind: "stock", ticker: "000660.KS", name: "SK Hynix", market: "KRX" },
  { kind: "stock", ticker: "035720.KS", name: "Kakao Corp.", market: "KRX" },
];

const PAGES: PageItem[] = [
  { kind: "page", label: "Home", path: "/home", hint: "Dashboard overview" },
  { kind: "page", label: "Portfolio", path: "/portfolio", hint: "Positions & analytics" },
  { kind: "page", label: "Watchlist", path: "/watchlist", hint: "Observed symbols" },
  { kind: "page", label: "Risk", path: "/risk", hint: "Defense status" },
  { kind: "page", label: "Discover", path: "/discover", hint: "Universe scan" },
  { kind: "page", label: "Market", path: "/market", hint: "Indexes & macro" },
  { kind: "page", label: "Alerts", path: "/alerts", hint: "Notification log" },
  { kind: "page", label: "Settings", path: "/settings", hint: "Account & broker" },
];

const RECENTS: RecentItem[] = [
  { kind: "recent", label: "NVDA", path: "/detail/NVDA" },
  { kind: "recent", label: "Portfolio", path: "/portfolio" },
  { kind: "recent", label: "005930.KS", path: "/detail/005930.KS" },
];

const EVT_OPEN = "pq:search:open";

/** Public helper — call from anywhere (button, keyboard shortcut, etc.). */
export function openSearchCommand() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(EVT_OPEN));
  }
}

export function SearchCommandMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setActiveIdx(0);
  }, []);

  // Cmd/Ctrl+K toggle + custom event listener
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    function onOpenEvent() {
      setOpen(true);
    }
    document.addEventListener("keydown", onKey);
    window.addEventListener(EVT_OPEN, onOpenEvent);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener(EVT_OPEN, onOpenEvent);
    };
  }, []);

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Filter sections
  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    const match = (haystack: string) => haystack.toLowerCase().includes(q);

    const stocks = q
      ? STOCKS.filter((s) => match(s.ticker) || match(s.name))
      : STOCKS.slice(0, 5);
    const pages = q
      ? PAGES.filter((p) => match(p.label) || (p.hint ? match(p.hint) : false))
      : PAGES;
    const recents = q ? [] : RECENTS;

    const ordered: CommandItem[] = [...stocks, ...pages, ...recents];
    return { stocks, pages, recents, flat: ordered };
  }, [query]);

  useEffect(() => {
    setActiveIdx(0);
  }, [query]);

  const runItem = useCallback(
    (item: CommandItem) => {
      close();
      if (item.kind === "stock") {
        router.push(`/detail/${item.ticker}`);
      } else {
        router.push(item.path);
      }
    },
    [close, router],
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    const flat = sections.flat;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => (flat.length === 0 ? 0 : (i + 1) % flat.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => (flat.length === 0 ? 0 : (i - 1 + flat.length) % flat.length));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = flat[activeIdx];
      if (item) runItem(item);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  }

  if (!open) return null;

  let runningIdx = 0;
  const nextIdx = () => runningIdx++;

  return (
    <ModalShell onClose={close} ariaLabel="Search palette" className="!items-start !pt-[12vh]">
      <div
        className="w-full max-w-xl overflow-hidden rounded-2xl shadow-[0_24px_60px_-20px_rgba(10,10,10,0.35)]"
        style={{ background: "var(--pq-ivory)", border: "0.5px solid var(--pq-hairline)" }}
      >
        {/* Input row */}
        <div
          className="flex items-center gap-3 px-5 py-4"
          style={{ borderBottom: "0.5px solid var(--pq-hairline)" }}
        >
          <Search className="h-[18px] w-[18px]" style={{ color: "var(--pq-bronze)" }} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search ticker, page…"
            className="flex-1 bg-transparent text-[15px] outline-none placeholder:text-[color:var(--pq-muted)]"
            style={{ color: "var(--pq-ink)" }}
          />
          <button
            onClick={close}
            type="button"
            aria-label="Close"
            className="flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-[rgba(139,111,71,0.08)]"
            style={{ color: "var(--pq-muted)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[360px] overflow-y-auto">
          {sections.flat.length === 0 && (
            <div className="px-5 py-10 text-center text-sm" style={{ color: "var(--pq-muted)" }}>
              No matches for <span className="italic">&ldquo;{query}&rdquo;</span>
            </div>
          )}

          {sections.stocks.length > 0 && (
            <Section title="Stocks" icon={<TrendingUp className="h-3 w-3" />}>
              {sections.stocks.map((s) => {
                const idx = nextIdx();
                return (
                  <CommandRow
                    key={`stock-${s.ticker}`}
                    active={idx === activeIdx}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => runItem(s)}
                  >
                    <span className="w-14 font-mono text-xs font-semibold" style={{ color: "var(--pq-bronze)" }}>
                      {s.ticker}
                    </span>
                    <span className="flex-1 truncate text-sm" style={{ color: "var(--pq-ink)" }}>
                      {s.name}
                    </span>
                    <span
                      className="text-[10px] uppercase"
                      style={{ letterSpacing: "0.12em", color: "var(--pq-muted)" }}
                    >
                      {s.market}
                    </span>
                  </CommandRow>
                );
              })}
            </Section>
          )}

          {sections.pages.length > 0 && (
            <Section title="Pages" icon={<LayoutGrid className="h-3 w-3" />}>
              {sections.pages.map((p) => {
                const idx = nextIdx();
                return (
                  <CommandRow
                    key={`page-${p.path}`}
                    active={idx === activeIdx}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => runItem(p)}
                  >
                    <span className="text-sm" style={{ color: "var(--pq-ink)" }}>
                      {p.label}
                    </span>
                    {p.hint && (
                      <span
                        className="ml-3 flex-1 truncate text-xs italic"
                        style={{ color: "var(--pq-muted)", fontFamily: "var(--font-serif), serif" }}
                      >
                        {p.hint}
                      </span>
                    )}
                    <CornerDownLeft className="h-3.5 w-3.5" style={{ color: "var(--pq-muted)" }} />
                  </CommandRow>
                );
              })}
            </Section>
          )}

          {sections.recents.length > 0 && (
            <Section title="Recent" icon={<Clock className="h-3 w-3" />}>
              {sections.recents.map((r) => {
                const idx = nextIdx();
                return (
                  <CommandRow
                    key={`recent-${r.path}`}
                    active={idx === activeIdx}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => runItem(r)}
                  >
                    <span className="text-sm" style={{ color: "var(--pq-ink)" }}>
                      {r.label}
                    </span>
                  </CommandRow>
                );
              })}
            </Section>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-5 py-2.5 text-[11px]"
          style={{
            borderTop: "0.5px solid var(--pq-hairline)",
            color: "var(--pq-muted)",
            letterSpacing: "0.08em",
          }}
        >
          <span className="uppercase">observe · view · open</span>
          <div className="flex items-center gap-3">
            <Kbd>↑↓</Kbd>
            <Kbd>Enter</Kbd>
            <Kbd>Esc</Kbd>
          </div>
        </div>
      </div>
    </ModalShell>
  );
}

/* ── tiny helpers ───────────────────────────────────── */

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="py-1">
      <div
        className="flex items-center gap-1.5 px-5 pb-1 pt-2 text-[10px] uppercase"
        style={{ letterSpacing: "0.2em", color: "var(--pq-muted)" }}
      >
        {icon}
        {title}
      </div>
      <div>{children}</div>
    </div>
  );
}

function CommandRow({
  active,
  onMouseEnter,
  onClick,
  children,
}: {
  active: boolean;
  onMouseEnter: () => void;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onMouseEnter={onMouseEnter}
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors",
      )}
      style={{
        background: active ? "rgba(139, 111, 71, 0.08)" : "transparent",
      }}
    >
      {children}
    </button>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd
      className="rounded px-1.5 py-0.5 font-mono text-[10px]"
      style={{ border: "0.5px solid var(--pq-hairline)", color: "var(--pq-muted)" }}
    >
      {children}
    </kbd>
  );
}
