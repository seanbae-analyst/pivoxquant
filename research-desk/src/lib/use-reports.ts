"use client";

/**
 * 보관함 상태 — localStorage 를 외부 저장소로 보고 useSyncExternalStore 로 읽는다.
 * 서버 렌더에서는 빈 목록, 브라우저에서 첫 읽기 때 localStorage 를 연다.
 */
import { useSyncExternalStore } from "react";
import type { Report } from "./research/types";
import { deleteReport, loadReports, saveReport } from "./storage";

const EMPTY: Report[] = [];
let cache: Report[] | null = null;
const listeners = new Set<() => void>();

function getSnapshot(): Report[] {
  if (cache === null) cache = loadReports();
  return cache;
}

function getServerSnapshot(): Report[] {
  return EMPTY;
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function publish(next: Report[]): void {
  cache = next;
  for (const l of listeners) l();
}

export function useReports(): Report[] {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function keepReport(report: Report): void {
  publish(saveReport(report));
}

export function dropReport(id: string): void {
  publish(deleteReport(id));
}
