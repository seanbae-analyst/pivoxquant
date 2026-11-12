/* 화면 넘김 (2026-11-12) — PivoxMap 의 표지 · 위 단계 줄 · 화면 넘김(components/Cover.tsx · Rail.tsx · Screen.tsx)을 정적 페이지에 옮긴 것.
   [data-pager] 안의 <section class="pg" data-title="…" id="…"> 를 한 화면씩 보여 준다. 첫 화면이 .pg-cover 면 표지다.
   선택: data-pager-url="none" — 주소의 # 를 읽거나 쓰지 않는다(모의 테스트처럼 # 를 설정 저장에 쓰는 페이지).
         data-pager-keys="none" — 키로 넘기지 않는다(← → 를 다른 일에 쓰는 페이지). 버튼 · 단계 줄 · 쓸기는 그대로.
   페이지 코드가 숨은 화면 안의 요소로 scrollIntoView 하면 그 화면으로 먼저 넘어간다(다른 화면의 결과로 데려가는 버튼들).
   - 앞으로 가면 오른쪽에서 28px, 뒤로 가면 왼쪽에서 들어온다(380ms, cubic-bezier(.2,.75,.2,1)). 움직임 줄이기 설정이면 움직이지 않는다.
   - 표지: 누르거나 Enter · Space · → · ↓ · 휠을 내리면 다음. 다른 화면: ← → · PageUp/PageDown · 좌우로 쓸기 · 단계 줄 · 이전/다음 버튼.
   - 주소의 #id 가 지금 화면이다(공유 · 새로고침). 브라우저 뒤로 가기도 화면을 따른다.
   - JS 가 없으면 아무것도 숨기지 않는다(모든 화면이 세로로 이어진다 — 인쇄 · 검색 · 화면 낭독기).
   외부 라이브러리 없음. CSP script-src 'self'(배포) · sha256(오프라인 사본)로 돈다. */
(function () {
  "use strict";
  var main = document.querySelector("[data-pager]");
  if (!main) return;
  var pages = Array.prototype.slice.call(main.children).filter(function (x) { return x.classList && x.classList.contains("pg"); });
  if (pages.length < 2) return;
  var SLIDE_PX = 28, SLIDE_MS = 380, EASE = "cubic-bezier(.2,.75,.2,1)";
  var INTERACTIVE = "a, button, input, textarea, select, summary, label, [contenteditable], .tblwrap";
  var root = document.documentElement;
  var rail = document.querySelector("[data-pager-rail]");
  var nav = document.querySelector("[data-pager-nav]");
  var hasCover = pages[0].classList.contains("pg-cover");
  var useUrl = main.getAttribute("data-pager-url") !== "none";
  var useKeys = main.getAttribute("data-pager-keys") !== "none";
  var cur = -1;

  function reduced() { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function indexOfId(id) { for (var i = 0; i < pages.length; i++) if (pages[i].id === id) return i; return -1; }
  function fromHash() {
    if (!useUrl) return 0;
    var i = -1;
    try { i = indexOfId(decodeURIComponent((location.hash || "").slice(1))); } catch (e) { i = -1; }
    return i < 0 ? 0 : i;
  }
  function hashIsPage() { try { return indexOfId(decodeURIComponent((location.hash || "").slice(1))) >= 0; } catch (e) { return false; } }

  // 단계 줄: 표지는 넣지 않는다(PivoxMap 처럼 표지는 단계 밖)
  var steps = pages.map(function (p, i) { return { i: i, title: p.getAttribute("data-title") || ("" + (i + 1)) }; }).filter(function (s) { return !(hasCover && s.i === 0); });
  function buildRail() {
    if (!rail) return;
    var ol = document.createElement("ol");
    ol.className = "pg-rail";
    steps.forEach(function (s, k) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.className = "pg-rail-item";
      b.setAttribute("data-i", s.i);
      var n = document.createElement("span"); n.className = "pg-rail-no"; n.setAttribute("aria-hidden", "true"); n.textContent = String(k + 1);
      var l = document.createElement("span"); l.className = "pg-rail-label"; l.textContent = s.title;
      b.appendChild(n); b.appendChild(l);
      b.addEventListener("click", function () { go(s.i); });
      li.appendChild(b);
      ol.appendChild(li);
    });
    // 좁은 폭: '2 / 5 · 명령 흐름' 한 줄이 버튼이 되어 같은 목록을 세로로 연다(PivoxMap Rail 과 같다)
    var mob = document.createElement("button");
    mob.type = "button";
    mob.className = "pg-rail-mobile";
    mob.setAttribute("aria-expanded", "false");
    ol.id = "pg-rail-list";
    mob.setAttribute("aria-controls", ol.id);
    mob.addEventListener("click", function () {
      var open = rail.getAttribute("data-open") === "1";
      rail.setAttribute("data-open", open ? "0" : "1");
      mob.setAttribute("aria-expanded", open ? "false" : "true");
    });
    rail.appendChild(mob);
    rail.appendChild(ol);
  }
  function paintRail() {
    if (!rail) return;
    var at = -1;
    Array.prototype.forEach.call(rail.querySelectorAll(".pg-rail > li"), function (li, k) {
      var i = steps[k].i, b = li.firstChild;
      li.setAttribute("data-status", i < cur ? "done" : (i === cur ? "now" : "todo"));
      if (i === cur) { b.setAttribute("aria-current", "step"); at = k; } else b.removeAttribute("aria-current");
    });
    rail.hidden = hasCover && cur === 0;
    var mob = rail.querySelector(".pg-rail-mobile");
    if (mob && at >= 0) mob.textContent = (at + 1) + " / " + steps.length + " · " + steps[at].title + "  ▾";
    rail.setAttribute("data-open", "0");
    if (mob) mob.setAttribute("aria-expanded", "false");
  }
  function paintNav() {
    if (!nav) return;
    var prev = nav.querySelector("[data-pager-prev]"), next = nav.querySelector("[data-pager-next]"), cnt = nav.querySelector("[data-pager-count]");
    nav.hidden = hasCover && cur === 0;
    if (prev) { prev.disabled = cur <= (hasCover ? 1 : 0); }
    if (next) {
      var last = cur >= pages.length - 1;
      next.disabled = last;
      var lab = next.querySelector("[data-pager-next-label]");
      if (lab) lab.textContent = last ? "끝" : (pages[cur + 1].getAttribute("data-title") || "다음");
    }
    if (cnt) {
      var k = steps.map(function (s) { return s.i; }).indexOf(cur);
      cnt.textContent = k < 0 ? "" : (k + 1) + " / " + steps.length;
    }
  }
  function slideIn(el, dir) {
    if (!el || reduced() || typeof el.animate !== "function") return;
    var host = el.parentElement;
    if (host) host.style.overflowX = "clip";
    var a = el.animate([{ opacity: 0, transform: "translateX(" + (dir * SLIDE_PX) + "px)" }, { opacity: 1, transform: "none" }], { duration: SLIDE_MS, easing: EASE });
    var release = function () { if (host) host.style.overflowX = ""; };
    if (a.finished) a.finished.then(release, release); else a.onfinish = release;
  }
  function show(i, opts) {
    opts = opts || {};
    i = Math.max(0, Math.min(pages.length - 1, i));
    if (i === cur) return;
    var dir = i > cur ? 1 : -1, first = cur < 0;
    pages.forEach(function (p, k) { p.hidden = k !== i; });
    cur = i;
    root.classList.toggle("pg-at-cover", hasCover && i === 0);
    paintRail(); paintNav();
    if (!first) { toScreen(pages[i]); slideIn(pages[i], dir); }
    if (opts.push && useUrl) {
      try { history.pushState({ pg: i }, "", "#" + pages[i].id); } catch (e) { /* file:// 등 */ }
    }
    if (!first && !opts.noFocus) {
      var h = pages[i].querySelector("h1, h2");
      if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
    }
  }
  // 넘긴 화면의 시작으로 — 화면이 첫 화면 높이 안에서 시작하면 맨 위로(머리 띠가 보이게), 더 아래에서 시작하면
  // (폰의 모의 테스트처럼 설정 판이 위에 쌓인 경우) 그 화면의 시작으로 간다. 위에 붙는 단계 줄 높이만큼 띄운다.
  function toScreen(el) {
    var top = el.getBoundingClientRect().top + window.pageYOffset;
    var bar = rail && !rail.hidden ? rail.getBoundingClientRect().height : 0;
    if (top < window.innerHeight * 0.75) window.scrollTo(0, 0);
    else window.scrollTo(0, Math.max(0, top - bar - 12));
  }
  function go(i) { show(i, { push: true }); }
  function next() { if (cur < pages.length - 1) go(cur + 1); }
  function prev() { if (cur > (hasCover ? 1 : 0)) go(cur - 1); else if (hasCover && cur === 1) go(0); }

  // 키
  window.addEventListener("keydown", function (e) {
    if (!useKeys) return;
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target;
    if (t && t.closest && t.closest("input, textarea, select, [contenteditable]")) return;
    var onCover = hasCover && cur === 0;
    if (onCover && ["Enter", " ", "ArrowRight", "ArrowDown", "PageDown"].indexOf(e.key) >= 0) {
      if (t && t.closest && t.closest(INTERACTIVE) && e.key !== "ArrowRight" && e.key !== "ArrowDown") return;
      e.preventDefault(); next(); return;
    }
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); next(); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); prev(); }
  });
  // 표지: 누르기 · 휠
  if (hasCover) {
    pages[0].addEventListener("click", function (e) { if (!(e.target.closest && e.target.closest("a, button, input, textarea, select"))) next(); });
    window.addEventListener("wheel", function (e) { if (cur === 0 && e.deltaY > 30) next(); }, { passive: true });
  }
  // 좌우로 쓸기(가로로 넘치는 표 · 그림 위에서는 하지 않는다)
  var sx = 0, sy = 0, st = 0, skip = false;
  main.addEventListener("touchstart", function (e) {
    var p = e.touches[0]; sx = p.clientX; sy = p.clientY; st = Date.now();
    skip = !!(e.target.closest && e.target.closest(".tblwrap, .fr, .mt-box, .xt, textarea, input"));
  }, { passive: true });
  main.addEventListener("touchend", function (e) {
    if (skip) return;
    var p = e.changedTouches[0], dx = p.clientX - sx, dy = p.clientY - sy;
    if (Date.now() - st < 700 && Math.abs(dx) > 70 && Math.abs(dx) > 1.6 * Math.abs(dy)) { if (dx < 0) next(); else prev(); }
  }, { passive: true });
  // 뒤로 가기 · 주소 바꾸기
  if (useUrl) {
    // 화면 id 가 아닌 # (다른 용도)는 무시한다 — 바꿀 때마다 첫 화면으로 튀지 않게
    window.addEventListener("popstate", function () { if (!location.hash || hashIsPage()) show(fromHash(), { noFocus: false }); });
    window.addEventListener("hashchange", function () { if (hashIsPage()) show(fromHash()); });
  }
  // 숨은 화면 안의 요소로 스크롤하려 하면 그 화면을 먼저 연다
  var nativeSIV = Element.prototype.scrollIntoView;
  if (nativeSIV) {
    Element.prototype.scrollIntoView = function () {
      var pg = this.closest && this.closest("[data-pager] > .pg");
      if (pg && pg.hidden) { var i = pages.indexOf(pg); if (i >= 0) show(i, { push: true, noFocus: true }); }
      return nativeSIV.apply(this, arguments);
    };
  }
  // 이전 · 다음 버튼 · 표지의 '시작하기'
  if (nav) {
    var pb = nav.querySelector("[data-pager-prev]"), nb = nav.querySelector("[data-pager-next]");
    if (pb) pb.addEventListener("click", prev);
    if (nb) nb.addEventListener("click", next);
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-pager-start]"), function (a) {
    a.addEventListener("click", function (e) { e.preventDefault(); next(); });
  });
  // 화면 안의 '#다른화면' 링크도 넘김으로
  main.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var i = indexOfId(a.getAttribute("href").slice(1));
    if (i >= 0) { e.preventDefault(); go(i); }
  });

  buildRail();
  root.classList.add("paged");
  if (rail) rail.removeAttribute("aria-hidden");
  show(fromHash(), { noFocus: true });
})();
