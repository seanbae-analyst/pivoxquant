// Pivox 인스타 프로필 사진 — 랜딩 표지와 같은 워드마크(Playfair Display 500, 대문자, 자간 0.22em)로 'PIVOX' 한 단어.
// 원형으로 잘려도 글자가 들어가게 폭을 원 안쪽(약 64%)에 맞춘다.
// 실행: node docs/marketing/instagram/profile/build.cjs  → pivox-profile.png (1080×1080)
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");
const FONT = path.join(__dirname, "..", "pinned", "playfair-display-latin-var.woff2");
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "Playfair Display"; src: url("file://${FONT}") format("woff2"); font-weight: 400 900; }
html, body { margin: 0; width: 1080px; height: 1080px; background: #050505; }
.c { position: relative; width: 1080px; height: 1080px; display: flex; align-items: center; justify-content: center;
  background: radial-gradient(ellipse 80% 80% at 50% 50%, rgba(245,240,232,.045) 0%, rgba(245,240,232,.015) 40%, transparent 75%), #050505; }
.wm { font-family: "Playfair Display", Georgia, serif; font-weight: 500; text-transform: uppercase; letter-spacing: .22em;
  margin-right: -.22em; line-height: 1; color: #F5F0E8; font-size: 164px; text-shadow: 0 0 24px rgba(245,240,232,.06); }
</style></head><body><div class="c"><div class="wm">Pivox</div></div></body></html>`;
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1080 } });
  // file:// font needs a file:// page (about:blank cannot load it and silently falls back to Georgia)
  const tmp = path.join(__dirname, "_profile.html");
  fs.writeFileSync(tmp, html);
  await p.goto(`file://${tmp}`);
  await p.evaluate(() => document.fonts.ready);
  const loaded = await p.evaluate(() => document.fonts.check('500 164px "Playfair Display"'));
  if (!loaded) throw new Error("Playfair Display did not load");
  const w = await p.evaluate(() => document.querySelector(".wm").getBoundingClientRect().width);
  console.log(`wordmark width ${Math.round(w)}px (${Math.round((w / 1080) * 100)}% of the frame)`);
  await p.screenshot({ path: path.join(__dirname, "pivox-profile.png") });
  fs.unlinkSync(tmp);
  await b.close();
})();
