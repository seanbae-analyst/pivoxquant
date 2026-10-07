"use client";

import { useSyncExternalStore } from "react";

/**
 * True below the `md` breakpoint (768px) — for the few places where the
 * phone layout is a different tree, not just a hidden class (e.g. the
 * holdings table → cards). Server and first paint say false, so SSR keeps
 * the desktop markup; the phone tree takes over after hydration. Where a
 * class swap is enough (`hidden md:block`), prefer the class.
 */
const QUERY = "(max-width: 767px)";

function subscribe(cb: () => void) {
  const mq = window.matchMedia?.(QUERY);
  mq?.addEventListener?.("change", cb);
  return () => mq?.removeEventListener?.("change", cb);
}

const read = () => window.matchMedia?.(QUERY).matches ?? false;

export function useIsPhone(): boolean {
  return useSyncExternalStore(subscribe, read, () => false);
}
