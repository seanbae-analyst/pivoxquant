"use client";

/**
 * <LastSyncNote /> — one quiet line under /mirror's content while the screen
 * is showing the on-device copy of the mirror (lib/persisted-swr-cache) and
 * that copy is older than STALE_AFTER_MS.
 *
 * It says when the numbers were last fetched and that a fresh read is on its
 * way; it disappears by itself the moment the fresh read lands. Nothing is
 * rendered for a fresh screen or a recent copy — a timestamp on every open
 * would be noise. Observational wording only: a time, not a judgement.
 */

import { API } from "@/lib/endpoints";
import { useStaleness } from "@/lib/persisted-swr-cache";

const pad2 = (n: number) => String(n).padStart(2, "0");

export function formatLastSync(at: Date, sameDay: boolean): string {
  const hm = `${pad2(at.getHours())}:${pad2(at.getMinutes())}`;
  return sameDay ? hm : `${at.getMonth() + 1}월 ${at.getDate()}일 ${hm}`;
}

export function LastSyncNote({
  swrKey = API.mirror.home,
  className = "",
}: {
  swrKey?: string;
  className?: string;
}) {
  const { syncedAt, isStale, sameDay } = useStaleness(swrKey);
  if (!syncedAt || !isStale) return null;
  return (
    <p
      role="status"
      data-testid="last-sync-note"
      className={`text-[12px] ${className}`.trim()}
      style={{ color: "rgba(var(--pq-ivory-rgb), 0.45)", lineHeight: 1.5 }}
    >
      마지막 동기화 {formatLastSync(syncedAt, sameDay)} · 최신 기록을 불러오는 중
    </p>
  );
}
