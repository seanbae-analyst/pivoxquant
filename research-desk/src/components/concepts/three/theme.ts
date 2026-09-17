/** 3D 씬이 쓰는 색 — globals.css 의 디자인 토큰과 같은 값. */
export const C = {
  bg: "#0c0b0a",
  raised: "#14120f",
  line: "#2a2622",
  ink: "#e9e3d8",
  dim: "#9a9186",
  faint: "#5f584f",
  accent: "#c99a5b",
  accentDim: "#7a5c33",
  ok: "#7fb069",
  bad: "#d1654f",
  open: "#b5a26b",
} as const;

/**
 * 영역 여섯 개의 색. 별자리에서 어느 무리가 어느 영역인지 알려면 이름표를 띄우는 것보다
 * 색이 낫다 (이름표는 3D 에서 서로 겹친다). 전부 따뜻한 중성 계열로 묶어 톤을 지킨다.
 */
export const AREA_TINT: Record<string, string> = {
  storage: "#a98c6b",
  metadata: "#c9a86b",
  quality: "#8fa08a",
  governance: "#c98a6b",
  ai: "#d4b483",
  org: "#9b8f9e",
};

/** 라벨 DOM 공통 스타일 — 3D 안의 텍스트는 Html 로 그려서 한글이 또렷하게 남는다. */
export const labelStyle: React.CSSProperties = {
  pointerEvents: "none",
  userSelect: "none",
  whiteSpace: "nowrap",
  fontFamily: "var(--font-mono)",
  letterSpacing: "0.01em",
};

/** WebGL 을 쓸 수 있나. 서버에서는 항상 false. */
export function hasWebGL(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** 움직임 줄이기를 켠 사용자에게는 자동 회전과 흐름 알갱이를 멈춘다. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
