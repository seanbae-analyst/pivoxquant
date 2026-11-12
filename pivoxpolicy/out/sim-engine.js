/* sim-engine.js — 모의 테스트 계산. pivoxpolicy/sim.py 의 run_scenario · replay_one · replay · best_next ·
   asi_coverage · improvement_actions 를 그대로 옮긴 것. 규칙을 바꾸면 sim.py 도 같이 바꾼다 —
   tests/test_sim.py 가 node 로 두 구현의 결과를 대조한다. 화면 코드 없음(toCSV 만 파이썬 짝이 없는 내보내기 도우미). */
(function (root) {
  "use strict";

  function covers(level, layer) {
    return level >= (layer === "agent" ? 2 : 1);
  }

  function runScenario(scn, env, levels) {
    var missing = (scn.requires || []).filter(function (r) { return !env[r]; });
    var imp = scn.impact || {};
    var impact = imp.fixed || ((imp.by_tools || {})[env.tools || "read"] || "");
    var steps = [];
    if (missing.length) {
      return { outcome: "no_surface", stage: 0, missing: missing, steps: steps, impact: impact,
               limited_by: [], detected_at: null, contained: null };
    }
    var limitedBy = [], detectedAt = null, contained = null;
    var stages = scn.stages || [];
    for (var k = 1; k <= stages.length; k++) {
      var st = stages[k - 1], checks = [], blockedBy = null;
      (st.checks || []).forEach(function (c) {
        var on = covers(Number(levels[c.control] || 0), c.layer);
        checks.push({ control: c.control, layer: c.layer, effect: c.effect, on: on });
        if (!on) return;
        if (c.effect === "prevent" && blockedBy === null) blockedBy = c.control;
        else if (c.effect === "limit") limitedBy.push(c.control);
        else if (c.effect === "detect" && detectedAt === null) detectedAt = k;
        else if (c.effect === "contain") contained = detectedAt !== null ? "early" : "late";
      });
      steps.push({ stage: k, checks: checks, blocked_by: blockedBy });
      if (blockedBy) {
        return { outcome: "blocked", stage: k, missing: [], steps: steps, impact: impact,
                 limited_by: limitedBy, detected_at: detectedAt, contained: contained };
      }
    }
    var reduced = limitedBy.length > 0 || contained === "early";
    return { outcome: reduced ? "reduced" : "damage", stage: steps.length, missing: [], steps: steps, impact: impact,
             limited_by: limitedBy, detected_at: detectedAt, contained: contained };
  }

  function replayOne(fails, levels, stageOf, statedOnly) {
    var fs = statedOnly ? fails.filter(function (f) { return f.level === "stated"; }) : fails.slice();
    if (!fs.length) return "unknown";
    var cov = fs.filter(function (f) { return covers(Number(levels[f.control] || 0), f.layer); });
    var early = cov.filter(function (f) { return stageOf[f.control] !== "after"; });
    if (early.length && cov.length === fs.length) return "blocked";
    if (early.length) return "blocked_maybe";
    if (cov.length) return "reduced";
    return "unchanged";
  }

  function replay(failures, levels, stageOf, statedOnly) {
    var per = {}, n = { blocked: 0, blocked_maybe: 0, reduced: 0, unchanged: 0, unknown: 0 };
    Object.keys(failures).sort().forEach(function (iid) {
      var v = replayOne(failures[iid], levels, stageOf, !!statedOnly);
      per[iid] = v; n[v] += 1;
    });
    return { per: per, blocked_lo: n.blocked, blocked_hi: n.blocked + n.blocked_maybe, reduced: n.reduced,
             unchanged: n.unchanged, unknown: n.unknown, total: Object.keys(per).length };
  }

  function bestNext(failures, levels, stageOf, statedOnly) {
    var base = replay(failures, levels, stageOf, statedOnly).blocked_hi, out = [];
    Object.keys(levels).sort().forEach(function (c) {
      if (levels[c] >= 2) return;
      var up = Object.assign({}, levels); up[c] = 2;
      out.push([c, replay(failures, up, stageOf, statedOnly).blocked_hi - base]);
    });
    out.sort(function (a, b) { return b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0); });
    return out;
  }

  var ASI_RE = /\bOWASP (ASI\d{2})\b/g;
  function asiOf(scn) {
    var seen = {};
    (scn.basis || []).forEach(function (b) {
      String(b).replace(ASI_RE, function (_, a) { seen[a] = true; return _; });
    });
    return Object.keys(seen).sort();
  }

  function asiCoverage(scenarios, env, levels, catalog) {
    return catalog.map(function (item) {
      var rows = scenarios.filter(function (s) { return asiOf(s).indexOf(item.id) >= 0; })
        .map(function (s) { return { id: s.id, outcome: runScenario(s, env, levels).outcome }; });
      var live = rows.filter(function (r) { return r.outcome !== "no_surface"; });
      var status = !rows.length ? "none" : !live.length ? "na"
        : live.every(function (r) { return r.outcome === "blocked"; }) ? "full"
        : live.every(function (r) { return r.outcome === "damage"; }) ? "gap" : "partial";
      return { id: item.id, status: status, scenarios: rows };
    });
  }

  function improvementActions(scenarios, env, failures, levels, stageOf, statedOnly) {
    var baseR = replay(failures, levels, stageOf, statedOnly), baseS = {}, out = [];
    scenarios.forEach(function (s) { baseS[s.id] = runScenario(s, env, levels).outcome; });
    Object.keys(levels).sort().forEach(function (c) {
      if (levels[c] >= 2) return;
      var up = Object.assign({}, levels); up[c] = 2;
      var r = replay(failures, up, stageOf, statedOnly), changed = [];
      scenarios.forEach(function (s) {
        var o = runScenario(s, env, up).outcome;
        if (o !== baseS[s.id]) changed.push({ id: s.id, from: baseS[s.id], to: o });
      });
      out.push({ control: c, from: Number(levels[c]), inc_lo: r.blocked_lo - baseR.blocked_lo,
                 inc_hi: r.blocked_hi - baseR.blocked_hi, scenarios: changed });
    });
    out.sort(function (a, b) {
      return b.inc_lo - a.inc_lo || b.inc_hi - a.inc_hi || b.scenarios.length - a.scenarios.length ||
        (a.control < b.control ? -1 : a.control > b.control ? 1 : 0);
    });
    return out;
  }

  // CSV — 엑셀이 한글을 읽게 BOM, 줄 끝 CRLF. 수식으로 읽힐 글(= + - @ 탭 CR 로 시작)은 앞에 ' 를 붙인다(CSV 수식 주입).
  function csvCell(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "number") return String(v);
    var t = String(v);
    if (/^[=+\-@\t\r]/.test(t)) t = "'" + t;
    return /[",\r\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
  }
  function toCSV(rows) {
    return "\ufeff" + rows.map(function (r) { return r.map(csvCell).join(","); }).join("\r\n") + "\r\n";
  }

  var api = { covers: covers, runScenario: runScenario, replayOne: replayOne, replay: replay, bestNext: bestNext,
              asiOf: asiOf, asiCoverage: asiCoverage, improvementActions: improvementActions, toCSV: toCSV };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PivoxSimEngine = api;
})(this);
