/* sim-ui.js — 모의 테스트 화면(데스크톱). 계산은 sim-engine.js(PivoxSimEngine), 데이터는 sim-data.js(PIVOX_SIM).
   글은 전부 textContent 로 넣는다(innerHTML 에 데이터를 넣지 않는다). 설정은 주소창 # 뒤에만 남긴다 — 저장·전송 없음. */
(function () {
  "use strict";
  var D = window.PIVOX_SIM, E = window.PivoxSimEngine;
  if (!D || !E) return;

  var LAYER_KO = { analog: "사람·계정", agent: "AI 적용" };
  var LEVEL_KO = ["없음", "사람·계정만", "AI 까지"];
  var SCORE_KO = ["다루지 않음", "자율", "구속력", "구속력 + 에이전트 명시"];
  var STAGE_KO = { before: "배치 전", in_use: "사용 중", after: "사후" };
  var EFFECT_ON = { prevent: "막음", limit: "닿는 범위를 줄임", detect: "알아챔", contain: "멈추고 회수" };
  var TOOLS = [["read", "조회만"], ["write", "쓰기·실행"], ["pay", "송금·결제"]];
  var REQ_KO = { untrusted_input: "외부 입력을 읽지 않는다", open_components: "외부 구성요소를 들이지 않는다",
                 memory: "장기 메모리를 쓰지 않는다", multi_agent: "다른 에이전트와 일을 주고받지 않는다" };
  var ENV_KEYS = ["tools", "untrusted_input", "open_components", "memory", "multi_agent"];
  var OUT_KO = { blocked: "막혔을 사건", blocked_maybe: "막혔을 수도", reduced: "피해 축소", unchanged: "그대로", unknown: "판단 근거 없음" };
  var RESULT_KO = { blocked: "막힘", reduced: "피해 축소", damage: "피해 발생", no_surface: "공격면 없음" };
  var JUR = ["KR", "US", "EU", "INTL"];

  var ctlById = {}, stageOf = {}, failures = {}, presetById = {}, profileById = {}, scnById = {}, incById = {};
  D.controls.forEach(function (c) { ctlById[c.id] = c; stageOf[c.id] = c.stage; });
  D.incidents.forEach(function (i) { failures[i.id] = i.fails; incById[i.id] = i; });
  D.presets.forEach(function (p) { presetById[p.id] = p; });
  D.agent_profiles.forEach(function (p) { profileById[p.id] = p; });
  D.scenarios.forEach(function (s) { scnById[s.id] = s; });
  var CASES = D.cases || [], caseById = {};
  CASES.forEach(function (c) { caseById[c.id] = c; });
  var CIDS = D.controls.map(function (c) { return c.id; });

  function envOf(p) {
    if (!p) return null;
    var e = {}; ENV_KEYS.forEach(function (k) { e[k] = k === "tools" ? p.tools : !!p[k]; }); return e;
  }
  var state = {
    preset: "KR-2", levels: Object.assign({}, (presetById["KR-2"] || D.presets[0]).levels),
    profile: "trading", env: envOf(profileById.trading) || { tools: "pay", untrusted_input: true, open_components: false },
    statedOnly: false, scenario: D.scenarios[0].id, open: {}, kase: null
  };
  // 케이스 → 설정 (sim.py case_setup 과 같은 규칙: 프리셋 위에 levels, 에이전트 종류 위에 env)
  function caseSetup(c) {
    var levels = Object.assign({}, presetById[c.preset].levels, c.levels || {});
    var env = Object.assign(envOf(profileById[c.profile]), c.env || {});
    return { levels: levels, env: env, profile: c.env ? "custom" : c.profile, scenario: c.scenario };
  }
  function applyCase(id) {
    var c = caseById[id];
    if (!c) { state.kase = null; return; }
    var su = caseSetup(c);
    state.kase = id; state.levels = su.levels; state.env = su.env; state.profile = su.profile; state.scenario = su.scenario;
    state.preset = matchPreset();
  }
  function caseDirty() {
    var c = caseById[state.kase]; if (!c) return false;
    var su = caseSetup(c);
    return su.scenario !== state.scenario || CIDS.some(function (k) { return su.levels[k] !== state.levels[k]; }) ||
      ENV_KEYS.some(function (k) { return su.env[k] !== state.env[k]; });
  }

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ── DOM 도우미 ──
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "cls") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (k) { if (k !== null && k !== undefined) n.appendChild(typeof k === "string" ? document.createTextNode(k) : k); });
    return n;
  }
  function $(id) { return document.getElementById(id); }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function link(url, text) { return url ? el("a", { href: url, rel: "noopener", target: "_blank", text: text }) : el("span", { text: text }); }
  function cname(id) { return ctlById[id] ? ctlById[id].name : id; }
  var uid = 0;
  function seg(container, name, options, current, onChange) {
    clear(container);
    options.forEach(function (o) {
      var id = "r" + (++uid);
      var inp = el("input", { type: "radio", name: name, id: id, value: String(o[0]) });
      if (String(o[0]) === String(current)) inp.checked = true;
      inp.addEventListener("change", function () { onChange(o[0]); });
      var lab = el("label", { "for": id }, [inp, el("span", { text: o[1] })]);
      if (o[2]) lab.setAttribute("title", o[2]);
      container.appendChild(lab);
    });
  }
  function bool(v) { return v === true || v === "true"; }

  // ── 주소창 # ↔ 설정 ──
  function writeHash() {
    var h = "p=" + state.preset + "&l=" + CIDS.map(function (c) { return state.levels[c]; }).join("") +
      "&a=" + state.profile + "&t=" + state.env.tools + "&u=" + (state.env.untrusted_input ? 1 : 0) +
      "&c=" + (state.env.open_components ? 1 : 0) + "&m=" + (state.env.memory ? 1 : 0) + "&g=" + (state.env.multi_agent ? 1 : 0) +
      "&s=" + state.scenario + "&b=" + (state.statedOnly ? 1 : 0) + (state.kase ? "&k=" + state.kase : "");
    if (history.replaceState) history.replaceState(null, "", "#" + h);
  }
  function readHash() {
    var q = {};
    (location.hash || "").replace(/^#/, "").split("&").forEach(function (kv) {
      var i = kv.indexOf("=");
      if (i > 0) { try { q[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1)); } catch (e) { /* 깨진 값은 무시 */ } }
    });
    if (q.l && /^[012]+$/.test(q.l) && q.l.length === CIDS.length) CIDS.forEach(function (c, i) { state.levels[c] = Number(q.l[i]); });
    else if (presetById[q.p]) state.levels = Object.assign({}, presetById[q.p].levels);
    state.preset = matchPreset();
    if (profileById[q.a] || q.a === "custom") state.profile = q.a;
    if (profileById[state.profile]) state.env = envOf(profileById[state.profile]);
    if (TOOLS.some(function (t) { return t[0] === q.t; })) state.env.tools = q.t;
    if (q.u === "0" || q.u === "1") state.env.untrusted_input = q.u === "1";
    if (q.c === "0" || q.c === "1") state.env.open_components = q.c === "1";
    if (q.m === "0" || q.m === "1") state.env.memory = q.m === "1";
    if (q.g === "0" || q.g === "1") state.env.multi_agent = q.g === "1";
    if (profileById[state.profile] && JSON.stringify(envOf(profileById[state.profile])) !== JSON.stringify(state.env)) state.profile = "custom";
    if (scnById[q.s]) state.scenario = q.s;
    if (q.b === "1") state.statedOnly = true;
    if (caseById[q.k]) state.kase = q.k;
  }
  function matchPreset() {
    for (var i = 0; i < D.presets.length; i++) {
      var p = D.presets[i];
      if (CIDS.every(function (c) { return p.levels[c] === state.levels[c]; })) return p.id;
    }
    return "custom";
  }

  // ── 왼쪽: 설정 ──
  function renderPresetSelect() {
    var s = clear($("preset"));
    s.appendChild(el("option", { value: "custom", text: "직접 설정 (우리 회사)" }));
    D.presets.forEach(function (p) { s.appendChild(el("option", { value: p.id, text: p.label })); });
  }
  function renderPresetHint() {
    $("preset").value = state.preset;
    var by = [[], [], []];
    CIDS.forEach(function (c) { by[state.levels[c]].push(cname(c)); });
    $("preset-hint").textContent = "AI 까지 " + by[2].length + "개" + (by[2].length && by[2].length < 7 ? " (" + by[2].join(" · ") + ")" : "") +
      " · 사람·계정만 " + by[1].length + "개 · 없음 " + by[0].length + "개";
  }
  function regBlock(cid) {
    var R = (D.regulation || {})[cid] || {}, box = el("div", { cls: "reg" });
    box.appendChild(el("p", { text: "관할별로 가장 센 문서 — 사람·계정 층 / AI 적용 층" }));
    var ul = el("ul");
    JUR.forEach(function (j) {
      var r = R[j]; if (!r) return;
      var li = el("li", null, [el("b", { text: (D.jurisdictions || {})[j] || j }), " — "]);
      ["analog", "agent"].forEach(function (layer, k) {
        var x = r[layer] || { score: 0 };
        if (k) li.appendChild(document.createTextNode(" / "));
        li.appendChild(document.createTextNode(LAYER_KO[layer] + " " + SCORE_KO[x.score] + (x.doc ? " · " : "")));
        if (x.doc) li.appendChild(link(x.url, x.title));
      });
      var q = (r.agent && r.agent.quote) || (r.analog && r.analog.quote) || "";
      if (q) li.appendChild(el("span", { cls: "quote", text: "근거 · " + q }));
      if (r.agent && r.agent.agent_named && r.agent.score < 3) {
        li.appendChild(el("span", { cls: "dim" }, ["에이전트를 이름 붙인 자율 문서: ", link(r.agent.agent_named.url, r.agent.agent_named.title)]));
      }
      ul.appendChild(li);
    });
    box.appendChild(ul);
    return box;
  }
  function renderControls() {
    var box = clear($("controls"));
    D.controls.forEach(function (c) {
      var mid = "more-" + c.id, open = !!state.open[c.id], h = c.help || {};
      var btn = el("button", { type: "button", cls: "nm", "aria-expanded": String(open), "aria-controls": mid },
        [c.num + ". " + c.name, el("small", { text: STAGE_KO[c.stage] || "" })]);
      btn.addEventListener("click", function () { state.open[c.id] = !state.open[c.id]; renderControls(); });
      var g = el("div", { cls: "seg", role: "radiogroup", "aria-label": c.name + " 적용 범위" });
      seg(g, "lv-" + c.id, [[0, "없음"], [1, "사람·계정", h.analog], [2, "AI 까지", h.agent]], state.levels[c.id], function (v) {
        state.levels[c.id] = Number(v); state.preset = matchPreset(); update();
      });
      var row = el("div", { cls: "ctl" }, [btn, g]);
      if (open) {
        row.appendChild(el("div", { cls: "more", id: mid }, [
          el("dl", null, [el("dt", { text: "사람·계정" }), el("dd", { text: h.analog || "" }), el("dt", { text: "AI 까지" }), el("dd", { text: h.agent || "" })]),
          regBlock(c.id)
        ]));
      }
      box.appendChild(row);
    });
  }
  function renderEnv() {
    var s = clear($("profile"));
    D.agent_profiles.forEach(function (p) { s.appendChild(el("option", { value: p.id, text: p.label })); });
    s.appendChild(el("option", { value: "custom", text: "직접 설정" }));
    s.value = state.profile;
    function custom() { state.profile = "custom"; }
    seg($("tools"), "tools", TOOLS, state.env.tools, function (v) { state.env.tools = v; custom(); update(); });
    seg($("untrusted"), "untrusted", [[true, "읽는다"], [false, "안 읽는다"]], state.env.untrusted_input, function (v) { state.env.untrusted_input = bool(v); custom(); update(); });
    seg($("components"), "components", [[true, "들인다"], [false, "고정된 것만"]], state.env.open_components, function (v) { state.env.open_components = bool(v); custom(); update(); });
    seg($("memory"), "memory", [[true, "쌓는다"], [false, "안 쌓는다"]], state.env.memory, function (v) { state.env.memory = bool(v); custom(); update(); });
    seg($("multi"), "multi", [[true, "주고받는다"], [false, "혼자 일한다"]], state.env.multi_agent, function (v) { state.env.multi_agent = bool(v); custom(); update(); });
  }

  // ── ① 원형 한눈에 + 단계 ──
  function whereText(r) {
    if (r.outcome === "no_surface") return "이 환경에서 성립하지 않음 — " + r.missing.map(function (x) { return REQ_KO[x]; }).join(", ");
    if (r.outcome === "blocked") return r.stage + "단계 · " + cname(r.steps[r.stage - 1].blocked_by);
    if (r.outcome === "reduced") {
      var w = r.limited_by.map(cname);
      if (r.contained === "early") w.push("탐지 후 " + cname("kill_switch"));
      return w.join(" · ") + " — " + r.impact;
    }
    return r.impact + (r.contained === "late" ? " (멈출 수단은 있으나 늦게)" : "");
  }
  function renderOverview() {
    var t = clear($("ov"));
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { "aria-label": "선택" }), el("th", { text: "공격 원형" }), el("th", { text: "이 설정에서" }),
      el("th", { text: "어디서 · 무엇이" }), el("th", { text: "근거" })])]));
    var tb = el("tbody");
    D.scenarios.forEach(function (s) {
      var r = E.runScenario(s, state.env, state.levels), id = "ov-" + s.id;
      var inp = el("input", { type: "radio", name: "scn", id: id, value: s.id });
      inp.checked = s.id === state.scenario;
      inp.addEventListener("change", function () { select(s.id); });
      var tr = el("tr", { cls: s.id === state.scenario ? "sel" : "" }, [
        el("td", null, [inp]),
        el("td", null, [el("label", { "for": id, cls: "t", text: s.title }), el("div", { cls: "s", text: s.summary })]),
        el("td", null, [el("span", { cls: "r " + r.outcome, text: RESULT_KO[r.outcome] })]),
        el("td", { cls: "w", text: whereText(r) }),
        el("td", { cls: "b", text: s.incidents.length ? "실제 사건 " + s.incidents.length + "건" : (s.basis || [""])[0].replace(/ (and|&) .*/, "").replace("OWASP ", "OWASP ") + " · 사건 없음" })
      ]);
      tr.addEventListener("click", function (e) { if (e.target.tagName !== "INPUT" && e.target.tagName !== "LABEL" && e.target.tagName !== "A") select(s.id); });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }
  function select(id) { if (state.scenario !== id) { state.scenario = id; update(); } }

  function renderWalk(animate) {
    var s = scnById[state.scenario], r = E.runScenario(s, state.env, state.levels);
    var ol = clear($("stages")), out = clear($("outcome")), items = [];
    $("run-hint").textContent = s.title;
    if (r.outcome === "no_surface") {
      ol.appendChild(el("li", { cls: "stage blocked" }, [el("span", { cls: "no", text: "–" }), el("div", null, [
        el("div", { cls: "t", text: "이 공격은 시작되지 않는다" }),
        el("div", { cls: "d", text: "지금 환경에서 에이전트가 " + r.missing.map(function (x) { return REQ_KO[x]; }).join(", ") + "." })
      ])]));
    } else {
      s.stages.forEach(function (st, idx) {
        var step = r.steps[idx], cls = "stage" + (!step ? " after" : step.blocked_by ? " blocked" : " passed");
        var ck = el("ul", { cls: "ck" });
        if (!step) ck.appendChild(el("li", { text: "이 단계까지 오지 않았다 — 앞에서 막혔다" }));
        (st.checks || []).forEach(function (c, j) {
          var on = step ? step.checks[j].on : E.covers(Number(state.levels[c.control] || 0), c.layer);
          var lv = Number(state.levels[c.control] || 0);
          var verdict = on ? EFFECT_ON[c.effect] + (c.effect === "contain" && r.contained === "late" ? " (알아챌 기록이 없어 늦게)" : "")
                           : "꺼짐 — 지금 " + LEVEL_KO[lv];
          ck.appendChild(el("li", { cls: on ? "on" : "" }, [el("b", { text: cname(c.control) + " · " + LAYER_KO[c.layer] }), " — " + verdict, el("span", { cls: "why", text: c.why })]));
        });
        if (!(st.checks || []).length) ck.appendChild(el("li", { text: "이 단계에서 끼어드는 통제 없음" }));
        var li = el("li", { cls: cls + (animate && !reduceMotion ? " pending" : "") }, [
          el("span", { cls: "no", text: String(idx + 1) }),
          el("div", null, [el("div", { cls: "t", text: st.title }), el("div", { cls: "d", text: st.desc }), ck])
        ]);
        ol.appendChild(li); items.push(li);
      });
    }
    var v, p;
    if (r.outcome === "blocked") { v = "막힘 — " + r.stage + "단계, " + cname(r.steps[r.stage - 1].blocked_by); p = "공격이 끝까지 가지 못했다. 막지 못했다면: " + r.impact + "."; }
    else if (r.outcome === "reduced") {
      var why = [];
      if (r.limited_by.length) why.push(r.limited_by.map(cname).join(" · ") + "(이)가 닿는 범위를 줄였다");
      if (r.contained === "early") why.push((r.detected_at ? r.detected_at + "단계에서 알아채고 " : "") + "멈췄다");
      v = "피해 축소 — " + r.impact; p = "공격은 끝까지 갔지만 " + why.join(", ") + ".";
    } else if (r.outcome === "damage") { v = "피해 발생 — " + r.impact; p = r.contained === "late" ? "멈출 수단은 있었지만 알아챌 기록이 없어 늦게 멈췄다." : "끼어든 통제가 없었다."; }
    else { v = "공격면 없음"; p = "이 원형은 지금 환경에서 성립하지 않는다."; }
    var show = function () { out.appendChild(el("div", { cls: "k", text: "결과 · " + s.title.split(" →")[0] })); out.appendChild(el("div", { cls: "v " + r.outcome, text: v })); out.appendChild(el("p", { text: p })); };
    if (animate && !reduceMotion) {
      items.forEach(function (li, i) { setTimeout(function () { li.classList.remove("pending"); }, 120 + i * 420); });
      setTimeout(show, 120 + items.length * 420);
    } else show();
    renderCases(s);
  }
  function renderCases(s) {
    $("scn-cases-h").textContent = s.incidents.length ? "이 원형의 근거 사건 " + s.incidents.length + "건" : "이 원형의 근거 — " + (s.basis || []).join(" · ");
    var ul = clear($("scn-list"));
    s.incidents.map(function (id) { return incById[id]; }).filter(Boolean).sort(function (a, b) { return a.date < b.date ? 1 : -1; }).forEach(function (i) {
      ul.appendChild(el("li", null, [el("time", { text: i.date }), el("div", null, [
        el("div", { cls: "t" }, [link(i.url, i.title)]),
        el("div", { cls: "k", text: i.fails.length ? "실패 판정: " + i.fails.map(function (f) { return cname(f.control) + "(" + LAYER_KO[f.layer] + ")"; }).join(" · ") : "실패 판정 없음 — 공개 자료에 피해 쪽 통제가 적혀 있지 않다" })
      ])]));
    });
  }

  // ── ② 다시 돌리기 ──
  function rangeText(r) { return r.blocked_lo === r.blocked_hi ? String(r.blocked_hi) : r.blocked_lo + "~" + r.blocked_hi; }
  function renderReplay() {
    seg($("basis"), "basis", [[false, "적었거나 추론한 실패"], [true, "원문이 적은 실패만"]], state.statedOnly, function (v) { state.statedOnly = bool(v); update(); });
    var r = E.replay(failures, state.levels, stageOf, state.statedOnly), judged = r.total - r.unknown;
    var cards = clear($("rep-cards"));
    function card(k, v, h, hl) { cards.appendChild(el("div", { cls: "card" + (hl ? " hl" : "") }, [el("div", { cls: "k", text: k }), el("div", { cls: "v", text: v }), el("div", { cls: "h", text: h })])); }
    card("막혔을 사건", rangeText(r), "판단할 수 있는 " + judged + "건 중", true);
    card("피해 축소", String(r.reduced), "사후 통제만 맞음");
    card("그대로", String(r.unchanged), "실패한 통제가 하나도 켜지지 않음");
    card("판단 근거 없음", String(r.unknown), "공개 자료에 피해 쪽 통제가 없음");
    $("rep-explain").textContent = "하한 = 그 사건에서 실패한 통제가 모두 켜졌을 때 · 상한 = 사전·사용 중 단계 통제가 하나라도 켜졌을 때.";
    var nx = clear($("next")), best = E.bestNext(failures, state.levels, stageOf, state.statedOnly).filter(function (x) { return x[1] > 0; }).slice(0, 4);
    if (best.length) {
      var ol = el("ol");
      best.forEach(function (b) { ol.appendChild(el("li", null, [el("b", { text: cname(b[0]) }), " — 막힘 상한 +" + b[1] + "건", el("div", { cls: "fine", text: ((ctlById[b[0]] || {}).help || {}).agent || "" })])); });
      nx.appendChild(ol);
    } else nx.appendChild(el("p", { cls: "fine", text: "더 켜서 늘어날 사건이 없다 — 남은 사건은 판단 근거가 없거나 사후 통제만 남았다." }));
    var t = clear($("cmp"));
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "프리셋" }), el("th", { cls: "num", text: "막혔을 사건" }), el("th", { cls: "num", text: "그대로" }), el("th", { cls: "num", text: "판단 근거 없음" })])]));
    var tb = el("tbody"), rows = D.presets.slice();
    if (state.preset === "custom") rows.unshift({ id: "custom", label: "지금 설정 (직접)", levels: state.levels });
    rows.forEach(function (p) {
      var x = E.replay(failures, p.levels, stageOf, state.statedOnly);
      tb.appendChild(el("tr", { cls: p.id === state.preset ? "cur" : "" }, [el("td", { text: p.label }),
        el("td", { cls: "num" }, [el("b", { text: rangeText(x) })]), el("td", { cls: "num", text: String(x.unchanged) }), el("td", { cls: "num", text: String(x.unknown) })]));
    });
    t.appendChild(tb);
    var pt = clear($("per"));
    pt.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "사건" }), el("th", { text: "실패 판정" }), el("th", { text: "결과" }), el("th", { text: "날짜" })])]));
    var pb = el("tbody"), order = { blocked: 0, blocked_maybe: 1, reduced: 2, unchanged: 3, unknown: 4 };
    D.incidents.slice().sort(function (a, b) { return order[r.per[a.id]] - order[r.per[b.id]] || (a.date < b.date ? 1 : -1); }).forEach(function (i) {
      var fs = state.statedOnly ? i.fails.filter(function (f) { return f.level === "stated"; }) : i.fails;
      pb.appendChild(el("tr", null, [el("td", null, [link(i.url, i.title)]),
        el("td", { text: fs.length ? fs.map(function (f) { return cname(f.control) + "(" + LAYER_KO[f.layer] + ")"; }).join(" · ") : "—" }),
        el("td", { text: OUT_KO[r.per[i.id]] }), el("td", { text: i.date })]));
    });
    pt.appendChild(pb);
  }

  // ── 데모 케이스 ──
  function renderCasePicker() {
    var s = clear($("case"));
    s.appendChild(el("option", { value: "", text: "— 케이스 없이 직접 설정 —" }));
    CASES.forEach(function (c, i) { s.appendChild(el("option", { value: c.id, text: (i + 1) + ". " + c.title })); });
    $("case-count").textContent = CASES.length + "개";
  }
  function renderCaseBanner() {
    var b = clear($("case-banner")), c = caseById[state.kase];
    $("case").value = c ? c.id : "";
    if (!c) { b.className = "case-banner"; return; }
    var dirty = caseDirty(), idx = CASES.indexOf(c) + 1;
    var su = caseSetup(c), r = E.runScenario(scnById[c.scenario], su.env, su.levels);
    b.className = "case-banner" + (dirty ? " off" : "");
    var head = el("div", { cls: "k" }, ["케이스 " + idx + " / " + CASES.length + " · " + c.org]);
    if (dirty) {
      var again = el("button", { type: "button", cls: "btn again", text: "케이스 설정으로 되돌리기" });
      again.addEventListener("click", function () { applyCase(c.id); update(); });
      head.appendChild(document.createTextNode(" · 설정을 바꿔 케이스에서 벗어났다")); head.appendChild(again);
    }
    b.appendChild(head);
    b.appendChild(el("div", { cls: "t", text: c.title }));
    b.appendChild(el("p", { cls: "s", text: c.story }));
    b.appendChild(el("dl", { cls: "grid" }, [
      el("dt", { text: "공격 원형" }), el("dd", { text: scnById[c.scenario].title }),
      el("dt", { text: "이 케이스의 결과" }), el("dd", null, [el("span", { cls: "r " + r.outcome, text: RESULT_KO[r.outcome] + (r.outcome === "blocked" ? " (" + r.stage + "단계)" : "") }), " — " + r.impact]),
      el("dt", { text: "볼 것" }), el("dd", { text: c.lesson })
    ]));
    if (r.outcome !== c.expect) {
      b.appendChild(el("p", { cls: "warn", text: "규제 데이터가 바뀌어 결과가 케이스 작성 때(" + RESULT_KO[c.expect] + ")와 다르다 — 위 설명은 업데이트 전 기준이다." }));
    }
  }
  function stepCase(d) {
    if (!CASES.length) return;
    var i = CASES.indexOf(caseById[state.kase]);
    i = i < 0 ? (d > 0 ? 0 : CASES.length - 1) : (i + d + CASES.length) % CASES.length;
    applyCase(CASES[i].id); update();
  }

  // ── ③ 규제가 바뀌면 ──
  function renderUpdates() {
    var R = D.registry || {}, H = D.history || [];
    $("reg-meta").textContent = "규제 문서 " + (R.docs || 0) + "건 · 가장 최근 문서 " + (R.latest || "—") +
      (H.length ? " · 마지막 반영 " + H[H.length - 1].at : "");
    var ol = clear($("hist")), labels = {};
    D.presets.forEach(function (p) { labels[p.id] = p.label; });
    if (!H.length) ol.appendChild(el("li", { text: "아직 기록이 없다." }));
    H.slice().reverse().forEach(function (h, ri) {
      var i = H.length - 1 - ri, prev = H[i - 1], ul = el("ul");
      if (prev) {
        Object.keys(h.presets).forEach(function (pid) {
          var a = prev.presets[pid], z = h.presets[pid];
          if (a && (a[0] !== z[0] || a[1] !== z[1])) ul.appendChild(el("li", null, [(labels[pid] || pid) + " — 막혔을 사건 " + a[0] + "~" + a[1] + " → ", el("b", { text: z[0] + "~" + z[1] })]));
          var sa = (prev.scenarios || {})[pid] || {}, sz = (h.scenarios || {})[pid] || {};
          Object.keys(sz).forEach(function (sid) {
            if (sa[sid] && sa[sid] !== sz[sid] && scnById[sid]) ul.appendChild(el("li", null, [(labels[pid] || pid) + " · " + scnById[sid].title.split(" →")[0] + ": " + RESULT_KO[sa[sid]] + " → ", el("b", { text: RESULT_KO[sz[sid]] })]));
          });
        });
        if (!ul.childNodes.length) ul.appendChild(el("li", { text: "결과가 바뀐 프리셋 없음" }));
      } else ul.appendChild(el("li", { text: "기준 — 문서 " + h.docs.length + "건" }));
      ol.appendChild(el("li", null, [el("div", { cls: "h" }, [el("time", { text: h.at }), el("span", { cls: "l", text: h.label })]), ul]));
    });
    var P = D.pending || { count: 0, top: [] }, pu = clear($("pend"));
    $("pend-n").textContent = P.count + "건";
    if (!P.top.length) pu.appendChild(el("li", { text: "후보 없음" }));
    P.top.forEach(function (x) {
      pu.appendChild(el("li", null, [el("time", { text: x.published }), el("div", null, [
        el("div", { cls: "k", text: x.jurisdiction + " · " + x.issuer + " · 점수 " + x.score + " (" + x.why.join(" · ") + ")" }),
        el("div", { cls: "t" }, [link(x.link, x.title)])
      ])]));
    });
  }

  // ── 묶기 ──
  function update() {
    renderPresetHint(); renderControls(); renderEnv(); renderCaseBanner(); renderOverview(); renderWalk(false); renderReplay(); writeHash();
  }

  $("case").addEventListener("change", function (e) { applyCase(e.target.value); update(); });
  $("prev").addEventListener("click", function () { stepCase(-1); });
  $("next-case").addEventListener("click", function () { stepCase(1); });
  document.addEventListener("keydown", function (e) {
    var t = e.target && e.target.tagName;
    if (t === "INPUT" || t === "SELECT" || t === "TEXTAREA" || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); stepCase(1); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); stepCase(-1); }
  });
  $("preset").addEventListener("change", function (e) {
    state.preset = e.target.value;
    if (presetById[state.preset]) state.levels = Object.assign({}, presetById[state.preset].levels);
    update();
  });
  $("profile").addEventListener("change", function (e) {
    state.profile = e.target.value;
    if (profileById[state.profile]) state.env = envOf(profileById[state.profile]);
    update();
  });
  $("run").addEventListener("click", function () {
    renderWalk(true);
    var ol = $("stages");
    if (ol.scrollIntoView) ol.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  });
  $("print").addEventListener("click", function () { window.print(); });
  $("copy").addEventListener("click", function () {
    writeHash();
    var url = location.href, msg = $("copy-msg");
    var done = function () { msg.textContent = "복사했다"; setTimeout(function () { msg.textContent = ""; }, 2400); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { msg.textContent = url; });
    else msg.textContent = url;
  });

  readHash();
  if (state.kase && !/[&#]l=/.test(location.hash)) applyCase(state.kase);   // 케이스 링크만 있으면 케이스 설정으로
  renderPresetSelect(); renderCasePicker(); renderUpdates(); update();
})();
