"""명령 흐름 — 명령(도구 호출) 하나가 런타임의 관문 일곱 개를 지나가는 길을 노선도처럼 그린다.

  관문은 세로 막대다: 빈 막대 = 검사 안 함(그 통제가 AI 수준이 아니다) · 채운 막대 = 검사하고 통과
                      굵은 채운 막대 = 차단 · 굵은 빈 막대 = 승인 대기
  아이보리 실선 = 명령이 지나간 길 · 브론즈 실선 = 승인되면 지나갈 길 · 선 없음 = 도달하지 않은 길(점선 · 점은 쓰지 않는다)

정책 엔진(policy.decide)이 남긴 checks 를 그대로 옮긴다. 그림을 위해 판정을 다시 계산하지 않는다.
글자는 관문 이름(머리줄 한 번)과 끝의 결과 한 단어뿐이다. 단계별 설명은 접어 둔다(details).
실험 페이지와 진단 보고서가 같이 쓴다(스크립트 없음, HTML + CSS).
"""

from __future__ import annotations

import functools
import html
from typing import Any

from . import terms
from .runtime import policy

STATE = {"pass": "검사하고 통과", "block": "차단", "approval": "승인 대기", "flag": "탐지", "off": "검사 안 함", "not_reached": "도달 안 함"}
DECISION = {"allow": "허용", "deny": "거부", "require_approval": "승인 대기", "no_tool": "도구 없음"}
SRC = {"web": "외부 글", "email": "메일", "customer_message": "고객 메시지", "agent": "다른 에이전트", "user": "운영자 지시",
       "plan": "에이전트 자체 계획", "tool_description": "도구 설명"}

e = html.escape


@functools.lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    from .diagnosis import _controls
    return {c["id"]: c["name"] for c in _controls()}


def gate_name(c: str) -> str:
    return _names().get(c, c)


def _fmt(v: Any) -> str:
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, int):
        return f"{v:,}"
    return f'"{v}"'


def _call(tool: str | None, args: dict[str, Any] | None) -> str:
    return f"{tool or '?'}(" + ", ".join(f"{k}={_fmt(v)}" for k, v in (args or {}).items()) + ")"


def _last_per_step(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """반복 단계는 마지막 시행만(멈춘 시행이거나 끝까지 간 시행)."""
    last: dict[int, dict[str, Any]] = {}
    for s in steps:
        last[s["step"]] = s
    return [last[k] for k in sorted(last)]


def _norm(checks: list[dict[str, Any]] | None) -> list[tuple[int, str, str, str]]:
    """일곱 관문 순서대로 (번호, 통제, 결과, 메모)."""
    by = {c["control"]: c for c in checks or []}
    out = []
    for i, c in enumerate(policy.CONTROL_ORDER, 1):
        ch = by.get(c) or {"result": "not_reached", "note": ""}
        out.append((i, c, ch["result"], ch.get("note") or ""))
    return out


# ── 길 계산: 결정 단계의 관문 상태 + 선 상태 + 끝 ──

def route(res: dict[str, Any]) -> dict[str, Any] | None:
    """run_case 결과 → {nodes: 관문 상태 7, segs: 관문 앞 선 7(live|cond|dead), end, at: 멈춘 관문 번호, alive_end: 끝으로 가는 선}.
    승인 의존이면 사람 승인 뒤 관문은 '승인 뒤 재판정' 의 상태로 잇고 선을 점선(cond)으로 그린다."""
    steps = _last_per_step(res.get("steps") or [])
    if not steps or steps[-1].get("decision") == "no_tool":
        return None
    last = steps[-1]
    nodes = [r for _, _, r, _ in _norm(last.get("checks"))]
    segs, alive, stop = [], "live", None
    for i, r in enumerate(nodes, 1):
        segs.append(alive)
        if r in ("block", "approval") and stop is None:
            stop, alive = i, "dead"
    end = {"allow": "exec", "deny": "block", "require_approval": "approval"}.get(last.get("decision"), "block")
    ia = res.get("if_approved")
    if end == "approval" and ia and ia.get("steps"):
        # 승인 뒤 재판정 중 '같은 호출'(같은 단계 · 같은 반복, 승인 표시 줄 제외)을 쓴다. 승인 뒤 다음 단계로 넘어가 거기서
        # 막혔더라도 이 노선은 멈췄던 호출 하나를 그린다 — 끝 단어는 전체 결과(차단), 다음 단계는 단계별 판정에 적힌다.
        same = [x for x in ia["steps"] if x["step"] == last["step"] and x.get("repeat") == last.get("repeat") and not x.get("approved")]
        rec = same[0] if same else _last_per_step(ia["steps"])[-1]
        after = [r for _, _, r, _ in _norm(rec.get("checks"))]
        alive = "cond"
        for i in range(stop, 7):          # 승인 관문 뒤
            nodes[i] = after[i]
            segs[i] = alive
            if after[i] == "block":
                alive = "dead"
        end = "cond_exec" if ia.get("outcome") == "passed" else "cond_block"
        if end == "cond_block":
            alive = "dead"
    return {"nodes": nodes, "segs": segs, "end": end, "at": stop, "alive_end": alive}


def end_word(res: dict[str, Any], rt: dict[str, Any] | None) -> tuple[str, str]:
    """(끝에 적는 한 단어, 클래스). 공격은 실행됨이 위험, 정상 업무는 막힘이 문제."""
    attack = res.get("kind", "attack") == "attack"
    if rt is None:
        return ("공격면 없음" if attack else "해당 없음"), "w-na"
    return {
        "exec": ("실행됨", "w-exec") if attack else ("처리됨", "w-ok"),
        "block": ("차단", "w-block") if attack else ("막힘", "w-exec"),
        "approval": ("승인 대기", "w-wait"),
        "cond_exec": ("승인되면 실행", "w-wait") if attack else ("승인 뒤 처리", "w-ok"),
        "cond_block": ("차단", "w-block"),
    }[rt["end"]]


# ── 그리기 ──

def _node(i: int, c: str, r: str, label: bool) -> str:
    lab = {"block": "차단", "approval": "승인 대기"}.get(r, "") if label else ""
    return (f'<i class="n s-{r}" data-state="{r}" title="{i} {e(gate_name(c))}: {e(STATE.get(r, r))}"></i>'
            + (f'<em class="nl">{lab}</em>' if lab else ""))


def track(res: dict[str, Any], label: str = "", mini: bool = False) -> str:
    """노선 한 줄. mini 면 기준 이름 · 멈춤 표시 글자 없이 작게(목록용)."""
    rt = route(res)
    word, wc = end_word(res, rt)
    cls = "mt-row mini" if mini else "mt-row"
    head = "" if mini else f'<span class="mt-l">{e(label)}</span>'
    if rt is None:
        return f'<div class="{cls}">{head}<div class="mt-track none"></div><span class="mt-w {wc}">{e(word)}</span></div>'
    cells = []
    for i, (c, r, sg) in enumerate(zip(policy.CONTROL_ORDER, rt["nodes"], rt["segs"]), 1):
        out = rt["segs"][i] if i < 7 else rt["alive_end"]
        if rt["at"] == i and rt["end"] in ("block", "approval"):
            out = "dead"
        cells.append(f'<span class="c in-{sg} out-{out}">' + _node(i, c, r, rt["at"] == i and not mini) + "</span>")
    cells.append(f'<span class="c end in-{rt["alive_end"]}"><b class="arrow"></b></span>')
    aria = (f"{label}: " if label else "") + ", ".join(
        f"{i} {gate_name(c)} {STATE.get(r, r)}" for i, (c, r) in enumerate(zip(policy.CONTROL_ORDER, rt["nodes"]), 1)) + f" → {word}"
    return (f'<div class="{cls}" role="img" aria-label="{e(aria)}">{head}<div class="mt-track">' + "".join(cells)
            + f'</div><span class="mt-w {wc}">{e(word)}</span></div>')


def header(mini: bool = False) -> str:
    """관문 이름 머리줄(그림마다 한 번). 폰에서는 번호만."""
    cells = "".join(f'<span><b>{i}</b><span class="gn">{e(gate_name(c))}</span></span>' for i, c in enumerate(policy.CONTROL_ORDER, 1))
    lab = "" if mini else '<span class="mt-l"></span>'
    return f'<div class="mt-row mt-head{" mini" if mini else ""}">{lab}<div class="mt-track">{cells}<span></span></div><span class="mt-w"></span></div>'


def legend() -> str:
    return ('<p class="mt-key"><span><i class="n s-off"></i>검사 안 함</span><span><i class="n s-pass"></i>검사하고 통과</span>'
            '<span><i class="n s-block"></i>차단</span><span><i class="n s-approval"></i>승인 대기</span>'
            '<span><b class="ln"></b>명령이 지나감</span><span><b class="ln cond"></b>승인되면 지나감</span></p>')


def gate_list(always: bool = False) -> str:
    """번호 → 관문 이름 한 줄. 기본은 폰에서만(넓은 화면은 머리줄에 이름이 있다). always 면 늘(번호만 있는 목록 위)."""
    return f'<p class="mt-gl{" on" if always else ""}">' + " · ".join(f"{i} {e(gate_name(c))}" for i, c in enumerate(policy.CONTROL_ORDER, 1)) + "</p>"


def rows(columns: list[str], items: list[tuple[str, str, list[dict[str, Any]]]]) -> str:
    """시나리오 한 줄 = 이름 + 기준마다 작은 노선. 머리줄(번호)은 한 번만.
    columns: 기준 이름들, items: [(굵은 이름, 작은 설명, [기준마다 run_case 결과])]."""
    head = ('<div class="fr-row fr-head"><span></span>'
            + "".join(f"<div><p>{e(c)}</p>{header(mini=True)}</div>" for c in columns) + "</div>")
    body = "".join(f'<div class="fr-row"><span class="fr-n"><b>{e(n)}</b>' + (f"<small>{e(sm)}</small>" if sm else "") + "</span>"
                   + "".join(f'<div class="fr-t" data-r="{e(c)}">{track(r, mini=True)}</div>' for c, r in zip(columns, rs)) + "</div>"
                   for n, sm, rs in items)
    return f'<div class="fr" style="--cols:{len(columns)}">{head}{body}</div>'


def steps_text(res: dict[str, Any], case: dict[str, Any]) -> list[str]:
    """단계마다 한 줄 — 도구 호출(출처) → 결정(멈춘 관문 · 이유)."""
    out = []
    raw = case.get("steps") or []
    for tr in _last_per_step(res.get("steps") or []):
        st = raw[tr["step"] - 1] if 0 < tr["step"] <= len(raw) else {}
        if tr.get("decision") == "no_tool":
            out.append(f"단계 {tr['step']}: {tr.get('reason') or ''}")
            continue
        src = ", ".join(SRC.get(s.get("kind"), s.get("kind")) for s in st.get("input_sources") or [])
        rep = f" ×{st['repeat']}" if int(st.get("repeat") or 1) > 1 else ""
        why = f" · {gate_name(tr['control'])}: {tr.get('reason') or ''}" if tr["decision"] != "allow" and tr.get("control") else ""
        out.append(f"단계 {tr['step']}{rep}: {_call(tr.get('tool'), st.get('args'))}" + (f" (출처 {src})" if src else "")
                   + f" → {DECISION.get(tr['decision'], tr['decision'])}{why}")
    ia = res.get("if_approved")
    if res.get("verdict") in ("held", "good") and ia:
        out.append("승인되면: 같은 요청을 다시 판정 → " + ("허용(실행)" if ia.get("outcome") == "passed" else f"{gate_name(ia['control'])}에서 거부"))
    return out


def figure(case: dict[str, Any], lanes: list[tuple[str, dict[str, Any]]], title: str | None = None, sub: str | None = None,
           detail: bool = True) -> str:
    """같은 명령을 여러 기준으로 — 노선을 위아래로 맞춰 놓는다. lanes: [(기준 이름, run_case 결과)]."""
    t = (case.get("title") or case["id"]) if title is None else title
    s = (case.get("story") or "") if sub is None else sub
    rows = "".join(track(r, lb) for lb, r in lanes)
    det = ""
    if detail:
        items = "".join(f"<li><b>{e(lb)}</b><ul>" + "".join(f"<li>{e(x)}</li>" for x in steps_text(r, case)) + "</ul></li>" for lb, r in lanes)
        det = f'<details class="mt-det"><summary>단계별 판정 보기</summary><ul>{items}</ul></details>'
    return ('<div class="mt">' + (f'<p class="mt-t">{e(t)}</p>' if t else "") + (f'<p class="mt-s">{e(s)}</p>' if s else "")
            + f'<div class="mt-box">{header()}{rows}</div>{det}</div>')


def outcome_text(res: dict[str, Any]) -> str:
    """판정 한 줄 설명(표 · 마크다운용)."""
    v, kind = res["verdict"], res["kind"]
    ctl = gate_name(res["control"]) if res.get("control") else None
    if v == "na":
        return "이 에이전트에는 그 공격이 쓸 도구가 없다."
    if kind == "attack":
        if v == "defect":
            return "모든 관문을 지나 명령이 실행됐다."
        if v == "good":
            ia = res.get("if_approved")
            if ia and ia.get("control"):
                return f"사람 승인에서 멈췄고, 승인되더라도 {gate_name(ia['control'])}에서 막힌다."
            return f"{ctl}에서 자동으로 막혔다."
        if v == "held":
            return "사람 승인에서만 멈췄다. 승인되면 실행된다."
    if v == "good":
        return "정상 업무가 끝까지 처리됐다."
    return f"정상 업무가 {ctl}에서 멈췄다(" + terms.verdict_label("benign", v, res.get("control")) + ")."


CSS = """
:root{--v-good:#5E4A31;--v-good-ink:var(--pq-ivory);--v-held:#B8956A;--v-held-ink:#050505;--v-defect:#F5F0E8;--v-defect-ink:#050505;
--v-na:#1d1b18;--v-na-ink:var(--pq-ivory-dim);--mt-live:var(--pq-ivory);--mt-cond:var(--pq-bronze);--mt-dead:var(--pq-ivory-line-strong);
--mt-gate:var(--pq-bronze);--mt-off:var(--pq-ivory-faint);--mt-bg:#050505}
.v-good{background:var(--v-good);color:var(--v-good-ink)}
.v-held{background:var(--v-held);color:var(--v-held-ink)}
.v-defect{background:var(--v-defect);color:var(--v-defect-ink)}
.v-na{background:var(--v-na);color:var(--v-na-ink)}
.mt{margin:0 0 34px}
.mt-t{margin:0;font-size:17px;font-weight:700;color:var(--pq-ivory)}
.mt-s{margin:4px 0 0;font-size:15px;line-height:1.6;color:var(--pq-ivory-dim);max-width:70ch}
.mt-box{margin:14px 0 0}
.mt-row{display:grid;grid-template-columns:7.5em minmax(0,1fr) 8.5em;align-items:center;gap:0 14px}
.mt-row+.mt-row:not(.mini){border-top:1px solid var(--pq-ivory-line)}
.mt-l{font-size:15px;font-weight:600;color:var(--pq-ivory-soft)}
.mt-track{display:grid;grid-template-columns:repeat(7,minmax(0,1fr)) 28px;align-items:center;height:64px}
.mt-head .mt-track{height:auto;align-items:end;padding-bottom:8px}
.mt-head .mt-track>span{display:flex;flex-direction:column;align-items:center;gap:2px;text-align:center}
.mt-head b{font-size:13px;color:var(--pq-ivory-dim)}
.mt-head .gn{font-size:13.5px;line-height:1.3;color:var(--pq-ivory-soft)}
.c{position:relative;display:flex;align-items:center;justify-content:center;height:100%}
.c::before,.c::after{content:"";position:absolute;top:50%;height:0}
.c::before{left:0;right:50%}
.c::after{left:50%;right:0}
.c.in-live::before,.c.out-live::after{border-top:3px solid var(--mt-live);margin-top:-1.5px}
.c.in-cond::before,.c.out-cond::after{border-top:3px solid var(--mt-cond);margin-top:-1.5px}
.c.in-dead::before,.c.out-dead::after{border-top:0}
.c.end::after{display:none}
.c.end .arrow{position:relative;z-index:1;width:0;height:0;margin-left:-8px;border-top:7px solid transparent;border-bottom:7px solid transparent;border-left:11px solid var(--mt-live)}
.c.end.in-cond .arrow{border-left-color:var(--mt-cond)}
.c.end.in-dead .arrow{display:none}
.n{position:relative;z-index:1;display:block;box-sizing:border-box;border-radius:2px;background:var(--mt-bg)}
.n.s-off{width:8px;height:24px;border:1.5px solid var(--mt-off)}
.n.s-pass,.n.s-flag{width:8px;height:24px;background:var(--mt-gate)}
.n.s-not_reached{width:8px;height:24px;border:1px solid var(--mt-dead);opacity:.55}
.n.s-block{width:14px;height:38px;border-radius:3px;background:var(--mt-gate)}
.n.s-approval{width:14px;height:38px;border-radius:3px;border:3px solid var(--mt-gate)}
.nl{position:absolute;top:calc(50% + 23px);left:50%;transform:translateX(-50%);font-style:normal;font-size:12.5px;font-weight:600;white-space:nowrap;color:var(--pq-bronze)}
.mt-w{font-size:16px;font-weight:700;white-space:nowrap}
.w-exec{color:var(--pq-ivory)}
.w-block,.w-wait{color:var(--pq-bronze)}
.w-ok{color:var(--pq-ivory-dim);font-weight:500}
.w-na{color:var(--pq-ivory-faint);font-weight:500}
.mt-key{display:flex;flex-wrap:wrap;align-items:center;gap:8px 22px;margin:0 0 6px;font-size:14px;color:var(--pq-ivory-soft)}
.mt-key span{display:inline-flex;align-items:center;gap:8px}
.mt-key .n.s-off,.mt-key .n.s-pass{height:18px}
.mt-key .n.s-block,.mt-key .n.s-approval{width:11px;height:22px}
.mt-key .n.s-approval{border-width:2.5px}
.ln{display:inline-block;width:28px;height:0;border-top:3px solid var(--mt-live)}
.ln.cond{border-top-color:var(--mt-cond)}
.mt-gl{display:none;margin:0 0 8px;font-size:13px;line-height:1.7;color:var(--pq-ivory-dim)}
.mt-gl.on{display:block}
.fr-row{display:grid;grid-template-columns:15em repeat(var(--cols,1),minmax(0,1fr));align-items:center;gap:6px 22px;padding:6px 0;border-bottom:1px solid var(--pq-ivory-line)}
.fr-head{align-items:end;border-bottom:0}
.fr-head p{margin:0 0 2px;font-size:14px;font-weight:600;color:var(--pq-ivory-soft)}
.fr-head .mt-w{display:none}
.fr-head .gn{display:none}
.fr-n{display:flex;flex-direction:column;font-size:15px;line-height:1.35}
.fr-n b{font-weight:600;color:var(--pq-ivory)}
.fr-n small{font-size:13px;color:var(--pq-ivory-dim)}
.mt-det{margin:8px 0 0;border:0}
.mt-det summary{justify-content:flex-start;gap:10px;padding:6px 0;font-size:14px;font-weight:500;color:var(--pq-ivory-dim)}
.mt-det summary::after{margin-left:2px}
.mt-det ul{margin:4px 0 0;padding-left:18px;font-size:14px;line-height:1.7;color:var(--pq-ivory-soft)}
.mt-det li>b{color:var(--pq-ivory)}
.mt-row.mini{grid-template-columns:minmax(0,1fr) 7.5em;gap:0 10px}
.mt-row.mini .mt-track{height:34px;grid-template-columns:repeat(7,minmax(0,1fr)) 18px}
.mt-head.mini .mt-track{height:auto}
.mt-head.mini .gn{font-size:12.5px}
.mt-row.mini .n.s-off{width:6px;height:15px;border-width:1.2px}
.mt-row.mini .n.s-pass,.mt-row.mini .n.s-flag{width:6px;height:15px}
.mt-row.mini .n.s-block,.mt-row.mini .n.s-approval{width:10px;height:24px;border-radius:2px}
.mt-row.mini .n.s-approval{border-width:2.5px}
.mt-row.mini .n.s-not_reached{width:6px;height:15px}
.mt-row.mini .c.in-live::before,.mt-row.mini .c.out-live::after,.mt-row.mini .c.in-cond::before,.mt-row.mini .c.out-cond::after{border-top-width:2px;margin-top:-1px}
.mt-row.mini .c.end .arrow{margin-left:-6px;border-top-width:5px;border-bottom-width:5px;border-left-width:8px}
.mt-row.mini .mt-w{font-size:14px}
@media(max-width:760px){
  .mt-row{grid-template-columns:minmax(0,1fr) 6.4em;gap:0 8px}
  .mt-row:not(.mini)>.mt-l{grid-column:1 / -1;padding-top:12px;font-size:14px}
  .mt-head>.mt-l{display:none}
  .mt-head .gn{display:none}
  .mt-gl{display:block}
  .mt-w{font-size:14.5px;white-space:normal;line-height:1.3}
  .mt-row.mini{grid-template-columns:minmax(0,1fr) 6.4em}
  .fr-row{grid-template-columns:minmax(0,1fr);gap:2px}
  .fr-head{display:none}
  .fr-t{display:grid;grid-template-columns:4.6em minmax(0,1fr);align-items:center}
  .fr[style*="--cols:1"] .fr-t{grid-template-columns:minmax(0,1fr)}
  .fr-t::before{content:attr(data-r);font-size:12.5px;color:var(--pq-ivory-dim)}
  .fr[style*="--cols:1"] .fr-t::before{display:none}
}
@media print{.mt{break-inside:avoid}}
"""

# 밝은 바탕(진단 보고서 · 인쇄). --pq-* 토큰을 밝은 값으로 다시 정하고, 판정 색은 어두울수록 노출이 큰 순서 척도
# (#C4A57B → #8A6A3F → #2E2418, dataviz validate_palette --ordinal --mode light --surface #ffffff 통과).
CSS_LIGHT = """
:root{--pq-ivory:#111;--pq-ivory-soft:#3a3a3a;--pq-ivory-dim:#666;--pq-ivory-faint:#9a958d;--pq-ivory-line:#ebe6dd;
--pq-ivory-line-strong:#cfc9be;--pq-bronze:#8a6a3f;--v-good:#C4A57B;--v-good-ink:#111;--v-held:#8A6A3F;--v-held-ink:#fff;
--v-defect:#2E2418;--v-defect-ink:#fff;--v-na:#f1ede6;--v-na-ink:#666;--mt-live:#111;--mt-cond:#8a6a3f;--mt-dead:#cfc9be;
--mt-gate:#8a6a3f;--mt-off:#9a958d;--mt-bg:#fff}
"""
