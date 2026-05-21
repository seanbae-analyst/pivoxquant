"use client";

/**
 * SearchCommandMenu — Cmd+K command palette.
 *
 * Sections: Stocks / Pages / Recent.
 * Keyboard: ↑↓ navigate, Enter select, Esc close.
 * Fires a custom window event `pq:search:open` that top-bar listens to,
 * so any button on any page can trigger it.
 *
 * Backend: live search via GET /api/search?q=&limit=10. Debounce 300ms.
 * Recent selections are stored in localStorage (last 5).
 *
 * Legal: result labels use "observe" / "view" / "open" only — no buy/sell/recommend.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X, TrendingUp, LayoutGrid, Clock, CornerDownLeft, Loader2 } from "lucide-react";
import { ModalShell } from "@/components/ui/modal-shell";
import { SEARCH } from "@/lib/endpoints";
import { cn } from "@/lib/utils";
import { displayName, normalizeTicker } from "@/lib/format";
import { useT } from "@/lib/locale";

type StockItem = { kind: "stock"; ticker: string; name: string; market: string };
type PageItem = { kind: "page"; label: string; path: string; hint?: string };
type RecentItem = { kind: "recent"; label: string; path: string };
export type CommandItem = StockItem | PageItem | RecentItem;

// Static Pages list — built per-locale inside the component via useMemo so
// the labels swap when the user toggles language without remounting the
// palette. (Was a module-level constant before Wave C-1.)
const PAGE_DEFS: Array<{ key: string; path: string }> = [
  { key: "home", path: "/home" },
  { key: "portfolio", path: "/portfolio" },
  { key: "watchlist", path: "/watchlist" },
  { key: "risk", path: "/risk" },
  { key: "discover", path: "/discover" },
  { key: "market", path: "/market" },
  { key: "alerts", path: "/alerts" },
  { key: "settings", path: "/settings" },
];

const EVT_OPEN = "pq:search:open";
const RECENTS_KEY = "pq:search:recents";
const RECENTS_MAX = 5;

/** Read recently selected tickers from localStorage. */
function loadRecents(): RecentItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(RECENTS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((r): r is { label: string; path: string } =>
        r && typeof r.label === "string" && typeof r.path === "string",
      )
      .slice(0, RECENTS_MAX)
      .map((r) => ({ kind: "recent" as const, label: r.label, path: r.path }));
  } catch {
    return [];
  }
}

function saveRecent(item: { label: string; path: string }) {
  if (typeof window === "undefined") return;
  try {
    const current = loadRecents();
    const without = current.filter((r) => r.path !== item.path);
    const next = [{ kind: "recent" as const, ...item }, ...without].slice(0, RECENTS_MAX);
    window.localStorage.setItem(
      RECENTS_KEY,
      JSON.stringify(next.map(({ label, path }) => ({ label, path }))),
    );
  } catch {
    /* ignore quota / private-mode failures */
  }
}

/** Public helper — call from anywhere (button, keyboard shortcut, etc.). */
export function openSearchCommand() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(EVT_OPEN));
  }
}

interface BackendSearchResult {
  ticker: string;
  name: string;
  exchange?: string;
  currency?: string;
  is_korean?: boolean;
}

export function SearchCommandMenu() {
  const router = useRouter();
  const t = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const [stocks, setStocks] = useState<StockItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errored, setErrored] = useState(false);
  const [recents, setRecents] = useState<RecentItem[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setActiveIdx(0);
    setStocks([]);
    setErrored(false);
    setLoading(false);
    abortRef.current?.abort();
  }, []);

  // Cmd/Ctrl+K toggle + custom event listener.
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

  // Hydrate recents whenever the palette opens — fresh each time in case
  // another tab updated them.
  useEffect(() => {
    if (open) {
      setRecents(loadRecents());
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Debounced backend search. Cancels any in-flight request before firing
  // a new one so stale responses can't overwrite fresh results.
  useEffect(() => {
    if (!open) return;
    const q = query.trim();
    if (q.length === 0) {
      setStocks([]);
      setErrored(false);
      setLoading(false);
      abortRef.current?.abort();
      return;
    }

    setLoading(true);
    setErrored(false);
    const ctrl = new AbortController();
    abortRef.current?.abort();
    abortRef.current = ctrl;

    const t = window.setTimeout(async () => {
      try {
        const url = `${SEARCH}?q=${encodeURIComponent(q)}&limit=10`;
        const res = await fetch(url, { credentials: "include", signal: ctrl.signal });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body: { results?: BackendSearchResult[] } = await res.json();
        const list = (body.results ?? []).map<StockItem>((r) => ({
          kind: "stock",
          ticker: r.ticker,
          name: displayName(r.ticker, r.name),
          market: r.exchange || (r.is_korean ? "KRX" : "—"),
        }));
        setStocks(list);
      } catch (err) {
        if ((err as { name?: string })?.name === "AbortError") return;
        setStocks([]);
        setErrored(true);
      } finally {
        // Guard: only clear loading for the request that actually fired.
        if (abortRef.current === ctrl) setLoading(false);
      }
    }, 300);

    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [query, open]);

  // Locale-aware Pages list — labels and hints are resolved per render so the
  // palette respects the active locale (Wave C-1 i18n sweep, 2026-05-17).
  const localizedPages = useMemo<PageItem[]>(
    () =>
      PAGE_DEFS.map((p) => ({
        kind: "page",
        label: t(`search.pages.${p.key}`),
        path: p.path,
        hint: t(`search.pages.${p.key}Hint`),
      })),
    [t],
  );

  // Flat order (keyboard nav) mirrors the on-screen section order.
  const sections = useMemo(() => {
    const q = query.trim();
    const hasQuery = q.length > 0;
    const pages = hasQuery
      ? localizedPages.filter(
          (p) =>
            p.label.toLowerCase().includes(q.toLowerCase()) ||
            (p.hint ? p.hint.toLowerCase().includes(q.toLowerCase()) : false),
        )
      : localizedPages;
    const recentSection = hasQuery ? [] : recents;
    const ordered: CommandItem[] = [...stocks, ...pages, ...recentSection];
    return { stocks, pages, recents: recentSection, flat: ordered };
  }, [query, stocks, recents, localizedPages]);

  useEffect(() => {
    setActiveIdx(0);
  }, [query, stocks]);

  const runItem = useCallback(
    (item: CommandItem) => {
      if (item.kind === "stock") {
        saveRecent({ label: item.ticker, path: `/detail/${item.ticker}` });
        router.push(`/detail/${item.ticker}`);
      } else {
        router.push(item.path);
      }
      close();
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
  const hasQuery = query.trim().length > 0;

  return (
    <ModalShell onClose={close} ariaLabel={t("search.paletteAriaLabel")} className="!items-start !pt-[12vh]">
      {/* v3 modal-shell exception per project_design_v3.md — rounded-2xl is intentional on modal/dialog shells (CTAs inside remain rounded-sm). */}
      <div
        className="w-full max-w-xl overflow-hidden rounded-2xl shadow-[0_24px_60px_-20px_rgba(10,10,10,0.35)]"
        style={{ background: "color-mix(in srgb, var(--pq-ivory) 4%, var(--pq-ink))", border: "0.5px solid rgba(245,240,232,0.12)" }}
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
            placeholder={t("search.placeholder")}
            aria-label={t("search.ariaLabel")}
            role="combobox"
            aria-expanded={sections.flat.length > 0}
            aria-haspopup="listbox"
            aria-autocomplete="list"
            aria-controls="cmd-listbox"
            aria-activedescendant={
              sections.flat.length > 0 && activeIdx >= 0
                ? `cmd-opt-${activeIdx}`
                : undefined
            }
            className="flex-1 bg-transparent text-pq-lead outline-none placeholder:text-[color:var(--pq-muted)]"
            style={{ color: "var(--pq-ivory)" }}
          />
          {loading && (
            <Loader2
              className="h-4 w-4 animate-spin"
              style={{ color: "var(--pq-muted)" }}
              aria-label={t("search.ariaSearching")}
            />
          )}
          <button
            onClick={close}
            type="button"
            aria-label={t("search.ariaClose")}
            className="flex h-11 w-11 items-center justify-center rounded-md transition-colors hover:bg-[rgba(139,111,71,0.08)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--pq-bronze)]"
            style={{ color: "var(--pq-muted)" }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div id="cmd-listbox" role="listbox" className="max-h-[360px] overflow-y-auto">
          {errored && (
            <div className="px-5 py-10 text-center text-sm" style={{ color: "var(--pq-muted)" }}>
              {t("search.unavailable")}
            </div>
          )}

          {!errored && hasQuery && !loading && sections.flat.length === 0 && (
            <div className="px-5 py-10 text-center text-sm" style={{ color: "var(--pq-muted)" }}>
              {t("search.noMatches", { query })}
            </div>
          )}

          {hasQuery && loading && sections.flat.length === 0 && (
            <div className="px-5 py-10 text-center text-sm" style={{ color: "var(--pq-muted)" }}>
              {t("search.searching")}
            </div>
          )}

          {sections.stocks.length > 0 && (
            <Section title={t("search.sections.stocks")} icon={<TrendingUp className="h-3 w-3" />}>
              {sections.stocks.map((s) => {
                const idx = nextIdx();
                return (
                  <CommandRow
                    key={`stock-${s.ticker}`}
                    idx={idx}
                    active={idx === activeIdx}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => runItem(s)}
                  >
                    <span className="w-24 font-mono text-xs font-semibold" style={{ color: "var(--pq-bronze)" }}>
                      {normalizeTicker(s.ticker)}
                    </span>
                    <span className="flex-1 truncate text-sm" style={{ color: "var(--pq-ivory)" }}>
                      {s.name}
                    </span>
                    <span
                      className="text-pq-eyebrow uppercase"
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
            <Section title={t("search.sections.pages")} icon={<LayoutGrid className="h-3 w-3" />}>
              {sections.pages.map((p) => {
                const idx = nextIdx();
                return (
                  <CommandRow
                    key={`page-${p.path}`}
                    idx={idx}
                    active={idx === activeIdx}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => runItem(p)}
                  >
                    <span className="text-sm" style={{ color: "var(--pq-ivory)" }}>
                      {p.label}
                    </span>
                    {p.hint && (
                      <span
                        className="ml-3 flex-1 truncate text-xs font-serif"
                        style={{ color: "var(--pq-muted)", }}
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
            <Section title={t("search.sections.recent")} icon={<Clock className="h-3 w-3" />}>
              {sections.recents.map((r) => {
                const idx = nextIdx();
                return (
                  <CommandRow
                    key={`recent-${r.path}`}
                    idx={idx}
                    active={idx === activeIdx}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => runItem(r)}
                  >
                    <span className="text-sm" style={{ color: "var(--pq-ivory)" }}>
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
          className="flex items-center justify-between px-5 py-2.5 text-pq-mono-sm"
          style={{
            borderTop: "0.5px solid var(--pq-hairline)",
            color: "var(--pq-muted)",
            letterSpacing: "0.08em",
          }}
        >
          <span className="uppercase">{t("search.footerTagline")}</span>
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
        className="flex items-center gap-1.5 px-5 pb-1 pt-2 text-pq-eyebrow uppercase"
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
  idx,
  active,
  onMouseEnter,
  onClick,
  children,
}: {
  idx: number;
  active: boolean;
  onMouseEnter: () => void;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="option"
      id={`cmd-opt-${idx}`}
      aria-selected={active}
      onMouseEnter={onMouseEnter}
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--pq-bronze)]",
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
      className="rounded px-1.5 py-0.5 font-mono text-pq-eyebrow"
      style={{ border: "0.5px solid var(--pq-hairline)", color: "var(--pq-muted)" }}
    >
      {children}
    </kbd>
  );
}
