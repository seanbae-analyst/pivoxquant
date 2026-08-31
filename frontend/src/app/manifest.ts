import type { MetadataRoute } from "next";

// PivoxQuant PWA manifest — Vantablack Luxe theme, editorial shortcuts.
// start_url "/" keeps the manifest aligned with the marketing/home root so
// installed users land on the correct surface based on auth state (root
// redirects to /home for logged-in users, marketing for guests).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "PivoxQuant — 당신은 당신 포트폴리오의 CFO",
    short_name: "PivoxQuant",
    description:
      "A quiet operating system for private capital. Observational research tool — not investment advice.",
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
