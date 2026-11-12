/* sim-engine.js — 모의 테스트 계산. pivoxpolicy/sim.py 의 run_scenario · replay_one · replay · best_next 를 그대로 옮긴 것.
   규칙을 바꾸면 sim.py 도 같이 바꾼다 — tests/test_sim.py 가 node 로 두 구현의 결과를 대조한다. 화면 코드 없음. */
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

  var api = { covers: covers, runScenario: runScenario, replayOne: replayOne, replay: replay, bestNext: bestNext };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PivoxSimEngine = api;
})(this);
