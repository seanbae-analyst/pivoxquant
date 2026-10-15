/**
 * public/sw.js — a notification tap opens its screen, not the cover
 * (2026-10-15 bug hunt). The worker marks the window it opens with
 * `pq_launch=push`; lib/launch-cover.ts reads that mark. The worker runs here
 * in a bare VM context with a fake `self`, so the real file is exercised.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";

import { NOTIFICATION_LAUNCH_PARAM } from "@/lib/launch-cover";

const source = readFileSync(join(process.cwd(), "public/sw.js"), "utf8");
const ORIGIN = "https://www.pivoxquant.com";

type Client = { url: string; focused: boolean; focus: () => Promise<void> };

function worker(open: string[] = []) {
  const handlers: Record<string, (e: unknown) => void> = {};
  const clients: Client[] = open.map((url) => {
    const c: Client = { url, focused: false, focus: async () => void (c.focused = true) };
    return c;
  });
  const opened: string[] = [];
  const self = {
    location: { origin: ORIGIN },
    addEventListener: (type: string, fn: (e: unknown) => void) => {
      handlers[type] = fn;
    },
    clients: {
      matchAll: async () => clients,
      openWindow: async (url: string) => void opened.push(url),
    },
  };
  runInNewContext(source, { self, URL, console });
  const click = async (url?: string) => {
    let done: Promise<unknown> = Promise.resolve();
    handlers.notificationclick({
      notification: { close() {}, data: url === undefined ? {} : { url } },
      waitUntil: (p: Promise<unknown>) => {
        done = p;
      },
    });
    await done;
  };
  return { click, clients, opened };
}

describe("service worker notificationclick", () => {
  it("opens the notification's screen with the launch mark the cover check reads", async () => {
    const w = worker();
    await w.click("/mirror");
    expect(w.opened).toEqual([`${ORIGIN}/mirror?${NOTIFICATION_LAUNCH_PARAM}=push`]);
  });

  it("keeps the notification's own query and defaults to /", async () => {
    const w = worker();
    await w.click("/journal?tab=imports");
    await w.click();
    expect(w.opened).toEqual([
      `${ORIGIN}/journal?tab=imports&${NOTIFICATION_LAUNCH_PARAM}=push`,
      `${ORIGIN}/?${NOTIFICATION_LAUNCH_PARAM}=push`,
    ]);
  });

  it("focuses a window already on that screen instead of opening another", async () => {
    const w = worker([`${ORIGIN}/mirror`]);
    await w.click("/mirror");
    expect(w.clients[0].focused).toBe(true);
    expect(w.opened).toEqual([]);
  });

  it("opens the fill push's own screen when a window shows the same path with another query", async () => {
    // Review 2026-10-15: matching on path alone raised an open /journal and
    // never opened the reason field for the fill the push was about.
    const w = worker([`${ORIGIN}/journal`, `${ORIGIN}/journal?pending=7`]);
    await w.click("/journal?pending=123");
    expect(w.clients.map((c) => c.focused)).toEqual([false, false]);
    expect(w.opened).toEqual([`${ORIGIN}/journal?pending=123&${NOTIFICATION_LAUNCH_PARAM}=push`]);
  });

  it("finds a window it opened earlier — the launch mark in that window's URL is not part of the screen", async () => {
    const w = worker([`${ORIGIN}/mirror?${NOTIFICATION_LAUNCH_PARAM}=push`]);
    await w.click("/mirror");
    expect(w.clients[0].focused).toBe(true);
    expect(w.opened).toEqual([]);
  });
});
