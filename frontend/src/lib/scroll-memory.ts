/**
 * Per-route scroll memory for the phone app (2026-10-09).
 *
 * Measured before this existed: 기록 scrolled to 900 → 거울 landed at 128 →
 * back to 기록 landed at 128. Each route now keeps its own spot:
 *
 *   - `y`       the window scroll (the dashboard scrolls the document);
 *   - `inner`   vertical scroll containers inside the page (the phone pager
 *               pages scroll themselves) and horizontal page tracks, keyed by
 *               their child-index path under the route frame — stable for a
 *               given page, and resolved again on the way back.
 *
 * Kept in memory and mirrored to sessionStorage so a reload of the installed
 * app keeps it too. Every storage access is guarded: private mode or blocked
 * storage just means the memory lasts until the tab closes.
 */

export interface InnerScroll {
  top: number;
  left: number;
}

export interface RouteScroll {
  y: number;
  inner: Record<string, InnerScroll>;
}

const STORAGE_KEY = "pq-route-scroll:v1";
/** Routes remembered at most — the oldest is dropped past this. */
const MAX_ROUTES = 24;

let memory: Map<string, RouteScroll> | null = null;

function load(): Map<string, RouteScroll> {
  if (memory) return memory;
  memory = new Map();
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed === "object") {
      for (const [path, v] of Object.entries(parsed as Record<string, unknown>)) {
        const entry = v as Partial<RouteScroll> | null;
        if (entry && typeof entry.y === "number") {
          memory.set(path, { y: entry.y, inner: entry.inner ?? {} });
        }
      }
    }
  } catch {
    /* storage unavailable — memory only */
  }
  return memory;
}

/** Write the in-memory map through to sessionStorage. */
export function persistScrollMemory(): void {
  const map = load();
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(map)));
  } catch {
    /* quota / blocked — keep the in-memory copy */
  }
}

function touch(path: string): RouteScroll {
  const map = load();
  const existing = map.get(path);
  const entry = existing ?? { y: 0, inner: {} };
  // Re-insert so the Map's order is "least recently written first".
  map.delete(path);
  map.set(path, entry);
  while (map.size > MAX_ROUTES) {
    const oldest = map.keys().next().value;
    if (oldest === undefined) break;
    map.delete(oldest);
  }
  return entry;
}

export function rememberWindowScroll(path: string, y: number): void {
  touch(path).y = Math.max(0, Math.round(y));
}

export function rememberInnerScroll(path: string, key: string, top: number, left: number): void {
  const entry = touch(path);
  if (top <= 0 && left <= 0) {
    delete entry.inner[key];
    return;
  }
  entry.inner[key] = { top: Math.round(top), left: Math.round(left) };
}

export function readRouteScroll(path: string): RouteScroll | null {
  return load().get(path) ?? null;
}

/** Test-only: drop the in-memory copy so the next read reloads storage. */
export function __resetScrollMemoryForTests(): void {
  memory = null;
}

/**
 * Child-index path of `el` under `root` ("0.2.1"), or null when `el` is not
 * inside `root`.
 */
export function nodePath(root: Element, el: Element): string | null {
  const parts: number[] = [];
  let node: Element | null = el;
  while (node && node !== root) {
    const parent: Element | null = node.parentElement;
    if (!parent) return null;
    parts.push(Array.prototype.indexOf.call(parent.children, node) as number);
    node = parent;
  }
  return node === root ? parts.reverse().join(".") : null;
}

/** Resolve a `nodePath` back to the element, or null if the tree changed. */
export function resolveNodePath(root: Element, path: string): Element | null {
  if (path === "") return root;
  let node: Element | null = root;
  for (const part of path.split(".")) {
    const i = Number(part);
    if (!node || !Number.isInteger(i)) return null;
    node = node.children.item(i);
  }
  return node;
}
