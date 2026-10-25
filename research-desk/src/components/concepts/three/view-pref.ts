/**
 * 입체/평면 보기 선택 — localStorage 를 외부 저장소로 보고 useSyncExternalStore 로 읽는다.
 * 서버 렌더와 하이드레이션 순간에는 항상 평면(지원 안 함)으로 시작해 불일치를 피한다.
 */
import { hasWebGL } from "./theme";

export interface ViewPref {
  supported: boolean;
  want: boolean;
}

const KEY = "concepts:view3d";
const SERVER: ViewPref = { supported: false, want: false };

let cache: ViewPref | null = null;
const listeners = new Set<() => void>();

function read(): ViewPref {
  if (cache === null) {
    let want = true;
    try {
      const saved = window.localStorage.getItem(KEY);
      if (saved !== null) want = saved === "1";
    } catch {
      /* 저장소가 막혀 있어도 기본값(입체)으로 돈다 */
    }
    cache = { supported: hasWebGL(), want };
  }
  return cache;
}

export function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function getSnapshot(): ViewPref {
  return read();
}

export function getServerSnapshot(): ViewPref {
  return SERVER;
}

/** 서버 렌더·하이드레이션 순간의 값인가 — 이때는 "WebGL 없음" 같은 판단을 아직 보여주면 안 된다. */
export function isPlaceholder(p: ViewPref): boolean {
  return p === SERVER;
}

export function setWant(want: boolean): void {
  cache = { supported: read().supported, want };
  try {
    window.localStorage.setItem(KEY, want ? "1" : "0");
  } catch {
    /* 위와 같다 */
  }
  for (const l of listeners) l();
}
