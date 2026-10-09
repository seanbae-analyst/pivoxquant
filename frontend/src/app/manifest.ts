import type { MetadataRoute } from "next";

// PivoxQuant PWA manifest — Vantablack Luxe theme, editorial shortcuts.
// start_url "/" keeps the manifest aligned with the marketing/home root so
// installed users land on the correct surface based on auth state (root
// redirects to /home for logged-in users, marketing for guests).
export default function manifest(): MetadataRoute.Manifest {
  return {
    // Stable app identity (W3C manifest `id`): without it the browser keys the
    // install on start_url, so changing start_url later would read as a
    // different app.
    id: "/",
    // 2026-10-09: the installed app's name and the install sheet copy describe
    // what the app does — the one loop it ships (멈춤 → 기록 → 거울), all of it
    // on the user's own record. The earlier "당신 포트폴리오의 CFO / 장부를
    // 결산" wording (and the 2026-09-02 note that synced it with layout.tsx
    // SITE_TITLE_KR) is gone from the manifest: this is the name the OS shows
    // under the icon and on the install sheet, so it names the product, not
    // the metaphor. layout.tsx's web title is a separate (marketing) surface.
    name: "PivoxQuant — 멈춤 · 기록 · 거울",
    short_name: "PivoxQuant",
    description:
      "사기 전에 멈춰 이유를 적고, 체결을 기록하고, 그 기록으로 말한 나와 실제의 나를 나란히 봅니다. 종목을 골라 주지 않습니다. 관측 자료이며 투자 권유가 아닙니다.",
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
      { src: "/icons/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      // Maskable: a separate cut whose mark sits inside the 80% safe zone, so
      // Android's circle / squircle / teardrop masks never clip the P or the dot.
      // Sources + renderer: public/icons/*.svg, scripts/render-pwa-assets.mjs.
      { src: "/icons/icon-maskable-192x192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/icon-maskable-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    // Long-press shortcuts — the loop in the order it is lived: 멈춤 before a
    // trade, 기록 after it, 거울 when looking back. Each carries its bottom-nav
    // icon (public/icons/shortcut-*.svg) so the three rows are told apart.
    shortcuts: [
      {
        name: "멈춤 — 사기 전에 이유 적기",
        short_name: "멈춤",
        description: "주문 전에 일곱 개의 질문에 답합니다.",
        url: "/pre-trade",
        icons: [
          { src: "/icons/shortcut-pause-96x96.png", sizes: "96x96", type: "image/png" },
          { src: "/icons/shortcut-pause-192x192.png", sizes: "192x192", type: "image/png" },
        ],
      },
      {
        name: "기록 — 체결에 한 줄 남기기",
        short_name: "기록",
        description: "체결과 그때의 이유를 남깁니다.",
        url: "/journal",
        icons: [
          { src: "/icons/shortcut-journal-96x96.png", sizes: "96x96", type: "image/png" },
          { src: "/icons/shortcut-journal-192x192.png", sizes: "192x192", type: "image/png" },
        ],
      },
      {
        name: "거울 — 말한 나와 실제의 나",
        short_name: "거울",
        description: "가입 때 답한 습관과 최근 30일 기록을 나란히 봅니다.",
        url: "/mirror",
        icons: [
          { src: "/icons/shortcut-mirror-96x96.png", sizes: "96x96", type: "image/png" },
          { src: "/icons/shortcut-mirror-192x192.png", sizes: "192x192", type: "image/png" },
        ],
      },
    ],
  };
}
