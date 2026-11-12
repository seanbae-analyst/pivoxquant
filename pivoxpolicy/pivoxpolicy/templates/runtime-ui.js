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
  var SCORE_KO = ["다루지 않음", "자율", "구속력", "구속력 + 에이전트 명시"];
  var LV_KO = ["없음", "사람·계정", "AI까지"];
  var KIND_KO = { read: "조회", write: "쓰기", send: "외부 전송", exec: "코드 실행", pay: "송금·결제" };
  var AUD_KO = { decision: "판정", admin: "관리", auth: "인증", approval: "승인", kill_switch: "즉시 중단", redteam: "레드팀", cases: "공격 팀" };
  var OP_KO = { login: "로그인", register: "등록", update: "수정", status: "상태 변경", rotate_key: "키 회전", token: "토큰 발급", approve: "승인",
                deny: "거부", redteam: "레드팀 실행", component_add: "구성요소 추가", component_delete: "구성요소 삭제", cases: "공격 팀 투입", matrix: "규제별 비교" };
  function verdictLabel(kind, v) {
    return v === "good" ? (kind === "attack" ? "막음" : "처리됨") : v === "held" ? "사람 승인에 기댐" : v === "defect" ? "결함(뚫림)" : v === "friction" ? "업무 마찰" : "해당 없음";
  }
  function verdictShort(kind, v) { return v === "good" ? (kind === "attack" ? "막음" : "처리") : v === "held" ? "승인" : v === "defect" ? "결함" : v === "friction" ? "마찰" : "·"; }
  // 멈춘 곳 — 사람 승인에서 멈췄으면 '승인했을 때' 를 같이 말한다
  function stopText(r, kind) {
    if (!r.control) return "—";
    var t = ctlName[r.control] + " · " + r.stopped_at + "단계", ia = r.if_approved;
    if (ia) t += ia.outcome === "blocked" ? " → 승인해도 " + ctlName[ia.control] + "에서 멈춤"
      : (kind === "benign" ? " → 승인하면 처리" : " → 승인하면 뚫림");
    return t;
  }
  function outcomeText(r) { return r.outcome === "blocked" && r.control === "human_approval" ? "승인 대기" : (OUT_KO[r.outcome] || r.outcome); }
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


  // ── 명세서로 등록 (도구 정의 → 추정 → 고치기 → 등록) ──
  var CONF_KO = { high: "높음", medium: "보통", low: "낮음" }, FMT_KO = { anthropic: "Anthropic", openai: "OpenAI", mcp: "MCP" };
  var inPrev = null;
  $("new-intake").addEventListener("click", function () { $("intake").hidden = false; $("reg").hidden = true; $("in-text").focus(); });
  $("in-close").addEventListener("click", function () { $("intake").hidden = true; });
  $("in-example").addEventListener("click", function () {
    api("GET", "/admin/api/intake/example").then(function (j) { $("in-text").value = j.spec_text; inPrev = null; $("in-register").disabled = true; clear($("in-out")); });
  });
  $("in-text").addEventListener("input", function () { inPrev = null; $("in-register").disabled = true; });
  function inOverrides() {
    var ov = { kinds: {} };
    Array.prototype.slice.call(document.querySelectorAll("#in-out select[data-tool]")).forEach(function (sel) {
      if (sel.value !== sel.getAttribute("data-inferred")) ov.kinds[sel.getAttribute("data-tool")] = sel.value;
    });
    return ov;
  }
  function inPreview() {
    say("in-err", "");
    var out = clear($("in-out"));
    out.appendChild(el("p", { cls: "fine", text: "명세를 읽는 중…" }));
    return api("POST", "/admin/api/intake/preview", { spec_text: $("in-text").value, overrides: inOverrides() }).then(function (j) {
      inPrev = j; renderIntake(j); $("in-register").disabled = false;
    }).catch(function (err) { clear(out); say("in-err", err.message); $("in-register").disabled = true; });
  }
  $("in-preview").addEventListener("click", inPreview);
  $("in-register").addEventListener("click", function () {
    say("in-err", "");
    api("POST", "/admin/api/intake/register", { spec_text: $("in-text").value, overrides: inOverrides() }).then(function (j) {
      $("intake").hidden = true; clear($("in-out")); showKey(j.api_key); return loadAgents(j.agent.id);
    }).catch(function (err) { say("in-err", err.message); });
  });
  function renderIntake(j) {
    var out = clear($("in-out")), lab = {}, a = j.agent, pr = j.compliance, M = obMeta();
    Object.keys(M.profile || {}).forEach(function (k) { (M.profile[k].options || []).forEach(function (o) { lab[o.id] = o.label; }); });
    out.appendChild(el("p", { cls: "sum", text: a.name + " · 도구 " + j.tools.length + " · 만든 공격 케이스 " + j.cases.length +
      " · 걸리는 조문 " + j.assessment.applicable + "(강제 " + j.assessment.binding + ", 설계 충돌 " + j.assessment.conflict + ")" }));
    if (j.warnings.length) {
      var w = el("div", { cls: "ob-conflict", role: "note" }, [el("b", { text: "확인할 것 " + j.warnings.length + "건" })]);
      j.warnings.forEach(function (x) { w.appendChild(el("p", { text: x })); });
      out.appendChild(w);
    }
    var t = el("table", { cls: "rt-t in-t" });
    t.appendChild(el("thead", null, [el("tr", null, ["도구", "형식", "종류(고칠 수 있음)", "근거", "확신도", "금액 인자", "고객 인자", "외부 글"].map(function (h) { return el("th", { text: h }); }))]));
    var tb = el("tbody");
    j.tools.forEach(function (x) {
      var sel = el("select", { "data-tool": x.name, "data-inferred": x.why === "사람이 고침" ? "" : x.kind, "aria-label": x.name + " 종류" });
      meta.kinds.forEach(function (k) { sel.appendChild(el("option", { value: k, text: KIND_KO[k] })); });
      sel.value = x.kind;
      tb.appendChild(el("tr", { cls: "conf-" + x.confidence }, [el("td", null, [el("b", { cls: "mono", text: x.name }), el("span", { cls: "basis-art", text: x.description })]),
        el("td", { cls: "sub", text: FMT_KO[x.format] || x.format }), el("td", null, [sel]), el("td", { text: x.why }),
        el("td", { cls: "conf", text: CONF_KO[x.confidence] || x.confidence }), el("td", { cls: "mono", text: x.amount_arg || "—" }),
        el("td", { cls: "mono", text: x.customer_arg || "—" }), el("td", { text: x.external ? "읽는다" : "—" })]));
    });
    t.appendChild(tb);
    out.appendChild(el("div", { cls: "tblwrap" }, [t]));
    var dl = el("dl", { cls: "kv in-kv" });
    [["하는 일", pr.activities.map(function (x) { return lab[x] || x; }).join(", ")], ["다루는 정보", pr.data.map(function (x) { return lab[x] || x; }).join(", ") || "없음"],
     ["쓰는 모델", lab[pr.external_llm] || pr.external_llm], ["일반투자자", pr.retail ? "상대한다" : "아니다"], ["자동화된 결정", pr.automated_decision ? "한다" : "아니다"],
     ["도구 권한", TOOLS.filter(function (x) { return x[0] === a.env.tools; }).map(function (x) { return x[1]; })[0] || a.env.tools],
     ["외부 입력", a.env.untrusted_input ? "읽는다" : "읽지 않는다"], ["지금 통제", meta.controls.map(function (c) { return c.name + " " + LV_KO[a.levels[c.id] || 0]; }).join(", ")]]
      .forEach(function (r) { dl.appendChild(el("dt", { text: r[0] })); dl.appendChild(el("dd", { text: r[1] })); });
    out.appendChild(el("h5", { cls: "ob-h5", text: "추정한 프로필" }));
    out.appendChild(dl);
    out.appendChild(el("h5", { cls: "ob-h5", text: "이 에이전트의 도구로 만든 공격 케이스 " + j.cases.length + "개" }));
    out.appendChild(el("ul", { cls: "in-cases" }, j.cases.map(function (c) { return el("li", null, [el("b", { text: c.kind === "attack" ? "공격" : "정상 업무" }), " " + c.title]); })));
    if (j.skipped.length) out.appendChild(el("details", { cls: "ob-na" }, [el("summary", { text: "만들지 않은 원형 " + j.skipped.length + "개와 이유" }),
      el("ul", null, j.skipped.map(function (x) { return el("li", { text: x }); }))]));
    out.appendChild(el("p", { cls: "fine", text: "종류를 고쳤으면 미리보기를 다시 누르면 케이스가 다시 만들어진다. 등록하면 명세의 구성요소(이름, 버전, 지문)를 승인 목록에 올린다." }));
    Array.prototype.slice.call(out.querySelectorAll("select[data-tool]")).forEach(function (sel) {
      sel.addEventListener("change", function () { $("in-register").disabled = false; });
    });
  }

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
    $("attack").hidden = false; $("oblig").hidden = false;
    clear($("cases-out")); clear($("matrix-out")); clear($("ob-out")); say("cases-hint", ""); say("matrix-hint", ""); say("ob-msg", "");
    renderObForm();
    ["d-save", "d-redteam", "d-cases", "d-matrix", "d-apply-btn", "ob-run", "ob-save"].forEach(function (id) { $(id).disabled = dead; });
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
    say("d-saved", pre.label + " 수준을 통제에 넣었다. 저장을 누르면 반영된다.");
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
    out.appendChild(el("p", { cls: "sum", text: "결함 " + s.defect + " · 사람 승인에 기댐 " + s.held + " · 업무 마찰 " + s.friction + " · 정상 " + s.good + " · 해당 없음 " + s.na }));
    if (j.preview) out.appendChild(el("p", { cls: "fine", text: "저장하지 않은 화면의 통제 수준으로 돌렸다. 에이전트에 반영하려면 저장을 누른다." }));
    var t = el("table", { cls: "rt-t" });
    t.appendChild(el("thead", null, [el("tr", null, ["케이스", "종류", "결과", "판정", "멈춘 곳", "단계"].map(function (h) { return el("th", { text: h }); }))]));
    var tb = el("tbody");
    j.results.forEach(function (r) {
      tb.appendChild(el("tr", { cls: "v-" + r.verdict }, [el("td", { text: r.title }),
        el("td", { cls: "sub", text: r.kind === "attack" ? "공격" : "정상 업무" }),
        el("td", null, [el("span", { cls: "o " + (r.control === "human_approval" ? "held" : r.outcome), text: outcomeText(r) })]),
        el("td", null, [el("span", { cls: "vd v-" + r.verdict, text: verdictLabel(r.kind, r.verdict) + (r.detected ? " · 탐지" : "") })]),
        el("td", { text: stopText(r, r.kind) }),
        el("td", null, [stepsDetails(r.if_approved ? r.if_approved.steps : r.steps)])]));
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
    var body = { presets: ids, current_levels: cur.levels }, prof = readObForm();
    if (prof.activities.length) body.profile = prof;
    api("POST", "/admin/api/agents/" + cur.id + "/matrix", body).then(function (j) { renderMatrix(j); loadAudit(); })
      .catch(function (err) { clear(out).appendChild(el("p", { cls: "err", text: err.message })); });
  });
  var mxData = null;
  var OB_SHORT = { "OB-binding_explicit": "적용 조문: 강제, 문언대로", "OB-binding_interpretive": "적용 조문: 강제, 해석 포함", "OB-guideline": "적용 조문: 가이드라인까지" };
  function colLabel(p) { return p.preset === "current" ? (levelsDirty() ? "지금 화면 (저장 안 함)" : "지금 설정") : (OB_SHORT[p.preset] || p.label); }
  function renderMatrix(j) {
    mxData = j;
    var out = clear($("matrix-out")), t = el("table", { cls: "mx-t" });
    var head = el("tr", null, [el("th", { cls: "cs", text: "케이스" })]);
    var dirty = levelsDirty();
    j.presets.forEach(function (p) {
      head.appendChild(el("th", { cls: "pz" + (p.preset === "current" ? " cur" : "") + (OB_SHORT[p.preset] ? " ob" : ""), text: colLabel(p) }));
    });
    t.appendChild(el("thead", null, [head]));
    var tb = el("tbody");
    j.cases.forEach(function (c) {
      var tr = el("tr", { cls: "k-" + c.kind }, [el("td", { cls: "cs" }, [el("b", { text: c.title }), el("span", { cls: "sub", text: c.kind === "attack" ? " 공격" : " 정상 업무" })])]);
      j.presets.forEach(function (p) {
        var cell = p.cells[c.id] || {}, v = cell.verdict || "na";
        var b = el("button", { type: "button", cls: "mx-btn", "aria-label": c.title + ", " + colLabel(p) + ", " + verdictLabel(c.kind, v) + ". 해부 열기",
                               title: cell.control ? stopText(cell, c.kind) : "" }, [el("span", { cls: "vd v-" + v, text: verdictShort(c.kind, v) })]);
        b.addEventListener("click", function () { renderCellDetail(c, p, cell, b); });
        tr.appendChild(el("td", { cls: "mx v-" + v }, [b]));
      });
      tb.appendChild(tr);
    });
    [["결함 합계", "defect"], ["사람 승인에 기댐", "held"], ["업무 마찰 합계", "friction"]].forEach(function (row) {
      var tr = el("tr", { cls: "mx-sum" }, [el("td", { cls: "cs", text: row[0] })]);
      j.presets.forEach(function (p) { tr.appendChild(el("td", { cls: "mx", text: String(p.summary[row[1]]) })); });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    out.appendChild(el("div", { cls: "tblwrap" }, [t]));
    out.appendChild(el("div", { id: "mx-detail", cls: "mx-det", hidden: "hidden", "aria-live": "polite" }));
    out.appendChild(el("p", { cls: "fine", text: "칸을 누르면 그 결과를 해부한다. 어디서 멈췄는지, 통제 하나를 올려 막을 수 있는지, 그 관할의 규제 근거가 무엇인지 보여 준다. 공격이 통과하면 결함, 정상 업무가 막히면 업무 마찰이다. '승인'은 사람 승인에서만 멈춘 공격이다. 승인자가 요약에 속거나 지쳐서 승인하면 뚫린다(승인해도 뒤의 통제가 막으면 막음으로 센다). 샌드박스라 에이전트 상태는 바뀌지 않는다." }));
  }



  // ── 적용 조문 (조항 단위 의무, 증권부터) ──
  var OB_ST = { met: "충족", partial: "사람·계정 층만", unmet: "미충족", offline: "런타임 밖", conflict: "설계 충돌" };
  var LINK_KO = {
    violation: "이 에이전트에 걸리는 강제 조문이 이 통제를 AI까지 명시해 요구한다. 위반 소지가 있다.",
    interpretive: "걸리는 강제 조문은 사람·계정 층만 말한다. 에이전트 계정에도 미친다고 읽으면 위반 소지, 아니면 규제 공백이다.",
    guideline: "자율 규범(가이드라인, 평가기준)만 이 통제를 요구한다. 위반은 아니지만 가이드라인 미이행이다.",
    gap: "이 에이전트에 걸리는 조문 중 이 통제를 요구하는 것이 없다. 합법이지만 위험한 규제 공백이다."
  };
  var LINK_SHORT = { violation: "위반 소지", interpretive: "해석에 따라 위반 소지", guideline: "가이드라인 미이행", gap: "규제 공백" };
  var STOP_KO = {
    violation: "강제 조문이 문언대로 요구하는 차단이다.",
    interpretive: "강제 조문은 사람·계정 층만 말한다. 이 차단은 그 조문이 에이전트에도 미친다고 읽을 때의 것이다.",
    guideline: "자율 규범(가이드라인, 평가기준)이 요구하는 차단이다.",
    gap: "이 차단을 요구하는 조문은 이 에이전트에 걸리지 않는다. 회사가 스스로 둔 통제다."
  };
  var STOP_SHORT = { violation: "강제 조문이 요구", interpretive: "해석에 따른 요구", guideline: "자율 규범이 요구", gap: "요구하는 조문 없음" };
  function obMeta() { return meta.obligations || { profile: {} }; }
  var obFormFor = null;
  function renderObForm() {
    // 같은 에이전트를 다시 그릴 때(통제 저장 뒤 등)는 저장하지 않은 선택을 지우지 않는다
    var keep = obFormFor && cur && obFormFor === cur.id ? readObForm() : null;
    var M = obMeta(), box = clear($("ob-form")), pv = keep || (cur && cur.compliance) || {};
    obFormFor = cur ? cur.id : null;
    $("ob-h").textContent = "적용 조문 (" + (M.label || "증권") + ")";
    var w = $("ob-warn");
    w.hidden = !!M.reviewed_by_counsel;
    w.textContent = "변호사 검토 전 초안이다(기준일 " + (M.as_of || "") + "). 조문 대응 · 적용 조건 · 해석 여지는 이 도구의 판단이며 법률 자문이 아니다.";
    Object.keys(M.profile || {}).forEach(function (key) {
      var q = M.profile[key], row = el("div", { cls: "ob-q" }, [el("span", { cls: "sub", text: q.label })]), opts = el("div", { cls: "ob-opts" });
      if (q.type === "bool") {
        var id = "obq-" + key, inp = el("input", { type: "checkbox", id: id, "data-k": key });
        inp.checked = pv[key] === true;
        opts.appendChild(el("label", { cls: "rp-item", "for": id }, [inp, el("span", { text: "예" })]));
      } else if (q.multi) {
        (q.options || []).forEach(function (o) {
          var id2 = "obq-" + key + "-" + o.id, i2 = el("input", { type: "checkbox", id: id2, value: o.id, "data-k": key });
          i2.checked = (pv[key] || []).indexOf(o.id) >= 0;
          opts.appendChild(el("label", { cls: "rp-item", "for": id2 }, [i2, el("span", { text: o.label })]));
        });
      } else {
        opts.appendChild(seg("obq-" + key, (q.options || []).map(function (o) { return [o.id, o.label]; }), pv[key] || (q.options[0] || {}).id, function () {}));
      }
      row.appendChild(opts);
      box.appendChild(row);
    });
  }
  function readObForm() {
    var M = obMeta(), out = {};
    Object.keys(M.profile || {}).forEach(function (key) {
      var q = M.profile[key];
      if (q.type === "bool") { var b = $("obq-" + key); out[key] = !!(b && b.checked); }
      else if (q.multi) out[key] = Array.prototype.slice.call(document.querySelectorAll('#ob-form input[data-k="' + key + '"]:checked')).map(function (i) { return i.value; });
      else { var r = document.querySelector('#ob-form input[name="obq-' + key + '"]:checked'); out[key] = r ? r.value : (q.options[0] || {}).id; }
    });
    return out;
  }
  $("ob-run").addEventListener("click", function () {
    var prof = readObForm(), out = clear($("ob-out"));
    if (!prof.activities.length) { say("ob-msg", "에이전트가 하는 일을 하나 이상 고른다."); return; }
    say("ob-msg", "");
    out.appendChild(el("p", { cls: "fine", text: "조문을 고르는 중…" }));
    var body = { profile: prof };
    if (levelsDirty()) body.levels = cur.levels;
    api("POST", "/admin/api/agents/" + cur.id + "/obligations", body).then(renderOb)
      .catch(function (err) { clear(out).appendChild(el("p", { cls: "err", text: err.message })); });
  });
  $("ob-save").addEventListener("click", function () {
    var prof = readObForm();
    if (!prof.activities.length) { say("ob-msg", "에이전트가 하는 일을 하나 이상 고른다."); return; }
    api("PATCH", "/admin/api/agents/" + cur.id, { compliance: prof }).then(function () { say("ob-msg", "프로필을 저장했다. 규제별 비교에 '적용 조문' 열이 붙는다."); return loadAgents(cur.id); })
      .catch(function (err) { say("ob-msg", err.message); });
  });
  function obRef(r) {
    var t = r.doc + " " + r.article;
    return r.source ? el("a", { href: r.source, target: "_blank", rel: "noopener noreferrer", text: t }) : el("span", { text: t });
  }
  function renderOb(j) {
    var out = clear($("ob-out")), s = j.summary, M = obMeta(), byId = {};
    j.applicable.forEach(function (r) { byId[r.id] = r; });
    out.appendChild(el("p", { cls: "sum", text: "적용 조문 " + s.applicable + " (강제 " + s.binding + " · 자율 " + s.voluntary + " · 런타임 밖 " + s.offline + ") · 걸리지 않는 조문 " + s.not_applicable }));
    out.appendChild(el("p", { cls: "fine", text: "지금 통제 기준: 충족 " + s.met + ", 사람·계정 층만 " + s.partial + ", 미충족 " + s.unmet + ", 런타임 밖 " + (s.offline - s.conflict) + ", 설계 충돌 " + s.conflict + ". 강제 조문 중 미충족이거나 사람·계정 층만인 것 " + s.unmet_binding + "개." }));
    out.appendChild(el("p", { cls: "hi-line" }, [el("b", { text: "AI 기본법 고영향 AI: " + (j.high_impact.value ? "해당" : "해당 안 함") }), " " + j.high_impact.reason]));
    // 설계 충돌 — 통제를 켜도 풀리지 않는다. 맨 위에 둔다
    var cf = j.applicable.filter(function (r) { return r.prohibits; });
    if (cf.length) {
      var box = el("div", { cls: "ob-conflict", role: "note" }, [el("b", { text: "설계 충돌 " + cf.length + "건: 통제를 켜도 풀리지 않는다. 프로필(쓰는 모델 · 다루는 정보)을 바꾸거나 예외 사유를 갖춰야 한다." })]);
      cf.forEach(function (r) {
        box.appendChild(el("p", null, [obRef(r), " " + r.requires + (r.unless ? " 해소: " + r.unless : "")]));
      });
      out.appendChild(box);
    }
    // 모드별 통제 수준
    var t = el("table", { cls: "ob-lv" }), hr = el("tr", null, [el("th", { text: "통제" }), el("th", { text: "지금" })]);
    M.modes.forEach(function (m) {
      var bt = btn("통제에 넣기", "sm", function () {
        meta.controls.forEach(function (c) { cur.levels[c.id] = Number(j.levels[m][c.id] || 0); });
        renderControls(); say("d-saved", M.mode_ko[m] + " 수준을 통제에 넣었다. 저장을 누르면 반영된다.");
      });
      hr.appendChild(el("th", null, [el("span", { text: M.mode_ko[m] }), el("br"), bt]));
    });
    t.appendChild(el("thead", null, [hr]));
    var tb = el("tbody");
    meta.controls.forEach(function (c) {
      var tr = el("tr", null, [el("td", { text: c.name }), el("td", { cls: "lvw", text: LV_KO[Number(cur.levels[c.id] || 0)] })]);
      M.modes.forEach(function (m) {
        var lv = Number(j.levels[m][c.id] || 0), ids = j.basis[m][c.id] || [], first = byId[ids[0]];
        tr.appendChild(el("td", { cls: "lvw lv" + lv }, [el("span", { text: LV_KO[lv] }),
          first ? el("span", { cls: "basis-art", text: first.article + (ids.length > 1 ? " 외 " + (ids.length - 1) : "") }) : null]));
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    out.appendChild(el("div", { cls: "tblwrap" }, [t]));
    // 적용 조문 표
    out.appendChild(el("h5", { cls: "ob-h5", text: "걸리는 조문" }));
    var t2 = el("table", { cls: "rt-t ob-t" });
    t2.appendChild(el("thead", null, [el("tr", null, ["조문", "강제력", "요구", "통제", "지금 상태"].map(function (h) { return el("th", { text: h }); }))]));
    var tb2 = el("tbody");
    j.applicable.forEach(function (r) {
      var det = el("details", null, [el("summary", { text: "원문" })]);
      if (r.quote) det.appendChild(el("blockquote", { cls: "basis-q", text: r.quote }));
      else det.appendChild(el("p", { cls: "fine", text: "원문 인용을 확인하지 못했다. 요구는 풀어 쓴 것이다." }));
      det.appendChild(el("p", { cls: "fine", text: "인용 확인: " + ({ registry: "문서 코딩에서 원문 대조", primary: "법령 원문", secondary: "법무법인 · 언론 2차 자료", none: "없음" }[r.quote_verified] || r.quote_verified) +
        (r.owner ? " · 흔히 맡는 책무: " + r.owner : "") + " · " + r.reason }));
      if (r.note) det.appendChild(el("p", { cls: "fine", text: r.note }));
      if (r.unless) det.appendChild(el("p", { cls: "fine", text: "해소: " + r.unless }));
      if (r.effective) det.appendChild(el("p", { cls: "fine", text: "시행 · 개정: " + r.effective }));
      var ctl = r.runtime ? ctlName[r.control] + " · " + (r.layer === "agent" ? "AI까지 명시" : r.extends === "direct" ? "행위 규율 (에이전트에도 문언대로)" : "사람·계정" + (r.extends ? " (에이전트는 해석)" : "")) : (r.category || "런타임 밖");
      tb2.appendChild(el("tr", { cls: "ob-" + r.status }, [el("td", null, [obRef(r), det]), el("td", { cls: r.binding ? "bind" : "sub", text: r.force_ko }),
        el("td", { text: r.requires }), el("td", { cls: "sub", text: ctl }), el("td", null, [el("span", { cls: "ob-st " + r.status, text: OB_ST[r.status] || r.status })])]));
    });
    t2.appendChild(tb2);
    out.appendChild(el("div", { cls: "tblwrap" }, [t2]));
    if (j.not_applicable.length) {
      var na = el("details", { cls: "ob-na" }, [el("summary", { text: "걸리지 않는 조문 " + j.not_applicable.length + "개와 이유" })]);
      var ul = el("ul");
      j.not_applicable.forEach(function (r) { ul.appendChild(el("li", null, [obRef(r), " (" + r.force_ko + "): " + r.reason])); });
      na.appendChild(ul);
      out.appendChild(na);
    }
  }
  function linkBlock(link, obs) {
    var box = el("div", { cls: "basis" });
    var stop = link.basis === "stop";
    box.appendChild(el("h6", { text: (stop ? "이 차단을 요구하는 조문: " + STOP_SHORT[link.kind] : "이 에이전트에 걸리는 조문: " + LINK_SHORT[link.kind]) }));
    box.appendChild(el("p", { cls: "basis-h", text: stop ? STOP_KO[link.kind] : LINK_KO[link.kind] }));
    (link.obligations || []).forEach(function (id) {
      var r = obs[id]; if (!r) return;
      box.appendChild(el("p", { cls: "basis-doc" }, [el("span", { cls: "k", text: r.force_ko + (r.binding ? " · 강제" : " · 자율") }), obRef(r)]));
      if (r.quote) box.appendChild(el("blockquote", { cls: "basis-q", text: r.quote }));
    });
    return box;
  }

  // ── 칸 해부: 멈춘 곳 · 최소 처방(같은 엔진으로 반사실 재실행) · 그 관할의 규제 근거 문서 ──
  function jurOf(presetId) { var j = String(presetId || "").split("-")[0]; return (meta.jurisdictions || {})[j] ? j : null; }
  function basisBlock(cid, j, thr) {
    var R = ((meta.regulation || {})[cid] || {})[j] || {}, an = R.analog || { score: 0 }, ag = R.agent || { score: 0 };
    var box = el("div", { cls: "basis" });
    var why = ag.score >= thr ? "이 관할은 AI 층까지 요구한다." :
      ag.score > 0 ? "AI 층은 " + SCORE_KO[ag.score] + " 문서에만 있다. " + (thr >= 2 ? "강제 규제만 지키는 회사에는 비어 있다." : "그 문서까지 지켜야 채워진다.") :
      an.score > 0 ? "사람·계정 층만 다루고 AI 층을 다루는 문서가 없다." : "이 통제를 다루는 문서가 없다.";
    box.appendChild(el("p", { cls: "basis-h" }, [el("b", { text: ctlName[cid] }), ": 사람·계정 층은 " + SCORE_KO[an.score] + ", AI 층은 " + SCORE_KO[ag.score] + ". " + why]));
    [["사람·계정", an], ["AI", ag]].forEach(function (pair) {
      var x = pair[1];
      if (!x.doc) return;
      var link = x.url ? el("a", { href: x.url, target: "_blank", rel: "noopener noreferrer", text: x.title }) : el("span", { text: x.title });
      box.appendChild(el("p", { cls: "basis-doc" }, [el("span", { cls: "k", text: pair[0] + " 근거" }), link]));
      if (x.quote) box.appendChild(el("blockquote", { cls: "basis-q", text: x.quote }));
    });
    if (ag.agent_named) {
      var n = ag.agent_named, l2 = n.url ? el("a", { href: n.url, target: "_blank", rel: "noopener noreferrer", text: n.title }) : el("span", { text: n.title });
      box.appendChild(el("p", { cls: "basis-doc" }, [el("span", { cls: "k", text: "에이전트를 이름으로 다룬 자율 문서" }), l2]));
    }
    return box;
  }
  function renderCellDetail(c, p, cell, opener) {
    var d = $("mx-detail"); clear(d); d.hidden = false;
    var label = colLabel(p), v = cell.verdict || "na";
    var close = btn("닫기", "sm", function () { d.hidden = true; clear(d); if (opener) opener.focus(); });
    d.appendChild(el("div", { cls: "mx-det-h" }, [el("div", null, [el("span", { cls: "k", text: label }), el("h5", { text: c.title })]), close]));
    if (c.story) d.appendChild(el("p", { cls: "story", text: c.story }));
    d.appendChild(el("p", { cls: "verdict-line" }, [el("span", { cls: "vd v-" + v, text: verdictLabel(c.kind, v) }), "  " + (cell.control ? stopText(cell, c.kind) :
      v === "defect" ? "모든 단계가 허용됐다. 막은 통제가 없다." : v === "na" ? "이 에이전트에는 이 공격에 쓸 도구가 없다." : "그대로 처리됐다.")]));
    // 이 규제의 통제 7개 수준 — 멈춘 통제 · 처방 통제를 표시
    var fixes = cell.fixes || [], chips = el("div", { cls: "lv-chips" });
    meta.controls.forEach(function (k) {
      var lv = Number((p.levels || {})[k.id] || 0), cls = "chip lv" + lv + (k.id === cell.control ? " stop" : "") + (fixes.indexOf(k.id) >= 0 ? " fix" : "");
      chips.appendChild(el("span", { cls: cls, title: (k.help || {}).agent || "" }, [el("b", { text: k.name }), " " + LV_KO[lv]]));
    });
    d.appendChild(chips);
    if (c.kind === "attack" && (v === "defect" || v === "held")) {
      d.appendChild(el("h6", { text: "최소 처방" }));
      d.appendChild(el("p", { text: fixes.length
        ? "통제 하나만 AI까지로 올리면 기계가 막는다: " + fixes.map(function (x) { return ctlName[x]; }).join(", ") + ". 같은 정책 엔진으로 다시 돌려 확인한 결과다."
        : "통제 하나를 올려서는 막히지 않는다. 둘 이상을 함께 올려야 한다(예: 탐지와 즉시 중단은 짝이 맞아야 멈춘다)." }));
    }
    if (cell.link && mxData && mxData.obligations) d.appendChild(linkBlock(cell.link, mxData.obligations));
    var j = jurOf(p.preset), thr = /-2$/.test(p.preset) ? 2 : 1;
    var focus = fixes.length ? fixes : (cell.control ? [cell.control] : []);
    if (j) {
      d.appendChild(el("h6", { text: "관할 비교: 이 관할에서 왜 이렇게 됐나" }));
      if (!focus.length) d.appendChild(el("p", { cls: "fine", text: "멈춘 통제가 없다. 이 케이스는 그대로 처리됐다." }));
      else focus.forEach(function (cid) { d.appendChild(basisBlock(cid, j, thr)); });
      d.appendChild(el("p", { cls: "fine", text: "관할 근거는 그 관할에서 이 통제를 가장 세게 다룬 문서 하나와 코딩 근거 인용이다." }));
    } else if (!(mxData && mxData.obligations)) d.appendChild(el("p", { cls: "fine", text: "적용성 프로필을 넣으면 이 결과와 관련된 조문(위반 소지, 해석, 가이드라인, 공백)을 보여 준다." }));
    d.appendChild(el("p", { cls: "fine", text: "조문 대응과 분류는 변호사 검토 전 초안이다. 법률 자문이 아니다." }));
    d.scrollIntoView({ block: "nearest" });
    close.focus();
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
