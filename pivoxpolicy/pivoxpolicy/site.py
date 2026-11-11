"""정적 대시보드 한 장 생성 — Pivox(블랙·골드) 디자인.

레지스트리(매트릭스·공백·루브릭·연표·문서)와 intel.jsonl(최신 동향·사건)을 읽어
out/index.html 한 장으로 낸다. CSS·뼈대는 templates/ (pivoxmap·pivoxdata·pivoxquant 에서 옮긴 것).
점수·레벨은 '증거 수준' 이지 '통제 유무/조언' 이 아니다 — 금지어(추천·조언·안전·적정) 쓰지 않는다.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import incidents as incidents_mod
from . import matrix as matrix_mod
from . import rubric as rubric_mod
from .intel import load_items
from .registry import OUT_DIR, SNAPSHOT_DIR, load_codings, load_controls, load_documents
from .schema import JURISDICTIONS

TEMPLATES = Path(__file__).resolve().parent / "templates"
REPO_URL = "https://github.com/seanbae-analyst/pivoxpolicy"
SITE_NAME = "PivoxPolicy"

_H_LABEL = {0: "미다룸", 1: "자율", 2: "구속력", 3: "에이전트 명시"}


def _e(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _tpl(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def _cell_class(score: int | None) -> str:
    return "h-x" if score is None else f"h-{score}"


def _cell_text(score: int | None, names_agents: bool) -> str:
    if score is None:
        return "?"
    s = str(score)
    return s + ("*" if names_agents and score > 0 else "")


# ── 섹션 빌더 ──────────────────────────────────────────────────────────

# 대시보드의 '지금 바뀐 것'·'사건' 은 AI 에이전트 관련성이 강한 항목만 보인다(intel.jsonl 전체 수집과 별개).
# 약한 일반 키워드(technology · intelligence · 보안 · 전체회의)로만 걸린 항목은 큐레이션에서 뺀다.
_STRONG = ("agent", "agentic", "에이전트", "ai agent", "llm", "프롬프트", "prompt injection",
           "생성형", "genai", "mcp", "인공지능", "artificial intelligence")
# 사건 목록은 보안 신호가 추가로 있어야 한다(AI 데이터센터 동맹 같은 산업 뉴스를 뺀다).
_SECURITY = ("attack", "hack", "breach", "exploit", "vuln", "malware", "ransomware", "backdoor",
             "injection", "exfiltrat", "compromise", "threat", "cve", "phishing", "espionage",
             "취약점", "침해", "해킹", "랜섬", "유출", "공격", "탈취", "악성", "보안위협", "사고")


def _link(url: str, text: str) -> str:
    """http(s) 링크만 a 태그로 — 피드가 준 javascript: · 상대 경로는 글자만 보인다."""
    if url and url.lower().startswith(("https://", "http://")):
        return f'<a href="{_e(url)}" target="_blank" rel="noopener">{_e(text)}</a>'
    return _e(text)


def _hay(it) -> str:
    return (" ".join(it.matched) + " " + it.title + " " + (it.summary or "")).lower()


def _is_agent_relevant(it) -> bool:
    return any(s in _hay(it) for s in _STRONG)


def _is_security(it) -> bool:
    return any(s in _hay(it) for s in _SECURITY)


def _now_and_incidents(items: list) -> tuple[str, str, list[str], list[str]]:
    """intel.jsonl → (NOW html, INCIDENTS html, now 출처, incident 출처). 에이전트 관련 항목만 큐레이션."""
    items = [i for i in items if _is_agent_relevant(i)]
    def row(it) -> str:
        d = it.jurisdiction or ""
        kind_ko = {"regulation": "규제", "guideline": "가이드", "threat_intel": "위협",
                   "incident": "사건", "standard": "표준", "mixed": "동향"}.get(it.topic, it.topic or "")
        k = " · ".join(x for x in (kind_ko, d, it.issuer) if x)
        dt = it.published[:10] if it.published else ""
        # 발행일이 없으면 수집일을 '수집' 이라고 밝혀 적는다 — 발행일처럼 보이면 안 된다
        shown = dt[5:] if dt else (f"수집 {it.first_seen[5:10]}" if it.first_seen else "날짜 없음")
        s = (it.summary or "")[:160]
        return (f'<li><time datetime="{_e(dt)}">{_e(shown)}</time>'
                f'<div><div class="k">{_e(k)}</div>'
                f'<div class="t">{_link(it.link, it.title)}</div>'
                + (f'<div class="s">{_e(s)}</div>' if s else "") + "</div></li>")

    reg = [i for i in items if i.topic in ("regulation", "guideline", "standard", "mixed")]
    inc = [i for i in items if i.topic in ("threat_intel", "incident") and _is_security(i)]

    def top(group, n=14):
        # 발행일 있는 것 최신순 → 없는 것(수집일 순)은 뒤로. 1차 먼저 (안정 정렬)
        group = sorted(group, key=lambda i: (i.published or i.first_seen or ""), reverse=True)
        group.sort(key=lambda i: not i.published)
        group.sort(key=lambda i: i.kind != "primary")
        return group[:n]

    now_items, inc_items = top(reg), top(inc)
    now_html = "\n".join(row(i) for i in now_items) or '<li class="fine">수집된 항목이 없습니다.</li>'
    inc_html = "\n".join(row(i) for i in inc_items) or '<li class="fine">수집된 항목이 없습니다.</li>'
    now_src = sorted({i.issuer for i in now_items if i.kind == "primary" and i.issuer})[:6]
    inc_src = sorted({i.issuer for i in inc_items if i.issuer})[:6]
    return now_html, inc_html, now_src, inc_src


def _incident_rows(incs) -> str:
    rows = []
    for i in sorted(incs, key=lambda x: x.date, reverse=True):
        k = " · ".join(x for x in (incidents_mod.AI_ROLE_KO.get(i.ai_role, i.ai_role), i.jurisdiction,
                                    {"primary": "1차", "vendor": "벤더 분석", "press": "보도"}[i.evidence_level]) if x)
        ctl = ", ".join(i.related_controls)
        rows.append(f'<li><time datetime="{_e(i.date)}">{_e(i.date)}</time><div><div class="k">{_e(k)}</div>'
                    f'<div class="t">{_link(i.source_url, i.title)}</div>'
                    + (f'<div class="s">관련 통제 — {_e(ctl)}</div>' if ctl else "") + "</div></li>")
    return "\n".join(rows)


def _matrix_section(docs, controls, coding, inc_counts=None, alt=None) -> tuple[str, str]:
    """alt = 다른 코더의 코딩. 주면 그 코더에선 관할 점수가 달라지는 칸에 ‡ 를 단다."""
    m = matrix_mod.build_matrix(docs, controls, coding)
    m_alt = matrix_mod.build_matrix(docs, controls, alt) if alt else None
    inc_counts = inc_counts or {}
    head = ("<thead><tr><th>통제</th>" + "".join(f"<th>{j}</th>" for j in JURISDICTIONS)
            + ('<th class="num" title="이 통제가 실패했거나 관련된 AI 에이전트 사건 수 (1차 증거)">사건</th>' if inc_counts else "")
            + "</tr></thead>")
    rows = []
    for c in controls:
        tds = [f"<th scope=\"row\">{c.num}. {_e(c.name_ko)}</th>"]
        for j in JURISDICTIONS:
            cell = m[j][c.id]
            mark = ""
            if m_alt is not None and m_alt[j][c.id].score != cell.score:
                other = m_alt[j][c.id].score
                mark = f'<sup class="fine" title="2차 코더: {"?" if other is None else other}">‡</sup>'
            tds.append(f'<td class="{_cell_class(cell.score)}">{_e(_cell_text(cell.score, cell.names_agents))}{mark}</td>')
        if inc_counts:
            r = inc_counts.get(c.id, {"total": 0, "primary": 0})
            tds.append(f'<td class="num">{r["total"]}<span class="fine"> ({r["primary"]})</span></td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    body = "<tbody>" + "\n".join(rows) + "</tbody>"
    return head + body, m


def _agreement_note(docs, controls, coding, alt, alt_name, incs) -> str:
    """방법 섹션의 '이 숫자로 말할 수 없는 것' 첫 줄들 — 코더 일치도를 실제 값으로."""
    from . import agreement as agreement_mod
    from . import kappa as kappa_mod
    if not alt:
        return "<li>1차 코딩은 발표 덱(2026-11-01)의 2차 인용 — provisional. 2차 코딩 전.</li>"
    res = kappa_mod.compare_coders(coding, alt, docs, controls)
    k = res["coverage"].kappa
    rows = matrix_mod.diff(matrix_mod.build_matrix(docs, controls, coding),
                           matrix_mod.build_matrix(docs, controls, alt), controls)
    n_judged = sum(1 for r in rows if r[2] is not None and r[3] is not None)
    out = [f"<li>문서 코딩: 1차(발표 덱 노트) vs 2차({_e(alt_name)}, 원문) — 공통 {res['n_cells']}칸 κ "
           f"{'n/a' if k is None else f'{k:.2f}'}. 관할 점수가 다른 칸 {len(rows)}개 = ‡ (판단이 갈림 {n_judged} · 1차 미코딩 {len(rows) - n_judged}). "
           "불일치는 대부분 '직원 통제(계정 정지·결재)를 에이전트 통제로 볼 것인가' 의 판정 규칙 차이다.</li>",
           "<li>2차 코더는 1차와 같은 모델 계열의 AI 다. κ 는 입력이 다른 두 AI 판단의 일치이지 사람 코더 간 신뢰도가 아니다.</li>"]
    raws = agreement_mod.load_incident_codings()
    if incs and alt_name in raws:
        first = {i.id: list(i.related_controls) for i in incs}
        second = agreement_mod.second_controls(raws[alt_name], set(first))
        a, b, _, per = agreement_mod.incident_vectors(first, second)
        ki = kappa_mod.cohen_kappa(a, b).kappa
        both = " · ".join(f"{c.id} {sum(1 for x, y in zip(*per[c.id]) if x and y)}" for c in controls)
        out.append(f"<li>사건 열은 1차 코더 기준. 사건 × 통제 κ {'n/a' if ki is None else f'{ki:.2f}'}. "
                   f"두 코더가 모두 실패를 본 사건 — {_e(both)}.</li>")
    return "".join(out)


def _gaps_section(m, controls) -> str:
    meaning = {None: "평가된 문서 없음", 0: "어떤 문서도 다루지 않음", 1: "자율 문서만"}
    out = []
    for j, cid, cell in matrix_mod.gaps(m, controls):
        c = next(x for x in controls if x.id == cid)
        txt = meaning.get(cell.score, "")
        if cell.score is None and cell.n_uncoded:
            txt = f"{cell.n_uncoded}개 문서 코딩 필요"
        cur = "?" if cell.score is None else str(cell.score)
        out.append(f'<li><time>{_e(j)}</time><div><div class="k">통제 {c.num} · {_e(c.name_ko)}</div>'
                   f'<div class="t">현재 {cur} — {_e(txt)}</div></div></li>')
    return "\n".join(out)


def _profile_section(rub) -> tuple[str, str, str]:
    groups = rub.groups()
    group_ko = {"agent_control": "에이전트 통제", "connection": "경고→조치 연결",
                "testing": "모의해킹·테스트", "response": "사고 대응"}
    cards = []
    for g, dims in groups.items():
        if not dims:  # 차원이 없는 그룹은 카드도 없다 (dims[0] 에서 IndexError 나던 것)
            continue
        cards.append(f'<div class="card"><div class="k">{_e(group_ko.get(g, g))}</div>'
                     f'<div class="v">{len(dims)}<span class="fine"> 차원</span></div>'
                     f'<div class="h">{_e(g)}</div></div>')
    head = "<thead><tr><th>#</th><th>차원</th><th>확인 질문</th><th>근거</th></tr></thead>"
    rows = []
    for d in rub.dimensions:
        basis = ", ".join(d.basis[:3])
        rows.append(f"<tr><td class=\"num\">{d.num}</td><th scope=\"row\">{_e(d.name_ko)}</th>"
                    f"<td>{_e(d.question)}</td><td class=\"fine\">{_e(basis)}</td></tr>")
    table = head + "<tbody>" + "\n".join(rows) + "</tbody>"
    return "\n".join(cards), table


def _timeline_section(docs) -> tuple[str, str]:
    dated = sorted((d for d in docs.values() if d.date), key=lambda d: d.date)  # type: ignore[arg-type]
    rows = []
    for d in dated:
        link = f'<a href="{_e(d.url)}" target="_blank" rel="noopener">{_e(d.title)}</a>' if d.url else _e(d.title)
        rows.append(f'<li><time datetime="{d.date}">{d.date}</time>'
                    f'<div><div class="k">{_e(d.jurisdiction)} · {_e(d.issuer)}</div>'
                    f'<div class="t">{link}</div></div></li>')
    rng = f"{dated[0].date} ~ {dated[-1].date}" if dated else ""
    return "\n".join(rows), rng


def _docs_section(docs) -> str:
    head = "<thead><tr><th>날짜</th><th>관할</th><th>기관</th><th>문서</th><th>종류</th></tr></thead>"
    rows = []
    order = sorted(docs.values(), key=lambda d: (d.jurisdiction, str(d.date or "")))
    for d in order:
        link = f'<a href="{_e(d.url)}" target="_blank" rel="noopener">{_e(d.title)}</a>' if d.url else _e(d.title)
        rows.append(f"<tr><td>{_e(d.date or '—')}</td><td>{_e(d.jurisdiction)}</td>"
                    f"<td>{_e(d.issuer)}</td><td>{link}</td><td class=\"fine\">{_e(d.doc_type)}</td></tr>")
    return head + "<tbody>" + "\n".join(rows) + "</tbody>"


def _feed_status(n_feeds: int, n_items: int) -> str:
    return (f'<span class="st st-live">live</span> 피드 {n_feeds}곳 · 수집 {n_items}건'
            if n_feeds else '<span class="st st-stale">stale</span> 피드 없음')


# ── 조립 ──────────────────────────────────────────────────────────────

def build(out_dir: Path = OUT_DIR, snapshot_dir: Path = SNAPSHOT_DIR, now: datetime | None = None) -> Path:
    controls = load_controls()
    docs = load_documents()
    codings = load_codings()
    coding = codings.get("deck_2026-11-01") or next(iter(codings.values()))
    alt_name = next((n for n in sorted(codings) if codings[n] is not coding), None)
    alt = codings.get(alt_name) if alt_name else None
    rub = rubric_mod.load_rubric()
    try:
        items = load_items(snapshot_dir)
    except FileNotFoundError:
        items = []

    now = now or datetime.now(timezone.utc)
    built_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    built = now.strftime("%Y-%m-%d %H:%M UTC")
    today = now.strftime("%Y-%m-%d")

    now_html, inc_html, now_src, inc_src = _now_and_incidents(items)
    incs = incidents_mod.load_incidents(control_ids={c.id for c in controls})
    inc_counts = incidents_mod.control_counts(incs)
    if incs:
        cur = sorted(incs, key=lambda x: x.date, reverse=True)
        inc_html = (_incident_rows(cur[:12])
                    + (f'<li class="more"><details><summary>사건 {len(cur) - 12}건 더 보기</summary><ul class="rows">'
                       + _incident_rows(cur[12:]) + "</ul></details></li>" if len(cur) > 12 else "")
                    + (f'<li class="more"><details><summary>피드에 새로 들어온 것</summary><ul class="rows">{inc_html}</ul></details></li>'
                       if inc_html and "수집된 항목이 없습니다" not in inc_html else ""))
        inc_src = ["registry/incidents.yaml"] + inc_src
    matrix_html, m = _matrix_section(docs, controls, coding, inc_counts, alt)
    agree_html = _agreement_note(docs, controls, coding, alt, alt_name, incs)
    gaps_html = _gaps_section(m, controls)
    cards_html, profile_html = _profile_section(rub)
    timeline_html, tl_range = _timeline_section(docs)
    docs_html = _docs_section(docs)

    n_feed_items = len(items)
    try:
        from .intel import load_feeds
        n_feeds = sum(1 for f in load_feeds() if f.get("enabled") is not False)
    except Exception:
        n_feeds = 0

    method = (
        "<p>세 층을 잰다. <strong>규제</strong>(문서 × 7통제, 구속력 0~3) · "
        "<strong>동향</strong>(발행 주체 피드에서 AI 에이전트 규제·위협을 바로) · "
        "<strong>평가</strong>(공개 자료로 재는 16개 차원). 점수·레벨은 '공개 증거 수준' 이지 "
        "'통제가 있다/없다' 가 아니다.</p>"
        f"<details><summary>소스 — 피드 {n_feeds}곳 · 문서 {len(docs)}건</summary>"
        "<p class=\"fine\">피드: KISA 보호나라 · 금융위 · 과기정통부 · 개인정보위 · NIST · 연준 · FDIC · 재무부 · SEC · "
        "FSB · EBA · ESMA · ECB · FCA · BoE · NCSC · JFSA + AI 위협 벤더 · arXiv. "
        "문서 URL 은 받아 본 것만 기록(registry/).</p></details>"
        "<details><summary>이 숫자로 말할 수 없는 것</summary><ul class=\"fine\">"
        + agree_html +
        "<li>공시 유무 ≠ 실행 유무. 미국 10-K 와 한국 사업보고서 공시 의무가 달라 국가 간 레벨 직접 비교 금지.</li>"
        "<li>평가 차원은 '무엇을 재는가' 만 보인다. 실제 기관 점수는 명예훼손·공정성 때문에 공개 페이지에 넣지 않았다.</li>"
        "<li>threat-intel·korea-primary 피드는 finder 가 받았으나 2차 verify 는 한도로 중단.</li>"
        "</ul></details>"
        "<p class=\"note\">정책 제안이며 법률 자문이 아니다. 개인 이름은 쓰지 않는다.</p>"
    )

    repl = {
        "PAGE_TITLE": "PivoxPolicy 동향·평가",
        "PAGE_DESCRIPTION": "AI 에이전트 금융 보안 규제·위협 동향과 내부통제 평가 — 발행 주체에서 바로, 공개 자료로.",
        "TOKENS_CSS": _tpl("tokens.css"),
        "BASE_CSS": _tpl("base.css"),
        "HEAT_CSS": _tpl("heat.css"),
        "BRAND_ARIA": "PivoxPolicy 홈", "BRAND_SUFFIX": "Policy",
        "KICKER": "AI 에이전트 · 금융 내부통제",
        "TITLE": "AI 에이전트 시대, 금융 내부통제를 재다",
        "LEDE": "규제·가이드라인이 무엇을 요구하는지, 공격이 어떻게 바뀌는지, 공개 자료로 무엇을 확인할 수 있는지를 한 곳에서.",
        "BUILT_AT_ISO": built_iso, "BUILT_AT": built,
        "FEED_STATUS": _feed_status(n_feeds, n_feed_items),
        "CHECKS": "점수·레벨 = 증거 수준",
        "NOW": now_html, "NOW_SOURCES": " · ".join(now_src) or "발행 주체 피드",
        "NOW_ASOF_ISO": today, "NOW_ASOF": today,
        "INCIDENTS": inc_html, "INCIDENTS_SOURCES": " · ".join(inc_src[:6]) or "공식 공지·보고서",
        "INCIDENTS_ASOF_ISO": today, "INCIDENTS_ASOF": today,
        "MATRIX_RUBRIC_ONE_LINE": "0 미다룸 · 1 자율 · 2 구속력 · 3 에이전트 명시 · ? 미확인",
        "MATRIX_CAPTION": "행 = 7개 에이전트 통제 · 열 = 관할. 칸 = 그 관할에서 그 통제를 요구하는 가장 센 문서의 구속력(1차 코더). ‡ = 2차 코더에선 점수가 다름. 마지막 열 = 그 통제가 실패했거나 관련된 AI 에이전트 사건 수(괄호 = 1차 증거).",
        "MATRIX": matrix_html,
        "H0_LABEL": _H_LABEL[0], "H1_LABEL": _H_LABEL[1], "H2_LABEL": _H_LABEL[2], "H3_LABEL": _H_LABEL[3],
        "MATRIX_SOURCES": "registry/documents · codings", "MATRIX_ASOF_ISO": today, "MATRIX_ASOF": today,
        "GAPS": gaps_html, "GAPS_SOURCES": "통제 × 관할 매트릭스", "GAPS_ASOF_ISO": today, "GAPS_ASOF": today,
        "PROFILE_SCOPE_ONE_LINE": "공개 자료로 재는 16개 차원 — 점수는 증거 수준이지 통제 유무가 아니다",
        "PROFILE_CARDS": cards_html, "PROFILE": profile_html,
        "PROFILE_RUBRIC_REF": "registry/rubric.yaml", "PROFILE_ASOF_ISO": today, "PROFILE_ASOF": today,
        "TIMELINE": timeline_html, "TIMELINE_RANGE": tl_range,
        "TIMELINE_SOURCES": "registry/documents", "TIMELINE_ASOF_ISO": today, "TIMELINE_ASOF": today,
        "DOCS": docs_html, "DOCS_COUNT": str(len(docs)), "DOCS_ASOF_ISO": today, "DOCS_ASOF": today,
        "METHOD": method, "DISCLAIMER": "정책 제안이며 법률 자문이 아니다.",
        "SITE_NAME": SITE_NAME, "CADENCE": "2시간마다 동향 갱신", "REPO_URL": REPO_URL,
    }
    import re
    page = _tpl("skeleton.html")
    # 저작용 주석(틀 예시·금지어 설명)을 뺀다 — 생성 결과엔 남기지 않는다.
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    # 한 번에 치환 — 차례로 replace 하면 앞 값(피드 제목 등) 안의 '{{DOCS}}' 가 뒤에서 펼쳐진다
    page = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda m: repl.get(m.group(1), m.group(0)), page)

    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "index.html"
    p.write_text(page, encoding="utf-8")
    return p
