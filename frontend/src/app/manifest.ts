import type { MetadataRoute } from "next";

// PivoxQuant PWA manifest — Vantablack Luxe theme, editorial shortcuts.
// start_url "/" keeps the manifest aligned with the marketing/home root so
// installed users land on the correct surface based on auth state (root
// redirects to /home for logged-in users, marketing for guests).
export default function manifest(): MetadataRoute.Manifest {
  return {
    // 2026-09-02: "당신은 당신 포트폴리오의 CFO" 는 삭제된 artifact 리포트
    // 파이프라인의 카피였다. 홈 화면에 설치되면 이 이름이 아이콘 밑에 박히므로
    // 실제 하는 일로 교체 (layout.tsx SITE_TITLE_KR 과 같은 문장을 쓴다).
    name: "PivoxQuant — 당신 포트폴리오의 CFO",
    short_name: "PivoxQuant",
    description:
      "장부를 지키고 결산해 되돌려주는 CFO. 사기 전에 멈춰 이유를 적고, 그 기록으로 자신의 매매 습관을 되비춥니다. 관측 자료이며 투자 권유가 아닙니다.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    display_override: ["standalone", "minimal-ui"],
    orientation: "portrait-primary",
    // Vantablack base — matches globals.css --sp-bg and prevents the white
    // flash on iOS splash before React hydrates.
    background_color: "#050505",
    theme_color: "#050505",
    categories: ["finance", "business", "productivity"],
    lang: "ko-KR",
    dir: "ltr",
    prefer_related_applications: false,
    // Web Share Target (Android share sheet → /journal/import?text=…). GET so
    // the page can prefill its text tab from the query; no file/image share —
    // the server never receives images (docs/product/IMPORT_INBOX_DESIGN.md).
    share_target: {
      action: "/journal/import",
      method: "GET",
      params: { title: "title", text: "text", url: "url" },
    },
    icons: [
      { src: "/icons/icon-72x72.png", sizes: "72x72", type: "image/png", purpose: "any" },
      { src: "/icons/icon-96x96.png", sizes: "96x96", type: "image/png", purpose: "any" },
      { src: "/icons/icon-144x144.png", sizes: "144x144", type: "image/png", purpose: "any" },
      { src: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // Maskable: reuses 512 until a true safe-zone asset is generated.
      // Lighthouse accepts dual-purpose declarations; Chrome prefers explicit.
      { src: "/icons/icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
      { src: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      {
        name: "Portfolio",
        short_name: "Portfolio",
        description: "Open your portfolio dashboard.",
        url: "/portfolio",
        icons: [{ src: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png" }],
      },
      {
        name: "Mirror",
        short_name: "Mirror",
        description: "What you declared, next to what your record shows.",
        url: "/mirror",
        icons: [{ src: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png" }],
      },
      {
        name: "Journal",
        short_name: "Journal",
        description: "Your decision record.",
        url: "/journal",
        icons: [{ src: "/icons/icon-192x192.png", sizes: "192x192", type: "image/png" }],
      },
    ],
  };
}
