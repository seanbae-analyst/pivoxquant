/* runtime-ui.js — 런타임 콘솔. 같은 출처의 /admin/api 만 부른다(세션 쿠키 + X-CSRF 헤더).
   글은 전부 textContent 로 넣는다 — 에이전트 이름 · 호출 인자 · 감사 기록은 외부에서 온 값이다. */
(function () {
  "use strict";
  var LEVEL_KO = ["없음", "사람·계정", "AI까지"];
  var STATUS_KO = { active: "활성", suspended: "즉시 중단", revoked: "폐기" };
  var DEC_KO = { allow: "허용", deny: "거부", require_approval: "승인 필요" };
  var RT_KO = { blocked: "막힘", damage: "피해 발생", no_surface: "쓸 도구 없음", runtime_na: "런타임 밖" };
  var MODEL_KO = { blocked: "막힘", reduced: "피해 축소", damage: "피해 발생", no_surface: "공격면 없음" };
  var OUT_KO = { blocked: "막힘", passed: "통과", no_surface: "공격면 없음" };
  var KIND_KO = { read: "조회", write: "쓰기", send: "외부 전송", exec: "코드 실행", pay: "송금·결제" };
  var AUD_KO = { decision: "판정", admin: "관리", auth: "인증", approval: "승인", kill_switch: "즉시 중단", redteam: "레드팀", cases: "공격 팀" };
  var OP_KO = { login: "로그인", register: "등록", update: "수정", status: "상태 변경", rotate_key: "키 회전", token: "토큰 발급", approve: "승인",
                deny: "거부", redteam: "레드팀 실행", component_add: "구성요소 추가", component_delete: "구성요소 삭제", cases: "공격 팀 투입", matrix: "규제별 비교" };
  function verdictLabel(kind, v) { return v === "good" ? (kind === "attack" ? "막음" : "처리됨") : v === "defect" ? "결함(뚫림)" : v === "friction" ? "업무 마찰" : "해당 없음"; }
  function verdictShort(kind, v) { return v === "good" ? (kind === "attack" ? "막음" : "처리") : v === "defect" ? "결함" : v === "friction" ? "마찰" : "·"; }
  var TOOLS = [["read", "조회만"], ["write", "쓰기·실행"], ["pay", "송금·결제"]];
  var FLAGS = [["untrusted_input", "외부 입력을 읽는다"], ["open_components", "외부 구성요소를 들인다"], ["memory", "장기 메모리"], ["multi_agent", "다른 에이전트와 일한다"]];
  var csrf = "", meta = null, agents = [], cur = null, ctlName = {};

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") n.textContent = attrs[k]; else if (k === "cls") n.className = attrs[k]; else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (k) { if (k !== null && k !== undefined) n.appendChild(typeof k === "string" ? document.createTextNode(k) : k); });
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function btn(text, cls, fn, attrs) { var b = el("button", Object.assign({ type: "button", cls: "btn " + (cls || ""), text: text }, attrs || {})); b.addEventListener("click", fn); return b; }
  function say(id, t) { var m = $(id); if (m) { m.textContent = t || ""; } }
  function fmt(n) { return typeof n === "number" ? n.toLocaleString("ko-KR") : String(n); }

  function api(method, path, body) {
    var h = { "Content-Type": "application/json" };
    if (method !== "GET") h["X-CSRF"] = csrf;
    return fetch(path, { method: method, headers: h, credentials: "same-origin", body: body === undefined ? undefined : JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (r.status === 401 && path !== "/admin/login") { showLogin(); }
          if (!r.ok) throw new Error(j.error || ("오류 " + r.status));
          return j;
        });
      });
  }

  // ── 로그인 ──
  function showLogin() { $("login").hidden = false; $("app").hidden = true; $("nav").hidden = true; $("login-token").focus(); }
  function showApp() { $("login").hidden = true; $("app").hidden = false; $("nav").hidden = false; }
  $("login-form").addEventListener("submit", function (e) {
    e.preventDefault();
    say("login-err", "");
    api("POST", "/admin/login", { token: $("login-token").value }).then(function (j) {
      csrf = j.csrf; $("login-token").value = ""; start();
    }).catch(function (err) { say("login-err", err.message); });
  });
  $("logout").addEventListener("click", function () { api("POST", "/admin/logout", {}).then(function () { csrf = ""; showLogin(); }); });

  // ── 에이전트 목록 ──
  function aiCount(a) { return Object.keys(a.levels || {}).filter(function (k) { return a.levels[k] >= 2; }).length; }
  function loadAgents(selectId) {
    return api("GET", "/admin/api/agents").then(function (j) {
      agents = j.agents; renderAgents();
      var id = selectId || (cur && cur.id);
      var a = agents.filter(function (x) { return x.id === id; })[0];
      if (a) showDetail(a);
    });
  }
  function renderAgents() {
    var t = clear($("agent-t"));
    t.appendChild(el("thead", null, [el("tr", null, ["이름", "id", "책임자", "종류", "상태", "AI까지", "키", "만료"].map(function (h) { return el("th", { text: h }); }))]));
    var tb = el("tbody");
    if (!agents.length) tb.appendChild(el("tr", null, [el("td", { colspan: "8", cls: "dim", text: "아직 등록한 에이전트가 없다. '새로 등록' 으로 시작한다." })]));
    agents.forEach(function (a) {
      var live = (a.keys || []).filter(function (k) { return !k.revoked_at; })[0];
      var pick = el("button", { type: "button", cls: "lnk", text: a.name });
      pick.addEventListener("click", function () { showDetail(a); $("detail").scrollIntoView({ block: "start" }); });
      tb.appendChild(el("tr", { cls: (cur && cur.id === a.id ? "sel " : "") + "st-" + a.status }, [
        el("td", null, [pick]), el("td", { cls: "mono", text: a.id }), el("td", { text: a.owner }),
        el("td", { text: profileLabel(a.profile) }), el("td", null, [el("span", { cls: "st " + a.status, text: STATUS_KO[a.status] || a.status })]),
        el("td", { text: aiCount(a) + " / 7" }), el("td", { cls: "mono", text: live ? live.prefix + "…" : "—" }),
        el("td", { text: a.expires_at ? a.expires_at.slice(0, 10) : "없음" })]));
    });
    t.appendChild(tb);
  }
  function profileLabel(id) { var p = (meta.profiles || []).filter(function (x) { return x.id === id; })[0]; return p ? p.label : "직접 구성"; }

  // ── 등록 ──
  $("new-agent").addEventListener("click", function () { $("reg").hidden = false; $("r-name").focus(); });
  $("reg-cancel").addEventListener("click", function () { $("reg").hidden = true; });
  $("reg-form").addEventListener("submit", function (e) {
    e.preventDefault(); say("reg-err", "");
    var prof = meta.profiles.filter(function (p) { return p.id === $("r-profile").value; })[0];
    var pre = meta.presets.filter(function (p) { return p.id === $("r-preset").value; })[0];
    var env = { tools: prof.tools }; FLAGS.forEach(function (f) { env[f[0]] = !!prof[f[0]]; });
    api("POST", "/admin/api/agents", { name: $("r-name").value, owner: $("r-owner").value, purpose: $("r-purpose").value,
      profile: prof.id, env: env, levels: pre.levels, expires_in_days: Number($("r-days").value) || 180 })
      .then(function (j) { $("reg").hidden = true; $("reg-form").reset(); showKey(j.api_key); return loadAgents(j.agent.id); })
      .catch(function (err) { say("reg-err", err.message); });
  });
  function showKey(k) { $("key-val").textContent = k; $("key-box").hidden = false; $("key-box").scrollIntoView({ block: "center" }); }
  $("key-copy").addEventListener("click", function () {
    var v = $("key-val").textContent;
    if (navigator.clipboard) navigator.clipboard.writeText(v).then(function () { $("key-copy").textContent = "복사했다"; });
  });
  $("key-hide").addEventListener("click", function () { $("key-val").textContent = ""; $("key-box").hidden = true; $("key-copy").textContent = "복사"; });

  // ── 상세 ──
  function seg(name, opts, curv, onChange) {
    var g = el("div", { cls: "seg", role: "radiogroup" });
    opts.forEach(function (o) {
      var id = "s-" + name + "-" + o[0], inp = el("input", { type: "radio", name: name, id: id, value: String(o[0]) });
      if (String(o[0]) === String(curv)) inp.checked = true;
      inp.addEventListener("change", function () { onChange(o[0]); });
      g.appendChild(el("label", { "for": id }, [inp, el("span", { text: o[1] })]));
    });
    return g;
  }
  function showDetail(a) {
    cur = JSON.parse(JSON.stringify(a)); renderAgents();
    $("detail").hidden = false; say("d-err", ""); say("d-saved", ""); clear($("rt-out"));
    $("d-id").textContent = a.id + " · " + (STATUS_KO[a.status] || a.status);
    $("d-name").textContent = a.name;
    $("d-meta").textContent = "책임자 " + a.owner + (a.purpose ? " · " + a.purpose : "") + " · 종류 " + profileLabel(a.profile) +
      " · 등록 " + (a.created_at || "").slice(0, 10) + " · 만료 " + (a.expires_at ? a.expires_at.slice(0, 10) : "없음");
    var acts = clear($("d-acts")), dead = a.status === "revoked";
    if (!dead && a.status === "active") acts.appendChild(btn("즉시 중단", "danger", function () { setStatus("suspended"); }));
    if (!dead && a.status === "suspended") acts.appendChild(btn("재개", "", function () { setStatus("active"); }));
    if (!dead) acts.appendChild(btn("키 회전", "", rotate));
    if (!dead) acts.appendChild(btn("폐기", "", function () { if (window.confirm(a.name + " 을(를) 폐기한다. 키와 토큰이 모두 끊기고 되돌릴 수 없다.")) setStatus("revoked"); }));
    renderControls();
    var env = clear($("d-env"));
    env.appendChild(el("span", { cls: "sub", text: "도구 권한" }));
    env.appendChild(seg("env-tools", TOOLS, cur.env.tools, function (v) { cur.env.tools = v; }));
    FLAGS.forEach(function (f) {
      env.appendChild(el("span", { cls: "sub", text: f[1] }));
      env.appendChild(seg("env-" + f[0], [[true, "예"], [false, "아니오"]], !!cur.env[f[0]], function (v) { cur.env[f[0]] = v === true || v === "true"; }));
    });
    $("d-max").value = cur.limits.max_amount === null ? "" : cur.limits.max_amount;
    $("d-burst").value = cur.limits.max_high_risk_per_min;
    renderTools();
    $("attack").hidden = false;
    clear($("cases-out")); clear($("matrix-out")); say("cases-hint", ""); say("matrix-hint", "");
    ["d-save", "d-redteam", "d-cases", "d-matrix", "d-apply-btn"].forEach(function (id) { $(id).disabled = dead; });
  }
  function levelsDirty() {
    var saved = (agents.filter(function (x) { return cur && x.id === cur.id; })[0] || {}).levels || {};
    return meta.controls.some(function (c) { return Number(saved[c.id] || 0) !== Number((cur.levels || {})[c.id] || 0); });
  }
  function renderControls() {
    var cbox = clear($("d-controls"));
    meta.controls.forEach(function (c) {
      cbox.appendChild(el("div", { cls: "ctl" }, [el("span", { cls: "nm", title: (c.help || {}).agent || "", text: c.num + ". " + c.name }),
        seg("lv-" + c.id, [[0, "없음"], [1, "사람·계정"], [2, "AI까지"]], cur.levels[c.id] || 0, function (v) { cur.levels[c.id] = Number(v); })]));
    });
  }
  function stepsDetails(steps, note) {
    var det = el("details", null, [el("summary", { text: (steps.length || 0) + "단계" })]), ol = el("ol", { cls: "rt-steps" });
    steps.forEach(function (st) {
      ol.appendChild(el("li", { cls: "d-" + st.decision }, [el("b", { text: (DEC_KO[st.decision] || st.decision) + (st.repeat > 1 ? " ×" + st.repeat : "") }),
        " " + st.note + (st.tool ? " (" + st.tool + ")" : "") + ": " + (st.reason || "")]));
    });
    if (note) ol.appendChild(el("li", { text: note }));
    det.appendChild(ol);
    return det;
  }
  // 규제 적용 — 프리셋 수준을 통제 세그먼트에 부어 넣는다(저장 전까지 미리보기)
  $("d-apply-btn").addEventListener("click", function () {
    var pre = (meta.presets || []).filter(function (p) { return p.id === $("d-apply").value; })[0];
    if (!pre || !cur) return;
    cur.levels = {}; meta.controls.forEach(function (c) { cur.levels[c.id] = Number((pre.levels || {})[c.id] || 0); });
    renderControls();
    say("d-saved", pre.label + " 수준을 부었다 — 저장을 누르면 반영된다.");
  });
  function renderTools() {
    var t = clear($("d-tools"));
    t.appendChild(el("thead", null, [el("tr", null, ["도구", "종류", "구성요소", ""].map(function (h) { return el("th", { text: h }); }))]));
    var tb = el("tbody");
    cur.tools.forEach(function (tl, i) {
      var c = tl.component;
      tb.appendChild(el("tr", null, [el("td", { cls: "mono", text: tl.name }), el("td", { text: KIND_KO[tl.kind] || tl.kind }),
        el("td", { cls: "mono", text: c ? c.name + "@" + c.version + (c.sha256 ? " · " + c.sha256.slice(0, 8) : "") : "—" }),
        el("td", null, [btn("빼기", "sm", function () { cur.tools.splice(i, 1); renderTools(); })])]));
    });
    t.appendChild(tb);
  }
  $("tool-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var name = $("t-name").value.trim(), comp = $("t-comp").value.trim(), t = { name: name, kind: $("t-kind").value };
    if (comp) { var at = comp.lastIndexOf("@"); if (at > 0) t.component = { name: comp.slice(0, at), version: comp.slice(at + 1) }; }
    cur.tools.push(t); renderTools(); $("tool-form").reset();
  });
  $("d-save").addEventListener("click", function () {
    say("d-err", "");
    var max = $("d-max").value === "" ? null : Number($("d-max").value);
    api("PATCH", "/admin/api/agents/" + cur.id, { levels: cur.levels, env: cur.env, tools: cur.tools,
      limits: { max_amount: max, max_high_risk_per_min: Number($("d-burst").value) || 5 } })
      .then(function () { say("d-saved", "저장했다"); return loadAgents(cur.id); }).catch(function (err) { say("d-err", err.message); });
  });
  function setStatus(s) {
    say("d-err", "");
    api("POST", "/admin/api/agents/" + cur.id + "/status", { status: s, reason: "콘솔" }).then(function () { loadAgents(cur.id); loadAudit(); })
      .catch(function (err) { say("d-err", err.message); });
  }
  function rotate() {
    if (!window.confirm("키를 회전한다. 지금 키와 그 키로 받은 토큰이 모두 끊긴다.")) return;
    api("POST", "/admin/api/agents/" + cur.id + "/rotate", {}).then(function (j) { showKey(j.api_key); loadAgents(cur.id); loadAudit(); })
      .catch(function (err) { say("d-err", err.message); });
  }

  // ── 레드팀 ──
  $("d-redteam").addEventListener("click", function () {
    var out = clear($("rt-out"));
    out.appendChild(el("p", { cls: "fine", text: "돌리는 중…" }));
    api("POST", "/admin/api/agents/" + cur.id + "/redteam", {}).then(function (j) { renderRedteam(j); loadAudit(); })
      .catch(function (err) { clear(out).appendChild(el("p", { cls: "err", text: err.message })); });
  });
  function renderRedteam(j) {
    var out = clear($("rt-out")), s = j.summary;
    out.appendChild(el("h4", { text: "레드팀 결과 — 막힘 " + s.blocked + " · 피해 발생 " + s.damage + " · 쓸 도구 없음 " + s.no_surface + " · 런타임 밖 " + s.runtime_na }));
    out.appendChild(el("p", { cls: "fine", text: "모델 예측은 모의 테스트(사람·계정 층과 피해 축소까지 셈)이고, 런타임 결과는 이 에이전트의 실제 정책이 호출을 어디서 멈췄는지다. 공격자는 사람 승인을 받을 수 없으므로 승인 요청에서 멈추면 막힌 것으로 센다." }));
    var t = el("table", { cls: "rt-t" });
    t.appendChild(el("thead", null, [el("tr", null, ["공격 원형", "모델 예측", "런타임 결과", "멈춘 곳", "단계"].map(function (h) { return el("th", { text: h }); }))]));
    var tb = el("tbody");
    j.results.forEach(function (r) {
      var diff = (r.outcome === "blocked") !== (r.model === "blocked") && r.outcome !== "runtime_na";
      var det = stepsDetails(r.steps, r.note);
      tb.appendChild(el("tr", { cls: diff ? "diff" : "" }, [el("td", { text: r.title }),
        el("td", null, [el("span", { cls: "o " + r.model, text: MODEL_KO[r.model] || r.model })]),
        el("td", null, [el("span", { cls: "o " + r.outcome, text: (RT_KO[r.outcome] || r.outcome) + (r.detected ? " · 탐지" : "") })]),
        el("td", { text: r.control ? ctlName[r.control] + " · " + r.stopped_at + "단계" : "—" }), el("td", null, [det])]));
    });
    t.appendChild(tb);
    out.appendChild(el("div", { cls: "tblwrap" }, [t]));
  }

  // ── 공격 팀 (현재 통제 그대로) ──
  $("d-cases").addEventListener("click", function () {
    var out = clear($("cases-out"));
    out.appendChild(el("p", { cls: "fine", text: "공격 팀 투입 중…" }));
    api("POST", "/admin/api/agents/" + cur.id + "/cases", levelsDirty() ? { levels: cur.levels } : {}).then(function (j) { renderCases(j); loadAudit(); })
      .catch(function (err) { clear(out).appendChild(el("p", { cls: "err", text: err.message })); });
  });
  function renderCases(j) {
    var out = clear($("cases-out")), s = j.summary;
    out.appendChild(el("p", { cls: "sum", text: "결함 " + s.defect + " · 업무 마찰 " + s.friction + " · 정상 " + s.good + " · 해당 없음 " + s.na }));
    if (j.preview) out.appendChild(el("p", { cls: "fine", text: "저장하지 않은 화면의 통제 수준으로 돌렸다. 에이전트에 반영하려면 저장을 누른다." }));
    var t = el("table", { cls: "rt-t" });
    t.appendChild(el("thead", null, [el("tr", null, ["케이스", "종류", "결과", "판정", "멈춘 곳", "단계"].map(function (h) { return el("th", { text: h }); }))]));
    var tb = el("tbody");
    j.results.forEach(function (r) {
      tb.appendChild(el("tr", { cls: "v-" + r.verdict }, [el("td", { text: r.title }),
        el("td", { cls: "sub", text: r.kind === "attack" ? "공격" : "정상 업무" }),
        el("td", null, [el("span", { cls: "o " + r.outcome, text: OUT_KO[r.outcome] || r.outcome })]),
        el("td", null, [el("span", { cls: "vd v-" + r.verdict, text: verdictLabel(r.kind, r.verdict) + (r.detected ? " · 탐지" : "") })]),
        el("td", { text: r.control ? ctlName[r.control] + " · " + r.stopped_at + "단계" : "—" }),
        el("td", null, [stepsDetails(r.steps)])]));
    });
    t.appendChild(tb);
    out.appendChild(el("div", { cls: "tblwrap" }, [t]));
  }

  // ── 규제별 비교 (케이스 × 프리셋) ──
  $("d-matrix").addEventListener("click", function () {
    var ids = Array.prototype.slice.call($("reg-pick").querySelectorAll("input:checked")).map(function (i) { return i.value; });
    if (!ids.length) { say("matrix-hint", "규제를 하나 이상 고른다."); return; }
    say("matrix-hint", "");
    var out = clear($("matrix-out"));
    out.appendChild(el("p", { cls: "fine", text: "규제마다 돌리는 중…" }));
    api("POST", "/admin/api/agents/" + cur.id + "/matrix", { presets: ids, current_levels: cur.levels }).then(function (j) { renderMatrix(j); loadAudit(); })
      .catch(function (err) { clear(out).appendChild(el("p", { cls: "err", text: err.message })); });
  });
  function renderMatrix(j) {
    var out = clear($("matrix-out")), t = el("table", { cls: "mx-t" });
    var head = el("tr", null, [el("th", { cls: "cs", text: "케이스" })]);
    var dirty = levelsDirty();
    j.presets.forEach(function (p) {
      head.appendChild(el("th", { cls: "pz" + (p.preset === "current" ? " cur" : ""), text: p.preset === "current" ? (dirty ? "지금 화면 (저장 안 함)" : "지금 설정") : p.label }));
    });
    t.appendChild(el("thead", null, [head]));
    var tb = el("tbody");
    j.cases.forEach(function (c) {
      var tr = el("tr", { cls: "k-" + c.kind }, [el("td", { cls: "cs" }, [el("b", { text: c.title }), el("span", { cls: "sub", text: c.kind === "attack" ? " 공격" : " 정상 업무" })])]);
      j.presets.forEach(function (p) {
        var cell = p.cells[c.id] || {}, v = cell.verdict || "na";
        tr.appendChild(el("td", { cls: "mx v-" + v, title: cell.control ? ctlName[cell.control] + "에서 멈춤" : "" }, [el("span", { cls: "vd v-" + v, text: verdictShort(c.kind, v) })]));
      });
      tb.appendChild(tr);
    });
    [["결함 합계", "defect"], ["업무 마찰 합계", "friction"]].forEach(function (row) {
      var tr = el("tr", { cls: "mx-sum" }, [el("td", { cls: "cs", text: row[0] })]);
      j.presets.forEach(function (p) { tr.appendChild(el("td", { cls: "mx", text: String(p.summary[row[1]]) })); });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    out.appendChild(el("div", { cls: "tblwrap" }, [t]));
    out.appendChild(el("p", { cls: "fine", text: "공격이 통과하면 결함, 정상 업무가 막히면 업무 마찰이다. 규제가 셀수록 결함은 줄고 마찰은 는다. 샌드박스라 에이전트 상태는 바뀌지 않는다." }));
  }

  // ── 승인 대기 ──
  function kv(obj) {
    var dl = el("dl", { cls: "kv" });
    Object.keys(obj || {}).forEach(function (k) { dl.appendChild(el("dt", { text: k })); dl.appendChild(el("dd", { text: typeof obj[k] === "object" ? JSON.stringify(obj[k]) : fmt(obj[k]) })); });
    return dl;
  }
  function loadApprovals() {
    return api("GET", "/admin/api/approvals?status=pending").then(function (j) {
      var box = clear($("apr-list")), n = j.approvals.length;
      $("nav-pend").textContent = n ? "(" + n + ")" : "";
      say("apr-meta", n ? n + "건 대기" : "대기 없음");
      if (!n) box.appendChild(el("p", { cls: "dim", text: "기다리는 승인 요청이 없다." }));
      j.approvals.forEach(function (ap) {
        var a = agents.filter(function (x) { return x.id === ap.agent_id; })[0], rq = ap.request;
        box.appendChild(el("div", { cls: "apr" }, [
          el("div", { cls: "apr-h" }, [el("b", { text: (a ? a.name : ap.agent_id) + " → " + rq.tool }), el("span", { cls: "fine", text: ap.created_at + " · " + ap.id })]),
          el("div", { cls: "apr-b" }, [el("div", null, [el("span", { cls: "k", text: "실제 인자" }), kv(rq.args)]),
            el("div", null, [el("span", { cls: "k", text: "입력 출처" }), el("ul", null, (rq.input_sources || []).map(function (s) {
              return el("li", { cls: s.trusted ? "" : "untrusted", text: s.kind + (s.trusted ? " (신뢰)" : " (외부)") + (s.ref ? " · " + s.ref : "") }); }))])]),
          el("div", { cls: "row" }, [btn("승인", "btn-primary sm", function () { decideApr(ap.id, true); }), btn("거부", "sm", function () { decideApr(ap.id, false); })])
        ]));
      });
    });
  }
  function decideApr(id, ok) { api("POST", "/admin/api/approvals/" + id, { approve: ok }).then(function () { loadApprovals(); loadAudit(); }); }

  // ── 감사 기록 ──
  function loadAudit() {
    return api("GET", "/admin/api/audit").then(function (j) {
      var t = clear($("aud-t"));
      t.appendChild(el("thead", null, [el("tr", null, ["#", "시각", "종류", "에이전트", "내용", "해시"].map(function (h) { return el("th", { text: h }); }))]));
      var tb = el("tbody"), names = {};
      agents.forEach(function (a) { names[a.id] = a.name; });
      j.rows.forEach(function (r) {
        var p = r.payload, what = p.decision ? (DEC_KO[p.decision] || p.decision) + " · " + p.tool + " · " + p.reason
          : (OP_KO[p.op] || p.op || "") + (p.status ? ": " + (STATUS_KO[p.status] || p.status) : "") + (p.by ? " · " + (p.by === "system" ? "자동" : p.by === "admin" ? "관리자" : p.by) : "") + (p.reason ? " · " + p.reason : "");
        tb.appendChild(el("tr", { cls: "k-" + r.kind }, [el("td", { cls: "mono", text: String(r.seq) }), el("td", { cls: "mono", text: r.ts.slice(5, 19).replace("T", " ") }),
          el("td", { text: AUD_KO[r.kind] || r.kind }), el("td", { text: names[r.agent_id] || r.agent_id || "—" }), el("td", { text: what }), el("td", { cls: "mono", text: r.hash.slice(0, 12) })]));
      });
      t.appendChild(tb);
    });
  }
  $("aud-verify").addEventListener("click", function () {
    api("GET", "/admin/api/audit/verify").then(function (v) { say("aud-v", v.ok ? "이어져 있다 — " + v.checked + "줄" : "끊겼다 — " + v.broken_at + "번째 줄부터"); });
  });

  // ── 구성요소 ──
  function renderComps(list) {
    var t = clear($("comp-t"));
    t.appendChild(el("thead", null, [el("tr", null, ["이름", "버전", "지문", "메모", ""].map(function (h) { return el("th", { text: h }); }))]));
    var tb = el("tbody");
    list.forEach(function (c) {
      tb.appendChild(el("tr", null, [el("td", { cls: "mono", text: c.name }), el("td", { cls: "mono", text: c.version }), el("td", { cls: "mono", text: c.sha256 ? c.sha256.slice(0, 16) + "…" : "고정 안 함" }),
        el("td", { text: c.note || "" }), el("td", null, [btn("빼기", "sm", function () {
          api("POST", "/admin/api/components/delete", { name: c.name, version: c.version }).then(function (j) { renderComps(j.components); });
        })])]));
    });
    t.appendChild(tb);
  }
  $("comp-form").addEventListener("submit", function (e) {
    e.preventDefault(); say("comp-err", "");
    api("POST", "/admin/api/components", { name: $("c-name").value.trim(), version: $("c-ver").value.trim(), sha256: $("c-sha").value.trim() || null })
      .then(function (j) { $("comp-form").reset(); renderComps(j.components); }).catch(function (err) { say("comp-err", err.message); });
  });

  // ── 연결 안내 ──
  function renderConnect() {
    var o = location.origin;
    $("con-code").textContent = [
      "# 1) 장기 키로 단기 토큰(15분)을 받는다",
      "curl -s -X POST " + o + "/v1/token -H 'Authorization: Bearer $PIVOX_AGENT_KEY' -H 'Content-Type: application/json' -d '{}'",
      "",
      "# 2) 도구를 쓰기 직전에 묻는다",
      "curl -s -X POST " + o + "/v1/decide -H 'Authorization: Bearer <토큰>' -H 'Content-Type: application/json' \\",
      "  -d '{\"tool\":\"transfer\",\"args\":{\"amount\":300000,\"target\":\"vendor-1\"},\"input_sources\":[{\"kind\":\"user\",\"trusted\":true}]}'",
      "",
      "# 파이썬 SDK",
      "from pivoxpolicy.runtime.sdk import Guard",
      "guard = Guard(\"" + o + "\", api_key=os.environ[\"PIVOX_AGENT_KEY\"])",
      "@guard.tool(\"transfer\")",
      "def transfer(amount, target): ...",
      "",
      "# 데모 에이전트: PIVOX_AGENT_KEY=pvx_... python3 examples/demo_agent.py --url " + o
    ].join("\n");
  }

  // ── 시작 ──
  function fillSelects() {
    var p = clear($("r-profile")), s = clear($("r-preset")), k = clear($("t-kind"));
    meta.profiles.forEach(function (x) { p.appendChild(el("option", { value: x.id, text: x.label })); });
    meta.presets.forEach(function (x) { s.appendChild(el("option", { value: x.id, text: x.label })); });
    s.value = "all";
    meta.kinds.forEach(function (x) { k.appendChild(el("option", { value: x, text: KIND_KO[x] })); });
    meta.controls.forEach(function (c) { ctlName[c.id] = c.name; });
    var ap = clear($("d-apply")), rp = clear($("reg-pick")), def = meta.matrix_default || [];
    meta.presets.forEach(function (x) { ap.appendChild(el("option", { value: x.id, text: x.label })); });
    ap.value = "KR-2";
    meta.presets.forEach(function (x) {
      var id = "rp-" + x.id, inp = el("input", { type: "checkbox", id: id, value: x.id });
      if (def.indexOf(x.id) >= 0) inp.checked = true;
      rp.appendChild(el("label", { cls: "rp-item", "for": id }, [inp, el("span", { text: x.label })]));
    });
  }
  var poll = null;
  function start() {
    showApp();
    api("GET", "/admin/api/meta").then(function (m) {
      meta = m; fillSelects(); renderConnect();
      return loadAgents();
    }).then(function () { loadApprovals(); loadAudit(); return api("GET", "/admin/api/components"); }).then(function (j) { renderComps(j.components); });
    clearInterval(poll);
    poll = setInterval(function () { if (!document.hidden && csrf) loadApprovals(); }, 5000);
  }
  api("GET", "/admin/api/session").then(function (s) { if (s.logged_in) { csrf = s.csrf; start(); } else showLogin(); }).catch(showLogin);
})();
