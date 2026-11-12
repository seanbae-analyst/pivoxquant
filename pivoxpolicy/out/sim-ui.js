/* sim-ui.js — 모의 테스트 화면(데스크톱). 계산은 sim-engine.js(PivoxSimEngine), 데이터는 sim-data.js(PIVOX_SIM).
   글은 전부 textContent로 넣는다(innerHTML에 데이터를 넣지 않는다). 설정은 주소창 # 뒤에만 남긴다 — 저장·전송 없음.
   CSV는 이 브라우저에서 만들어 내려받는다(서버로 가지 않는다). */
(function () {
  "use strict";
  var D = window.PIVOX_SIM, E = window.PivoxSimEngine;
  if (!D || !E) return;

  var LAYER_KO = { analog: "사람·계정", agent: "AI 적용" };
  var LEVEL_KO = ["없음", "사람·계정만", "AI까지"];
  var SCORE_KO = ["다루지 않음", "자율", "구속력", "구속력 + 에이전트 명시"];
  var REG_SHORT = ["—", "자율", "강제", "강제"];
  var STAGE_KO = { before: "배치 전", in_use: "사용 중", after: "사후" };
  var EFFECT_ON = { prevent: "막음", limit: "닿는 범위를 줄임", detect: "알아챔", contain: "멈추고 회수" };
  var DECISION = { prevent: "차단", limit: "범위 제한", detect: "기록·탐지", contain: "멈춤·회수" };
  var ENTRY_KO = { untrusted_input: "외부 입력을 읽는다", open_components: "외부 구성요소를 들인다",
                   memory: "장기 메모리를 쓴다", multi_agent: "다른 에이전트와 일을 주고받는다" };
  var TOOLS = [["read", "조회만"], ["write", "쓰기·실행"], ["pay", "송금·결제"]];
  var REQ_KO = { untrusted_input: "외부 입력을 읽지 않는다", open_components: "외부 구성요소를 들이지 않는다",
                 memory: "장기 메모리를 쓰지 않는다", multi_agent: "다른 에이전트와 일을 주고받지 않는다",
                 exec_tools: "코드를 실행할 도구 권한(쓰기·실행 이상)이 없다" };
  var ENV_KEYS = ["tools", "untrusted_input", "open_components", "memory", "multi_agent"];
  var FLAG_KEYS = ["untrusted_input", "open_components", "memory", "multi_agent"];
  var ENV_NAME = { tools: "도구 권한", untrusted_input: "외부 입력", open_components: "외부 구성요소", memory: "장기 메모리", multi_agent: "멀티 에이전트" };
  var ENV_OPTS = { untrusted_input: [[true, "읽는다"], [false, "안 읽는다"]], open_components: [[true, "들인다"], [false, "고정된 것만"]],
                   memory: [[true, "쌓는다"], [false, "안 쌓는다"]], multi_agent: [[true, "주고받는다"], [false, "혼자 일한다"]] };
  var ENV_SEG = { tools: "tools", untrusted_input: "untrusted", open_components: "components", memory: "memory", multi_agent: "multi" };
  var OUT_KO = { blocked: "막혔을 사건", blocked_maybe: "막혔을 수도", reduced: "피해 축소", unchanged: "그대로", unknown: "판단 근거 없음" };
  var RESULT_KO = { blocked: "막힘", reduced: "피해 축소", damage: "피해 발생", no_surface: "공격면 없음" };
  var SHORT_OUT = { blocked: "막힘", reduced: "축소", damage: "발생", no_surface: "—" };
  var ASI_KO = { full: "막음", partial: "부분", gap: "공백", na: "해당 없음", none: "원형 없음" };
  var INC_ORDER = ["blocked", "blocked_maybe", "reduced", "unchanged", "unknown"];
  var INC_WHY = { blocked: "이 사건에서 실패한 통제가 이 설정에서 모두 켜져 있다", blocked_maybe: "사전·사용 중 단계의 실패 통제가 일부만 켜졌다. 막혔을 수도 있다",
                  reduced: "사후 단계 통제만 켜졌다. 피해를 줄였을 것이다", unchanged: "실패한 통제가 하나도 켜지지 않았다",
                  unknown: "공개 자료에 피해 쪽 실패 통제가 나오지 않아 판단하지 않는다" };
  var DIAG_ST = [["", "모름"], ["none", "없음"], ["plan", "계획"], ["partial", "부분"], ["done", "구현"]];
  var DIAG_KO = {}; DIAG_ST.forEach(function (x) { DIAG_KO[x[0]] = x[1]; });
  var JUR = ["KR", "US", "EU", "INTL"], JUR3 = ["KR", "US", "EU"];

  var ctlById = {}, stageOf = {}, failures = {}, presetById = {}, profileById = {}, scnById = {}, incById = {};
  D.controls.forEach(function (c) { ctlById[c.id] = c; stageOf[c.id] = c.stage; });
  D.incidents.forEach(function (i) { failures[i.id] = i.fails; incById[i.id] = i; });
  D.presets.forEach(function (p) { presetById[p.id] = p; });
  D.agent_profiles.forEach(function (p) { profileById[p.id] = p; });
  D.scenarios.forEach(function (s) { scnById[s.id] = s; });
  var CASES = D.cases || [], caseById = {};
  CASES.forEach(function (c) { caseById[c.id] = c; });
  var CIDS = D.controls.map(function (c) { return c.id; });
  var ASI = (D.owasp_asi || {}).items || [], asiById = {};
  ASI.forEach(function (a) { asiById[a.id] = a; });

  function envOf(p) {
    if (!p) return null;
    var e = {}; ENV_KEYS.forEach(function (k) { e[k] = k === "tools" ? p.tools : !!p[k]; }); return e;
  }
  var state = {
    preset: "KR-2", levels: Object.assign({}, (presetById["KR-2"] || D.presets[0]).levels),
    profile: "trading", env: envOf(profileById.trading) || { tools: "pay", untrusted_input: true, open_components: false },
    statedOnly: false, scenario: D.scenarios[0].id, open: {}, kase: null,
    base: null,      // 비교 중이면 고정된 기준 {levels, env, profile} — 왼쪽 설정은 변경안이 된다
    drawer: null,    // 서랍 — {kind: "cell", sid, col} 히트맵 칸 · {kind: "inc", iid} 사건 추적
    diag: {}         // 자가 진단 — 통제 id → {analog, agent, note}. 주소창에도 안 남긴다(메모가 길고 민감할 수 있다)
  };
  function snapshot() { return { levels: Object.assign({}, state.levels), env: Object.assign({}, state.env), profile: state.profile }; }
  function ref() { return state.base || state; }
  // 케이스 → 설정 (sim.py case_setup과 같은 규칙: 프리셋 위에 levels, 에이전트 종류 위에 env)
  function caseSetup(c) {
    var levels = Object.assign({}, presetById[c.preset].levels, c.levels || {});
    var env = Object.assign(envOf(profileById[c.profile]), c.env || {});
    return { levels: levels, env: env, profile: c.env ? "custom" : c.profile, scenario: c.scenario };
  }
  function applyCase(id) {
    var c = caseById[id];
    state.base = null;
    if (!c) { state.kase = null; return; }
    var su = caseSetup(c);
    state.kase = id; state.levels = su.levels; state.env = su.env; state.profile = su.profile; state.scenario = su.scenario;
    state.preset = matchPreset();
  }
  function caseDirty() {
    var c = caseById[state.kase]; if (!c) return false;
    var su = caseSetup(c), r = ref();          // 비교 중이면 기준이 케이스, 변경안은 그 위의 대책
    return su.scenario !== state.scenario || CIDS.some(function (k) { return su.levels[k] !== r.levels[k]; }) ||
      ENV_KEYS.some(function (k) { return su.env[k] !== r.env[k]; });
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
  function short(s) { return s.title.split(" →")[0]; }
  function button(text, cls, onClick, attrs) {
    var b = el("button", Object.assign({ type: "button", cls: "btn" + (cls ? " " + cls : ""), text: text }, attrs || {}));
    b.addEventListener("click", onClick);
    return b;
  }
  function seg(container, name, options, current, onChange) {
    clear(container);
    options.forEach(function (o) {
      var id = "r-" + name + "-" + String(o[0]);      // 같은 id로 다시 그려서 키보드 포커스를 되돌린다
      var inp = el("input", { type: "radio", name: name, id: id, value: String(o[0]) });
      if (String(o[0]) === String(current)) inp.checked = true;
      inp.addEventListener("change", function () { onChange(o[0]); });
      var lab = el("label", { "for": id }, [inp, el("span", { text: o[1] })]);
      if (o[2]) lab.setAttribute("title", o[2]);
      container.appendChild(lab);
    });
  }
  function bool(v) { return v === true || v === "true"; }
  function sign(n) { return n > 0 ? "+" + n : n < 0 ? "-" + (-n) : "±0"; }
  function rangeText(r) { return r.blocked_lo === r.blocked_hi ? String(r.blocked_hi) : r.blocked_lo + "~" + r.blocked_hi; }
  function optLabel(k, v) {
    if (k === "tools") { var t = TOOLS.filter(function (x) { return x[0] === v; })[0]; return t ? t[1] : v; }
    var o = (ENV_OPTS[k] || []).filter(function (x) { return x[0] === !!v; })[0]; return o ? o[1] : String(v);
  }
  function envSummary(env) {
    return optLabel("tools", env.tools) + " · 외부 입력 " + optLabel("untrusted_input", env.untrusted_input) + " · 구성요소 " +
      optLabel("open_components", env.open_components) + " · 메모리 " + optLabel("memory", env.memory) + " · " + optLabel("multi_agent", env.multi_agent);
  }
  function presetOf(levels) {
    for (var i = 0; i < D.presets.length; i++) {
      var p = D.presets[i];
      if (CIDS.every(function (c) { return p.levels[c] === levels[c]; })) return p.id;
    }
    return "custom";
  }
  function matchPreset() { return presetOf(state.levels); }
  function profileOf(env) {
    for (var i = 0; i < D.agent_profiles.length; i++) {
      var p = D.agent_profiles[i];
      if (JSON.stringify(envOf(p)) === JSON.stringify(env)) return p.id;
    }
    return "custom";
  }
  function cfgLabel(c) {
    var pid = presetOf(c.levels), prof = profileById[c.profile] || profileById[profileOf(c.env)];
    return (presetById[pid] ? presetById[pid].label : "직접 설정한 통제") + " · " + (prof ? prof.label : "직접 설정한 환경");
  }

  // ── 계산 묶음 ──
  function scnResults(levels, env) {
    var m = {}; D.scenarios.forEach(function (s) { m[s.id] = E.runScenario(s, env, levels); }); return m;
  }
  function tally(res) {
    var n = { blocked: 0, reduced: 0, damage: 0, no_surface: 0 };
    Object.keys(res).forEach(function (k) { n[res[k].outcome] += 1; }); return n;
  }
  function asiTally(cov) {
    var n = { full: 0, partial: 0, gap: 0, na: 0, none: 0 }; cov.forEach(function (c) { n[c.status] += 1; }); return n;
  }

  // ── 주소창 # ↔ 설정 ──
  function bits(env) { return FLAG_KEYS.map(function (k) { return env[k] ? 1 : 0; }).join(""); }
  function encodeCfg(c) { return CIDS.map(function (k) { return c.levels[k]; }).join("") + "." + c.env.tools + "." + bits(c.env); }
  function decodeCfg(s) {
    var p = String(s || "").split(".");
    if (p.length !== 3 || !/^[012]+$/.test(p[0]) || p[0].length !== CIDS.length || !/^[01]{4}$/.test(p[2]) ||
        !TOOLS.some(function (t) { return t[0] === p[1]; })) return null;
    var levels = {}, env = { tools: p[1] };
    CIDS.forEach(function (c, i) { levels[c] = Number(p[0][i]); });
    FLAG_KEYS.forEach(function (k, i) { env[k] = p[2][i] === "1"; });
    return { levels: levels, env: env, profile: profileOf(env) };
  }
  function writeHash() {
    var h = "p=" + state.preset + "&l=" + CIDS.map(function (c) { return state.levels[c]; }).join("") +
      "&a=" + state.profile + "&t=" + state.env.tools + "&u=" + (state.env.untrusted_input ? 1 : 0) +
      "&c=" + (state.env.open_components ? 1 : 0) + "&m=" + (state.env.memory ? 1 : 0) + "&g=" + (state.env.multi_agent ? 1 : 0) +
      "&s=" + state.scenario + "&b=" + (state.statedOnly ? 1 : 0) + (state.kase ? "&k=" + state.kase : "") +
      (state.base ? "&x=" + encodeCfg(state.base) : "");
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
    if (q.x) state.base = decodeCfg(q.x);
  }

  // ── 왼쪽: 비교 · 설정 ──
  var pendingFocus = null;
  function startCompare() { state.base = snapshot(); pendingFocus = "cmp-discard"; update(); }
  function discardCompare() {
    var b = state.base; if (!b) return;
    state.levels = Object.assign({}, b.levels); state.env = Object.assign({}, b.env); state.profile = b.profile;
    state.preset = matchPreset(); state.base = null; pendingFocus = "cmp-start"; update();
  }
  function adoptCompare() { state.base = null; pendingFocus = "cmp-start"; update(); }
  function renderCompareCtl() {
    var box = clear($("cmp-ctl")), on = !!state.base;
    document.body.classList.toggle("comparing", on);
    Array.prototype.forEach.call(document.querySelectorAll("[data-tag]"), function (t) { t.textContent = on ? "· 변경안" : ""; });
    if (!on) {
      box.appendChild(button("변경안 만들기", "", startCompare, { id: "cmp-start" }));
      $("cmp-hint").textContent = "지금 설정을 기준으로 고정한다. 그 뒤 아래에서 바꾸는 것은 변경안이 되고, 결과 숫자마다 기준과의 차이가 붙는다.";
    } else {
      box.appendChild(button("변경안 버리기", "", discardCompare, { id: "cmp-discard" }));
      box.appendChild(button("변경안을 새 기준으로", "", adoptCompare, { id: "cmp-adopt" }));
      $("cmp-hint").textContent = "기준(고정): " + cfgLabel(state.base) + ". 아래 설정이 변경안이다.";
    }
  }
  function renderPresetSelect() {
    var s = clear($("preset"));
    s.appendChild(el("option", { value: "custom", text: "직접 설정 (우리 회사)" }));
    D.presets.forEach(function (p) { s.appendChild(el("option", { value: p.id, text: p.label })); });
  }
  function renderPresetHint() {
    $("preset").value = state.preset;
    var by = [[], [], []];
    CIDS.forEach(function (c) { by[state.levels[c]].push(cname(c)); });
    $("preset-hint").textContent = "AI까지 " + by[2].length + "개" + (by[2].length && by[2].length < 7 ? " (" + by[2].join(" · ") + ")" : "") +
      " · 사람·계정만 " + by[1].length + "개 · 없음 " + by[0].length + "개";
  }
  function regBlock(cid) {
    var R = (D.regulation || {})[cid] || {}, box = el("div", { cls: "reg" });
    box.appendChild(el("p", { text: "관할별로 가장 센 문서 (사람·계정 층 / AI 적용 층)" }));
    var ul = el("ul");
    JUR.forEach(function (j) {
      var r = R[j]; if (!r) return;
      var li = el("li", null, [el("b", { text: (D.jurisdictions || {})[j] || j }), " "]);
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
      var btn = el("button", { type: "button", cls: "nm", id: "nm-" + c.id, "aria-expanded": String(open), "aria-controls": mid },
        [c.num + ". " + c.name, el("small", { text: STAGE_KO[c.stage] || "" })]);
      btn.addEventListener("click", function () { state.open[c.id] = !state.open[c.id]; renderControls(); $("nm-" + c.id).focus(); });
      var g = el("div", { cls: "seg", role: "radiogroup", "aria-label": c.name + " 적용 범위" });
      seg(g, "lv-" + c.id, [[0, "없음"], [1, "사람·계정", h.analog], [2, "AI까지", h.agent]], state.levels[c.id], function (v) {
        state.levels[c.id] = Number(v); state.preset = matchPreset(); update();
      });
      var changed = !!state.base && state.base.levels[c.id] !== state.levels[c.id];
      var row = el("div", { cls: "ctl" + (changed ? " chg" : "") }, [btn, g]);
      if (changed) row.appendChild(el("div", { cls: "was-l", text: "기준 " + LEVEL_KO[state.base.levels[c.id]] + " → 변경안 " + LEVEL_KO[state.levels[c.id]] }));
      if (open) {
        row.appendChild(el("div", { cls: "more", id: mid }, [
          el("dl", null, [el("dt", { text: "사람·계정" }), el("dd", { text: h.analog || "" }), el("dt", { text: "AI까지" }), el("dd", { text: h.agent || "" })]),
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
    FLAG_KEYS.forEach(function (k) {
      seg($(ENV_SEG[k]), ENV_SEG[k], ENV_OPTS[k], state.env[k], function (v) { state.env[k] = bool(v); custom(); update(); });
    });
    ENV_KEYS.forEach(function (k) { $(ENV_SEG[k]).classList.toggle("chg", !!state.base && state.base.env[k] !== state.env[k]); });
  }

  // ── 한눈에: 비교 요약 + KPI 3개 ──
  function renderCompareBar() {
    var b = clear($("cmpbar"));
    b.className = "cmpbar";
    if (!state.base) return;
    var B = state.base, ch = [];
    CIDS.forEach(function (c) { if (B.levels[c] !== state.levels[c]) ch.push(cname(c) + " " + LEVEL_KO[B.levels[c]] + " → " + LEVEL_KO[state.levels[c]]); });
    ENV_KEYS.forEach(function (k) { if (B.env[k] !== state.env[k]) ch.push(ENV_NAME[k] + " " + optLabel(k, B.env[k]) + " → " + optLabel(k, state.env[k])); });
    b.className = "cmpbar on";
    b.appendChild(el("div", { cls: "k", text: "변경안을 비교하는 중. 기준은 " + cfgLabel(B) }));
    if (!ch.length) {
      b.appendChild(el("p", { cls: "t", text: "아직 바꾼 것이 없다. 왼쪽에서 통제나 환경을 바꾸거나, 개선 조치 표에서 '변경안에 넣기'를 누른다." }));
      return;
    }
    b.appendChild(el("p", { cls: "t", text: "바꾼 것 " + ch.length + "개: " + ch.join(", ") }));
    var rb = scnResults(B.levels, B.env), rn = scnResults(state.levels, state.env), moved = [];
    D.scenarios.forEach(function (s) { if (rb[s.id].outcome !== rn[s.id].outcome) moved.push(short(s) + " " + SHORT_OUT[rb[s.id].outcome] + "→" + SHORT_OUT[rn[s.id].outcome]); });
    var pb = E.replay(failures, B.levels, stageOf, state.statedOnly), pn = E.replay(failures, state.levels, stageOf, state.statedOnly);
    var ab = asiTally(E.asiCoverage(D.scenarios, B.env, B.levels, ASI)), an = asiTally(E.asiCoverage(D.scenarios, state.env, state.levels, ASI));
    b.appendChild(el("p", { cls: "s", text: "원형 결과 " + moved.length + "개 바뀜" + (moved.length ? " (" + moved.join(" · ") + ")" : "") +
      " · 사건 막힘 " + rangeText(pb) + " → " + rangeText(pn) + " · OWASP 막음 " + ab.full + " → " + an.full }));
  }
  function strip(items, cls, label) {
    var s = el("span", { cls: "strip", role: "img", "aria-label": label });
    items.forEach(function (x) { s.appendChild(el("i", { cls: cls(x), title: x.title })); });
    return s;
  }
  function kpi(title, value, sub, rows, delta) {
    var v = el("div", { cls: "v" }, [value[0], value[1] ? el("small", { text: value[1] }) : null]);
    var dl = el("dl", { cls: "mv" });
    rows.forEach(function (r) {
      dl.appendChild(el("dt", { cls: r.cur ? "cur" : "", text: r.label }));
      dl.appendChild(el("dd", null, [r.viz]));
      dl.appendChild(el("dd", { cls: "n" + (r.cur ? " cur" : ""), text: r.n }));
    });
    return el("div", { cls: "kpi" }, [el("div", { cls: "k", text: title }), v, delta ? el("div", { cls: "d", text: delta }) : null,
      el("div", { cls: "h", text: sub }), dl]);
  }
  function bandConfigs() {
    var rows = [{ label: "통제 없음", levels: presetById.none.levels, env: state.env }];
    if (state.base) rows.push({ label: "기준", levels: state.base.levels, env: state.base.env, base: true });
    rows.push({ label: state.base ? "변경안" : "지금", levels: state.levels, env: state.env, cur: true });
    rows.push({ label: "모두 AI까지", levels: presetById.all.levels, env: state.env });
    return rows;
  }
  function renderBand() {
    var box = clear($("band")), cfgs = bandConfigs();
    var prof = profileById[state.profile];
    $("pos-env").textContent = "에이전트: " + (prof ? prof.label : "직접 설정한 환경");
    $("pos-env").title = envSummary(state.env);

    // ① 원형
    var nS = D.scenarios.length, now = null, bt = null;
    var rows1 = cfgs.map(function (c) {
      var res = scnResults(c.levels, c.env), t = tally(res);
      if (c.cur) now = t;
      if (c.base) bt = t;
      var items = D.scenarios.map(function (s) { return { o: res[s.id].outcome, title: short(s) + " — " + RESULT_KO[res[s.id].outcome] }; });
      return { label: c.label, cur: c.cur, n: "막힘 " + t.blocked + " · 발생 " + t.damage,
               viz: strip(items, function (x) { return x.o; }, c.label + ": 막힘 " + t.blocked + ", 축소 " + t.reduced + ", 발생 " + t.damage + ", 공격면 없음 " + t.no_surface) };
    });
    box.appendChild(kpi("공격 원형 " + nS + "개 중 막힘", [String(now.blocked), " / 공격면 있는 " + (nS - now.no_surface) + "개"],
      "피해 축소 " + now.reduced + " · 피해 발생 " + now.damage + " · 공격면 없음 " + now.no_surface, rows1,
      bt ? "기준 " + bt.blocked + " → " + sign(now.blocked - bt.blocked) + " · 발생 " + sign(now.damage - bt.damage) : ""));

    // ② 사건
    var rn = null, rbz = null;
    var reps = cfgs.map(function (c) {
      var r = E.replay(failures, c.levels, stageOf, state.statedOnly);
      if (c.cur) rn = r;
      if (c.base) rbz = r;
      return r;
    });
    var judged = rn.total - rn.unknown;
    var rows2 = cfgs.map(function (c, i) {
      var r = reps[i], tr = el("span", { cls: "track", role: "img", "aria-label": c.label + ": 막혔을 사건 " + rangeText(r) + " / " + judged });
      var hi = el("span", { cls: "hi" }), lo = el("span", { cls: "lo" });
      hi.style.width = (judged ? 100 * r.blocked_hi / judged : 0) + "%";
      lo.style.width = (judged ? 100 * r.blocked_lo / judged : 0) + "%";
      tr.appendChild(hi); tr.appendChild(lo);
      return { label: c.label, cur: c.cur, n: rangeText(r) + "건", viz: tr };
    });
    box.appendChild(kpi("막혔을 실제 사건", [rangeText(rn), " / 판단할 수 있는 " + judged + "건"],
      "진한 막대가 하한(실패한 통제가 모두 켜진 경우), 옅은 막대까지가 상한", rows2,
      rbz ? "기준 " + rangeText(rbz) + " → 하한 " + sign(rn.blocked_lo - rbz.blocked_lo) + " · 상한 " + sign(rn.blocked_hi - rbz.blocked_hi) : ""));

    // ④ OWASP
    var an = null, ab = null;
    var rows3 = cfgs.map(function (c) {
      var cov = E.asiCoverage(D.scenarios, c.env, c.levels, ASI), t = asiTally(cov);
      if (c.cur) an = t;
      if (c.base) ab = t;
      var items = cov.map(function (x) { return { o: x.status, title: x.id + " " + (asiById[x.id] || {}).ko + " — " + ASI_KO[x.status] }; });
      return { label: c.label, cur: c.cur, n: "막음 " + t.full + " · 공백 " + t.gap,
               viz: strip(items, function (x) { return "a-" + x.o; }, c.label + ": 막음 " + t.full + ", 부분 " + t.partial + ", 공백 " + t.gap) };
    });
    box.appendChild(kpi("OWASP 10개 항목 중 막음", [String(an.full), " / 잰 항목 " + (ASI.length - an.none - an.na) + "개"],
      "부분 " + an.partial + " · 공백 " + an.gap + " · 해당 없음 " + an.na + " · 원형 없음 " + an.none + " (자체 계산)", rows3,
      ab ? "기준 " + ab.full + " → " + sign(an.full - ab.full) + " · 공백 " + sign(an.gap - ab.gap) : ""));

    var lg = clear($("legend"));
    [["blocked", "막힘 · 막음"], ["reduced", "피해 축소 · 부분"], ["damage", "피해 발생 · 공백"], ["no_surface", "공격면 없음 · 해당 없음 · 원형 없음"]].forEach(function (x) {
      lg.appendChild(el("span", null, [el("i", { cls: x[0] }), x[1]]));
    });
    lg.appendChild(el("span", { cls: "dim", text: "'통제 없음'과 '모두 AI까지' 줄도 지금 에이전트 환경으로 계산했다." }));
  }

  // ── ① 원형 한눈에 + 단계 ──
  function whereText(r) {
    if (r.outcome === "no_surface") return "이 환경에서는 성립하지 않는다: " + r.missing.map(function (x) { return REQ_KO[x]; }).join(", ");
    if (r.outcome === "blocked") return r.stage + "단계 · " + cname(r.steps[r.stage - 1].blocked_by);
    if (r.outcome === "reduced") {
      var w = r.limited_by.map(cname);
      if (r.contained === "early") w.push("탐지 후 " + cname("kill_switch"));
      return "줄인 통제: " + w.join(", ") + ". 남은 피해: " + r.impact;
    }
    return r.impact + (r.contained === "late" ? " (멈출 수단은 있으나 늦게)" : "");
  }
  function renderOverview() {
    var t = clear($("ov")), rb = state.base ? scnResults(state.base.levels, state.base.env) : null;
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { "aria-label": "선택" }), el("th", { text: "공격 원형" }),
      el("th", { text: state.base ? "변경안에서" : "이 설정에서" }), el("th", { text: "막힌 곳 또는 피해" }), el("th", { text: "근거" })])]));
    var tb = el("tbody");
    D.scenarios.forEach(function (s) {
      var r = E.runScenario(s, state.env, state.levels), id = "ov-" + s.id;
      var inp = el("input", { type: "radio", name: "scn", id: id, value: s.id });
      inp.checked = s.id === state.scenario;
      inp.addEventListener("change", function () { select(s.id); });
      var moved = !!rb && rb[s.id].outcome !== r.outcome;
      var res = el("td", null, [moved ? el("span", { cls: "was", text: "기준 " + RESULT_KO[rb[s.id].outcome] + " →" }) : null,
        el("span", { cls: "r " + r.outcome, text: RESULT_KO[r.outcome] })]);
      var tr = el("tr", { cls: (s.id === state.scenario ? "sel" : "") + (moved ? " chg" : "") }, [
        el("td", null, [inp]),
        el("td", null, [el("label", { "for": id, cls: "t", text: s.title }), el("div", { cls: "s", text: s.summary })]),
        res,
        el("td", { cls: "w", text: whereText(r) }),
        el("td", { cls: "b", text: s.incidents.length ? "실제 사건 " + s.incidents.length + "건" : (s.basis || [""])[0].replace(/ (and|&) .*/, "") + " · 사건 없음" })
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
    if (r.outcome === "no_surface") {
      ol.appendChild(el("li", { cls: "stage blocked" }, [el("span", { cls: "no", text: "–" }), el("div", null, [
        el("div", { cls: "t", text: "이 공격은 시작되지 않는다" }),
        el("div", { cls: "d", text: "지금 환경에서 에이전트가 " + r.missing.map(function (x) { return REQ_KO[x]; }).join(", ") + "." })
      ])]));
    } else {
      s.stages.forEach(function (st, idx) {
        var step = r.steps[idx], cls = "stage" + (!step ? " after" : step.blocked_by ? " blocked" : " passed");
        var ck = el("ul", { cls: "ck" });
        if (!step) ck.appendChild(el("li", { text: "앞 단계에서 막혀 여기까지 오지 않았다" }));
        (st.checks || []).forEach(function (c, j) {
          var on = step ? step.checks[j].on : E.covers(Number(state.levels[c.control] || 0), c.layer);
          var lv = Number(state.levels[c.control] || 0);
          var verdict = on ? EFFECT_ON[c.effect] + (c.effect === "contain" && r.contained === "late" ? " (알아챌 기록이 없어 늦게)" : "")
                           : "꺼짐 (지금 " + LEVEL_KO[lv] + ")";
          ck.appendChild(el("li", { cls: on ? "on" : "" }, [el("b", { text: cname(c.control) + " · " + LAYER_KO[c.layer] }), ": " + verdict, el("span", { cls: "why", text: c.why })]));
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
    if (r.outcome === "blocked") { v = r.stage + "단계에서 막힘 (" + cname(r.steps[r.stage - 1].blocked_by) + ")"; p = "공격이 끝까지 가지 못했다. 막지 못했다면: " + r.impact + "."; }
    else if (r.outcome === "reduced") {
      var why = [];
      if (r.limited_by.length) why.push(r.limited_by.map(cname).join(" · ") + "(이)가 닿는 범위를 줄였다");
      if (r.contained === "early") why.push((r.detected_at ? r.detected_at + "단계에서 알아채고 " : "") + "멈췄다");
      v = "피해 축소: " + r.impact; p = "공격은 끝까지 갔지만 " + why.join(", ") + ".";
    } else if (r.outcome === "damage") { v = "피해 발생: " + r.impact; p = r.contained === "late" ? "멈출 수단은 있었지만 알아챌 기록이 없어 늦게 멈췄다." : "끼어든 통제가 없었다."; }
    else { v = "공격면 없음"; p = "이 원형은 지금 환경에서 성립하지 않는다."; }
    var show = function () { out.appendChild(el("div", { cls: "k", text: "결과 · " + short(s) })); out.appendChild(el("div", { cls: "v " + r.outcome, text: v })); out.appendChild(el("p", { text: p })); };
    if (animate && !reduceMotion) {
      items.forEach(function (li, i) { setTimeout(function () { li.classList.remove("pending"); }, 120 + i * 420); });
      setTimeout(show, 120 + items.length * 420);
    } else show();
    renderCases(s);
  }
  // ── ① 공격 흐름: 진입 → 단계 → 결과, 단계마다 통제(켜짐/꺼짐) ──
  function flowStates(s, r) {
    return s.stages.map(function (st, idx) {
      var step = r.steps[idx];
      if (!step) return "after";
      if (step.blocked_by) return "stop";
      return step.checks.some(function (c) { return c.on; }) ? "touch" : "pass";
    });
  }
  function flowRow(s, levels, env, label, baseStates, baseOutcome) {
    var r = E.runScenario(s, env, levels), row = el("div", { cls: "flow-row" });
    var req = s.requires || [];
    var head = el("div", { cls: "flow-top" }, [label ? el("span", { cls: "flow-l", text: label }) : null,
      el("span", { cls: "entry", text: req.length || s.requires_tools ? "진입 조건: 에이전트가 " + req.map(function (x) { return ENTRY_KO[x]; })
        .concat(s.requires_tools ? ["도구 권한 " + s.requires_tools.map(function (t) { return optLabel("tools", t); }).join(" 또는 ") + "을 가진다"] : []).join(" · ")
        : "진입 조건 없음. 어느 에이전트에서나 시작될 수 있다" })]);
    row.appendChild(head);
    if (r.outcome === "no_surface") {
      row.appendChild(el("div", { cls: "flow-none" }, [el("b", { text: "시작되지 않음" }),
        ". 지금 환경에서 에이전트가 " + r.missing.map(function (x) { return REQ_KO[x]; }).join(", ") + ". 공격 흐름이 없다."]));
      return row;
    }
    var states = flowStates(s, r);
    var ol = el("ol", { cls: "flow", "aria-label": (label ? label + ", " : "") + short(s) + " 공격 흐름" });
    ol.style.gridTemplateColumns = "repeat(" + s.stages.length + ", minmax(0,1fr)) 176px";
    s.stages.forEach(function (st, idx) {
      var step = r.steps[idx], stt = states[idx], on = [];
      var gates = el("ul", { cls: "gates" });
      (st.checks || []).forEach(function (c, j) {
        var lv = Number(levels[c.control] || 0), o = step ? step.checks[j].on : E.covers(lv, c.layer);
        if (o && step) on.push(DECISION[c.effect]);
        gates.appendChild(el("li", { cls: o ? "on " + c.effect : "off", title: cname(c.control) + " · " + LAYER_KO[c.layer] + " — " + c.why +
            (o ? "" : " (이 설정: " + LEVEL_KO[lv] + ")") }, [
          el("i"), el("span", { cls: "g", text: cname(c.control) + " " + (c.layer === "agent" ? "AI" : "사람") }),
          el("span", { cls: "e", text: o ? DECISION[c.effect] : "꺼짐" })]));
      });
      if (!(st.checks || []).length) gates.appendChild(el("li", { cls: "none", text: "끼어드는 통제 없음" }));
      var tag = stt === "stop" ? "여기서 차단" : stt === "after" ? "도달 안 함" : stt === "touch" ? on.join(" · ") : "통과";
      var moved = baseStates && baseStates[idx] !== stt;
      ol.appendChild(el("li", { cls: "fn " + stt + (moved ? " chg" : "") }, [
        el("div", { cls: "fh" }, [el("span", { cls: "no", text: String(idx + 1) }), el("span", { cls: "tag", text: tag })]),
        el("div", { cls: "ft", text: st.title }), gates]));
    });
    var endMoved = baseOutcome && baseOutcome !== r.outcome;
    ol.appendChild(el("li", { cls: "fn end " + r.outcome + (endMoved ? " chg" : "") }, [
      el("div", { cls: "fh" }, [el("span", { cls: "tag", text: "결과" })]),
      el("div", { cls: "ft", text: RESULT_KO[r.outcome] + (r.outcome === "blocked" ? " · " + r.stage + "단계" : "") }),
      el("p", { cls: "fi", text: r.outcome === "blocked" ? "막지 못했다면: " + r.impact :
        r.outcome === "reduced" ? "줄인 통제: " + r.limited_by.map(cname).concat(r.contained === "early" ? ["탐지 후 " + cname("kill_switch")] : []).join(", ") + ". 남은 피해: " + r.impact :
        r.impact + (r.contained === "late" ? " · 멈출 수단은 있었지만 늦게" : "") })]));
    row.appendChild(ol);
    return row;
  }
  function renderFlow(animate) {
    var s = scnById[state.scenario], box = clear($("flow"));
    $("flow-name").textContent = short(s);
    if (state.base) {
      var rb = E.runScenario(s, state.base.env, state.base.levels);
      box.appendChild(flowRow(s, state.base.levels, state.base.env, "기준"));
      box.appendChild(flowRow(s, state.levels, state.env, "변경안", rb.outcome === "no_surface" ? null : flowStates(s, rb), rb.outcome));
    } else box.appendChild(flowRow(s, state.levels, state.env, ""));
    if (animate && !reduceMotion) {
      Array.prototype.forEach.call(box.querySelectorAll(".flow"), function (ol) {
        Array.prototype.forEach.call(ol.children, function (li, i) {
          li.classList.add("pending");
          setTimeout(function () { li.classList.remove("pending"); }, 120 + i * 420);
        });
      });
    }
  }

  function renderCases(s) {
    $("scn-cases-h").textContent = s.incidents.length ? "이 원형의 근거 사건 " + s.incidents.length + "건" : "이 원형의 근거: " + (s.basis || []).join(", ");
    var ul = clear($("scn-list"));
    s.incidents.map(function (id) { return incById[id]; }).filter(Boolean).sort(function (a, b) { return a.date < b.date ? 1 : -1; }).forEach(function (i) {
      ul.appendChild(el("li", null, [el("time", { text: i.date }), el("div", null, [
        el("div", { cls: "t" }, [link(i.url, i.title)]),
        el("div", { cls: "k", text: i.fails.length ? "실패 판정: " + i.fails.map(function (f) { return cname(f.control) + "(" + LAYER_KO[f.layer] + ")"; }).join(" · ") : "실패 판정 없음 — 공개 자료에 피해 쪽 통제가 적혀 있지 않다" })
      ])]));
    });
  }

  // ── ① 히트맵: 원형 × 프리셋 + 서랍 ──
  function heatCols() {
    var mid = D.presets.filter(function (p) { return p.id !== "none" && p.id !== "all"; });
    var cols = [presetById.none].concat(mid, [presetById.all]).map(function (p) {
      var parts = p.label.split(" — ");
      return { id: p.id, label: p.label, top: p.id === "none" ? "통제" : p.id === "all" ? "모두" : parts[0].replace("국제 권고", "국제"),
               sub: p.id === "none" ? "없음" : p.id === "all" ? "AI까지" : (parts[1] || "").replace(" 규제만", "").replace("가이드라인까지", "가이드"),
               levels: p.levels, env: state.env, preset: true };
    });
    if (state.base) cols.push({ id: "_base", label: "기준", top: "기준", sub: "고정", levels: state.base.levels, env: state.base.env, base: true });
    cols.push({ id: "_now", label: state.base ? "변경안" : "지금 설정", top: state.base ? "변경안" : "지금", sub: "설정", levels: state.levels, env: state.env, now: true });
    return cols;
  }
  function renderHeat() {
    var t = clear($("heat")), cols = heatCols(), rb = state.base ? scnResults(state.base.levels, state.base.env) : null;
    var first = true;
    var hr = el("tr", null, [el("th", { scope: "col", cls: "rh", text: "공격 원형" })]);
    cols.forEach(function (c) {
      var mine = c.now || c.base, cls = mine ? "mine" + (first ? " first" : "") : "";
      if (mine) first = false;
      hr.appendChild(el("th", { scope: "col", cls: cls }, [el("b", { text: c.top }), c.sub]));
    });
    t.appendChild(el("thead", null, [hr]));
    var tb = el("tbody");
    D.scenarios.forEach(function (s) {
      var asis = E.asiOf(s), f2 = true;
      var tr = el("tr", null, [el("th", { scope: "row", cls: "rh" }, [el("span", { cls: "t", text: short(s) }),
        el("span", { cls: "s", text: (s.incidents.length ? "사건 " + s.incidents.length + "건" : "사건 없음") + (asis.length ? " · " + asis.join(" · ") : "") })])]);
      cols.forEach(function (c) {
        var r = E.runScenario(s, c.env, c.levels);
        var on = !!state.drawer && state.drawer.sid === s.id && state.drawer.col === c.id;
        var moved = c.now && !!rb && rb[s.id].outcome !== r.outcome;
        var b = el("button", { type: "button", id: "hc-" + s.id + "-" + c.id, cls: "hc " + r.outcome + (on ? " on" : "") + (moved ? " chg" : ""),
          "aria-label": short(s) + " · " + c.label + ": " + RESULT_KO[r.outcome] + (r.outcome === "blocked" ? " " + r.stage + "단계" : "") +
            (moved ? " (기준 " + RESULT_KO[rb[s.id].outcome] + ")" : ""),
          "aria-pressed": on ? "true" : "false",
          text: SHORT_OUT[r.outcome] + (r.outcome === "blocked" ? " " + r.stage : "") });
        b.addEventListener("click", function () { openDrawer(s.id, c.id); });
        var mine = c.now || c.base;
        tr.appendChild(el("td", { cls: mine ? "mine" + (f2 ? " first" : "") : "" }, [b]));
        if (mine) f2 = false;
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
  }
  var drawerFrom = null;
  function openDrawer(sid, colId) { openPanel({ kind: "cell", sid: sid, col: colId }, "hc-" + sid + "-" + colId); }
  function openIncDrawer(iid) { openPanel({ kind: "inc", iid: iid }, "tr-" + iid); }
  function openPanel(d, from) {
    if (!state.drawer) drawerFrom = from;
    state.drawer = d;
    renderHeat(); renderDrawer();
    $("drawer").hidden = false;
    document.body.classList.add("drawer-open");
    $("drawer-x").focus();
  }
  function closeDrawer() {
    if (!state.drawer) return;
    var d = state.drawer, back = d.kind === "inc" ? "tr-" + d.iid : "hc-" + d.sid + "-" + d.col;
    state.drawer = null; $("drawer").hidden = true; document.body.classList.remove("drawer-open"); renderHeat();
    var f = $(back) || $(drawerFrom);
    if (f) f.focus();
  }
  function renderDrawer() {
    var d = state.drawer; if (!d) return;
    if (d.kind === "inc") renderIncDrawer(d); else renderCellDrawer(d);
  }
  // 추적 — 통제(층) → 관할별 그 층의 가장 센 문서 → ③ 개선 조치의 순위
  function regList(cid, layer) {
    var ul = el("ul", { cls: "tr-reg" });
    JUR.forEach(function (j) {
      var x = regOf(cid, j)[layer] || { score: 0 };
      var li = el("li", null, [el("b", { text: (D.jurisdictions || {})[j] || j }), " " + SCORE_KO[x.score]]);
      if (x.doc) { li.appendChild(document.createTextNode(" · ")); li.appendChild(link(x.url, x.title)); }
      ul.appendChild(li);
    });
    return ul;
  }
  function traceBlock(title, items) {
    var acts = actions(), rank = {};
    acts.forEach(function (a, k) { rank[a.control] = { n: k + 1, a: a }; });
    var box = el("div", { cls: "trace" }, [el("h3", { cls: "h3", text: title })]);
    if (!items.length) box.appendChild(el("p", { cls: "fine", text: "이어 볼 통제가 없다." }));
    items.forEach(function (it) {
      var ar = rank[it.cid], tail = el("div", { cls: "tr-a" });
      if (ar) {
        tail.appendChild(document.createTextNode("개선 조치 " + ar.n + "순위. 사건 막힘 하한 " + sign(ar.a.inc_lo) + " · 상한 " + sign(ar.a.inc_hi) + " "));
        if (state.levels[it.cid] < 2) tail.appendChild(button("변경안에 넣기", "sm", function () {
          if (!state.base) state.base = snapshot();
          state.levels[it.cid] = 2; state.preset = matchPreset(); pendingFocus = "drawer-x"; update();
        }));
        else tail.appendChild(el("span", { cls: "in", text: "변경안에 있음" }));
      } else tail.appendChild(document.createTextNode((state.base ? "기준" : "지금 설정") + "에서 이미 AI까지 켜져 있어 개선 조치 목록에 없다"));
      box.appendChild(el("div", { cls: "tr-item" + (it.on ? " on" : "") }, [
        el("div", { cls: "tr-c" }, [el("i"), el("b", { text: cname(it.cid) + " · " + LAYER_KO[it.layer] }),
          ": " + (it.on ? "켜짐" : "꺼짐") + " (" + LEVEL_KO[it.lv] + ")" + (it.extra ? " · " + it.extra : "")]),
        regList(it.cid, it.layer), tail]));
    });
    return box;
  }
  function renderIncDrawer(d) {
    var i = incById[d.iid];
    if (!i) { closeDrawer(); return; }
    var body = clear($("drawer-body")), s = scnById[i.scenario];
    var r = E.replay(failures, state.levels, stageOf, state.statedOnly), out = r.per[i.id];
    $("drawer-k").textContent = "사건 추적 · " + i.date;
    $("drawer-h").textContent = i.title;
    var sb = s ? el("button", { type: "button", cls: "lnk", text: short(s) }) : null;
    if (sb) sb.addEventListener("click", function () {
      state.scenario = s.id; closeDrawer(); update(); renderFlow(true);
      var o = $("h-flow"); if (o.scrollIntoView) o.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    });
    body.appendChild(el("dl", { cls: "meta" }, [
      el("dt", { text: "출처" }), el("dd", null, [link(i.url, "원문")]),
      el("dt", { text: "공격 원형" }), el("dd", null, [sb || "—"]),
      el("dt", { text: "판정" }), el("dd", { text: "두 팀 블라인드 코딩 → 조정본 · 실패 통제 " + i.fails.length + "개" })
    ]));
    var vcls = { blocked: "blocked", blocked_maybe: "reduced", reduced: "reduced", unchanged: "damage", unknown: "no_surface" }[out];
    body.appendChild(el("div", { cls: "res" }, [el("div", { cls: "v " + vcls, text: OUT_KO[out] + (state.base ? " (변경안)" : "") }),
      el("p", { text: INC_WHY[out] + (state.statedOnly ? " · 원문이 적은 실패만 센다" : "") })]));
    var items = i.fails.map(function (f) {
      var lv = Number(state.levels[f.control] || 0);
      return { cid: f.control, layer: f.layer, lv: lv, on: E.covers(lv, f.layer),
               extra: (f.level === "stated" ? "원문이 적은 실패" : "원문 사실에서 추론") + (state.statedOnly && f.level !== "stated" ? " (지금 기준에서는 빠짐)" : "") };
    });
    body.appendChild(traceBlock("실패한 통제와 규제 근거", items));
  }
  function renderCellDrawer(d) {
    var col = heatCols().filter(function (c) { return c.id === d.col; })[0], s = scnById[d.sid];
    if (!col || !s) { closeDrawer(); return; }
    var r = E.runScenario(s, col.env, col.levels), body = clear($("drawer-body"));
    $("drawer-k").textContent = "공격 원형 × " + col.label;
    $("drawer-h").textContent = short(s);
    body.appendChild(el("p", { cls: "s", text: s.summary }));
    body.appendChild(el("dl", { cls: "meta" }, [
      el("dt", { text: "통제" }), el("dd", { text: (presetById[presetOf(col.levels)] || { label: "직접 설정" }).label }),
      el("dt", { text: "에이전트" }), el("dd", { text: envSummary(col.env) }),
      el("dt", { text: "근거" }), el("dd", { text: (s.incidents.length ? "실제 사건 " + s.incidents.length + "건 · " : "") + (s.basis || []).join(" · ") })
    ]));
    body.appendChild(el("div", { cls: "res" }, [el("div", { cls: "v " + r.outcome, text: RESULT_KO[r.outcome] + (r.outcome === "blocked" ? ", " + r.stage + "단계" : "") }),
      el("p", { text: whereText(r) })]));
    body.appendChild(el("h3", { cls: "h3", text: "단계별 결정 기록" }));
    var ol = el("ol", { cls: "log" });
    if (r.outcome === "no_surface") {
      ol.appendChild(el("li", { cls: "block" }, [el("span", { cls: "no", text: "–" }), el("div", null, [el("div", { cls: "dec", text: "시작되지 않음" }),
        el("div", { cls: "d", text: "에이전트가 " + r.missing.map(function (x) { return REQ_KO[x]; }).join(", ") + "." })])]));
    } else {
      s.stages.forEach(function (st, idx) {
        var step = r.steps[idx], dec, cls;
        if (!step) { dec = "도달 안 함"; cls = "skip"; }
        else if (step.blocked_by) { dec = cname(step.blocked_by) + "에서 차단"; cls = "block"; }
        else {
          var on = step.checks.filter(function (c) { return c.on; }).map(function (c) { return cname(c.control) + " " + DECISION[c.effect]; });
          dec = on.length ? on.join(" · ") : "통과"; cls = on.length ? "act" : "pass";
        }
        var ck = el("ul");
        (st.checks || []).forEach(function (c, j) {
          var lv = Number(col.levels[c.control] || 0), on = step ? step.checks[j].on : E.covers(lv, c.layer);
          ck.appendChild(el("li", { cls: on ? "on" : "" }, [(on ? "켜짐 · " : "꺼짐 · ") + cname(c.control) + " " + LAYER_KO[c.layer] + " — " +
            (on ? EFFECT_ON[c.effect] : "이 설정 " + LEVEL_KO[lv])]));
        });
        if (!(st.checks || []).length) ck.appendChild(el("li", { text: "끼어드는 통제 없음" }));
        ol.appendChild(el("li", { cls: cls }, [el("span", { cls: "no", text: String(idx + 1) }),
          el("div", null, [el("div", { cls: "t", text: st.title }), el("div", { cls: "dec", text: dec }), ck])]));
      });
    }
    body.appendChild(ol);
    var seen = {}, items = [];
    s.stages.forEach(function (st) {
      (st.checks || []).forEach(function (c) {
        var k = c.control + "|" + c.layer, lv = Number(col.levels[c.control] || 0);
        if (seen[k]) return;
        seen[k] = 1;
        items.push({ cid: c.control, layer: c.layer, lv: lv, on: E.covers(lv, c.layer), extra: DECISION[c.effect] + " 자리" });
      });
    });
    body.appendChild(traceBlock("이 원형에 끼어드는 통제와 규제 근거", items));
    var acts = el("div", { cls: "drawer-acts" });
    acts.appendChild(button("①에서 흐름 따라 보기", "", function () {
      state.scenario = s.id; closeDrawer(); update(); renderFlow(true); renderWalk(true);
      var o = $("h-flow");
      if (o.scrollIntoView) o.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }));
    if (col.preset) {
      acts.appendChild(button("이 프리셋을 " + (state.base ? "변경안" : "왼쪽 설정") + "에 불러오기", "", function () {
        state.levels = Object.assign({}, col.levels); state.preset = col.id; state.drawer = { kind: "cell", sid: s.id, col: "_now" };
        pendingFocus = "drawer-x"; update();
      }));
    }
    body.appendChild(acts);
  }

  // ── ② 다시 돌리기 ──
  function renderReplay() {
    seg($("basis"), "basis", [[false, "적었거나 추론한 실패"], [true, "원문이 적은 실패만"]], state.statedOnly, function (v) { state.statedOnly = bool(v); update(); });
    var r = E.replay(failures, state.levels, stageOf, state.statedOnly), judged = r.total - r.unknown;
    var b = state.base ? E.replay(failures, state.base.levels, stageOf, state.statedOnly) : null;
    var cards = clear($("rep-cards"));
    function card(k, v, h, hl, was) {
      cards.appendChild(el("div", { cls: "card" + (hl ? " hl" : "") }, [el("div", { cls: "k", text: k }), el("div", { cls: "v", text: v }),
        was ? el("div", { cls: "was-c", text: was }) : null, el("div", { cls: "h", text: h })]));
    }
    card("막혔을 사건", rangeText(r), "판단할 수 있는 " + judged + "건 중", true,
      b ? "기준 " + rangeText(b) + " · 하한 " + sign(r.blocked_lo - b.blocked_lo) + " · 상한 " + sign(r.blocked_hi - b.blocked_hi) : "");
    card("피해 축소", String(r.reduced), "사후 통제만 맞음", false, b ? "기준 " + b.reduced + " · " + sign(r.reduced - b.reduced) : "");
    card("그대로", String(r.unchanged), "실패한 통제가 하나도 켜지지 않음", false, b ? "기준 " + b.unchanged + " · " + sign(r.unchanged - b.unchanged) : "");
    card("판단 근거 없음", String(r.unknown), "공개 자료에 피해 쪽 통제가 없음");
    $("rep-explain").textContent = "하한 = 그 사건에서 실패한 통제가 모두 켜졌을 때 · 상한 = 사전·사용 중 단계 통제가 하나라도 켜졌을 때.";
    var t = clear($("cmp"));
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "프리셋" }), el("th", { cls: "num", text: "막혔을 사건" }), el("th", { cls: "num", text: "피해 축소" }),
      el("th", { cls: "num", text: "그대로" }), el("th", { cls: "num", text: "판단 근거 없음" })])]));
    var tb = el("tbody"), rows = D.presets.map(function (p) { return { label: p.label, levels: p.levels, cur: !state.base && p.id === state.preset }; });
    if (state.base) {
      rows.unshift({ label: "기준 (고정)", levels: state.base.levels, base: true });
      rows.unshift({ label: "변경안", levels: state.levels, cur: true });
    } else if (state.preset === "custom") rows.unshift({ label: "지금 설정 (직접)", levels: state.levels, cur: true });
    rows.forEach(function (p) {
      var x = E.replay(failures, p.levels, stageOf, state.statedOnly);
      tb.appendChild(el("tr", { cls: p.cur ? "cur" : p.base ? "base" : "" }, [el("td", { text: p.label }),
        el("td", { cls: "num" }, [el("b", { text: rangeText(x) })]), el("td", { cls: "num", text: String(x.reduced) }),
        el("td", { cls: "num", text: String(x.unchanged) }), el("td", { cls: "num", text: String(x.unknown) })]));
    });
    t.appendChild(tb);
    var pt = clear($("per"));
    pt.appendChild(el("thead", null, [el("tr", null, [el("th", { "aria-label": "추적" }), el("th", { text: "사건" }), el("th", { text: "실패 판정" }), el("th", { text: "결과" }), el("th", { text: "날짜" })])]));
    var pb = el("tbody"), order = { blocked: 0, blocked_maybe: 1, reduced: 2, unchanged: 3, unknown: 4 };
    D.incidents.slice().sort(function (a, z) { return order[r.per[a.id]] - order[r.per[z.id]] || (a.date < z.date ? 1 : -1); }).forEach(function (i) {
      var fs = state.statedOnly ? i.fails.filter(function (f) { return f.level === "stated"; }) : i.fails;
      var moved = !!b && b.per[i.id] !== r.per[i.id];
      var tb2 = el("button", { type: "button", id: "tr-" + i.id, cls: "btn sm", text: "추적", "aria-label": i.title + " 추적" });
      tb2.addEventListener("click", function () { openIncDrawer(i.id); });
      pb.appendChild(el("tr", { cls: moved ? "chg" : "" }, [el("td", null, [tb2]), el("td", null, [link(i.url, i.title)]),
        el("td", { text: fs.length ? fs.map(function (f) { return cname(f.control) + "(" + LAYER_KO[f.layer] + ")"; }).join(" · ") : "—" }),
        el("td", null, [moved ? el("span", { cls: "was", text: "기준 " + OUT_KO[b.per[i.id]] + " →" }) : null, OUT_KO[r.per[i.id]]]), el("td", { text: i.date })]));
    });
    pt.appendChild(pb);
    renderSankey(r, b);
  }

  // ── ② 사건 흐름: 사건 → 원형 → 이 설정의 결과 (SVG — 글은 textContent) ──
  var SVGNS = "http://www.w3.org/2000/svg";
  function sv(tag, attrs, text) {
    var n = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function bandPath(x0, y0a, y0b, x1, y1a, y1b) {
    var m = (x0 + x1) / 2, f = function (v) { return Math.round(v * 10) / 10; };
    return "M" + f(x0) + "," + f(y0a) + "C" + f(m) + "," + f(y0a) + " " + f(m) + "," + f(y1a) + " " + f(x1) + "," + f(y1a) +
      "L" + f(x1) + "," + f(y1b) + "C" + f(m) + "," + f(y1b) + " " + f(m) + "," + f(y0b) + " " + f(x0) + "," + f(y0b) + "Z";
  }
  function renderSankey(r, b) {
    var box = clear($("sankey"));
    var W = Math.max(680, Math.round(box.clientWidth || 852)), H = 380, NW = 12, gap = 12;
    var scns = D.scenarios.filter(function (s) { return D.incidents.some(function (i) { return i.scenario === s.id; }); });
    var total = D.incidents.length, flows = {}, outN = {};
    INC_ORDER.forEach(function (o) { outN[o] = 0; });
    scns.forEach(function (s) { flows[s.id] = {}; INC_ORDER.forEach(function (o) { flows[s.id][o] = 0; }); });
    D.incidents.forEach(function (i) { if (flows[i.scenario]) { flows[i.scenario][r.per[i.id]] += 1; outN[r.per[i.id]] += 1; } });
    var outs = INC_ORDER.filter(function (o) { return outN[o] > 0; });
    var k = (H - 16 - gap * (Math.max(scns.length, outs.length) - 1)) / total;
    var x0 = 108, x2 = W - 196, x1 = Math.round((x0 + x2) / 2);
    function stack(counts) {
      var tot = counts.reduce(function (a, c) { return a + c * k; }, 0) + gap * (counts.length - 1), y = (H - tot) / 2;
      return counts.map(function (c) { var o = { y: y, h: c * k }; y += c * k + gap; return o; });
    }
    var n0 = { y: (H - total * k) / 2, h: total * k };
    var sN = stack(scns.map(function (s) { return s.incidents.length; }));
    var oN = stack(outs.map(function (o) { return outN[o]; }));
    var svg = sv("svg", { viewBox: "0 0 " + W + " " + H, width: String(W), height: String(H), role: "img",
      "aria-label": "사건 " + total + "건이 공격 원형을 거쳐 이 설정에서 끝난 결과: " + outs.map(function (o) { return OUT_KO[o] + " " + outN[o] + "건"; }).join(", ") });
    var gL = sv("g"), gN = sv("g"), gT = sv("g");
    var off0 = n0.y, tOff = {};
    outs.forEach(function (o, j) { tOff[o] = oN[j].y; });
    scns.forEach(function (s, i) {
      var h = s.incidents.length * k, sy = sN[i].y;
      var p0 = sv("path", { d: bandPath(x0 + NW, off0, off0 + h, x1, sy, sy + h), "class": "lk l0" });
      p0.appendChild(sv("title", {}, "사건 → " + short(s) + " " + s.incidents.length + "건"));
      gL.appendChild(p0);
      off0 += h;
      var sOff = sy;
      outs.forEach(function (o) {
        var c = flows[s.id][o]; if (!c) return;
        var hh = c * k, p1 = sv("path", { d: bandPath(x1 + NW, sOff, sOff + hh, x2, tOff[o], tOff[o] + hh), "class": "lk o-" + o });
        p1.appendChild(sv("title", {}, short(s) + " → " + OUT_KO[o] + " " + c + "건"));
        gL.appendChild(p1);
        sOff += hh; tOff[o] += hh;
      });
      var g = sv("g", { "class": "sc", tabindex: "0", role: "button", "aria-label": short(s) + " " + s.incidents.length + "건, 공격 흐름 보기" });
      g.appendChild(sv("rect", { x: x1, y: sy, width: NW, height: Math.max(h, 1), "class": "nd" }));
      var t = sv("text", { x: x1 + NW + 8, y: sy + h / 2, "class": "lb", "dominant-baseline": "middle" });
      t.appendChild(sv("tspan", {}, short(s) + " "));
      t.appendChild(sv("tspan", { "class": "c" }, String(s.incidents.length)));
      g.appendChild(t);
      var go = function () {
        state.scenario = s.id; update(); renderFlow(true);
        var o = $("h-flow"); if (o.scrollIntoView) o.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      };
      g.addEventListener("click", go);
      g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      gN.appendChild(g);
    });
    gN.appendChild(sv("rect", { x: x0, y: n0.y, width: NW, height: n0.h, "class": "nd" }));
    gT.appendChild(sv("text", { x: x0 - 10, y: H / 2 - 9, "class": "lb end", "text-anchor": "end" }, "사건 " + total + "건"));
    var yrs = D.incidents.map(function (i) { return String(i.date || "").slice(0, 4); }).filter(Boolean).sort();
    if (yrs.length) gT.appendChild(sv("text", { x: x0 - 10, y: H / 2 + 10, "class": "lb end sub", "text-anchor": "end" }, yrs[0] + "~" + yrs[yrs.length - 1] + " 공개"));
    outs.forEach(function (o, j) {
      var y = oN[j].y, h = oN[j].h;
      var g = sv("g", { "class": "oc", tabindex: "0", role: "button", "aria-label": OUT_KO[o] + " " + outN[o] + "건, 사건별 결과 표 열기" });
      g.appendChild(sv("rect", { x: x2, y: y, width: NW, height: Math.max(h, 1), "class": "nd o-" + o }));
      var t = sv("text", { x: x2 + NW + 8, y: y + h / 2, "class": "lb", "dominant-baseline": "middle" });
      t.appendChild(sv("tspan", {}, OUT_KO[o] + " "));
      t.appendChild(sv("tspan", { "class": "c" }, outN[o] + "건"));
      g.appendChild(t);
      var open = function () { var dd = $("per-d"); dd.open = true; if (dd.scrollIntoView) dd.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" }); };
      g.addEventListener("click", open);
      g.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
      gN.appendChild(g);
    });
    svg.appendChild(gL); svg.appendChild(gN); svg.appendChild(gT);
    box.appendChild(svg);
    var moved = b ? D.incidents.filter(function (i) { return b.per[i.id] !== r.per[i.id]; }).length : 0;
    $("sk-note").textContent = (state.base ? "변경안 기준 · 기준에서 결과가 바뀐 사건 " + moved + "건 · " : "") + "띠를 가리키면 건수 · 원형을 누르면 ①의 흐름도로";
  }

  // ── ③ 개선 조치 ──
  function regOf(cid, j) { return (((D.regulation || {})[cid] || {})[j]) || {}; }
  function actions() {
    var R = ref();
    return E.improvementActions(D.scenarios, R.env, failures, R.levels, stageOf, state.statedOnly);
  }
  function addToProposal(cid) {
    if (!state.base) state.base = snapshot();
    state.levels[cid] = 2; state.preset = matchPreset(); pendingFocus = "act-x-" + cid; update();
  }
  function removeFromProposal(cid) {
    if (!state.base) return;
    state.levels[cid] = state.base.levels[cid]; state.preset = matchPreset(); pendingFocus = "act-add-" + cid; update();
  }
  function renderActions() {
    var acts = actions(), t = clear($("acts"));
    $("acts-note").textContent = (state.base ? "기준" : "지금 설정") + "에서 통제 하나만 AI까지 올렸을 때의 효과다. 하나씩 따로 잰 값이라 더하면 안 된다. " +
      "여러 개를 합친 효과는 '변경안에 넣기'로 넣은 뒤 위 숫자에서 본다. 정렬은 사건 막힘 하한이 많이 느는 순서이고, 같으면 상한, 그다음 바뀌는 원형 수로 정한다. 점수나 가중치는 쓰지 않는다. " +
      "규제 칸은 관할마다 그 통제의 AI 층을 가장 세게 다룬 문서가 강제인지 자율인지 보여 준다. CSV에는 관할별 근거 문서와 비어 있는 담당·기한·상태 칸이 들어간다.";
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { cls: "num", text: "순위" }), el("th", { text: "조치" }), el("th", { text: "단계" }),
      el("th", { text: "사건 막힘" }), el("th", { text: "결과가 바뀌는 원형" }), el("th", { text: "규제 (AI 층)" }), el("th", { text: "변경안" })])]));
    var tb = el("tbody");
    if (!acts.length) tb.appendChild(el("tr", null, [el("td", { colspan: "7", text: "모든 통제가 이미 AI 까지다." })]));
    acts.forEach(function (a, k) {
      var c = ctlById[a.control] || {}, inProp = !!state.base && state.levels[a.control] >= 2, zero = !a.inc_lo && !a.inc_hi && !a.scenarios.length;
      var eff = !a.inc_lo && !a.inc_hi ? el("td", { cls: "eff dim", text: "—" }) : el("td", { cls: "eff" }, [el("span", null, ["하한 ", el("b", { text: sign(a.inc_lo) })]),
        el("span", null, ["상한 ", el("b", { text: sign(a.inc_hi) })])]);
      var sc = el("td", { cls: "sc" });
      if (!a.scenarios.length) sc.appendChild(document.createTextNode("—"));
      a.scenarios.forEach(function (x) { sc.appendChild(el("span", null, [short(scnById[x.id]) + " ", el("b", { text: SHORT_OUT[x.from] + " → " + SHORT_OUT[x.to] })])); });
      var rg = el("td", { cls: "reg" });
      JUR3.forEach(function (j) {
        var g = regOf(a.control, j).agent || { score: 0 }, an = regOf(a.control, j).analog || { score: 0 }, jn = (D.jurisdictions || {})[j] || j;
        rg.appendChild(el("span", { title: jn + ": 사람·계정 층 " + SCORE_KO[an.score] + " / AI 층 " + SCORE_KO[g.score] + (g.title ? " · " + g.title : "") },
          [jn + " ", el("b", { cls: g.score >= 2 ? "must" : "", text: REG_SHORT[g.score] })]));
      });
      var act = el("td", { cls: "act" }, [el("b", { text: (c.num ? c.num + ". " : "") + cname(a.control) + ", " + LEVEL_KO[a.from] + " → AI까지" }),
        el("div", { cls: "fine", text: (c.help || {}).agent || "" })]);
      var cell = el("td", { cls: "prop" });
      if (inProp) {
        cell.appendChild(el("span", { cls: "in", text: "넣음" }));
        cell.appendChild(button("빼기", "", function () { removeFromProposal(a.control); }, { id: "act-x-" + a.control, "aria-label": cname(a.control) + " 변경안에서 빼기" }));
      } else {
        cell.appendChild(button("변경안에 넣기", "", function () { addToProposal(a.control); }, { id: "act-add-" + a.control, "aria-label": cname(a.control) + " AI 까지를 변경안에 넣기" }));
      }
      tb.appendChild(el("tr", { cls: (zero ? "zero" : "") + (inProp ? " inprop" : "") }, [el("td", { cls: "num", text: String(k + 1) }), act,
        el("td", { cls: "stg", text: STAGE_KO[c.stage] || "" }), eff, sc, rg, cell]));
    });
    t.appendChild(tb);
    $("acts-csv").disabled = !acts.length;
  }
  function today() {
    var d = new Date(), p = function (n) { return (n < 10 ? "0" : "") + n; };
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
  }
  function csvRows() {
    var acts = actions(), R = ref(), prof = profileById[R.profile] || profileById[profileOf(R.env)];
    var head = ["순위", "통제", "조치 (AI까지)", "단계", "지금", "목표", "사건 막힘 하한 증가", "사건 막힘 상한 증가", "결과가 바뀌는 원형"];
    JUR3.forEach(function (j) { var n = (D.jurisdictions || {})[j] || j; head.push(n + " 사람·계정 층", n + " AI 층", n + " 근거 문서"); });
    head.push("변경안에 포함", "자가 진단 사람·계정", "자가 진단 AI", "진단 메모", "담당", "기한", "상태", "메모", "기준 설정", "에이전트 환경", "설정 링크", "만든 날", "출처");
    var rows = [head];
    acts.forEach(function (a, k) {
      var c = ctlById[a.control] || {};
      var row = [k + 1, cname(a.control), (c.help || {}).agent || "", STAGE_KO[c.stage] || "", LEVEL_KO[a.from], LEVEL_KO[2], a.inc_lo, a.inc_hi,
        a.scenarios.map(function (x) { return short(scnById[x.id]) + " " + RESULT_KO[x.from] + "→" + RESULT_KO[x.to]; }).join(" / ")];
      JUR3.forEach(function (j) {
        var g = regOf(a.control, j).agent || { score: 0 }, an = regOf(a.control, j).analog || { score: 0 }, top = g.doc ? g : an;
        row.push(SCORE_KO[an.score], SCORE_KO[g.score], top.title ? top.title + (top.url ? " " + top.url : "") : "");
      });
      var dg = state.diag[a.control] || {};
      row.push(state.base && state.levels[a.control] >= 2 ? "예" : "", dg.analog || dg.agent ? DIAG_KO[dg.analog || ""] : "", dg.analog || dg.agent ? DIAG_KO[dg.agent || ""] : "",
        dg.note || "", "", "", "", "",
        (presetById[presetOf(R.levels)] || { label: "직접 설정" }).label, (prof ? prof.label + ": " : "") + envSummary(R.env),
        location.href, today(), "PivoxPolicy 모의 테스트. 자체 계산이며 법률 자문이 아님");
      rows.push(row);
    });
    return rows;
  }
  function exportCSV() {
    writeHash();
    var rows = csvRows();
    var url = URL.createObjectURL(new Blob([E.toCSV(rows)], { type: "text/csv;charset=utf-8" }));
    var a = el("a", { href: url, download: "pivoxpolicy-actions_" + today() + ".csv" });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
    var msg = $("csv-msg");
    msg.textContent = "내려받았다. 조치 " + (rows.length - 1) + "개, 담당·기한·상태는 비어 있다";
    setTimeout(function () { msg.textContent = ""; }, 4000);
  }

  // ── ④ OWASP 커버리지 ──
  function renderAsi() {
    var cov = E.asiCoverage(D.scenarios, state.env, state.levels, ASI), t = clear($("asi"));
    var bc = state.base ? E.asiCoverage(D.scenarios, state.base.env, state.base.levels, ASI) : null, n = asiTally(cov);
    $("asi-sum").textContent = "막음 " + n.full + " · 부분 " + n.partial + " · 공백 " + n.gap + " · 해당 없음 " + n.na + " · 원형 없음 " + n.none;
    var hr = el("tr", null, [el("th", { text: "항목" })]);
    if (bc) hr.appendChild(el("th", { text: "기준" }));
    hr.appendChild(el("th", { text: bc ? "변경안" : "이 설정에서" }));
    hr.appendChild(el("th", { text: "근거 원형과 결과 (누르면 위 표에서 고른다)" }));
    t.appendChild(el("thead", null, [hr]));
    var tb = el("tbody");
    cov.forEach(function (c, i) {
      var a = asiById[c.id] || {}, moved = !!bc && bc[i].status !== c.status;
      var tr = el("tr", { cls: moved ? "chg" : "" }, [el("td", { cls: "it" }, [el("b", { text: c.id + " " + (a.ko || "") }), el("span", { cls: "en", text: a.name || "" })])]);
      if (bc) tr.appendChild(el("td", null, [el("span", { cls: "asi-st " + bc[i].status, text: ASI_KO[bc[i].status] })]));
      tr.appendChild(el("td", null, [el("span", { cls: "asi-st " + c.status, text: ASI_KO[c.status] })]));
      var sc = el("td", { cls: "sc" });
      if (!c.scenarios.length) sc.appendChild(el("span", { cls: "dim", text: "이 항목을 근거로 둔 원형이 없어 재지 않는다" }));
      c.scenarios.forEach(function (x) {
        var sb = el("button", { type: "button", cls: "lnk", text: short(scnById[x.id]) });
        sb.addEventListener("click", function () {
          state.scenario = x.id; pendingFocus = "ov-" + x.id; update();
          var o = $("ov-" + x.id);
          if (o && o.scrollIntoView) o.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
        });
        sc.appendChild(el("span", null, [sb, " ", el("b", { cls: "r " + x.outcome, text: RESULT_KO[x.outcome] })]));
      });
      tr.appendChild(sc);
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    var note = clear($("asi-note"));
    note.appendChild(document.createTextNode("자체 계산이며 OWASP의 평가나 인증이 아니다. 그 항목을 근거로 둔 원형이 이 환경에서 모두 막히면 막음, 모두 피해가 나면 공백, " +
      "그 사이면 부분이다. 공격면이 없으면 해당 없음, 근거 원형이 없으면 원형 없음으로 둔다. 항목 제목은 "));
    note.appendChild(link((D.owasp_asi || {}).source, "OWASP Top 10 for Agentic Applications (2025-12-09 발표)"));
    note.appendChild(document.createTextNode(" 그대로."));
  }

  // ── ⑤ 가정해 보기: 새 문서가 통제를 요구한다면 → 관할 프리셋 다시 계산 (가정일 뿐, 실제 반영은 코딩 후) ──
  var WI = { j: "KR", strength: 2, layer: "agent", ctl: {}, cand: "" };
  function wiLevels(p, thr) {
    var lv = Object.assign({}, p.levels);
    if (WI.strength < thr) return lv;               // 자율 문서는 '강제 규제만' 프리셋에 들지 않는다
    CIDS.forEach(function (c) { if (WI.ctl[c]) lv[c] = WI.layer === "agent" ? 2 : Math.max(lv[c], 1); });
    return lv;
  }
  function renderWhatIfForm() {
    var box = clear($("whatif")), f = el("div", { cls: "wi-form" });
    var js = el("select", { id: "wi-j", "aria-label": "관할" });
    JUR.forEach(function (j) { js.appendChild(el("option", { value: j, text: (D.jurisdictions || {})[j] || j })); });
    js.value = WI.j;
    js.addEventListener("change", function () { WI.j = js.value; renderWhatIf(); });
    var st = el("div", { cls: "seg", role: "radiogroup", "aria-label": "문서의 힘" });
    seg(st, "wi-s", [[2, "구속력 (법령·감독규정)"], [1, "자율 (가이드라인)"]], WI.strength, function (v) { WI.strength = Number(v); renderWhatIf(); });
    var ly = el("div", { cls: "seg", role: "radiogroup", "aria-label": "어느 층" });
    seg(ly, "wi-l", [["agent", "AI 에이전트에 적용"], ["analog", "사람·계정에만"]], WI.layer, function (v) { WI.layer = v; renderWhatIf(); });
    var cs = el("div", { cls: "wi-ctl", role: "group", "aria-label": "요구하는 통제" });
    D.controls.forEach(function (c) {
      var id = "wi-c-" + c.id, inp = el("input", { type: "checkbox", id: id });
      inp.checked = !!WI.ctl[c.id];
      inp.addEventListener("change", function () { WI.ctl[c.id] = inp.checked; renderWhatIf(); });
      cs.appendChild(el("label", { "for": id, cls: "chk" }, [inp, " " + c.num + ". " + c.name]));
    });
    var P = (D.pending || {}).top || [], cand = el("select", { id: "wi-cand", "aria-label": "근거로 삼을 반영 대기 후보" });
    cand.appendChild(el("option", { value: "", text: "이름 없는 새 문서" }));
    P.forEach(function (x, i) { cand.appendChild(el("option", { value: String(i), text: x.jurisdiction + " · " + x.title.slice(0, 70) })); });
    cand.addEventListener("change", function () {
      WI.cand = cand.value;
      var x = P[Number(cand.value)];
      if (x && JUR.indexOf(x.jurisdiction) >= 0) { WI.j = x.jurisdiction; js.value = x.jurisdiction; }
      renderWhatIf();
    });
    f.appendChild(el("div", { cls: "wi-row" }, [el("span", { cls: "sub", text: "어떤 문서" }), cand]));
    f.appendChild(el("div", { cls: "wi-row" }, [el("span", { cls: "sub", text: "관할" }), js]));
    f.appendChild(el("div", { cls: "wi-row" }, [el("span", { cls: "sub", text: "문서의 힘" }), st]));
    f.appendChild(el("div", { cls: "wi-row" }, [el("span", { cls: "sub", text: "적용 대상" }), ly]));
    f.appendChild(el("div", { cls: "wi-row" }, [el("span", { cls: "sub", text: "요구하는 통제" }), cs]));
    box.appendChild(f);
    box.appendChild(el("div", { cls: "wi-out", id: "wi-out", "aria-live": "polite" }));
  }
  function renderWhatIf() {
    var out = clear($("wi-out")), picked = CIDS.filter(function (c) { return WI.ctl[c]; });
    if (!picked.length) { out.appendChild(el("p", { cls: "fine", text: "요구하는 통제를 하나 이상 고르면, 그 관할의 프리셋을 다시 계산해 지금 에이전트 환경에서 무엇이 바뀌는지 보인다." })); return; }
    var x = ((D.pending || {}).top || [])[Number(WI.cand)], who = WI.cand !== "" && x ? "'" + x.title + "' 문서" : "새 문서";
    out.appendChild(el("p", { cls: "wi-say" }, [el("b", { text: "가정." }), " " + who + "가 이렇게 요구한다고 친다. 관할 " + ((D.jurisdictions || {})[WI.j] || WI.j) +
      " · 통제 " + picked.map(cname).join(", ") + " · " + (WI.layer === "agent" ? "AI 에이전트에 적용" : "사람·계정에만") + " · " + (WI.strength === 2 ? "구속력" : "자율") +
      ". 실제 반영은 문서 등록 · 두 팀 코딩 · 조정 뒤다."]));
    var t = el("table", { cls: "wi-t" });
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "프리셋" }), el("th", { text: "사건 막힘" }), el("th", { text: "결과가 바뀌는 원형 (지금 환경)" }),
      el("th", { text: "OWASP 막음" }), el("th", { "aria-label": "비교" })])]));
    var tb = el("tbody"), any = false;
    [2, 1].forEach(function (thr) {
      var p = presetById[WI.j + "-" + thr];
      if (!p) return;
      var after = wiLevels(p, thr), same = CIDS.every(function (c) { return after[c] === p.levels[c]; });
      var r0 = E.replay(failures, p.levels, stageOf, state.statedOnly), r1 = E.replay(failures, after, stageOf, state.statedOnly);
      var s0 = scnResults(p.levels, state.env), s1 = scnResults(after, state.env), moved = [];
      D.scenarios.forEach(function (s) { if (s0[s.id].outcome !== s1[s.id].outcome) moved.push(short(s) + " " + SHORT_OUT[s0[s.id].outcome] + "→" + SHORT_OUT[s1[s.id].outcome]); });
      var a0 = asiTally(E.asiCoverage(D.scenarios, state.env, p.levels, ASI)).full, a1 = asiTally(E.asiCoverage(D.scenarios, state.env, after, ASI)).full;
      var cmp = same ? el("span", { cls: "dim", text: "이미 그 수준" }) : button("변경안으로 비교", "sm", function () {
        state.base = { levels: Object.assign({}, p.levels), env: Object.assign({}, state.env), profile: state.profile };
        state.levels = after; state.preset = matchPreset(); state.kase = null; update();
        var b = $("posture"); if (b.scrollIntoView) b.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      });
      if (!same) any = true;
      tb.appendChild(el("tr", { cls: same ? "zero" : "" }, [el("td", { text: p.label }),
        el("td", null, [rangeText(r0) + " → ", el("b", { text: rangeText(r1) })]),
        el("td", { text: moved.length ? moved.join(" · ") : "—" }),
        el("td", null, [a0 + " → ", el("b", { text: String(a1) })]), el("td", null, [cmp])]));
    });
    t.appendChild(tb);
    out.appendChild(el("div", { cls: "tblwrap" }, [t]));
    if (!any) out.appendChild(el("p", { cls: "fine", text: "바뀌는 것이 없다. 그 관할 프리셋이 이미 그 수준이다(자율 문서는 '강제 규제만' 프리셋을 바꾸지 않는다)." }));
  }

  // ── ⑥ 자가 진단 + 근거 메모 — 이 브라우저 안에만. JSON으로 내보내고 불러온다 ──
  var diagDirty = false;
  function hasDiag() { return CIDS.some(function (c) { var d = state.diag[c]; return d && (d.analog || d.agent || d.note); }); }
  function renderDiagTable() {
    var t = clear($("diag-t"));
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "통제" }), el("th", { text: "사람·계정 층" }), el("th", { text: "AI 층" }),
      el("th", { text: "근거 메모 (300자)" }), el("th", { text: "지금 설정" })])]));
    var tb = el("tbody");
    D.controls.forEach(function (c) {
      var d = state.diag[c.id] || (state.diag[c.id] = { analog: "", agent: "", note: "" });
      function sel(layer) {
        var x = el("select", { id: "diag-" + layer + "-" + c.id, "aria-label": c.name + " " + LAYER_KO[layer] + " 층 상태" });
        DIAG_ST.forEach(function (o) { x.appendChild(el("option", { value: o[0], text: o[1] })); });
        x.value = d[layer] || "";
        x.addEventListener("change", function () { d[layer] = x.value; diagDirty = true; renderDiagSum(); });
        return x;
      }
      var note = el("input", { type: "text", id: "diag-n-" + c.id, maxlength: "300", "aria-label": c.name + " 근거 메모",
        placeholder: ((c.help || {}).agent || "").slice(0, 28) + "…" });
      note.value = d.note || "";
      note.addEventListener("input", function () { d.note = note.value.slice(0, 300); diagDirty = true; });
      tb.appendChild(el("tr", null, [el("th", { scope: "row", text: c.num + ". " + c.name }), el("td", null, [sel("analog")]), el("td", null, [sel("agent")]),
        el("td", { cls: "memo" }, [note]), el("td", { cls: "lv", id: "diag-lv-" + c.id })]));
    });
    t.appendChild(tb);
    renderDiagSum();
  }
  function renderDiagSum() {
    var n = {}; DIAG_ST.forEach(function (x) { n[x[0]] = 0; });
    CIDS.forEach(function (c) { n[(state.diag[c] || {}).agent || ""] += 1; });
    $("diag-sum").textContent = "AI 층: 구현 " + n.done + " · 부분 " + n.partial + " · 계획 " + n.plan + " · 없음 " + n.none + " · 모름 " + n[""];
    CIDS.forEach(function (c) { var x = $("diag-lv-" + c); if (x) x.textContent = LEVEL_KO[state.levels[c]]; });
  }
  function diagLevels() {
    var partial = $("diag-partial").checked, ok = function (v) { return v === "done" || (partial && v === "partial"); }, lv = {};
    CIDS.forEach(function (c) { var d = state.diag[c] || {}; lv[c] = ok(d.agent) ? 2 : ok(d.analog) ? 1 : 0; });
    return lv;
  }
  function diagMsg(t) { var m = $("diag-msg"); m.textContent = t; setTimeout(function () { if (m.textContent === t) m.textContent = ""; }, 5000); }
  function download(name, type, text) {
    var url = URL.createObjectURL(new Blob([text], { type: type }));
    var a = el("a", { href: url, download: name });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }
  function exportDiag() {
    var ctl = {};
    D.controls.forEach(function (c) { var d = state.diag[c.id] || {}; ctl[c.id] = { name: c.name, analog: d.analog || "", agent: d.agent || "", note: d.note || "" }; });
    download("pivoxpolicy-self-assessment_" + today() + ".json", "application/json", JSON.stringify({
      format: "pivoxpolicy-self-assessment", version: 1, exported_at: new Date().toISOString(),
      statuses: DIAG_KO, include_partial: $("diag-partial").checked, agent: { profile: state.profile, env: state.env }, controls: ctl
    }, null, 2) + "\n");
    diagDirty = false;
    diagMsg("내려받았다. 진단은 이 파일에만 남는다");
  }
  function importDiag(file) {
    if (!file) return;
    if (file.size > 200000) { diagMsg("파일이 너무 크다(200KB까지)"); return; }
    var rd = new FileReader();
    rd.onload = function () {
      var j;
      try { j = JSON.parse(String(rd.result)); } catch (e) { diagMsg("JSON을 읽지 못했다"); return; }
      if (!j || j.format !== "pivoxpolicy-self-assessment" || typeof j.controls !== "object") { diagMsg("PivoxPolicy 자가 진단 파일이 아니다"); return; }
      var n = 0;
      CIDS.forEach(function (c) {
        var x = j.controls[c]; if (!x || typeof x !== "object") return;
        var okS = function (v) { return typeof v === "string" && DIAG_KO.hasOwnProperty(v) ? v : ""; };
        state.diag[c] = { analog: okS(x.analog), agent: okS(x.agent), note: typeof x.note === "string" ? x.note.slice(0, 300) : "" };
        n += 1;
      });
      if (j.include_partial === true || j.include_partial === false) $("diag-partial").checked = j.include_partial;
      diagDirty = false; renderDiagTable();
      diagMsg("통제 " + n + "개를 불러왔다. '진단을 설정에 반영'을 누르면 왼쪽 설정이 바뀐다");
    };
    rd.onerror = function () { diagMsg("파일을 읽지 못했다"); };
    rd.readAsText(file);
  }

  // ── 정책 초안 (.md + YAML 뼈대) — 검토용, 자체 형식 ──
  function mdText(t) { return String(t || "").replace(/[\[\]]/g, "").replace(/\s+/g, " ").trim(); }
  function policyDraft() {
    var prof = profileById[state.profile], acts = E.improvementActions(D.scenarios, state.env, failures, state.levels, stageOf, state.statedOnly), rank = {};
    acts.forEach(function (a, k) { rank[a.control] = { n: k + 1, a: a }; });
    var q = function (v) { return JSON.stringify(String(v === undefined || v === null ? "" : v)); };
    var L = ["# AI 에이전트 내부통제 정책 초안: " + (prof ? prof.label : "직접 설정한 에이전트"), "",
      "> **검토용 초안이다.** PivoxPolicy 모의 테스트에서 만든 뼈대이고, 형식은 이 도구 자체 형식이다(특정 집행 도구의 스키마가 아니다).",
      "> 법률 자문이 아니며 그대로 운영에 넣지 않는다. 규제 근거는 관할마다 그 통제를 가장 세게 다룬 문서 하나다.", "",
      "- 만든 날: " + today(),
      "- 에이전트: " + (prof ? prof.label + ", " : "") + envSummary(state.env),
      "- 통제 수준: " + ((presetById[state.preset] || {}).label || "직접 설정") + (state.base ? " (변경안. 기준은 " + cfgLabel(state.base) + ")" : ""),
      "- 설정 링크: " + location.href, "", "## 통제별 요구", ""];
    var Y = ["pivoxpolicy_policy_draft: 1", "generated: " + q(today()), "note: " + q("검토용 초안. 이 도구의 자체 형식이며 특정 도구의 스키마도, 법률 자문도 아님"),
      "agent:", "  type: " + q(prof ? prof.label : "custom"), "  tools: " + q(state.env.tools),
      "  reads_untrusted_input: " + !!state.env.untrusted_input, "  imports_external_components: " + !!state.env.open_components,
      "  long_term_memory: " + !!state.env.memory, "  multi_agent: " + !!state.env.multi_agent, "controls:"];
    D.controls.forEach(function (c) {
      var lv = Number(state.levels[c.id] || 0), h = c.help || {}, d = state.diag[c.id] || {}, rk = rank[c.id];
      L.push("### " + c.num + ". " + c.name + " (" + LEVEL_KO[lv] + ")", "");
      if (lv >= 1) L.push("- 사람·계정: " + mdText(h.analog));
      if (lv >= 2) L.push("- AI 에이전트: " + mdText(h.agent));
      if (lv === 0) L.push("- 이 설정에서는 적용하지 않는다.");
      if (rk) L.push("- 다음 단계(AI까지): " + mdText(h.agent) + " (개선 조치 " + rk.n + "순위, 사건 막힘 하한 " + sign(rk.a.inc_lo) + " · 상한 " + sign(rk.a.inc_hi) + ")");
      if (d.analog || d.agent || d.note) L.push("- 자가 진단: 사람·계정 " + DIAG_KO[d.analog || ""] + " · AI " + DIAG_KO[d.agent || ""] + (d.note ? ". 메모: " + mdText(d.note) : ""));
      L.push("- 규제 근거:");
      Y.push("  - id: " + q(c.id), "    name: " + q(c.name), "    apply_to: " + q(["none", "human", "human_and_ai"][lv]) + "   # none | human | human_and_ai",
        "    requirement_human: " + q(lv >= 1 ? h.analog : ""), "    requirement_ai: " + q(lv >= 2 ? h.agent : ""),
        "    owner: \"\"", "    review_by: \"\"");
      if (d.analog || d.agent || d.note) Y.push("    self_assessment: {human: " + q(DIAG_KO[d.analog || ""]) + ", ai: " + q(DIAG_KO[d.agent || ""]) + ", note: " + q(d.note || "") + "}");
      Y.push("    basis:");
      JUR.forEach(function (j) {
        var R = regOf(c.id, j), jn = (D.jurisdictions || {})[j] || j, parts = [];
        ["analog", "agent"].forEach(function (layer) {
          var x = R[layer] || { score: 0 };
          parts.push(LAYER_KO[layer] + " " + SCORE_KO[x.score] + (x.doc ? " [" + mdText(x.title) + "](" + x.url + ")" : ""));
          if (x.doc) Y.push("      - {jurisdiction: " + q(j) + ", layer: " + q(layer === "agent" ? "ai" : "human") + ", strength: " + q(SCORE_KO[x.score]) +
            ", doc: " + q(x.title) + ", url: " + q(x.url) + "}");
        });
        L.push("  - " + jn + ": " + parts.join(" / "));
      });
      L.push("- 담당: ", "- 검토 기한: ", "");
    });
    L.push("## 기계가 읽는 뼈대 (YAML, 자체 형식)", "", "```yaml");
    return L.concat(Y, ["```", ""]).join("\n");
  }

  // ── 데모 케이스 ──
  function renderCasePicker() {
    var s = clear($("case"));
    s.appendChild(el("option", { value: "", text: "케이스 없이 직접 설정" }));
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
    var head = el("div", { cls: "k" }, ["케이스 " + idx + " / " + CASES.length + " · " + c.org + (state.base && !dirty ? " · 기준 = 이 케이스" : "")]);
    if (dirty) {
      head.appendChild(document.createTextNode(" · 설정을 바꿔 케이스에서 벗어났다"));
      head.appendChild(button("케이스 설정으로 되돌리기", "again", function () { applyCase(c.id); update(); }));
    }
    b.appendChild(head);
    b.appendChild(el("div", { cls: "t", text: c.title }));
    b.appendChild(el("p", { cls: "s", text: c.story }));
    b.appendChild(el("dl", { cls: "grid" }, [
      el("dt", { text: "공격 원형" }), el("dd", { text: scnById[c.scenario].title }),
      el("dt", { text: "이 케이스의 결과" }), el("dd", null, [el("span", { cls: "r " + r.outcome, text: RESULT_KO[r.outcome] + (r.outcome === "blocked" ? " (" + r.stage + "단계)" : "") }), ", " + r.impact]),
      el("dt", { text: "볼 것" }), el("dd", { text: c.lesson })
    ]));
    if (r.outcome !== c.expect) {
      b.appendChild(el("p", { cls: "warn", text: "규제 데이터가 바뀌어 결과가 케이스 작성 때(" + RESULT_KO[c.expect] + ")와 다르다. 위 설명은 업데이트 전 기준이다." }));
    }
  }
  function stepCase(d) {
    if (!CASES.length) return;
    var i = CASES.indexOf(caseById[state.kase]);
    i = i < 0 ? (d > 0 ? 0 : CASES.length - 1) : (i + d + CASES.length) % CASES.length;
    applyCase(CASES[i].id); update();
  }

  // ── ⑤ 규제가 바뀌면 ──
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
          if (a && (a[0] !== z[0] || a[1] !== z[1])) ul.appendChild(el("li", null, [(labels[pid] || pid) + ": 막혔을 사건 " + a[0] + "~" + a[1] + " → ", el("b", { text: z[0] + "~" + z[1] })]));
          var sa = (prev.scenarios || {})[pid] || {}, sz = (h.scenarios || {})[pid] || {};
          Object.keys(sz).forEach(function (sid) {
            if (sa[sid] && sa[sid] !== sz[sid] && scnById[sid]) ul.appendChild(el("li", null, [(labels[pid] || pid) + " · " + short(scnById[sid]) + ": " + RESULT_KO[sa[sid]] + " → ", el("b", { text: RESULT_KO[sz[sid]] })]));
          });
        });
        if (!ul.childNodes.length) ul.appendChild(el("li", { text: "결과가 바뀐 프리셋 없음" }));
      } else ul.appendChild(el("li", { text: "기준점. 문서 " + h.docs.length + "건" }));
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
    var fid = pendingFocus || (document.activeElement && document.activeElement.id);
    pendingFocus = null;
    renderCompareCtl(); renderPresetHint(); renderControls(); renderEnv(); renderCaseBanner(); renderCompareBar(); renderBand();
    renderOverview(); renderFlow(false); renderWalk(false); renderHeat(); renderReplay(); renderActions(); renderAsi(); renderWhatIf(); renderDiagSum();
    if (state.drawer) renderDrawer();
    writeHash();
    var f = fid && $(fid);
    if (f && document.activeElement !== f && f.focus) f.focus({ preventScroll: true });
  }

  $("case").addEventListener("change", function (e) { applyCase(e.target.value); update(); });
  $("prev").addEventListener("click", function () { stepCase(-1); });
  $("next-case").addEventListener("click", function () { stepCase(1); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && state.drawer) { e.preventDefault(); closeDrawer(); return; }
    var t = e.target && e.target.tagName;
    if (t === "INPUT" || t === "SELECT" || t === "TEXTAREA" || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.target && e.target.closest && e.target.closest("#heat, #drawer")) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); stepCase(1); }
    else if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); stepCase(-1); }
  });
  $("drawer-x").addEventListener("click", closeDrawer);
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
    renderFlow(true); renderWalk(true);
    var f = $("h-flow");
    if (f.scrollIntoView) f.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  });
  $("acts-csv").addEventListener("click", exportCSV);
  $("policy-md").addEventListener("click", function () {
    writeHash();
    download("pivoxpolicy-policy-draft_" + today() + ".md", "text/markdown;charset=utf-8", policyDraft());
    var m = $("csv-msg"); m.textContent = "정책 초안을 내려받았다. 검토용 뼈대다"; setTimeout(function () { m.textContent = ""; }, 4000);
  });
  $("diag-apply").addEventListener("click", function () {
    var lv = diagLevels(), n = [0, 0, 0];
    CIDS.forEach(function (c) { n[lv[c]] += 1; });
    state.levels = lv; state.preset = matchPreset(); update();
    diagMsg("반영했다. AI까지 " + n[2] + " · 사람·계정만 " + n[1] + " · 없음 " + n[0] + (state.base ? " (변경안에)" : ""));
  });
  $("diag-export").addEventListener("click", exportDiag);
  $("diag-file").addEventListener("change", function (e) { importDiag(e.target.files && e.target.files[0]); e.target.value = ""; });
  $("diag-clear").addEventListener("click", function () {
    if (hasDiag() && !window.confirm("자가 진단을 모두 지운다. 내보내지 않은 내용은 사라진다.")) return;
    state.diag = {}; diagDirty = false; renderDiagTable(); diagMsg("비웠다");
  });
  window.addEventListener("beforeunload", function (e) { if (diagDirty && hasDiag()) { e.preventDefault(); e.returnValue = ""; } });
  var rsz = null;
  window.addEventListener("resize", function () { clearTimeout(rsz); rsz = setTimeout(function () { renderReplay(); }, 150); });
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
  renderPresetSelect(); renderCasePicker(); renderUpdates(); renderWhatIfForm(); renderDiagTable(); update();
})();
