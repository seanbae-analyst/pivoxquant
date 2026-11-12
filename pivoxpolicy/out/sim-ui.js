/* sim-ui.js — 모의 테스트 화면. 계산은 sim-engine.js(PivoxSimEngine), 데이터는 sim-data.js(PIVOX_SIM).
   글은 전부 textContent 로 넣는다(innerHTML 에 데이터를 넣지 않는다). 상태는 페이지 안에만 — 저장하지 않는다. */
(function () {
  "use strict";
  var D = window.PIVOX_SIM, E = window.PivoxSimEngine;
  if (!D || !E) return;

  var LAYER_KO = { analog: "사람·계정", agent: "AI 적용" };
  var LEVEL_KO = ["없음", "사람·계정만", "AI 까지"];
  var STAGE_KO = { before: "배치 전", in_use: "사용 중", after: "사후" };
  var EFFECT_ON = { prevent: "막음", limit: "닿는 범위를 줄임", detect: "알아챔", contain: "멈추고 회수" };
  var TOOLS = [["read", "조회만"], ["write", "쓰기·실행"], ["pay", "송금·결제"]];
  var REQ_KO = { untrusted_input: "외부 입력을 읽지 않는다", open_components: "외부 구성요소를 들이지 않는다" };
  var OUT_KO = { blocked: "막혔을 사건", blocked_maybe: "막혔을 수도", reduced: "피해 축소", unchanged: "그대로", unknown: "판단 근거 없음" };

  var ctlById = {}, stageOf = {}, failures = {};
  D.controls.forEach(function (c) { ctlById[c.id] = c; stageOf[c.id] = c.stage; });
  D.incidents.forEach(function (i) { failures[i.id] = i.fails; });
  var presetById = {};
  D.presets.forEach(function (p) { presetById[p.id] = p; });

  var state = {
    preset: "KR-2",
    levels: Object.assign({}, (presetById["KR-2"] || D.presets[0]).levels),
    profile: "trading",
    env: { tools: "pay", untrusted_input: true, open_components: false },
    statedOnly: false,
    scenario: D.scenarios[0].id,
    ran: false
  };
  (function applyProfile() {
    var p = D.agent_profiles.filter(function (x) { return x.id === state.profile; })[0];
    if (p) state.env = { tools: p.tools, untrusted_input: !!p.untrusted_input, open_components: !!p.open_components };
  })();

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ── DOM 도우미 ──
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k];
      else if (k === "cls") n.className = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (k) { if (k) n.appendChild(typeof k === "string" ? document.createTextNode(k) : k); });
    return n;
  }
  function $(id) { return document.getElementById(id); }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  var uid = 0;
  function seg(container, name, options, current, onChange) {
    clear(container);
    options.forEach(function (o) {
      var id = "r" + (++uid);
      var inp = el("input", { type: "radio", name: name, id: id, value: String(o[0]) });
      if (String(o[0]) === String(current)) inp.checked = true;
      inp.addEventListener("change", function () { onChange(o[0]); });
      container.appendChild(el("label", { "for": id }, [inp, el("span", { text: o[1] })]));
    });
  }

  // ── 왼쪽: 설정 ──
  function renderPreset() {
    var s = clear($("preset"));
    s.appendChild(el("option", { value: "custom", text: "직접 설정" }));
    D.presets.forEach(function (p) { s.appendChild(el("option", { value: p.id, text: p.label })); });
    s.value = state.preset;
  }
  function renderControls() {
    var box = clear($("controls"));
    D.controls.forEach(function (c) {
      var g = el("div", { cls: "seg", role: "radiogroup", "aria-label": c.name });
      seg(g, "lv-" + c.id, [[0, "없음"], [1, "사람·계정"], [2, "AI 까지"]], state.levels[c.id], function (v) {
        state.levels[c.id] = Number(v);
        state.preset = matchPreset();
        $("preset").value = state.preset;
        update();
      });
      box.appendChild(el("div", { cls: "ctl" }, [
        el("div", { cls: "nm" }, [c.num + ". " + c.name, el("small", { text: STAGE_KO[c.stage] || "" })]), g
      ]));
    });
  }
  function matchPreset() {
    for (var i = 0; i < D.presets.length; i++) {
      var p = D.presets[i], same = true;
      for (var k in p.levels) if (p.levels[k] !== state.levels[k]) { same = false; break; }
      if (same) return p.id;
    }
    return "custom";
  }
  function renderEnv() {
    var s = clear($("profile"));
    D.agent_profiles.forEach(function (p) { s.appendChild(el("option", { value: p.id, text: p.label })); });
    s.appendChild(el("option", { value: "custom", text: "직접 설정" }));
    s.value = state.profile;
    seg($("tools"), "tools", TOOLS, state.env.tools, function (v) { state.env.tools = v; state.profile = "custom"; $("profile").value = "custom"; update(); });
    seg($("untrusted"), "untrusted", [[true, "읽는다"], [false, "안 읽는다"]], state.env.untrusted_input, function (v) {
      state.env.untrusted_input = v === true || v === "true"; state.profile = "custom"; $("profile").value = "custom"; update();
    });
    seg($("components"), "components", [[true, "들인다"], [false, "고정된 것만"]], state.env.open_components, function (v) {
      state.env.open_components = v === true || v === "true"; state.profile = "custom"; $("profile").value = "custom"; update();
    });
  }

  // ── ① 공격 원형 ──
  function renderScenarioList() {
    var box = clear($("scenarios"));
    D.scenarios.forEach(function (s) {
      var id = "s-" + s.id;
      var inp = el("input", { type: "radio", name: "scn", id: id, value: s.id });
      if (s.id === state.scenario) inp.checked = true;
      inp.addEventListener("change", function () { state.scenario = s.id; state.ran = false; update(); });
      var miss = (s.requires || []).filter(function (r) { return !state.env[r]; });
      var row = el("label", { cls: "scn" + (miss.length ? " na" : ""), "for": id }, [
        inp,
        el("div", null, [
          el("div", { cls: "t", text: s.title }),
          el("div", { cls: "s", text: s.summary }),
          el("div", { cls: "k", text: "근거 사건 " + s.incidents.length + "건" + (miss.length ? " · 지금 환경: " + miss.map(function (r) { return REQ_KO[r]; }).join(", ") : "") })
        ])
      ]);
      box.appendChild(row);
    });
  }
  function scenarioById(id) { return D.scenarios.filter(function (s) { return s.id === id; })[0]; }
  function cname(id) { return ctlById[id] ? ctlById[id].name : id; }

  function renderStages(animate) {
    var s = scenarioById(state.scenario), r = E.runScenario(s, state.env, state.levels);
    var ol = clear($("stages")), out = clear($("outcome"));
    if (!state.ran) {
      $("run").textContent = "실행";
      return;
    }
    $("run").textContent = "다시 실행";
    var items = [];
    if (r.outcome === "no_surface") {
      ol.appendChild(el("li", { cls: "stage blocked" }, [el("span", { cls: "no", text: "–" }), el("div", null, [
        el("div", { cls: "t", text: "이 공격은 시작되지 않는다" }),
        el("div", { cls: "d", text: "지금 환경에서 에이전트가 " + r.missing.map(function (x) { return REQ_KO[x]; }).join(", ") + "." })
      ])]));
    } else {
      s.stages.forEach(function (st, idx) {
        var k = idx + 1, step = r.steps[idx];
        var cls = "stage";
        if (!step) cls += " after";
        else if (step.blocked_by) cls += " blocked";
        else cls += " passed";
        var ck = el("ul", { cls: "ck" });
        (st.checks || []).forEach(function (c, j) {
          var on = step ? step.checks[j].on : E.covers(Number(state.levels[c.control] || 0), c.layer);
          var lv = Number(state.levels[c.control] || 0);
          var label = cname(c.control) + " · " + LAYER_KO[c.layer];
          var verdict = on ? EFFECT_ON[c.effect] + (c.effect === "contain" && r.contained === "late" ? "(알아챌 기록이 없어 늦게)" : "")
                           : "꺼짐 — 지금 " + LEVEL_KO[lv];
          ck.appendChild(el("li", { cls: on ? "on" : "" }, [el("b", { text: label }), " — " + verdict, el("span", { cls: "why", text: c.why })]));
        });
        if (!(st.checks || []).length) ck.appendChild(el("li", { text: "이 단계에서 끼어드는 통제 없음" }));
        if (!step) ck.insertBefore(el("li", { text: "이 단계까지 오지 않았다 — 앞에서 막혔다" }), ck.firstChild);
        var li = el("li", { cls: cls + (animate && !reduceMotion ? " pending" : "") }, [
          el("span", { cls: "no", text: String(k) }),
          el("div", null, [el("div", { cls: "t", text: st.title }), el("div", { cls: "d", text: st.desc }), ck])
        ]);
        ol.appendChild(li); items.push(li);
      });
    }
    var v, p;
    if (r.outcome === "blocked") {
      v = "막힘 — " + r.stage + "단계에서 " + cname(r.steps[r.stage - 1].blocked_by);
      p = "공격이 끝까지 가지 못했다. 막지 못했다면: " + r.impact + ".";
    } else if (r.outcome === "reduced") {
      var why = [];
      if (r.limited_by.length) why.push(r.limited_by.map(cname).join(" · ") + "(이)가 닿는 범위를 줄였다");
      if (r.contained === "early") why.push((r.detected_at ? r.detected_at + "단계에서 알아채고 " : "") + "멈췄다");
      v = "피해 축소 — " + r.impact;
      p = "공격은 끝까지 갔지만 " + why.join(", ") + ".";
    } else if (r.outcome === "damage") {
      v = "피해 발생 — " + r.impact;
      p = r.contained === "late" ? "멈출 수단은 있었지만 알아챌 기록이 없어 늦게 멈췄다." : "끼어든 통제가 없었다.";
    } else {
      v = "공격면 없음";
      p = "이 원형은 지금 환경에서 성립하지 않는다 — 다른 원형을 골라 보라.";
    }
    var show = function () { out.appendChild(el("div", { cls: "v " + r.outcome, text: v })); out.appendChild(el("p", { text: p })); };
    if (animate && !reduceMotion) {
      items.forEach(function (li, i) { setTimeout(function () { li.classList.remove("pending"); }, 120 + i * 420); });
      setTimeout(show, 120 + items.length * 420);
    } else show();
  }
  function renderScenarioCases() {
    var s = scenarioById(state.scenario), ul = clear($("scn-list"));
    var byId = {}; D.incidents.forEach(function (i) { byId[i.id] = i; });
    s.incidents.map(function (id) { return byId[id]; }).filter(Boolean)
      .sort(function (a, b) { return a.date < b.date ? 1 : -1; })
      .forEach(function (i) {
        ul.appendChild(el("li", null, [el("time", { text: i.date }), el("div", null, [
          el("div", { cls: "t" }, [el("a", { href: i.url, rel: "noopener", target: "_blank", text: i.title })]),
          el("div", { cls: "k", text: i.fails.length ? "실패 판정: " + i.fails.map(function (f) { return cname(f.control) + "(" + LAYER_KO[f.layer] + ")"; }).join(" · ") : "실패 판정 없음 — 공개 자료에 피해 쪽 통제가 적혀 있지 않다" })
        ])]));
      });
  }

  // ── ② 다시 돌리기 ──
  function renderReplay() {
    seg($("basis"), "basis", [[false, "적었거나 추론한 실패"], [true, "원문이 적은 실패만"]], state.statedOnly, function (v) {
      state.statedOnly = v === true || v === "true"; renderReplay();
    });
    var r = E.replay(failures, state.levels, stageOf, state.statedOnly);
    var judged = r.total - r.unknown;
    var cards = clear($("rep-cards"));
    function card(k, v, h, hl) { cards.appendChild(el("div", { cls: "card" + (hl ? " hl" : "") }, [el("div", { cls: "k", text: k }), el("div", { cls: "v", text: v }), el("div", { cls: "h", text: h })])); }
    card("막혔을 사건", (r.blocked_lo === r.blocked_hi ? String(r.blocked_hi) : r.blocked_lo + "~" + r.blocked_hi), "판단할 수 있는 " + judged + "건 중", true);
    card("피해 축소", String(r.reduced), "사후 통제만 맞음");
    card("그대로", String(r.unchanged), "실패한 통제가 하나도 켜지지 않음");
    card("판단 근거 없음", String(r.unknown), "공개 자료에 피해 쪽 통제가 없음");
    $("rep-explain").textContent = "하한 = 그 사건에서 실패한 통제가 모두 켜졌을 때 · 상한 = 사전·사용 중 단계 통제가 하나라도 켜졌을 때.";
    var nx = clear($("next")), best = E.bestNext(failures, state.levels, stageOf, state.statedOnly).filter(function (x) { return x[1] > 0; }).slice(0, 3);
    if (best.length) {
      nx.appendChild(el("div", { cls: "fine", text: "다음에 AI 까지 켜면 가장 많이 늘어나는 통제" }));
      var ol = el("ol");
      best.forEach(function (b) { ol.appendChild(el("li", null, [el("b", { text: cname(b[0]) }), " — 막힘 상한 +" + b[1] + "건"])); });
      nx.appendChild(ol);
    } else nx.appendChild(el("div", { cls: "fine", text: "더 켜서 늘어날 사건이 없다 — 남은 사건은 판단 근거가 없거나 사후 통제만 남았다." }));
    renderCompare(); renderPer(r);
  }
  function renderCompare() {
    var t = clear($("cmp"));
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "프리셋" }), el("th", { cls: "num", text: "막혔을 사건" }), el("th", { cls: "num", text: "그대로" }), el("th", { cls: "num", text: "판단 근거 없음" })])]));
    var tb = el("tbody");
    D.presets.forEach(function (p) {
      var r = E.replay(failures, p.levels, stageOf, state.statedOnly);
      tb.appendChild(el("tr", { cls: p.id === state.preset ? "cur" : "" }, [
        el("td", { text: p.label }),
        el("td", { cls: "num" }, [el("b", { text: r.blocked_lo === r.blocked_hi ? String(r.blocked_hi) : r.blocked_lo + "~" + r.blocked_hi })]),
        el("td", { cls: "num", text: String(r.unchanged) }), el("td", { cls: "num", text: String(r.unknown) })
      ]));
    });
    t.appendChild(tb);
  }
  function renderPer(r) {
    var t = clear($("per"));
    t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "사건" }), el("th", { text: "실패 판정" }), el("th", { text: "결과" }), el("th", { text: "날짜" })])]));
    var tb = el("tbody"), order = { blocked: 0, blocked_maybe: 1, reduced: 2, unchanged: 3, unknown: 4 };
    D.incidents.slice().sort(function (a, b) { return order[r.per[a.id]] - order[r.per[b.id]] || (a.date < b.date ? 1 : -1); }).forEach(function (i) {
      var fs = state.statedOnly ? i.fails.filter(function (f) { return f.level === "stated"; }) : i.fails;
      tb.appendChild(el("tr", null, [
        el("td", null, [el("a", { href: i.url, rel: "noopener", target: "_blank", text: i.title })]),
        el("td", { text: fs.length ? fs.map(function (f) { return cname(f.control) + "(" + LAYER_KO[f.layer] + ")"; }).join(" · ") : "—" }),
        el("td", { text: OUT_KO[r.per[i.id]] }), el("td", { text: i.date })
      ]));
    });
    t.appendChild(tb);
  }

  // ── 묶기 ──
  function update() { renderControlsChecked(); renderScenarioList(); renderStages(false); renderScenarioCases(); renderReplay(); }
  function renderControlsChecked() {
    D.controls.forEach(function (c) {
      document.querySelectorAll('input[name="lv-' + c.id + '"]').forEach(function (inp) { inp.checked = Number(inp.value) === state.levels[c.id]; });
    });
  }

  $("preset").addEventListener("change", function (e) {
    state.preset = e.target.value;
    if (presetById[state.preset]) state.levels = Object.assign({}, presetById[state.preset].levels);
    update();
  });
  $("profile").addEventListener("change", function (e) {
    state.profile = e.target.value;
    var p = D.agent_profiles.filter(function (x) { return x.id === state.profile; })[0];
    if (p) state.env = { tools: p.tools, untrusted_input: !!p.untrusted_input, open_components: !!p.open_components };
    renderEnv(); update();
  });
  $("run").addEventListener("click", function () {
    state.ran = true; renderStages(true);
    var ol = $("stages");
    if (ol.scrollIntoView) ol.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  });

  renderPreset(); renderControls(); renderEnv(); update();
})();
