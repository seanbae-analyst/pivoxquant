"""첫 화면 — out/index.html. 이 연구가 무엇을 재는지, 무엇을 찾았는지, 어디로 가면 되는지.

숫자는 전부 빌드할 때 레지스트리에서 다시 계산한다(문서 · 사건 · κ · 간극 · 모의 테스트) — 손으로 적은 숫자가 없다.
대시보드는 out/dashboard.html(site.py), 모의 테스트는 out/sim.html(sim.py). 자바스크립트 없음.
추천·조언과 '안전합니다' 같은 단정은 쓰지 않는다 — '증거 수준' · '반사실 계산'으로 말한다(제목의 '안전한가'는 연구 질문).
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry import OUT_DIR, SNAPSHOT_DIR

TEMPLATES = Path(__file__).resolve().parent / "templates"
JUR3 = ("KR", "US", "EU")
JUR_KO = {"KR": "한국", "US": "미국", "EU": "EU", "INTL": "국제 권고"}
SCORE_SHORT = {0: "", 1: "자율", 2: "구속", 3: "명시"}
SCORE_KO = {0: "다루지 않음", 1: "자율", 2: "구속력", 3: "구속력 + 에이전트 명시"}
LAYER_KO = {"analog": "사람·계정", "agent": "AI 적용"}
RESULT_KO = {"blocked": "막힘", "reduced": "피해 축소", "damage": "피해 발생", "no_surface": "공격면 없음"}
DECISION = {"prevent": "차단", "limit": "범위 제한", "detect": "기록·탐지", "contain": "멈춤·회수"}
LEVEL_KO = {0: "없음", 1: "사람·계정만", 2: "AI까지"}
# 미리보기 — 실제 사건이 있는 원형 하나를 두 프리셋으로. 없으면 첫 원형.
PREVIEW_SCENARIO, PREVIEW_PROFILE, PREVIEW_PRESETS = "ai_credentials", "support", ("KR-2", "all")


def _e(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _tpl(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def facts(snapshot_dir: Path = SNAPSHOT_DIR) -> dict[str, Any]:
    """랜딩에 싣는 숫자 — 레지스트리 · 코딩 · 사건 조정본 · 모의 테스트에서."""
    from . import agreement as agreement_mod
    from . import incidents as incidents_mod
    from . import kappa as kappa_mod
    from . import matrix as matrix_mod
    from . import sim as sim_mod
    from .registry import load_codings, load_controls, load_documents
    from .schema import independent_v2, primary_coder

    controls = load_controls()
    docs = load_documents()
    codings = load_codings()
    coding = codings[primary_coder(codings)]
    ms = matrix_mod.layer_matrices(docs, controls, coding)
    score = {layer: {j: {c.id: ms[layer][j][c.id].score or 0 for c in controls} for j in JUR_KO} for layer in ("analog", "agent")}
    cells3 = len(JUR3) * len(controls)
    a2 = sum(1 for j in JUR3 for c in controls if score["analog"][j][c.id] >= 2)
    g2 = sum(1 for j in JUR3 for c in controls if score["agent"][j][c.id] >= 2)
    g3 = sum(1 for j in JUR_KO for c in controls if score["agent"][j][c.id] >= 3)
    gaps = {j: sum(1 for jj, cid, _ in matrix_mod.gaps(ms["agent"], controls) if jj == j and score["analog"][j][cid] >= 2) for j in JUR_KO}

    pair = independent_v2(codings)[:2]
    doc_k = {}
    if len(pair) == 2:
        views = kappa_mod.compare(codings[pair[0]], codings[pair[1]], docs, controls)["views"]
        doc_k = {layer: views[layer]["coverage"].kappa for layer in ("analog", "agent")}

    incs = incidents_mod.load_incidents(control_ids={c.id for c in controls})
    raws = agreement_mod.load_incident_codings()
    inc_k = None
    ipair = agreement_mod.independent_incident_v2(raws)
    if len(ipair) >= 2:
        ids = {i.id for i in incs}
        va = agreement_mod.incident_view(raws[ipair[0]], "any", ids)
        vb = agreement_mod.incident_view(raws[ipair[1]], "any", ids)
        common = sorted(set(va) & set(vb))
        inc_k = kappa_mod.cohen_kappa([va[i][c] for i in common for c in agreement_mod.CONTROL_IDS],
                                      [vb[i][c] for i in common for c in agreement_mod.CONTROL_IDS]).kappa
    adj = next((n for n in sorted(raws) if agreement_mod.is_incident_adjudicated(raws[n])), None)
    fails_by_ctl = agreement_mod.consensus_counts(raws[adj], {i.id: i.evidence_level for i in incs}) if adj else {}

    p = sim_mod.payload()
    stage_of = {c["id"]: c["stage"] for c in p["controls"]}
    fails = {i["id"]: i["fails"] for i in p["incidents"]}
    presets = {x["id"]: x for x in p["presets"]}
    replays = {pid: sim_mod.replay(fails, presets[pid]["levels"], stage_of) for pid in ("none", "KR-2", "US-2", "EU-2", "all") if pid in presets}
    judged = next(iter(replays.values()))
    judged = judged["total"] - judged["unknown"]
    try:
        hist = sim_mod.load_history()
    except Exception:
        hist = []
    try:
        from .intel import load_feeds, load_items
        n_feeds = sum(1 for f in load_feeds() if f.get("enabled") is not False)
        n_items = len(load_items(snapshot_dir))
    except Exception:
        n_feeds = n_items = 0
    return {
        "controls": controls, "score": score, "cells3": cells3, "a2": a2, "g2": g2, "g3": g3, "gaps": gaps,
        "n_docs": len(docs), "n_norm": sum(1 for d in docs.values() if d.binding >= 1 and d.status != "superseded"),
        "doc_k": doc_k, "inc_k": inc_k, "n_inc": len(incs), "judged": judged, "fails_by_ctl": fails_by_ctl,
        "n_scn": len(p["scenarios"]), "n_cases": len(p.get("cases") or []), "n_profiles": len(p["agent_profiles"]),
        "n_pending": p["pending"]["count"], "presets": presets, "replays": replays, "hist": hist,
        "n_feeds": n_feeds, "n_items": n_items, "payload": p,
    }


# ── 조각 ──────────────────────────────────────────────────────────────

def _k(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def _mini_matrix(f: dict[str, Any]) -> str:
    head = "<thead><tr><th scope=\"col\">통제</th>" + "".join(
        f'<th scope="col" colspan="2">{_e(JUR_KO[j])}<small>직원 / AI</small></th>' for j in JUR3) + "</tr></thead>"
    rows = []
    for c in f["controls"]:
        tds = [f'<th scope="row">{c.num}. {_e(c.name_ko)}</th>']
        for j in JUR3:
            for layer in ("analog", "agent"):
                s = f["score"][layer][j][c.id]
                tds.append(f'<td class="s{s}{" ai" if layer == "agent" else ""}" title="{_e(JUR_KO[j])} · {LAYER_KO[layer]} 층 — {SCORE_KO[s]}">'
                           f"{SCORE_SHORT[s]}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    return f'<table class="mini">{head}<tbody>{"".join(rows)}</tbody></table>'


def _flow_row(scn: dict[str, Any], levels: dict[str, int], env: dict[str, Any], label: str, names: dict[str, str]) -> str:
    """sim-ui.js의 flowRow와 같은 마크업 — 서버에서 한 번 그린다(랜딩은 스크립트가 없다)."""
    from . import sim as sim_mod
    r = sim_mod.run_scenario(scn, env, levels)
    out = [f'<div class="flow-row"><div class="flow-top"><span class="flow-l">{_e(label)}</span></div>']
    if r["outcome"] == "no_surface":
        return "".join(out) + '<div class="flow-none"><b>시작되지 않음</b></div></div>'
    cols = f"repeat({len(scn['stages'])}, minmax(0,1fr)) 176px"
    out.append(f'<ol class="flow" style="grid-template-columns:{cols}" aria-label="{_e(label)} — 공격 흐름">')
    for idx, st in enumerate(scn["stages"]):
        step = r["steps"][idx] if idx < len(r["steps"]) else None
        if step is None:
            stt = "after"
        elif step["blocked_by"]:
            stt = "stop"
        else:
            stt = "touch" if any(c["on"] for c in step["checks"]) else "pass"
        gates, on = [], []
        for j, c in enumerate(st.get("checks") or []):
            lv = int(levels.get(c["control"], 0))
            o = step["checks"][j]["on"] if step else sim_mod.covers(lv, c["layer"])
            if o and step:
                on.append(DECISION[c["effect"]])
            gates.append(f'<li class="{"on " + c["effect"] if o else "off"}" title="{_e(names[c["control"]])} · {LAYER_KO[c["layer"]]} — {_e(c["why"])}">'
                         f'<i></i><span class="g">{_e(names[c["control"]])} {"AI" if c["layer"] == "agent" else "사람"}</span>'
                         f'<span class="e">{DECISION[c["effect"]] if o else "꺼짐"}</span></li>')
        if not gates:
            gates.append('<li class="none">끼어드는 통제 없음</li>')
        tag = {"stop": "여기서 차단", "after": "도달 안 함", "pass": "통과"}.get(stt) or " · ".join(on)
        out.append(f'<li class="fn {stt}"><div class="fh"><span class="no">{idx + 1}</span><span class="tag">{_e(tag)}</span></div>'
                   f'<div class="ft">{_e(st["title"])}</div><ul class="gates">{"".join(gates)}</ul></li>')
    res = RESULT_KO[r["outcome"]] + (f" · {r['stage']}단계" if r["outcome"] == "blocked" else "")
    fi = ("막지 못했다면: " + r["impact"]) if r["outcome"] == "blocked" else r["impact"]
    out.append(f'<li class="fn end {r["outcome"]}"><div class="fh"><span class="tag">결과</span></div>'
               f'<div class="ft">{_e(res)}</div><p class="fi">{_e(fi)}</p></li></ol></div>')
    return "".join(out)


def _preview(f: dict[str, Any]) -> tuple[str, str]:
    p = f["payload"]
    scns = {s["id"]: s for s in p["scenarios"]}
    profs = {x["id"]: x for x in p["agent_profiles"]}
    s = scns.get(PREVIEW_SCENARIO) or p["scenarios"][0]
    prof = profs.get(PREVIEW_PROFILE) or p["agent_profiles"][0]
    from . import sim as sim_mod
    env = {k: prof.get(k) for k in sim_mod.ENV_KEYS}
    names = {c["id"]: c["name"] for c in p["controls"]}
    rows = "".join(_flow_row(s, f["presets"][pid]["levels"], env, f["presets"][pid]["label"], names)
                   for pid in PREVIEW_PRESETS if pid in f["presets"])
    title = s["title"].split(" →")[0]
    why = (f"실제 사건 {len(s['incidents'])}건이 이 경로였다" if s["incidents"]
           else "위협 목록 " + _e(", ".join(s.get("basis") or [])) + "에서 가져온 원형이다")
    cap = f"'{_e(title)}' 원형을 {_e(prof['label'])}에 대고 두 번 돌린 결과({why})."
    return rows, cap


def _bars(f: dict[str, Any]) -> str:
    rows = []
    for pid in ("none", "KR-2", "US-2", "EU-2", "all"):
        if pid not in f["replays"]:
            continue
        r, j = f["replays"][pid], f["judged"] or 1
        rng = str(r["blocked_hi"]) if r["blocked_lo"] == r["blocked_hi"] else f"{r['blocked_lo']}~{r['blocked_hi']}"
        rows.append(f'<dt>{_e(f["presets"][pid]["label"])}</dt><dd><span class="track" role="img" aria-label="막혔을 사건 {rng} / {f["judged"]}">'
                    f'<span class="hi" style="width:{100 * r["blocked_hi"] / j:.1f}%"></span>'
                    f'<span class="lo" style="width:{100 * r["blocked_lo"] / j:.1f}%"></span></span></dd><dd class="n">{rng}건</dd>')
    return '<dl class="bars">' + "".join(rows) + "</dl>"


def _method(f: dict[str, Any]) -> str:
    """방법 — 단계 · 하는 일 · 누가 · 지금 규모. 숫자는 레지스트리에서."""
    dk, nk = f["doc_k"], f["inc_k"]
    rows = [
        ("수집", "규제기관, 표준기구, 보안 회사의 공개 피드를 읽는다.", "자동", f"피드 {f['n_feeds']}곳, 항목 {f['n_items']}건"),
        ("후보", "AI 에이전트와 관련된 새 규제와 가이드라인을 점수로 골라 둔다.", "자동", f"반영 대기 {f['n_pending']}건"),
        ("등록", "후보 중 연구에 넣을 문서를 고르고 원문을 고정한다.", "사람", f"문서 {f['n_docs']}건(규범 문서 {f['n_norm']}건)"),
        ("판정", "서로 결과를 보지 않는 두 팀이 통제 7개를 직원·계정과 AI 두 층으로 판정하고, 갈린 칸만 조정한다.", "AI 코더 두 팀",
         f"κ 문서 {_k(dk.get('analog'))}(직원·계정), {_k(dk.get('agent'))}(AI) / 사건 {_k(nk)}"),
        ("매트릭스", "관할마다 통제별로 가장 센 문서의 수준을 모은다.", "계산", f"간극 {sum(f['gaps'][j] for j in JUR3)}칸"),
        ("모의 테스트", "공격 원형을 단계별로 돌리고, 공개 사건을 반사실로 다시 계산한다.", "계산", f"원형 {f['n_scn']}개, 사건 {f['n_inc']}건, 이력 {len(f['hist'])}줄"),
    ]
    body = "".join(f'<tr><td class="n">{k}</td><th scope="row">{_e(t)}</th><td>{_e(d)}</td><td class="who">{_e(w)}</td><td class="now">{_e(x)}</td></tr>'
                   for k, (t, d, w, x) in enumerate(rows, 1))
    return ('<table class="method"><thead><tr><th scope="col" class="n"></th><th scope="col">단계</th><th scope="col">하는 일</th>'
            '<th scope="col">누가</th><th scope="col">지금</th></tr></thead><tbody>' + body + "</tbody></table>")


def build(out_dir: Path = OUT_DIR, snapshot_dir: Path = SNAPSHOT_DIR, now: datetime | None = None) -> Path:
    f = facts(snapshot_dir)
    now = now or datetime.now(timezone.utc)
    ctl = {c.id: c for c in f["controls"]}
    top = sorted(f["fails_by_ctl"].items(), key=lambda kv: -kv[1]["total"])
    top_txt = (f"{ctl[top[0][0]].name_ko}({top[0][1]['total']}건)" + (f"과 {ctl[top[1][0]].name_ko}({top[1][1]['total']}건)" if len(top) > 1 else "")
               if top and top[0][1]["total"] else "확인되지 않았다")
    gaps = f["gaps"]
    r = f["replays"]

    def rng(pid: str) -> str:
        x = r.get(pid)
        if not x:
            return "—"
        return str(x["blocked_hi"]) if x["blocked_lo"] == x["blocked_hi"] else f"{x['blocked_lo']}~{x['blocked_hi']}"

    preview, preview_cap = _preview(f)
    repl = {
        "TOKENS_CSS": _tpl("tokens.css"), "BASE_CSS": _tpl("base.css"), "FLOW_CSS": _tpl("flow.css"), "LANDING_CSS": _tpl("landing.css"),
        "BUILT_AT_ISO": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "BUILT_AT": f"{now.year}년 {now.month}월 {now.day}일",
        "N_DOCS": str(f["n_docs"]), "N_NORM": str(f["n_norm"]), "N_INC": str(f["n_inc"]), "JUDGED": str(f["judged"]),
        "N_SCN": str(f["n_scn"]), "N_CASES": str(f["n_cases"]), "N_PROFILES": str(f["n_profiles"]),
        "CELLS3": str(f["cells3"]), "A2": str(f["a2"]), "G2": str(f["g2"]), "G3": str(f["g3"]),
        "GAPS": str(sum(gaps[j] for j in JUR3)), "GAPS_KR": str(gaps["KR"]), "GAPS_US": str(gaps["US"]), "GAPS_EU": str(gaps["EU"]),
        "INC_K": _k(f["inc_k"]), "TOP_FAILS": _e(top_txt),
        "R_KR": rng("KR-2"), "R_US": rng("US-2"), "R_EU": rng("EU-2"), "R_ALL": rng("all"),
        "MINI": _mini_matrix(f), "PREVIEW": preview, "PREVIEW_CAP": preview_cap, "BARS": _bars(f), "METHOD": _method(f),
    }
    page = _tpl("landing.html")
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    page = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: repl.get(m.group(1), m.group(0)), page)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "index.html"
    p.write_text(page, encoding="utf-8")
    return p
