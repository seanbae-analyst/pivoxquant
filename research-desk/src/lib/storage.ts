/**
 * 보고서 보관 — 브라우저 localStorage. 서버에는 아무것도 남지 않는다.
 * 저장소가 막혀 있어도(사생활 모드 등) 화면은 동작해야 하므로 전부 try/catch.
 */
import type { Report } from "./research/types";

const KEY = "research-desk:reports";
const CAP = 30;

export function loadReports(): Report[] {
  try {
    const raw = globalThis.localStorage?.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as Report[]) : [];
  } catch {
    return [];
  }
}

export function saveReport(report: Report): Report[] {
  const next = [report, ...loadReports().filter((r) => r.id !== report.id)].slice(0, CAP);
  try {
    globalThis.localStorage?.setItem(KEY, JSON.stringify(next));
  } catch {
    /* 저장 실패는 조용히 — 화면에는 이미 보고서가 있다 */
  }
  return next;
}

export function deleteReport(id: string): Report[] {
  const next = loadReports().filter((r) => r.id !== id);
  try {
    globalThis.localStorage?.setItem(KEY, JSON.stringify(next));
  } catch {
    /* 위와 같다 */
  }
  return next;
}
