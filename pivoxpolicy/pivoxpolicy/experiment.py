"""실험 — 합성 에이전트 유형 × 규제 기준. 논문 표와 그림을 만든다.

설계
  에이전트 유형: registry/experiment_agents.yaml(증권사의 대표적인 에이전트 자리 일곱 곳, 하는 일 · 정보 · 배포 형태를 고정)
  규제 기준: 통제 없음(기준선) · 명문 기준 · 확장 해석 기준 · 자율규범 포함 기준 · 모든 통제 AI 수준(기준선).
             가운데 셋은 그 유형에 걸리는 조문(obligations)에서 도출한 통제 수준이다.
  시나리오: 각 유형의 실제 도구로 만든 공격 · 정상 업무 시나리오(intake.generate_cases). 같은 정책 엔진 샌드박스로 돈다.
지표
  공격: 자동 차단 · 승인 의존 · 미차단 · 공격면 없음 / 정상 업무: 정상 처리 · 승인 대기 · 과잉 차단
  해석 의존: 명문 기준과 확장 해석 기준 사이에서 판정이 바뀌는 공격 시나리오
  승인자 오판 민감도: 승인 의존 시나리오를 승인자가 확률 p 로 잘못 승인할 때의 기대 미차단 = 미차단 + p × 승인 의존
  공격 유형별: 같은 공격 유형(terms.SCENARIO)끼리 묶은 판정 — 어떤 공격이 해석에 달려 있는지
  적용성: 걸리는 조문 · 강제 조문 · AI 명시 또는 행위 규율 강제 조문 · 구성상 저촉 · 명문 기준이 AI 수준까지 요구하는 통제 수
재현: 결과는 결정적이다(난수 없음). manifest 에 의무 라이브러리 기준일 · 조문 수 · 에이전트 정의 지문 · 시나리오 지문 · 도구 버전을 남긴다.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import flow, intake, terms
from . import obligations as obl
from .registry import OUT_DIR, REGISTRY_DIR
from .runtime import cases as cases_mod
from .runtime import policy

AGENTS_PATH = REGISTRY_DIR / "experiment_agents.yaml"
READINGS = ("none", "binding_explicit", "binding_interpretive", "guideline", "all")
READING_KO = {"none": "통제 없음", **terms.MODE, "all": "모든 통제 AI 수준"}
ATTACK_KEYS = ("good", "held", "defect", "na")
BENIGN_KEYS = ("good", "approval", "overblock")
P_GRID = (0.0, 0.05, 0.1, 0.3)
SCENARIO_ORDER = ("prompt_injection", "approval_exploitation", "insider_misuse", "rogue_agent", "multi_agent_cascade",
                  "supply_chain", "ai_credentials", "cross_customer_leak")
ACT_SHORT = {"order": "주문", "transfer": "이체 · 정산", "advice": "투자 권유", "customer_service": "고객 응대",
             "credit": "신용공여", "internal": "내부 업무", "code": "코드 실행"}
LLM_SHORT = {"onprem": "사내 설치", "domestic_cloud": "국내 클라우드", "foreign_api": "해외 API"}


def load_agents(path: Path = AGENTS_PATH) -> list[dict[str, Any]]:
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("agents") or []


def _hash(obj: Any) -> str:
    return hashlib.sha256(policy.canonical(obj).encode("utf-8")).hexdigest()[:16]


def _git_rev() -> str:
    from .diagnosis import _git_rev as g
    return g()


def _prepare(a: dict[str, Any], lib: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, dict[str, int]]]:
    """유형 하나 → (intake 결과, 조문 평가, 샌드박스 에이전트, 기준별 통제 수준)."""
    b = intake.build(a["spec"])
    A = obl.assess(lib, b["compliance"])
    base = {"id": f"agt_exp{a['id'].lower()}", "status": "active", "expires_at": None, **b["agent"]}
    lv = {"none": {c: 0 for c in policy.CONTROL_ORDER}, "all": {c: 2 for c in policy.CONTROL_ORDER}, **A["levels"]}
    return b, A, base, lv


def flows(path: Path = AGENTS_PATH, readings: tuple[str, ...] = ("binding_explicit", "binding_interpretive")) -> dict[str, dict[str, Any]]:
    """명령 흐름 그림용 — 유형마다 시나리오별로 기준마다 run_case 결과(단계별 판정 checks 포함). run() 과 같은 준비 · 같은 엔진."""
    lib = obl.load_library()
    out = {}
    for a in load_agents(path):
        b, A, base, lv = _prepare(a, lib)
        out[a["id"]] = {"label": a["label"], "levels": {rd: lv[rd] for rd in readings},
                        "cases": [(c, {rd: cases_mod.run_case({**base, "levels": lv[rd]}, c, b["components"]) for rd in readings})
                                  for c in b["cases"]]}
    return out


def run(path: Path = AGENTS_PATH, readings: tuple[str, ...] = READINGS, p_grid: tuple[float, ...] = P_GRID) -> dict[str, Any]:
    lib = obl.load_library()
    specs = load_agents(path)
    agents = []
    for a in specs:
        b, A, base, lv = _prepare(a, lib)
        per: dict[str, Any] = {}
        verdicts: dict[str, dict[str, str]] = {}
        scn = {c["id"]: c["scenario"] for c in b["cases"]}
        for rd in readings:
            res = cases_mod.run_cases({**base, "levels": lv[rd]}, b["cases"], b["components"])
            att = [r for r in res["results"] if r["kind"] == "attack"]
            ben = [r for r in res["results"] if r["kind"] == "benign"]
            m = {k: sum(1 for r in att if r["verdict"] == k) for k in ATTACK_KEYS}
            m.update({f"benign_{k}": 0 for k in BENIGN_KEYS})
            for r in ben:
                key = "good" if r["verdict"] == "good" else (terms.benign_key(r["control"]) if r["verdict"] == "friction" else None)
                if key:
                    m[f"benign_{key}"] += 1
            m["ai_controls"] = sum(1 for v in lv[rd].values() if v == 2)
            m["attacks"] = len(att)
            m["exposure"] = {str(p): round(m["defect"] + p * m["held"], 3) for p in p_grid}
            per[rd] = m
            verdicts[rd] = {r["id"]: r["verdict"] for r in att}
        dep = sorted(cid for cid in verdicts.get("binding_explicit", {})
                     if verdicts["binding_explicit"][cid] != verdicts.get("binding_interpretive", {}).get(cid))
        app = A["applicable"]
        agents.append({
            "id": a["id"], "label": a["label"], "profile": b["compliance"], "high_impact": A["high_impact"]["value"],
            "applicable": len(app), "binding": sum(r["binding"] for r in app),
            "binding_ai": sum(1 for r in app if r["binding"] and (r.get("layer") == "agent" or r.get("extends") == "direct")),
            "conflict": sum(1 for r in app if r.get("prohibits")), "offline": sum(1 for r in app if not r["runtime"]),
            "conflicts": [f"{r['doc']} {r['article']}" for r in app if r.get("prohibits")],
            "explicit_ai_controls": [c for c, v in A["levels"]["binding_explicit"].items() if v == 2],
            "explicit_basis": {c: A["basis"]["binding_explicit"][c] for c, v in A["levels"]["binding_explicit"].items() if v == 2},
            "levels": {rd: lv[rd] for rd in readings}, "readings": per, "interpretation_dependent": dep,
            "attack_cases": [{"id": cid, "scenario": scn.get(cid), "verdicts": {rd: verdicts[rd][cid] for rd in readings}}
                             for cid in sorted(verdicts[readings[0]])],
            "cases": len(b["cases"]), "case_hash": _hash(b["cases"]), "tools": len(b["tools"])})
    agg = {rd: {k: sum(x["readings"][rd][k] for x in agents) for k in (*ATTACK_KEYS, *(f"benign_{k}" for k in BENIGN_KEYS), "attacks")}
           for rd in readings}
    for rd in readings:
        agg[rd]["exposure"] = {str(p): round(agg[rd]["defect"] + p * agg[rd]["held"], 3) for p in p_grid}
    return {"agents": agents, "aggregate": agg, "readings": list(readings), "p_grid": list(p_grid),
            "manifest": {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "tool_rev": _git_rev(),
                         "library_as_of": str(lib.get("as_of")), "obligations": len(lib.get("obligations") or []),
                         "reviewed_by_counsel": bool(lib.get("reviewed_by_counsel")), "agents_hash": _hash(specs),
                         "case_hashes": {x["id"]: x["case_hash"] for x in agents}}}


# ── 요약 문장(숫자에서 만든다) ──

def findings(R: dict[str, Any]) -> list[str]:
    ag, A = R["aggregate"], R["agents"]
    n = ag["binding_explicit"]["attacks"]
    pct = lambda a, b: f"{(100 * a / b):.0f}%" if b else "—"  # noqa: E731
    e, i, g = ag["binding_explicit"], ag["binding_interpretive"], ag["guideline"]
    none_ai = [x["label"] for x in A if not x["explicit_ai_controls"]]
    some_ai = [f"{x['label']}({', '.join(terms_name(c) for c in x['explicit_ai_controls'])})" for x in A if x["explicit_ai_controls"]]
    dep = sum(len(x["interpretation_dependent"]) for x in A)
    out = [
        f"에이전트 유형 {len(A)}개, 공격 시나리오 {n}개. 명문 기준만 따르면 미차단 {e['defect']}개({pct(e['defect'], n)}), 승인 의존 {e['held']}개({pct(e['held'], n)}), "
        f"자동 차단 {e['good']}개({pct(e['good'], n)})다.",
        f"확장 해석 기준에서는 미차단 {i['defect']}개, 승인 의존 {i['held']}개, 자율규범 포함 기준에서는 미차단 {g['defect']}개, 승인 의존 {g['held']}개다.",
        f"명문 기준이 어떤 통제도 AI 수준까지 요구하지 않는 유형이 {len(none_ai)}개다({', '.join(none_ai)}). "
        f"AI 수준 요구가 생기는 유형은 {', '.join(some_ai) or '없음'}이다.",
        f"판정이 명문 기준과 확장 해석 기준 사이에서 바뀌는 공격 시나리오(해석 의존)는 {dep}개({pct(dep, n)})다. "
        "사람·계정을 대상으로 쓴 조문을 에이전트에도 적용하느냐가 결과를 가른다.",
    ]
    p = R["p_grid"]
    if len(p) > 1:
        hi = str(p[-1])
        out.append(f"승인자가 승인 의존 시나리오의 {int(float(hi) * 100)}%를 잘못 승인한다고 가정하면 명문 기준의 기대 미차단은 {e['exposure'][hi]}개다.")
    sc = by_scenario(R)
    fully = [terms.SCENARIO.get(k, k) for k, v in sc.items() if v["n"] and v["dep"] == v["n"]]
    if fully:
        from .diagnosis import _josa
        out.append(f"공격 유형 가운데 {_josa(', '.join(fully), '은', '는')} 모든 시나리오의 판정이 명문 기준과 확장 해석 기준 사이에서 바뀐다.")
    cf = [x["label"] for x in A if x["conflict"]]
    if cf:
        out.append(f"구성상 저촉은 외부 클라우드 · 해외 API 모델을 쓰는 유형 {len(cf)}개({', '.join(cf)})에서 나타난다. 통제 수준과 상관없이 구성을 바꾸거나 예외 사유가 있어야 한다.")
    return out


# ── 그림(HTML · CSS, 스크립트 없음) ──
# SVG viewBox 로 그리면 폰에서 글자가 화면 폭에 비례해 줄어든다(390px 폭에서 5.4px). 막대도 글자도 HTML 로 그려 글자 크기를 고정한다.
# 색은 노출 정도의 순서 척도(한 색상, 밝을수록 노출): 자동 차단 #5E4A31 → 승인 의존 #B8956A → 미차단 #F5F0E8
# (dataviz validate_palette --ordinal --mode dark --surface #050505 통과). 정의는 flow.CSS 의 .v-* 와 같다.

LBL = {"good": "자동 차단", "held": "승인 의존", "defect": "미차단", "na": "공격면 없음"}


def segbar(parts: list[tuple[str, int]], total: int, min_share: float = 0.08, cls: str = "sb") -> str:
    """하나의 전체(공격 시나리오 수)를 판정별로 나눈 막대. 칸이 넉넉할 때만 칸 안에 수를 적는다(나머지는 title · 표)."""
    segs = []
    for k, v in parts:
        if not v:
            continue
        lab = str(v) if total and v / total >= min_share else ""
        segs.append(f'<span class="v-{k}" style="flex-grow:{v}" title="{LBL[k]} {v}">{lab}</span>')
    aria = ", ".join(f"{LBL[k]} {v}" for k, v in parts if v) + f" (전체 {total})"
    return f'<div class="{cls}" role="img" aria-label="{html.escape(aria)}">' + "".join(segs) + "</div>"


def figure_aggregate(R: dict[str, Any]) -> str:
    """그림: 규제 기준별 공격 시나리오 판정(전체 유형 합)."""
    rows = R["readings"]
    total = R["aggregate"][rows[0]]["attacks"]
    dep = sum(len(x["interpretation_dependent"]) for x in R["agents"])
    out = ['<div class="agg">']
    for rd in rows:
        a = R["aggregate"][rd]
        cur = " is-key" if rd == "binding_explicit" else ""
        out.append(f'<div class="agg-row{cur}"><span class="agg-l">{html.escape(READING_KO[rd])}</span>'
                   + segbar([(k, a[k]) for k in ATTACK_KEYS], total)
                   + f'<span class="agg-v"><b>{a["defect"]}</b> 미차단</span></div>')
        if rd == "binding_explicit" and "binding_interpretive" in rows:
            out.append(f'<p class="agg-note">명문 기준과 확장 해석 기준 사이에서 판정이 바뀌는 시나리오 {dep}개(해석 의존)</p>')
    out.append(f'<p class="agg-foot">막대 하나 = 공격 시나리오 {total}개(유형 {len(R["agents"])}개 합)</p></div>')
    return "".join(out)


def figure_agents(R: dict[str, Any]) -> str:
    """그림: 유형별 × 기준별 작은 막대(명문 · 확장 해석 · 자율규범 포함). 폰에서는 유형마다 세 줄로 쌓는다."""
    rds = [r for r in ("binding_explicit", "binding_interpretive", "guideline") if r in R["readings"]]
    out = ['<div class="am"><div class="am-row am-head"><span></span>' + "".join(f"<span>{html.escape(READING_KO[r])}</span>" for r in rds) + "</div>"]
    for x in R["agents"]:
        cells = "".join(f'<div class="am-cell" data-r="{html.escape(READING_KO[rd])}">'
                        + segbar([(k, x["readings"][rd][k]) for k in ATTACK_KEYS], x["readings"][rd]["attacks"], 0.18, "sb sb-s") + "</div>"
                        for rd in rds)
        out.append(f'<div class="am-row"><span class="am-l"><b>{html.escape(x["id"])}</b> {html.escape(x["label"])}'
                   f'<small>공격 {x["readings"][rds[0]]["attacks"]}개</small></span>{cells}</div>')
    out.append("</div>")
    return "".join(out)


def legend() -> str:
    return '<p class="key">' + "".join(f'<span><i class="v-{k}"></i>{LBL[k]}</span>' for k in ATTACK_KEYS) + "</p>"


def _featured(F: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """그림에 크게 싣는 흐름 두 개 — 해석 의존의 두 갈래(명문 기준에서 미차단 / 승인 의존 → 확장 해석 기준에서 자동 차단).
    손으로 고르지 않고 규칙으로 고른다: 유형 순서대로 처음 나오는 것, 미차단 쪽은 간접 프롬프트 주입을 먼저."""
    pick = []
    for want, pref in (("defect", "prompt_injection"), ("held", None)):
        cands = [(aid, c, rs) for aid, f in F.items() for c, rs in f["cases"]
                 if c.get("kind", "attack") == "attack" and rs["binding_explicit"]["verdict"] == want
                 and rs["binding_interpretive"]["verdict"] == "good"]
        cands.sort(key=lambda t: (t[1].get("scenario") != pref, list(F).index(t[0])))
        if cands:
            pick.append(cands[0])
    return pick


def _ai_sub(levels: dict[str, int]) -> str:
    on = [terms_name(c) for c, v in levels.items() if v == 2]
    return "AI 수준 통제: " + (", ".join(on) if on else "없음")


def flow_figures(F: dict[str, dict[str, Any]], start: int) -> tuple[str, int]:
    """대표 흐름 그림(그림 start, start+1 …)."""
    out, n = [], start
    for aid, c, rs in _featured(F):
        f = F[aid]
        lanes = [(READING_KO[rd], _ai_sub(f["levels"][rd]), rs[rd]) for rd in ("binding_explicit", "binding_interpretive")]
        vl = terms.verdict_label("attack", rs["binding_explicit"]["verdict"])
        out.append(f'<figure class="fig flowfig"><figcaption><b>그림 {n}</b> 명령 한 건의 흐름. {html.escape(aid + " " + f["label"])}. '
                   f'명문 기준에서는 {html.escape(vl)}, 확장 해석 기준에서는 자동 차단이다. 칸은 정책 엔진이 실제로 남긴 단계별 판정이다.</figcaption>'
                   + flow.compare(c, lanes) + "</figure>")
        n += 1
    return "".join(out), n


def flow_catalog(F: dict[str, dict[str, Any]]) -> str:
    """시나리오 전체의 흐름 — 유형마다 접어 둔다(스크립트 없는 details)."""
    out = []
    for aid, f in F.items():
        items = []
        for c, rs in f["cases"]:
            ve, vi = (terms.verdict_label(c.get("kind", "attack"), rs[rd]["verdict"], rs[rd].get("control"))
                      for rd in ("binding_explicit", "binding_interpretive"))
            lanes = [(READING_KO[rd], _ai_sub(f["levels"][rd]), rs[rd]) for rd in ("binding_explicit", "binding_interpretive")]
            tag = "정상 업무" if c.get("kind") == "benign" else "공격"
            items.append(f'<details class="fc-case"><summary><span class="fc-t">{html.escape(c.get("title") or c["id"])}</span>'
                         f'<span class="fc-v">{tag} · 명문 {html.escape(ve)} → 확장 해석 {html.escape(vi)}</span></summary>'
                         + flow.compare(c, lanes, title="") + "</details>")
        out.append(f'<details class="fc-agent"><summary><b>{html.escape(aid)} {html.escape(f["label"])}</b><span>시나리오 {len(f["cases"])}개</span></summary>'
                   + "".join(items) + "</details>")
    return '<div class="fc">' + "".join(out) + "</div>"


# ── 표 ──

def by_scenario(R: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """공격 유형별 합: n(시나리오 수), 기준마다 판정 수, dep(해석 의존 수)."""
    out: dict[str, dict[str, Any]] = {}
    for x in R["agents"]:
        dep = set(x["interpretation_dependent"])
        for c in x["attack_cases"]:
            k = c["scenario"] or "?"
            d = out.setdefault(k, {"n": 0, "dep": 0, **{rd: {v: 0 for v in ATTACK_KEYS} for rd in R["readings"]}})
            d["n"] += 1
            d["dep"] += c["id"] in dep
            for rd, v in c["verdicts"].items():
                d[rd][v] += 1
    order = {k: i for i, k in enumerate(SCENARIO_ORDER)}
    return dict(sorted(out.items(), key=lambda kv: order.get(kv[0], 99)))


def tables(R: dict[str, Any]) -> list[tuple[str, list[str], list[list[str]]]]:
    A, rds = R["agents"], R["readings"]
    mid = [r for r in ("binding_explicit", "binding_interpretive", "guideline") if r in rds]
    t1 = ("표 1. 에이전트 유형별 적용 조문. 강제는 걸리는 조문 가운데 강제 조문, AI 수준 강제는 그 가운데 AI를 명시하거나 행위 자체를 규율하는 조문이다.",
          ["유형", "하는 일", "모델", "걸리는 조문", "강제", "AI 수준 강제", "구성상 저촉", "명문 기준의 AI 수준 통제", "고영향 AI"],
          [[f"{x['id']} {x['label']}", ", ".join(ACT_SHORT.get(a, a) for a in x["profile"]["activities"]),
            LLM_SHORT.get(x["profile"]["external_llm"], x["profile"]["external_llm"] or ""),
            str(x["applicable"]), str(x["binding"]), str(x["binding_ai"]), str(x["conflict"]),
            ", ".join(terms_name(c) for c in x["explicit_ai_controls"]) or "없음", "추정 해당" if x["high_impact"] else "아님"] for x in A])
    t2 = ("표 2. 유형별 미차단 / 승인 의존. 칸은 '미차단 수 / 승인 의존 수'이다.", ["유형"] + [READING_KO[rd] for rd in rds] + ["해석 의존"],
          [[f"{x['id']} {x['label']}"] + [f"{x['readings'][rd]['defect']} / {x['readings'][rd]['held']}" for rd in rds]
           + [str(len(x["interpretation_dependent"]))] for x in A])
    sc = by_scenario(R)
    t3 = ("표 3. 공격 유형별 판정(유형 합). 칸은 '미차단 수 / 승인 의존 수'이다.", ["공격 유형", "시나리오"] + [READING_KO[rd] for rd in mid] + ["해석 의존"],
          [[terms.SCENARIO.get(k, k), str(v["n"])] + [f"{v[rd]['defect']} / {v[rd]['held']}" for rd in mid] + [str(v["dep"])] for k, v in sc.items()])
    t4 = ("표 4. 규제 기준별 시나리오 판정(유형 합)", ["기준", "자동 차단", "승인 의존", "미차단", "공격면 없음", "정상 처리", "승인 대기", "과잉 차단"],
          [[READING_KO[rd]] + [str(R["aggregate"][rd][k]) for k in ATTACK_KEYS] + [str(R["aggregate"][rd][f"benign_{k}"]) for k in BENIGN_KEYS] for rd in rds])
    t5 = ("표 5. 승인자 오판 민감도. 기대 미차단 = 미차단 + p × 승인 의존(유형 합)", ["기준"] + [f"p = {p}" for p in R["p_grid"]],
          [[READING_KO[rd]] + [str(R["aggregate"][rd]["exposure"][str(p)]) for p in R["p_grid"]] for rd in rds])
    return [t1, t2, t3, t4, t5]


def _dep_names(x: dict[str, Any]) -> list[str]:
    """해석 의존 시나리오를 공격 유형 이름으로(같은 유형은 개수로 묶는다)."""
    scn = {c["id"]: c["scenario"] for c in x["attack_cases"]}
    cnt: dict[str, int] = {}
    for cid in x["interpretation_dependent"]:
        k = scn.get(cid) or "?"
        cnt[k] = cnt.get(k, 0) + 1
    order = {k: i for i, k in enumerate(SCENARIO_ORDER)}
    return [terms.SCENARIO.get(k, k) + (f" {n}" if n > 1 else "") for k, n in sorted(cnt.items(), key=lambda kv: order.get(kv[0], 99))]


@functools.lru_cache(maxsize=1)
def _ctl_names() -> dict[str, str]:
    from .diagnosis import _controls
    return {c["id"]: c["name"] for c in _controls()}


def terms_name(cid: str) -> str:
    return _ctl_names().get(cid, cid)


# ── 쓰기 ──

def to_markdown(R: dict[str, Any]) -> str:
    out = ["# 실험: 에이전트 유형 × 규제 기준", "", f"만든 시각 {R['manifest']['generated_at']} · 의무 라이브러리 기준일 {R['manifest']['library_as_of']} "
           f"(조문 {R['manifest']['obligations']}개, 변호사 검토 전) · 도구 버전 {R['manifest']['tool_rev']}", "", "## 결과 요약", ""]
    out += [f"- {s}" for s in findings(R)] + [""]
    for title, head, rows in tables(R):
        parts = title.split(". ")
        note = ". ".join(parts[2:])
        out += [f"## {parts[0]}. {parts[1]}", ""] + ([note, ""] if note else []) + ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        out += ["| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in rows] + [""]
    out += ["## 해석 의존 시나리오", ""] + [f"- {x['id']} {x['label']}: {', '.join(_dep_names(x)) or '없음'} ({', '.join(x['interpretation_dependent'])})"
                                          for x in R["agents"]] + [""]
    return "\n".join(out)


def to_csv(R: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["agent", "label", "reading", "metric", "value"])
    for x in R["agents"]:
        for rd, m in x["readings"].items():
            for k, v in m.items():
                if k == "exposure":
                    for p, e in v.items():
                        w.writerow([x["id"], x["label"], rd, f"exposure_p{p}", e])
                else:
                    w.writerow([x["id"], x["label"], rd, k, v])
        for k in ("applicable", "binding", "binding_ai", "conflict", "offline", "cases", "tools"):
            w.writerow([x["id"], x["label"], "", k, x[k]])
        w.writerow([x["id"], x["label"], "", "interpretation_dependent", len(x["interpretation_dependent"])])
    return "﻿" + buf.getvalue()


def write_all(out_dir: Path = OUT_DIR / "experiment", R: dict[str, Any] | None = None) -> list[Path]:
    R = R or run()
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {"results.csv": to_csv(R), "summary.md": to_markdown(R),
             "manifest.json": json.dumps(R["manifest"], ensure_ascii=False, indent=1),
             "results.json": json.dumps(R, ensure_ascii=False, indent=1, default=str)}
    paths = []
    for name, text in files.items():
        p = out_dir / name
        p.write_text(text, encoding="utf-8")
        paths.append(p)
    return paths


def page(R: dict[str, Any], F: dict[str, dict[str, Any]] | None = None) -> str:
    """연구 노트 형식의 실험 페이지(out/experiment.html). 첫 화면과 같은 틀 · 토큰 · 규칙(그림 N 캡션, 상자는 그림에만)."""
    from .landing import _tpl
    e = html.escape
    m = R["manifest"]
    T = tables(R)
    F = F if F is not None else flows()
    flow_figs, nxt = flow_figures(F, 2)

    def table(t):
        title, head, rows = t
        return (f'<figure class="fig tblfig"><figcaption><b>{e(title.split(". ")[0])}</b> {e(title.split(". ", 1)[1])}</figcaption><div class="tblwrap"><table class="xt">'
                "<thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div></figure>")

    dep_rows = "".join(f"<li><b>{e(x['id'] + ' ' + x['label'])}</b> {e(', '.join(_dep_names(x)) or '없음')}</li>" for x in R["agents"])
    body = f"""
<header class="masthead" id="top">
<p class="kicker">실험 노트 · {e(m['generated_at'][:10])} 기준</p>
<h1>에이전트 유형마다, 규제를 어떻게 읽느냐에 따라</h1>
<p class="deck">증권사의 대표적인 AI 에이전트 일곱 유형에 실제로 걸리는 조문을 골라 통제 수준을 세 가지 기준으로 도출하고, 각 유형의 도구로 만든 공격 시나리오를 같은 정책 엔진으로 돌렸다. 기준은 명문 기준, 확장 해석 기준, 자율규범 포함 기준이다.</p>
</header>
<section class="sh lead" aria-labelledby="h-r"><h2 id="h-r">결과</h2><div>
<div class="summary">{''.join(f'<p>{e(s)}</p>' for s in findings(R))}</div>
<figure class="fig"><figcaption><b>그림 1</b> 규제 기준별 공격 시나리오 판정. 일곱 유형의 시나리오를 합했다. 통제 없음과 모든 통제 AI 수준은 기준선이다.</figcaption>{legend()}{figure_aggregate(R)}</figure>
</div></section>
<section class="sh" aria-labelledby="h-f"><h2 id="h-f">명령 흐름</h2><div>
<p class="body">명령 하나(에이전트의 도구 호출)는 지시 출처에서 시작해 런타임의 판정 일곱 단계를 차례로 지난다. 어느 단계에서 멈추는지, 어느 단계를 검사 없이 지나는지가 판정을 가른다. 아래 그림의 칸은 정책 엔진이 그 명령에 실제로 남긴 단계별 판정이다.</p>
{flow.order_legend()}
{flow_figs}
<h3 class="deph">시나리오 전체</h3>
<p class="body">유형마다 모든 시나리오의 흐름을 명문 기준과 확장 해석 기준으로 나란히 볼 수 있다. 제목을 누르면 펼쳐진다.</p>
{flow_catalog(F)}
</div></section>
<section class="sh" aria-labelledby="h-a"><h2 id="h-a">유형별</h2><div>
<figure class="fig"><figcaption><b>그림 {nxt}</b> 유형별 판정. 막대 하나가 그 유형의 공격 시나리오 전체다.</figcaption>{legend()}{figure_agents(R)}</figure>
{table(T[0])}{table(T[1])}
</div></section>
<section class="sh" aria-labelledby="h-s"><h2 id="h-s">공격 유형별</h2><div>
{table(T[2])}
<h3 class="deph">해석 의존 시나리오</h3><p class="body">명문 기준과 확장 해석 기준 사이에서 판정이 바뀌는 시나리오를 공격 유형으로 묶었다. 시나리오별 식별자는 experiment/summary.md 에 있다.</p><ul class="dep">{dep_rows}</ul>
</div></section>
<section class="sh" aria-labelledby="h-t"><h2 id="h-t">합계와 민감도</h2><div>{table(T[3])}{table(T[4])}</div></section>
<section class="sh" aria-labelledby="h-m"><h2 id="h-m">방법</h2><div>
<p class="body">에이전트 유형은 저자가 정한 합성 유형이다(registry/experiment_agents.yaml). 도구 이름, 인자, 배포 형태, 하는 일, 다루는 정보를 고정하고, 통제 수준만 기준마다 바꾼다. 걸리는 조문은 증권 의무 라이브러리({m['obligations']}개, 기준일 {e(m['library_as_of'])})에서 적용 조건으로 골랐다.</p>
<p class="body">명문 기준은 강제 조문을 문언대로 읽어, AI를 명시하거나 행위 자체를 규율하는 조문만 AI 수준을 요구한 것으로 본다. 확장 해석 기준은 사람·계정을 대상으로 쓴 강제 조문도 에이전트에 적용한다. 자율규범 포함 기준은 가이드라인과 평가기준까지 넣는다.</p>
<p class="body">시나리오 판정은 정책 엔진 샌드박스 재실행이다. 사람 승인 단계에서 멈춘 공격은 승인자가 승인한다고 가정해 한 번 더 돌려, 뒤의 통제가 막으면 자동 차단, 실행되면 승인 의존으로 분류한다. 결과는 결정적이다.</p>
</div></section>
<section class="sh" aria-labelledby="h-l"><h2 id="h-l">한계</h2><div><ul class="lim">
<li>조문 대응과 적용 조건, 조문이 에이전트에 미치는 방식의 구분은 변호사 검토 전이다.</li>
<li>에이전트 유형과 도구 구성은 가정이다. 같은 업무라도 도구를 다르게 나누면 결과가 달라진다.</li>
<li>시나리오는 정책 엔진의 판정을 본다. 모델이 실제로 숨은 지시를 따르는지는 LLM 레드팀으로 따로 잰다.</li>
<li>통제 수준 2(AI 수준)는 런타임이 집행한다고 가정한다. 운영 효과성(실제로 그렇게 돌고 있는지)은 이 실험 밖이다.</li>
</ul>
<p class="note-s">재현: 도구 버전 {e(m['tool_rev'])} · 에이전트 정의 지문 {e(m['agents_hash'])} · 시나리오 지문 {e(', '.join(f'{k} {v}' for k, v in m['case_hashes'].items()))}. 원자료는 experiment/results.csv · results.json.</p>
</div></section>"""
    css = """
.fig figcaption{font-size:14.5px;max-width:72ch}
.key{display:flex;flex-wrap:wrap;gap:8px 18px;margin:0 0 14px;font-size:14.5px;color:var(--pq-ivory-soft)}
.key i{display:inline-block;width:14px;height:14px;margin-right:7px;vertical-align:-2px;border-radius:3px}
.key i.v-na{box-shadow:inset 0 0 0 1px var(--pq-ivory-line-strong)}
.sb{display:flex;gap:2px;height:28px;min-width:0}
.sb span{display:flex;align-items:center;flex:1 1 0;min-width:2px;padding:0 0 0 8px;border-radius:4px;font-size:14px;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}
.sb-s{height:22px}
.sb-s span{padding-left:6px;font-size:13px}
.agg{display:flex;flex-direction:column;gap:10px}
.agg-row{display:grid;grid-template-columns:10.5em minmax(0,1fr) 6.5em;align-items:center;gap:14px}
.agg-l{font-size:15.5px;color:var(--pq-ivory-soft)}
.agg-row.is-key .agg-l{font-weight:700;color:var(--pq-ivory)}
.agg-v{font-size:15px;color:var(--pq-ivory-dim);white-space:nowrap}
.agg-v b{font-size:18px;color:var(--pq-ivory);margin-right:4px}
.agg-note{margin:-2px 0 2px calc(10.5em + 14px);padding-left:12px;border-left:2px solid var(--pq-bronze);font-size:14px;line-height:1.6;color:var(--pq-bronze)}
.agg-foot{margin:6px 0 0;font-size:13.5px;color:var(--pq-ivory-dim)}
.am{display:flex;flex-direction:column;gap:12px}
.am-row{display:grid;grid-template-columns:13em repeat(3,minmax(0,1fr));align-items:center;gap:14px}
.am-head span{font-size:14px;font-weight:600;color:var(--pq-ivory-dim)}
.am-l{font-size:15px;color:var(--pq-ivory-soft);line-height:1.35}
.am-l b{margin-right:4px;color:var(--pq-ivory)}
.am-l small{display:block;font-size:13px;color:var(--pq-ivory-dim)}
.tblfig{margin:32px 0 0}
.xt{font-size:14.5px}
.xt td:first-child{white-space:nowrap;font-weight:600}
.xt th{white-space:nowrap}
.deph{margin:40px 0 8px;font-size:18px}
.dep{margin:8px 0 0;padding-left:18px;font-size:15px;line-height:1.7;color:var(--pq-ivory-soft)}
.dep li{margin:4px 0}
.lim{margin:0;padding-left:18px;color:var(--pq-ivory-soft);font-size:15px;line-height:1.75}
.summary p{margin:0 0 12px}
.flowfig{margin:28px 0 8px}
.fc{display:flex;flex-direction:column;gap:8px;margin:8px 0 0}
.fc details{border:0}
.fc summary{justify-content:flex-start;flex-wrap:wrap;align-items:baseline;gap:4px 12px;padding:12px 14px;border:1px solid var(--pq-ivory-line-strong);border-radius:8px;font-weight:400}
.fc summary::after{margin-left:auto;align-self:center}
.fc details>summary::after{transform:none}
.fc details[open]>summary::after{transform:rotate(45deg)}
.fc details>:not(summary){padding-bottom:0}
.fc-agent>summary b{font-size:16px;color:var(--pq-ivory)}
.fc-agent>summary span{font-size:14px;color:var(--pq-ivory-dim)}
.fc-agent[open]{padding-bottom:6px}
.fc-agent>.fc-case{margin:8px 0 0 14px}
.fc-case>summary{padding:10px 12px}
.fc-t{font-size:15px;color:var(--pq-ivory)}
.fc-v{font-size:14px;color:var(--pq-ivory-dim)}
.fc-case>.fl{margin:12px 0 18px 4px}
@media(max-width:760px){
  .agg-row{grid-template-columns:minmax(0,1fr) auto;gap:6px 10px}
  .agg-row .sb{grid-column:1 / -1;grid-row:2}
  .agg-note{margin-left:0}
  .am-head{display:none}
  .am-row{grid-template-columns:minmax(0,1fr);gap:6px;padding-bottom:12px;border-bottom:1px solid var(--pq-ivory-line)}
  .am-cell{display:grid;grid-template-columns:7.5em minmax(0,1fr);align-items:center;gap:8px}
  .am-cell::before{content:attr(data-r);font-size:13.5px;color:var(--pq-ivory-dim)}
  .fc-agent>.fc-case{margin-left:0}
}
""" + flow.CSS
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>실험: 에이전트 유형 × 규제 기준 · PivoxPolicy</title>
<meta name="description" content="증권사 AI 에이전트 일곱 유형에 걸리는 조문으로 통제 수준을 도출하고 공격 시나리오를 돌린 실험." />
<meta name="theme-color" content="#050505" />
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin />
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" />
<style>
{_tpl("tokens.css")}
{_tpl("base.css")}
{_tpl("landing.css")}
{css}
</style>
</head>
<body>
<a class="skip" href="#main">본문으로</a>
<div class="wrap land">
<header class="topbar">
<a class="brand" href="./" aria-label="PivoxPolicy 홈">Pivox<span class="b">Policy</span></a>
<nav class="nav" aria-label="페이지"><a href="sim.html">모의 테스트</a><a href="dashboard.html">대시보드</a><a href="./">첫 화면</a></nav>
</header>
<main id="main">{body}
</main>
<footer class="site"><span>PivoxPolicy 실험 노트. 법률 자문이 아니다.</span><span class="links"><a href="./">첫 화면</a></span></footer>
</div>
</body>
</html>
"""


def build(out_dir: Path = OUT_DIR) -> list[Path]:
    """out/experiment.html + out/experiment/(CSV · MD · JSON · manifest)."""
    R = run()
    paths = write_all(out_dir / "experiment", R)
    p = out_dir / "experiment.html"
    p.write_text(page(R), encoding="utf-8")
    return [p, *paths]
