// Pivox 인스타그램 고정 게시물 3개 (1080×1350 캐러셀) — Quant · Map · Data 를 같은 구성으로.
// 표지는 세 제품 랜딩 첫 화면과 같다: 검은 바탕 + 은은한 스폿 + Playfair 500 대문자 워드마크(자간 0.22em),
// 'PIVOX' 아이보리 · 제품명 브론즈 (PivoxMap Cover.tsx 와 같은 규칙).
// 실행: node docs/marketing/instagram/pinned/build.cjs  → out/<제품>/01.png …
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const OUT = path.join(__dirname, "out");
const FONT = path.join(__dirname, "playfair-display-latin-var.woff2");

const PRODUCTS = [
  {
    id: "quant", n: "01", name: "Quant", url: "pivoxquant.com", tag: "나의 거래",
    cover: "사기 전에 멈추고, 적고, 돌아봅니다",
    note: "관측 자료이며 투자 권유가 아닙니다.",
    define: {
      kicker: "PivoxQuant 는",
      head: "사기 전에 한 번 멈추고,<br>이유를 적고,<br>나중에 돌아보는 도구예요.",
      body: "이미 가진 포트폴리오를 읽고, 내 기록을 거울처럼 되비춰요. 미국 · 한국 주식.",
    },
    why: {
      kicker: "왜 기록인가",
      head: "부자로 만들어 준다고<br>약속하지 않습니다.",
      body: "1991–96년 미국 개인투자자 6만여 가구를 본 연구에서, 회전율 상위 20%는 하위 20%보다 거래비용을 뺀 연 수익률이 약 7%p 낮았어요.",
      src: "Barber & Odean (2000), Journal of Finance",
    },
    how: {
      kicker: "멈춤 → 기록 → 거울",
      items: [
        ["멈춤", "사기 전, 일곱 가지 질문에 답하며 이유를 적어요."],
        ["기록", "산 이유와 사려다 만 이유가 한자리에 남아요. 보유기간 · 회전율 · 집중도 같은 습관 6가지를 보여 줘요."],
        ["거울", "처음에 적은 '내 방식'과 최근 30일 실제 거래 사이의 간극을 보여 줘요."],
      ],
    },
    rules: {
      kicker: "하지 않는 것",
      items: ["점수 · 등급 · 유형 라벨", "종목 고르기", "사라 · 팔라는 신호", "주문 — 증권 계좌는 읽기만"],
    },
    cta: { status: ["클로즈드 베타", "무료"], line: "기록은 사기 전에 시작돼요." },
  },
  {
    id: "map", n: "02", name: "Map", url: "map.pivoxquant.com", tag: "회사의 데이터",
    cover: "컬럼마다 표준용어를 붙입니다",
    define: {
      kicker: "PivoxMap 은",
      head: "표준 사전과 파일을 올리면,<br>컬럼마다 표준용어를<br>제안하는 도구예요.",
      body: "엑셀 · CSV · ODS · XML · JSON. 웹 시스템에서 받은 '.xls' 표와 보고서형 시트도 읽어요.",
    },
    why: {
      kicker: "왜 표준인가",
      head: "같은 '등록일자'가<br>파일마다 다른 이름으로.",
      body: "REG_DT · 등록일 · CRT_DATE … 이름이 다르면 합칠 수도, 비교할 수도 없어요. 사람이 하나씩 맞추던 일을 줄여요.",
      src: "예: REG_DT → 등록일자 (REG_YMD)",
    },
    how: {
      kicker: "올리고 → 검토하고 → 내보내기",
      items: [
        ["자동 확정", "확신 있는 건 바로 붙이고, 애매한 것만 사람이 키보드로 승인해요."],
        ["쌓이는 사전", "승인 · 수정이 동의어로 쌓여 다음 파일부터 자동으로 잡혀요. 사전 없이 첫 파일로 시작해도 돼요."],
        ["증빙까지", "리포트 · CSV, 공공데이터 품질관리 매뉴얼 예시 양식의 평가 증빙 xlsx 로 내보내요."],
      ],
    },
    rules: {
      kicker: "데이터를 다루는 방식",
      items: ["파일은 브라우저 안에서 읽어요", "서버로 가는 건 컬럼명 · 값의 형식뿐 — 원본 값 0", "개인정보 의심 컬럼은 표시해요", "누가 · 언제 · 무엇으로 바꿨는지 지우지 않고 기록해요"],
    },
    cta: { status: ["샘플은 로그인 없이", "팀 작업 공간"], line: "흩어진 컬럼명을 하나의 표준으로." },
  },
  {
    id: "data", n: "03", name: "Data", url: "data.pivoxquant.com", tag: "산업의 변화",
    cover: "기업의 AI 전환을 매일 숫자로",
    define: {
      kicker: "PivoxData 는",
      head: "기업의 AI 전환(AX)을<br>매일 같은 방식으로<br>숫자로 보는 레이더예요.",
      body: "업종별 도입률, 기업이 돈을 내는 AI, 개발 현장의 도구 경쟁, 빅테크가 쓰는 돈까지.",
    },
    why: {
      kicker: "왜 숫자인가",
      head: "기사보다 먼저<br>움직이는 숫자가 있어요.",
      body: "개발자가 실제로 내려받는 패키지, 연구자가 쓰는 말, 사람들이 받는 오픈 모델, 빅테크의 설비투자 공시.",
      src: "npm · PyPI · arXiv · Hugging Face · SEC EDGAR",
    },
    how: {
      kicker: "크기보다 속도",
      items: [
        ["평소보다 얼마나", "크기가 아니라 평소보다 얼마나 빨리 커지는지로 줄 세워요. 소스 전체가 오르는 몫은 대조군으로 빼요."],
        ["누가 앞서나", "AI SDK · 벡터 DB · 음성 AI · 코딩 도구 … 분야마다 1위가 바뀌는 순간을 잡아요."],
        ["AX 사건", "회사 · 정부가 직접 낸 발표만 모아 원문 링크와 함께 보여 줘요."],
      ],
    },
    rules: {
      kicker: "믿을 수 있게",
      items: ["매일 자동 갱신, 같은 방식으로", "검산이 하나라도 어긋나면 갱신하지 않아요", "공개 데이터만, 출처를 밝혀요", "화면의 문장은 데이터로 계산해 다시 써요"],
    },
    cta: { status: ["매일 갱신", "무료"], line: "숫자가 먼저 말하게." },
  },
];

const TOTAL = 6;
const esc = (s) => String(s).replace(/&(?!amp;|lt;|gt;)/g, "&amp;");

const css = `
@font-face { font-family: "Playfair Display"; src: url("file://${FONT}") format("woff2"); font-weight: 400 900; }
:root { --ink:#050505; --ivory:#F5F0E8; --soft:rgba(245,240,232,.82); --dim:rgba(245,240,232,.62); --faint:rgba(245,240,232,.40);
  --line:rgba(245,240,232,.10); --veil:rgba(245,240,232,.035); --bronze:#B8956A; }
* { box-sizing:border-box; margin:0; padding:0; }
html,body { width:1080px; height:1350px; background:var(--ink); }
body { font-family:"Pretendard Variable",Pretendard,system-ui,sans-serif; color:var(--ivory); -webkit-font-smoothing:antialiased; word-break:keep-all; }
.card { position:relative; width:1080px; height:1350px; overflow:hidden; background:var(--ink); display:flex; flex-direction:column; padding:72px 80px; }
.spot { position:absolute; inset:0; pointer-events:none;
  background:radial-gradient(ellipse 80% 80% at 50% 50%, rgba(245,240,232,.03) 0%, rgba(245,240,232,.012) 40%, transparent 75%); }
.wm { font-family:"Playfair Display",Georgia,serif; font-weight:500; text-transform:uppercase; letter-spacing:.22em; margin-right:-.22em;
  line-height:1; color:var(--ivory); text-shadow:0 0 24px rgba(245,240,232,.06); white-space:nowrap; }
.wm b, .logo b { font-weight:inherit; color:var(--bronze); }
.top { position:relative; display:flex; justify-content:space-between; align-items:center; font-size:34px; }
.logo { font-weight:700; letter-spacing:-.01em; }
.count { font-size:26px; color:var(--faint); font-variant-numeric:tabular-nums; }
.body { position:relative; flex:1; display:flex; flex-direction:column; justify-content:center; }
.foot { position:relative; display:flex; justify-content:space-between; align-items:center; padding-top:32px; border-top:1px solid var(--line); font-size:26px; color:var(--faint); }
.foot .next { color:var(--bronze); font-weight:600; }
.kicker { font-size:32px; font-weight:600; color:var(--bronze); margin-bottom:36px; }
h2 { font-size:68px; line-height:1.3; font-weight:700; letter-spacing:-.025em; }
p.lead { margin-top:44px; font-size:36px; line-height:1.6; color:var(--dim); }
.src { margin-top:40px; font-size:24px; color:var(--faint); }
.note { position:relative; margin-top:20px; font-size:22px; color:var(--faint); }
/* cover */
.cover .center { position:relative; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.cover .sub { margin-top:64px; font-size:36px; color:var(--dim); font-weight:500; }
.cover .bottom { position:relative; display:flex; flex-direction:column; align-items:center; gap:22px; }
.cover .go { font-size:30px; font-weight:600; color:var(--bronze); }
.cover .series { font-size:24px; color:var(--faint); }
.chip { display:inline-flex; align-items:center; gap:14px; padding:12px 26px; border-radius:999px; border:1px solid var(--line); background:var(--veil); font-size:26px; color:var(--soft); }
.chip i { width:12px; height:12px; border-radius:50%; background:var(--bronze); display:inline-block; }
/* how */
.list { margin-top:12px; border:1px solid var(--line); border-radius:28px; overflow:hidden; background:var(--veil); }
.row { display:flex; gap:32px; padding:40px 40px; align-items:flex-start; }
.row + .row { border-top:1px solid var(--line); }
.num { flex:none; width:60px; height:60px; border-radius:50%; background:rgba(184,149,106,.14); color:var(--bronze); font-weight:700; font-size:28px; display:flex; align-items:center; justify-content:center; }
.row h3 { font-size:40px; font-weight:700; letter-spacing:-.02em; }
.row p { margin-top:12px; font-size:30px; line-height:1.55; color:var(--dim); }
/* rules */
.rules { margin-top:12px; display:flex; flex-direction:column; gap:20px; }
.rule { display:flex; gap:24px; align-items:center; padding:30px 36px; border-radius:24px; border:1px solid var(--line); background:var(--veil); font-size:34px; line-height:1.4; color:var(--soft); }
.rule .mk { flex:none; width:44px; height:44px; border-radius:50%; border:2px solid var(--bronze); color:var(--bronze); display:flex; align-items:center; justify-content:center; font-size:24px; font-weight:700; }
/* cta */
.cta .center { position:relative; flex:1; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
.cta .line { font-size:44px; font-weight:700; letter-spacing:-.02em; margin-bottom:56px; }
.cta .url { margin-top:56px; font-size:44px; font-weight:600; color:var(--bronze); }
.cta .chips { margin-top:36px; display:flex; gap:16px; justify-content:center; }
.cta .note { margin-bottom:28px; }
.family { position:relative; padding-top:40px; border-top:1px solid var(--line); }
.family .cap { font-size:24px; color:var(--faint); text-align:center; margin-bottom:28px; }
.family .fams { display:flex; justify-content:space-between; }
.fam { flex:1; text-align:center; opacity:.42; }
.fam.on { opacity:1; }
.fam .wm { font-size:26px; }
.fam .t { margin-top:14px; font-size:22px; color:var(--dim); }
`;

const wm = (name) => `Pivox<b>${name}</b>`;
const top = (p, i) => `<div class="top"><div class="logo">${wm(p.name)}</div><div class="count">${String(i).padStart(2, "0")} / 0${TOTAL}</div></div>`;
const foot = (p, last) => `<div class="foot"><span>${p.url}</span>${last ? "<span>Pivox</span>" : '<span class="next">넘겨보기 →</span>'}</div>`;
const note = (p) => (p.note ? `<div class="note">${p.note}</div>` : "");

// 표지 워드마크 크기: 랜딩과 같은 비율로, 카드 폭(여백 제외 920px) 안에 들게.
const coverSize = (p) => Math.floor(920 / ((5 + p.name.length) * 0.92));

function slides(p) {
  return [
    `<div class="card cover"><div class="spot"></div>
      <div class="top"><div class="logo">${wm(p.name)}</div><div class="count">PIVOX ${p.n} · ${p.tag}</div></div>
      <div class="center"><h1 class="wm" style="font-size:${coverSize(p)}px">${wm(p.name)}</h1><div class="sub">${p.cover}</div></div>
      <div class="bottom"><div class="go">넘겨보기 →</div><div class="series">${p.url}</div></div></div>`,
    `<div class="card"><div class="spot"></div>${top(p, 2)}
      <div class="body"><div class="kicker">${p.define.kicker}</div><h2>${p.define.head}</h2><p class="lead">${p.define.body}</p></div>${note(p)}${foot(p)}</div>`,
    `<div class="card"><div class="spot"></div>${top(p, 3)}
      <div class="body"><div class="kicker">${p.why.kicker}</div><h2>${p.why.head}</h2><p class="lead">${p.why.body}</p><div class="src">${p.why.src}</div></div>${note(p)}${foot(p)}</div>`,
    `<div class="card"><div class="spot"></div>${top(p, 4)}
      <div class="body"><div class="kicker">${p.how.kicker}</div><div class="list">${p.how.items
        .map(([h, d], i) => `<div class="row"><div class="num">${i + 1}</div><div><h3>${h}</h3><p>${d}</p></div></div>`)
        .join("")}</div></div>${note(p)}${foot(p)}</div>`,
    `<div class="card"><div class="spot"></div>${top(p, 5)}
      <div class="body"><div class="kicker">${p.rules.kicker}</div><div class="rules">${p.rules.items
        .map((t) => `<div class="rule"><span class="mk">${p.id === "quant" ? "–" : "✓"}</span><span>${t}</span></div>`)
        .join("")}</div></div>${note(p)}${foot(p)}</div>`,
    `<div class="card cta"><div class="spot"></div>${top(p, 6)}
      <div class="center"><div class="line">${p.cta.line}</div><h1 class="wm" style="font-size:${Math.round(coverSize(p) * 0.78)}px">${wm(p.name)}</h1>
        <div class="url">${p.url}</div><div class="chips">${p.cta.status.map((s) => `<span class="chip"><i></i>${s}</span>`).join("")}</div></div>
      ${note(p)}
      <div class="family"><div class="cap">나의 거래 · 회사의 데이터 · 산업의 변화 — 흘려보내지 않고 숫자로 봅니다</div><div class="fams">${PRODUCTS.map(
        (q) => `<div class="fam${q.id === p.id ? " on" : ""}"><div class="wm">${wm(q.name)}</div><div class="t">${q.tag}</div></div>`,
      ).join("")}</div></div></div>`,
  ];
}

const page = (inner) => `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>${css}</style></head><body>${inner}</body></html>`;

(async () => {
  const only = process.argv[2];
  const browser = await chromium.launch();
  const tab = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  for (const p of PRODUCTS) {
    if (only && only !== p.id) continue;
    const dir = path.join(OUT, `${p.n}-${p.id}`);
    fs.mkdirSync(dir, { recursive: true });
    const list = slides(p);
    for (let i = 0; i < list.length; i++) {
      const html = page(esc(list[i]));
      const file = path.join(dir, `${String(i + 1).padStart(2, "0")}.html`);
      fs.writeFileSync(file, html);
      await tab.goto(`file://${file}`, { waitUntil: "networkidle" });
      await tab.evaluate(() => document.fonts.ready);
      const over = await tab.evaluate(() => document.querySelector(".card").scrollHeight > 1350);
      if (over) console.warn(`넘침: ${p.id} ${i + 1}`);
      await tab.screenshot({ path: file.replace(/\.html$/, ".png") });
      fs.unlinkSync(file);
    }
    console.log(`${p.id}: ${list.length}장 → ${dir}`);
  }
  await browser.close();
})();
