"use client";

/**
 * Settings on a phone — a list, then one section per screen.
 *
 * 2026-10-07, CEO "너무 웹사이트야": /settings was eight screens of stacked
 * cards on a phone. An app's settings is a list of rows; a row opens its
 * section and the back button returns to the list. Desktop keeps the anchor
 * rail and the full page.
 *
 * The open section lives in the URL (`?s=notifications`) through
 * history.pushState, so the phone's own back gesture closes it. The old
 * anchors still work: /settings#import-tokens opens the import pane, etc.
 * Every section stays mounted; only `hidden md:block` changes.
 */

import { useSyncExternalStore } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export type SettingsPane = "account" | "notifications" | "import" | "privacy";

export const SETTINGS_PANES: ReadonlyArray<{ id: SettingsPane; title: string; sub: string }> = [
  { id: "account", title: "계정", sub: "이름 · 이메일 · 로그인 수단 · 언어" },
  { id: "notifications", title: "알림", sub: "푸시 · 이메일 · 월간 리포트" },
  { id: "import", title: "체결 자동 기록", sub: "폰 연결 열쇠 · 설정 안내" },
  { id: "privacy", title: "개인정보 · 데이터", sub: "내보내기 · 로그아웃 · 탈퇴" },
];

const HASH_TO_PANE: Record<string, SettingsPane> = {
  "#section-a": "account",
  "#section-c": "notifications",
  "#import-tokens": "import",
  "#section-e": "privacy",
};

const EVENT = "pq-settings-pane";

export function paneFromLocation(search: string, hash: string): SettingsPane | null {
  const s = new URLSearchParams(search).get("s");
  if (s && SETTINGS_PANES.some((p) => p.id === s)) return s as SettingsPane;
  return HASH_TO_PANE[hash] ?? null;
}

function subscribe(cb: () => void) {
  window.addEventListener("popstate", cb);
  window.addEventListener("hashchange", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("popstate", cb);
    window.removeEventListener("hashchange", cb);
    window.removeEventListener(EVENT, cb);
  };
}

const read = () => paneFromLocation(window.location.search, window.location.hash);

export function useSettingsPane(): SettingsPane | null {
  return useSyncExternalStore(subscribe, read, () => null);
}

export function openPane(p: SettingsPane) {
  window.history.pushState({ pqPane: p }, "", `${window.location.pathname}?s=${p}`);
  window.dispatchEvent(new Event(EVENT));
  window.scrollTo({ top: 0 });
}

export function closePane() {
  if ((window.history.state as { pqPane?: string } | null)?.pqPane) {
    window.history.back();
    return;
  }
  // Opened by a deep link — there is no list entry behind it to go back to.
  window.history.replaceState(null, "", window.location.pathname);
  window.dispatchEvent(new Event(EVENT));
  window.scrollTo({ top: 0 });
}

/** The row list — phone only, shown when no section is open. */
export function SettingsPhoneList() {
  return (
    <nav aria-label="설정 항목" className="md:hidden" data-testid="settings-phone-list">
      <ul className="overflow-hidden rounded-[4px] border border-[var(--pq-ivory-line)]">
        {SETTINGS_PANES.map((p, i) => (
          <li key={p.id} className={i > 0 ? "border-t border-[var(--pq-ivory-line)]" : ""}>
            <button
              type="button"
              onClick={() => openPane(p.id)}
              className="flex min-h-[64px] w-full items-center gap-3 px-4 py-3 text-left active:bg-[rgba(245,240,232,0.04)]"
              data-testid={`settings-row-${p.id}`}
            >
              <span className="flex-1">
                <span className="block text-[16px] text-[var(--pq-ivory)]">{p.title}</span>
                <span className="mt-0.5 block text-[13px] text-[var(--pq-ivory-dim)]">{p.sub}</span>
              </span>
              <ChevronRight size={18} className="text-[var(--pq-ivory-faint)]" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Back row above an open section — phone only. */
export function SettingsPhoneBack({ pane }: { pane: SettingsPane }) {
  const title = SETTINGS_PANES.find((p) => p.id === pane)?.title ?? "";
  return (
    <div className="mb-4 flex items-center gap-1 md:hidden">
      <button
        type="button"
        onClick={closePane}
        className="-ml-2 inline-flex min-h-[44px] items-center gap-0.5 px-2 text-[15px] text-[var(--pq-bronze-light)]"
        data-testid="settings-phone-back"
      >
        <ChevronLeft size={18} aria-hidden />
        설정
      </button>
      <span className="ml-1 text-[15px] text-[var(--pq-ivory)]">· {title}</span>
    </div>
  );
}
