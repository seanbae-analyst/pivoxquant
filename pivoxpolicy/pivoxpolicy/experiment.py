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
# 원칙: 글자를 그림 밖으로. 점 하나 = 공격 시나리오 하나, 밝을수록 노출(미차단). 명령 흐름은 노선도(flow.py).
# SVG viewBox 는 쓰지 않는다 — 폰에서 그림 폭에 비례해 글자가 줄어든다(390px 폭에서 5.4px였다).
# 판정 색은 노출 순서 척도(어두운 바탕 #5E4A31 → #B8956A → #F5F0E8, dataviz validate_palette --ordinal 통과, flow.CSS 의 --v-*).

LBL = {"good": "자동 차단", "held": "승인 의존", "defect": "미차단", "na": "공격면 없음"}
DOT_ORDER = ("defect", "held", "good", "na")          # 밝은 점(미차단)부터
KEY_READINGS = ("binding_explicit", "binding_interpretive", "guideline")
READING_SHORT = {"binding_explicit": "명문 기준", "binding_interpretive": "확장 해석", "guideline": "자율규범 포함"}
READING_HOW = {"binding_explicit": "강제 조문을 문언대로 읽는다", "binding_interpretive": "사람·계정 조문을 에이전트에도 적용한다",
               "guideline": "가이드라인 · 평가기준까지 넣는다"}


def bar(m: dict[str, int], total: int, cls: str = "bar") -> str:
    """막대 하나 = 공격 시나리오 전체. 왼쪽부터 미차단(아이보리) · 승인 의존(브론즈), 빈 칸 = 자동 차단."""
    title = ", ".join(f"{LBL[k]} {m.get(k, 0)}" for k in DOT_ORDER if m.get(k)) + f" (전체 {total})"
    segs = "".join(f'<span class="v-{k}" style="width:{100 * m[k] / total:.3f}%"></span>' for k in ("defect", "held") if total and m.get(k))
    return f'<span class="{cls}" role="img" aria-label="{html.escape(title)}" title="{html.escape(title)}">{segs}</span>'


def bar_key() -> str:
    return ('<p class="dkey"><span><i class="sw v-defect"></i>미차단</span><span><i class="sw v-held"></i>승인 의존</span>'
            '<span><i class="sw sw-empty"></i>자동 차단</span></p>')


def figure_compare(R: dict[str, Any]) -> str:
    """그림 1: 기준 셋 — 이름 · 막대 · 큰 수(미차단)."""
    ag = R["aggregate"]
    total = ag["binding_explicit"]["attacks"]
    out = ['<div class="cmp">']
    for rd in KEY_READINGS:
        a = ag[rd]
        held = f"<small>승인 의존 {a['held']}</small>" if a["held"] else ""
        out.append(f'<div class="cmp-row{" is-key" if rd == "binding_explicit" else ""}">'
                   f'<div class="cmp-l"><b>{html.escape(READING_SHORT[rd])}</b><span>{html.escape(READING_HOW[rd])}</span></div>'
                   f'{bar(a, total)}<div class="cmp-n"><b>{a["defect"]}</b><span>미차단</span>{held}</div></div>')
    out.append(f'<div class="cmp-axis"><span></span><span class="ax"><span>0</span><span>{total}</span></span><span></span></div></div>')
    return "".join(out)


def figure_types(R: dict[str, Any]) -> str:
    """그림: 유형 × 기준 — 칸마다 얇은 막대 + 미차단 수."""
    head = '<div class="tm-row tm-head"><span></span>' + "".join(f"<span>{html.escape(READING_SHORT[r])}</span>" for r in KEY_READINGS) + "</div>"
    rows = []
    for x in R["agents"]:
        cells = []
        for rd in KEY_READINGS:
            m = x["readings"][rd]
            cells.append(f'<span class="tm-c">{bar(m, m["attacks"], "bar bar-s")}<em class="{"" if m["defect"] else "z"}">{m["defect"]}</em></span>')
        rows.append(f'<div class="tm-row"><span class="tm-l"><b>{html.escape(x["id"])}</b> {html.escape(x["label"])}</span>{"".join(cells)}</div>')
    return '<div class="tm">' + head + "".join(rows) + "</div>"


def _featured(F: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """크게 싣는 흐름 두 개 — 해석 의존의 두 갈래(명문 기준에서 미차단 / 승인 의존 → 확장 해석 기준에서 자동 차단).
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


def _case_name(c: dict[str, Any]) -> tuple[str, str]:
    """(굵게 적을 공격 유형, 작게 적을 내용)."""
    t = c.get("title") or c["id"]
    head, _, rest = t.partition(": ")
    return (head, rest) if rest else (t, "")


def flow_figures(F: dict[str, dict[str, Any]], start: int) -> tuple[str, int]:
    out, n = [], start
    for aid, c, rs in _featured(F):
        f = F[aid]
        head, _ = _case_name(c)
        vl = terms.verdict_label("attack", rs["binding_explicit"]["verdict"])
        lanes = [(READING_SHORT[rd], rs[rd]) for rd in ("binding_explicit", "binding_interpretive")]
        out.append(f'<figure class="fig flowfig"><figcaption><b>그림 {n}</b> {html.escape(f["label"])} 에이전트 · {html.escape(head)}. '
                   f'명문 기준에서는 {html.escape(vl)}, 확장 해석에서는 자동 차단.</figcaption>'
                   + flow.figure(c, lanes, title="", sub=c.get("story") or "") + "</figure>")
        n += 1
    return "".join(out), n


def flow_catalog(F: dict[str, dict[str, Any]]) -> str:
    """시나리오 전체 — 유형마다 접어 두고, 시나리오 한 줄 = 작은 노선 두 개(명문 · 확장 해석)."""
    rds = ("binding_explicit", "binding_interpretive")
    out = []
    for aid, f in F.items():
        items = [(*_case_name(c), [rs[rd] for rd in rds]) for c, rs in f["cases"]]
        n_att = sum(1 for c, _ in f["cases"] if c.get("kind", "attack") == "attack")
        out.append(f'<details class="cg"><summary><b>{html.escape(aid)} {html.escape(f["label"])}</b>'
                   f'<span>공격 {n_att} · 정상 업무 {len(f["cases"]) - n_att}</span></summary>'
                   f'<div class="cg-body">{flow.rows([READING_SHORT[rd] for rd in rds], items)}</div></details>')
    return flow.gate_list(always=True) + '<div class="cgs">' + "".join(out) + "</div>"


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
    ag = R["aggregate"]
    total = ag["binding_explicit"]["attacks"]
    dep = sum(len(x["interpretation_dependent"]) for x in R["agents"])
    none_ai = [x["label"] for x in R["agents"] if not x["explicit_ai_controls"]]

    def table(t):
        title, head, rows = t
        return (f'<figure class="fig tblfig"><figcaption><b>{e(title.split(". ")[0])}</b> {e(title.split(". ", 1)[1])}</figcaption><div class="tblwrap"><table class="xt">'
                "<thead><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div></figure>")

    dep_rows = "".join(f"<li><b>{e(x['id'] + ' ' + x['label'])}</b> {e(', '.join(_dep_names(x)) or '없음')}</li>" for x in R["agents"])
    body = f"""
<section class="pg pg-cover" id="cover" data-title="표지" aria-labelledby="h-cover">
<div class="pg-spot" aria-hidden="true"></div>
<p class="pg-kicker">실험 노트 · {e(m['generated_at'][:10])} 기준</p>
<p class="pg-wordmark" aria-hidden="true">Pivox<span>Policy</span></p>
<h1 class="pg-q" id="h-cover">같은 공격, 규제를 어떻게 읽느냐에 따라</h1>
<p class="pg-sub">증권사 AI 에이전트 {len(R['agents'])}개 유형, 공격 시나리오 {total}개를 같은 런타임으로 돌렸다. 바꾼 것은 규제를 읽는 방식 하나다.</p>
<a class="pg-start" href="#result" data-pager-start>시작하기 <span aria-hidden="true">→</span></a>
<p class="pg-hint">화면을 누르면 넘어간다</p>
</section>
<section class="pg sh lead" id="result" data-title="결과" aria-labelledby="h-r"><h2 id="h-r">결과</h2><div>
<figure class="fig"><figcaption><b>그림 1</b> 막대 하나가 공격 시나리오 {total}개 전체다. 밝은 부분이 막지 못한 것이다.</figcaption>{bar_key()}{figure_compare(R)}</figure>
<p class="callout"><b>{dep}개</b>({round(100 * dep / total) if total else 0}%)는 규제를 어떻게 읽느냐에 따라 판정이 바뀐다.</p>
</div></section>
<section class="pg sh" id="flow" data-title="명령 흐름" aria-labelledby="h-f"><h2 id="h-f">명령 흐름</h2><div>
<p class="body">명령 하나는 런타임의 관문 일곱 개를 차례로 지난다. 명문 기준에서는 관문 대부분이 비어 있어 명령이 그대로 지나간다.</p>
{flow.legend()}{flow.gate_list()}
{flow_figs}
</div></section>
<section class="pg sh" id="all" data-title="시나리오 전체" aria-labelledby="h-all"><h2 id="h-all">시나리오 전체</h2><div>
<p class="body">유형을 펼치면 시나리오마다 작은 노선 두 개(명문 기준 · 확장 해석)가 나온다.</p>
{flow.legend()}{flow_catalog(F)}
</div></section>
<section class="pg sh" id="types" data-title="유형별" aria-labelledby="h-a"><h2 id="h-a">유형별</h2><div>
<figure class="fig"><figcaption><b>그림 {nxt}</b> 유형별 판정. 숫자는 미차단 수다.</figcaption>{bar_key()}{figure_types(R)}</figure>
<p class="callout">명문 기준이 AI 수준 통제를 하나도 요구하지 않는 유형: <b>{e(', '.join(none_ai) or '없음')}</b></p>
</div></section>
<section class="pg sh" id="more" data-title="자세히" aria-labelledby="h-d"><h2 id="h-d">자세히</h2><div>
<details class="more"><summary>요약 문장</summary><div class="summary">{''.join(f'<p>{e(x)}</p>' for x in findings(R))}</div></details>
<details class="more"><summary>표 1 · 2 유형별 적용 조문과 판정</summary>{table(T[0])}{table(T[1])}</details>
<details class="more"><summary>표 3 공격 유형별 판정과 해석 의존 시나리오</summary>{table(T[2])}<ul class="dep">{dep_rows}</ul></details>
<details class="more"><summary>표 4 · 5 합계와 승인자 오판 민감도</summary>{table(T[3])}{table(T[4])}</details>
<details class="more"><summary>방법과 한계</summary><ul class="lim">
<li>에이전트 유형 {len(R['agents'])}개는 저자가 정한 합성 유형이다(registry/experiment_agents.yaml). 도구 · 인자 · 배포 형태를 고정하고 통제 수준만 바꾼다.</li>
<li>걸리는 조문은 증권 의무 라이브러리({m['obligations']}개, 기준일 {e(m['library_as_of'])})에서 적용 조건으로 골랐다. 변호사 검토 전이다.</li>
<li>명문 기준은 AI를 명시하거나 행위 자체를 규율하는 강제 조문만, 확장 해석은 사람·계정 조문까지, 자율규범 포함은 가이드라인까지 AI 수준 요구로 본다.</li>
<li>판정은 정책 엔진 샌드박스 재실행이다. 사람 승인에서 멈춘 공격은 승인된다고 가정해 다시 돌린다. 모델이 숨은 지시를 실제로 따르는지는 LLM 레드팀으로 따로 잰다.</li>
<li>재현: 도구 버전 {e(m['tool_rev'])} · 에이전트 정의 지문 {e(m['agents_hash'])}. 원자료 experiment/results.csv · results.json.</li>
</ul></details>
</div></section>"""
    css = """
.fig figcaption{font-size:15.5px;max-width:72ch}
.dkey{display:flex;flex-wrap:wrap;gap:8px 20px;margin:0 0 16px;font-size:15px;color:var(--pq-ivory-soft)}
.dkey span{display:inline-flex;align-items:center;gap:8px}
.sw{display:inline-block;width:14px;height:14px;border-radius:3px}
.sw-empty{background:var(--pq-ivory-line-strong)}
.bar{display:flex;gap:2px;height:16px;border-radius:4px;background:var(--pq-ivory-line-strong);overflow:hidden}
.bar span{height:100%}
.bar-s{height:10px;border-radius:3px}
.cmp{display:flex;flex-direction:column}
.cmp-row{display:grid;grid-template-columns:12.5em minmax(0,1fr) 7.5em;align-items:center;gap:22px;padding:18px 0;border-bottom:1px solid var(--pq-ivory-line)}
.cmp-l{display:flex;flex-direction:column;gap:2px}
.cmp-l b{font-size:18px;color:var(--pq-ivory)}
.cmp-l span{font-size:14px;line-height:1.45;color:var(--pq-ivory-dim)}
.cmp-row.is-key .cmp-l b{color:var(--pq-bronze)}
.cmp-n{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 6px}
.cmp-n b{font-size:41px;line-height:1;font-weight:700;letter-spacing:-0.02em;color:var(--pq-ivory)}
.cmp-n span{font-size:15px;color:var(--pq-ivory-dim)}
.cmp-n small{flex-basis:100%;margin-top:4px;font-size:14px;color:var(--pq-bronze)}
.cmp-axis{display:grid;grid-template-columns:12.5em minmax(0,1fr) 7.5em;gap:22px;padding-top:6px}
.cmp-axis .ax{display:flex;justify-content:space-between;font-size:14px;color:var(--pq-ivory-faint);font-variant-numeric:tabular-nums}
.tm-c{display:grid;grid-template-columns:minmax(0,1fr) 2em;align-items:center;gap:10px}
.tm-c em{font-style:normal;font-size:16px;font-weight:700;color:var(--pq-ivory);font-variant-numeric:tabular-nums}
.tm-c em.z{font-weight:500;color:var(--pq-ivory-faint)}
.callout{margin:22px 0 0;padding-left:14px;border-left:3px solid var(--pq-bronze);font-size:18px;line-height:1.6;color:var(--pq-ivory-soft);max-width:none}
.callout b{color:var(--pq-ivory)}
.tm{display:flex;flex-direction:column}
.tm-row{display:grid;grid-template-columns:14em repeat(3,minmax(0,1fr));align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--pq-ivory-line)}
.tm-head{padding-top:0}
.tm-head span{font-size:15px;font-weight:600;color:var(--pq-ivory-dim)}
.tm-l{font-size:16px;color:var(--pq-ivory-soft)}
.tm-l b{margin-right:4px;color:var(--pq-ivory)}
.flowfig{margin:30px 0 10px}
.flowfig figcaption{margin-bottom:4px}
.cgs{display:flex;flex-direction:column;gap:8px}
.cg{border:0}
.cg>summary{justify-content:flex-start;flex-wrap:wrap;gap:4px 14px;padding:13px 16px;border:1px solid var(--pq-ivory-line-strong);border-radius:10px;font-weight:400}
.cg>summary b{font-size:17px;color:var(--pq-ivory)}
.cg>summary span{font-size:15px;color:var(--pq-ivory-dim)}
.cg>summary::after{margin-left:auto}
.cg-body{padding:8px 4px 4px}
.more{border:0;border-top:1px solid var(--pq-ivory-line)}
.more:last-of-type{border-bottom:1px solid var(--pq-ivory-line)}
.more>summary{font-size:16.5px}
.tblfig{margin:16px 0 0}
.xt{font-size:15.5px}
.xt td:first-child{white-space:nowrap;font-weight:600}
.xt th{white-space:nowrap}
.deph{margin:44px 0 12px;font-size:19px}
.dep{margin:14px 0 0;padding-left:18px;font-size:16px;line-height:1.7;color:var(--pq-ivory-soft)}
.lim{margin:0;padding-left:18px;color:var(--pq-ivory-soft);font-size:16px;line-height:1.75}
.summary p{margin:0 0 12px;font-size:16.5px}
.summary p:first-child{font-size:17.5px}
@media(max-width:760px){
  .cmp-row,.cmp-axis{grid-template-columns:minmax(0,1fr) 7.2em;gap:10px 14px}
  .cmp-row .bar{grid-column:1 / -1;grid-row:2}
  .cmp-axis>span:first-child,.cmp-axis>span:last-child{display:none}
  .cmp-axis .ax{grid-column:1 / -1}
  .cmp-n b{font-size:35px}
  .tm-row{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 12px}
  .tm-l{grid-column:1 / -1}
  .tm-head span:first-child{display:none}
  .tm-head span{font-size:14px}
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
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource/playfair-display@5.3.0/latin-500.css" />
<style>
{_tpl("tokens.css")}
{_tpl("base.css")}
{_tpl("landing.css")}
{css}
{_tpl("pager.css")}
</style>
</head>
<body>
<a class="skip" href="#main">본문으로</a>
<div class="wrap land">
<header class="topbar">
<a class="brand" href="./" aria-label="PivoxPolicy 홈">Pivox<span class="b">Policy</span></a>
<nav class="nav" aria-label="페이지"><a href="sim.html">모의 테스트</a><a href="dashboard.html">대시보드</a><a href="./">첫 화면</a></nav>
</header>
<nav class="pg-railbar" data-pager-rail aria-label="화면"></nav>
<main id="main" data-pager>{body}
</main>
<div class="pg-nav" data-pager-nav>
<button type="button" class="pg-btn prev" data-pager-prev><span aria-hidden="true">←</span><span class="lab">이전</span></button>
<span class="pg-count" data-pager-count></span>
<button type="button" class="pg-btn next" data-pager-next><span data-pager-next-label>다음</span><span aria-hidden="true">→</span></button>
</div>
<footer class="site"><span>PivoxPolicy 실험 노트. 법률 자문이 아니다.</span><span class="links"><a href="./">첫 화면</a></span></footer>
</div>
<script src="./pager.js"></script>
</body>
</html>
"""


def build(out_dir: Path = OUT_DIR) -> list[Path]:
    """out/experiment.html + out/experiment/(CSV · MD · JSON · manifest)."""
    R = run()
    paths = write_all(out_dir / "experiment", R)
    p = out_dir / "experiment.html"
    p.write_text(page(R), encoding="utf-8")
    from .landing import _tpl
    js = out_dir / "pager.js"                 # 화면 넘김(templates/pager.js) — 배포는 파일로, 오프라인 사본은 bundle 이 인라인한다
    js.write_text(_tpl("pager.js"), encoding="utf-8")
    return [p, js, *paths]
