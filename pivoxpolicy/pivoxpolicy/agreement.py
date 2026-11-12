"""2차 코딩 합치기 · 사건 × 통제 코딩의 코더 간 일치도.

- 문서 코딩(문서 × 통제 covered)의 κ 는 kappa.compare_coders 가 이미 낸다 — 여기서는 에이전트가 낸 JSON 을
  registry/codings/<coder>.yaml 로 옮기는 것만 한다.
- 사건 코딩(사건 × 통제 실패 여부)은 registry/incidents.yaml 의 related_controls(1차)와
  registry/incident_codings/<coder>.yaml(2차)을 통제마다 참/거짓으로 펼쳐 κ 를 낸다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from . import kappa as kappa_mod
from .registry import REGISTRY_DIR

CONTROL_IDS = ("inventory", "vendors", "unique_id", "least_privilege", "human_approval", "audit_trail", "kill_switch")


# PyYAML 이 읽는 글자(printable) 밖 — DEL · C1 제어문자 등. json.dumps 는 C0 만 이스케이프해서 이것들이 날것으로 남고,
# 그러면 그 코딩 파일 하나 때문에 모든 명령이 ReaderError 로 죽는다.
# U+0085 · U+2028 · U+2029 는 YAML 에선 줄바꿈이라 큰따옴표 안에서도 접혀(앞 공백이 사라짐) 값이 바뀐다 — 함께 이스케이프.
_NON_PRINTABLE = re.compile("[^\x09\x0A\x0D\x20-\x7E\xA0-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]|[\u2028\u2029]")


def _q(s: Any) -> str:
    """YAML 큰따옴표 문자열. JSON 문자열은 YAML 큰따옴표 문자열이기도 하다."""
    out = json.dumps("" if s is None else str(s), ensure_ascii=False)
    return _NON_PRINTABLE.sub(lambda m: f"\\u{ord(m.group(0)):04x}", out)


def _tri(v: Any, where: str) -> bool | None:
    """에이전트가 낸 covered 값 → True/False/None. 'true' 같은 글자는 받아 주고, 그 밖은 오류
    (예전엔 'true' 문자열이 조용히 null 이 됐다)."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "false", "null", "none", ""):
        t = v.strip().lower()
        return True if t == "true" else False if t == "false" else None
    raise ValueError(f"{where}: covered 는 true/false/null (받음: {v!r})")


def coding_yaml(result: dict[str, Any], coder: str, basis: str, coded_at: str) -> str:
    """에이전트 JSON({items:{doc:{ctl:{covered,evidence,note}}}}) → codings YAML 글."""
    lines = [
        f"# 2차 코딩 — {coder}. AI 코더(에이전트)가 1차 코딩을 보지 않고 원문을 받아 코딩했다.",
        "# 같은 모델 계열이 1차(덱 노트 기반)와 2차(원문 기반)를 했으므로, κ 는 '입력이 다른 두 AI 판단의 일치' 이지",
        "# 사람 코더 간 신뢰도가 아니다. 논문에는 사람 코더 1명을 더해 보고하는 것이 맞다.",
        f"coder: {_q(coder)}",
        f"coded_at: {_q(coded_at)}",
        f"basis: {_q(basis)}",
        "provisional: true",
        "items:",
    ]
    for doc_id, cells in sorted((result.get("items") or {}).items()):
        lines.append(f"  {_q(doc_id)}:")
        for cid in CONTROL_IDS:
            c = (cells or {}).get(cid) or {}
            cov = _tri(c.get("covered"), f"{doc_id}.{cid}")
            cov_s = "true" if cov is True else "false" if cov is False else "null"
            parts = [f"covered: {cov_s}"]
            if c.get("evidence"):
                parts.append(f"evidence: {_q(c['evidence'])}")
            if c.get("note"):
                parts.append(f"note: {_q(c['note'])}")
            lines.append(f"    {cid}: {{{', '.join(parts)}}}")
    return "\n".join(lines) + "\n"


def coding_yaml_v2(result: dict[str, Any], coder: str, basis: str, coded_at: str, header: list[str] | None = None) -> str:
    """두 층 코딩 — 에이전트 JSON({items:{doc:{ctl:{analog:{covered,evidence}, agent:{covered,subject,evidence}, note}}}})
    → codings YAML 글(codebook: 2). 빠진 통제·층은 null(미코딩)."""
    lines = [f"# {h}" for h in (header or [])] + [
        f"coder: {_q(coder)}",
        f"coded_at: {_q(coded_at)}",
        "codebook: 2",
        f"basis: {_q(basis)}",
        "provisional: true",
        "items:",
    ]
    for doc_id, cells in sorted((result.get("items") or {}).items()):
        lines.append(f"  {_q(doc_id)}:")
        for cid in CONTROL_IDS:
            c = (cells or {}).get(cid) or {}
            lines.append(f"    {cid}:")
            for layer in ("analog", "agent"):
                sub = c.get(layer) if isinstance(c.get(layer), dict) else {}
                cov = _tri(sub.get("covered"), f"{doc_id}.{cid}.{layer}")
                parts = [f"covered: {'true' if cov is True else 'false' if cov is False else 'null'}"]
                if layer == "agent":
                    subj = sub.get("subject") if cov is True else None
                    if cov is True and subj not in ("agent", "ai"):
                        raise ValueError(f"{doc_id}.{cid}.agent: covered true 면 subject 는 agent/ai (받음: {subj!r})")
                    parts.append(f"subject: {subj if subj else 'null'}")
                if cov is True:
                    if not sub.get("evidence"):
                        raise ValueError(f"{doc_id}.{cid}.{layer}: covered true 인데 evidence 없음")
                    parts.append(f"evidence: {_q(sub['evidence'])}")
                lines.append(f"      {layer}: {{{', '.join(parts)}}}")
            if c.get("note"):
                lines.append(f"      note: {_q(c['note'])}")
    return "\n".join(lines) + "\n"


class IncidentCodingError(ValueError):
    pass


def load_incident_codings(registry_dir: Path = REGISTRY_DIR) -> dict[str, dict[str, Any]]:
    d = registry_dir / "incident_codings"
    out: dict[str, dict[str, Any]] = {}
    if not d.exists():
        return out
    for p in sorted(d.glob("*.yaml")):
        out[p.stem] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return out


# ── 사건 코드북 v2 (registry/incident_codebook.yaml) — 칸마다 failed · level(stated/inferred) · layer(agent/analog) ──

INCIDENT_LEVELS = ("stated", "inferred")
INCIDENT_LAYERS = ("agent", "analog")
# κ 를 내는 관점 — 칸을 참/거짓으로 펴는 법
INCIDENT_VIEWS: dict[str, str] = {
    "stated": "원문이 실패를 적은 것만 (stated)",
    "any": "적었거나 추론 (stated ∨ inferred) — v1 과 견주는 값",
    "agent": "AI·에이전트 층 (수준 무관)",
    "analog": "일반 통제 층 (수준 무관)",
}


def is_incident_v2(raw: dict[str, Any] | None) -> bool:
    return isinstance(raw, dict) and raw.get("codebook") == 2


def _view_true(cell: dict[str, Any], view: str) -> bool:
    if cell.get("failed") is not True:
        return False
    if view == "stated":
        return cell.get("level") == "stated"
    if view in INCIDENT_LAYERS:
        return cell.get("layer") == view
    return True


def validate_incident_v2(raw: dict[str, Any], incident_ids: set[str] | None = None,
                         corpus_dir: Path | None = None) -> list[str]:
    """v2 사건 코딩의 문제 목록. corpus_dir 를 주면 인용이 원문에 그대로 있는지도 본다."""
    problems: list[str] = []
    for iid, rec in sorted((raw.get("incidents") or {}).items()):
        if incident_ids is not None and iid not in incident_ids:
            problems.append(f"모르는 사건: {iid}")
            continue
        ctls = (rec or {}).get("controls") or {}
        if not isinstance(ctls, dict):
            problems.append(f"{iid}: controls 는 통제 → {{failed, …}} 매핑")
            continue
        text = None
        if corpus_dir is not None and (corpus_dir / f"{iid}.txt").exists():
            text = " ".join((corpus_dir / f"{iid}.txt").read_text(encoding="utf-8").split())
        for cid, cell in ctls.items():
            where = f"{iid}.{cid}"
            if cid not in CONTROL_IDS:
                problems.append(f"{where}: 모르는 통제")
                continue
            f = (cell or {}).get("failed")
            if f not in (True, False, None):
                problems.append(f"{where}: failed 는 true/false/null")
            if f is True:
                if cell.get("level") not in INCIDENT_LEVELS:
                    problems.append(f"{where}: level 은 stated/inferred")
                if cell.get("layer") not in INCIDENT_LAYERS:
                    problems.append(f"{where}: layer 는 agent/analog")
                if not cell.get("quote"):
                    problems.append(f"{where}: quote 필요")
                elif text is not None and " ".join(str(cell["quote"]).split()) not in text:
                    problems.append(f"{where}: quote 가 원문에 없음")
    return problems


def incident_view(raw: dict[str, Any], view: str, incident_ids: set[str] | None = None) -> dict[str, dict[str, bool]]:
    """v2 사건 코딩 → {iid:{ctl:bool}}. basis thin 이거나 null 이 섞인 사건은 뺀다(판단 못 함)."""
    if view not in INCIDENT_VIEWS:
        raise ValueError(f"view 는 {tuple(INCIDENT_VIEWS)} 중 하나")
    probs = validate_incident_v2(raw, incident_ids)
    if probs:
        raise IncidentCodingError(probs[0])
    out: dict[str, dict[str, bool]] = {}
    for iid, rec in sorted((raw.get("incidents") or {}).items()):
        ctls = (rec or {}).get("controls") or {}
        if (rec or {}).get("basis") == "thin" or any((ctls.get(c) or {}).get("failed") is None for c in CONTROL_IDS):
            continue
        out[iid] = {c: _view_true(ctls[c], view) for c in CONTROL_IDS}
    return out


def render_incident_v2_agreement(raw_a: dict[str, Any], raw_b: dict[str, Any], a: str, b: str,
                                 incident_ids: set[str] | None = None) -> str:
    """v2 사건 코더 둘의 κ — 관점마다 · 통제마다."""
    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    va = {v: incident_view(raw_a, v, incident_ids) for v in INCIDENT_VIEWS}
    vb = {v: incident_view(raw_b, v, incident_ids) for v in INCIDENT_VIEWS}
    common = sorted(set(va["any"]) & set(vb["any"]))
    thin = sorted((set(raw_a.get("incidents") or {}) | set(raw_b.get("incidents") or {})) - set(common))
    lines = [f"# 사건 × 통제 코딩 일치도 (코드북 v2) — `{a}` vs `{b}`", "",
             f"공통 사건 {len(common)}건 × 통제 7 = 셀 {len(common) * 7}. 원문이 얇거나 한쪽이 판단을 못 한 사건 {len(thin)}건은 뺐다"
             + (": " + ", ".join(f"`{i}`" for i in thin) if thin else "") + ".", "",
             "| 관점 | A 참 | B 참 | 둘 다 참 | 일치율 | κ | Landis–Koch |", "|---|---|---|---|---|---|---|"]
    per_view: dict[str, Any] = {}
    for v, label in INCIDENT_VIEWS.items():
        x = [va[v][i][c] for i in common for c in CONTROL_IDS]
        y = [vb[v][i][c] for i in common for c in CONTROL_IDS]
        k = kappa_mod.cohen_kappa(x, y)
        per_view[v] = (x, y)
        lines.append(f"| {label} | {sum(x)} | {sum(y)} | {sum(p and q for p, q in zip(x, y))} | {f(k.observed_agreement)} | "
                     f"**{f(k.kappa)}** | {k.landis_koch()} |")
    lines += ["", "## 통제별 — 둘 다 참 (보수적인 사건 수)", "",
              "| 통제 | 적은 것만: 둘 다 참 · κ | 적었거나 추론: 둘 다 참 · κ | 그중 AI 층 · 일반 층 (둘 다 참) |", "|---|---|---|---|"]
    for c in CONTROL_IDS:
        cells = []
        for v in ("stated", "any"):
            x = [va[v][i][c] for i in common]
            y = [vb[v][i][c] for i in common]
            cells.append(f"{sum(p and q for p, q in zip(x, y))} · {f(kappa_mod.cohen_kappa(x, y).kappa)}")
        lay = [sum(va[v][i][c] and vb[v][i][c] for i in common) for v in ("agent", "analog")]
        lines.append(f"| {c} | {cells[0]} | {cells[1]} | {lay[0]} · {lay[1]} |")
    lines += ["", "## 불일치 — 적었거나 추론 관점", ""]
    n = 0
    ia, ib = raw_a.get("incidents") or {}, raw_b.get("incidents") or {}
    for i in common:
        for c in CONTROL_IDS:
            if va["any"][i][c] != vb["any"][i][c]:
                n += 1
                side, cell = ("A", ia[i]["controls"][c]) if va["any"][i][c] else ("B", ib[i]["controls"][c])
                lines.append(f"- `{i}` × {c} — {side} 만 참 ({cell.get('level')}/{cell.get('layer')}): {cell.get('reason', '')}")
    if not n:
        lines.append("없음.")
    return "\n".join(lines) + "\n"


def incident_coding_yaml_v2(result: dict[str, Any], coder: str, coded_at: str, basis: str,
                            header: list[str] | None = None) -> str:
    """블라인드 에이전트 JSON → incident_codings YAML (codebook: 2)."""
    lines = [f"# {h}" for h in (header or [])] + [
        f"coder: {_q(coder)}", f"coded_at: {_q(coded_at)}", "codebook: 2", f"basis: {_q(basis)}", "provisional: true", "incidents:"]
    for iid, rec in sorted((result.get("incidents") or {}).items()):
        lines.append(f"  {_q(iid)}:")
        lines.append(f"    basis: {_q((rec or {}).get('basis') or 'source')}")
        lines.append("    controls:")
        ctls = (rec or {}).get("controls") or {}
        for c in CONTROL_IDS:
            cell = ctls.get(c) or {}
            fv = _tri(cell.get("failed"), f"{iid}.{c}")
            parts = [f"failed: {'true' if fv is True else 'false' if fv is False else 'null'}"]
            if fv is True:
                for k in ("level", "layer", "quote", "reason"):
                    parts.append(f"{k}: {_q(cell.get(k))}")
            lines.append(f"      {c}: {{{', '.join(parts)}}}")
        if (rec or {}).get("note"):
            lines.append(f"    note: {_q(rec['note'])}")
    return "\n".join(lines) + "\n"


def second_controls(raw: dict[str, Any], incident_ids: set[str] | None = None) -> dict[str, dict[str, bool]]:
    """incident_codings YAML({incidents:{iid:{controls:[...]}}}) → {iid:{ctl:bool}}.
    v2 코딩(codebook: 2)은 '적었거나 추론' 관점으로 편다 — v1·1차와 같은 물음.
    모르는 통제는 오류, incident_ids 를 주면 모르는 사건도 오류(오타가 '불일치' 로 섞이지 않게)."""
    if is_incident_v2(raw):
        return incident_view(raw, "any", incident_ids)
    out: dict[str, dict[str, bool]] = {}
    for iid, rec in sorted((raw.get("incidents") or {}).items()):
        if incident_ids is not None and iid not in incident_ids:
            raise IncidentCodingError(f"모르는 사건: {iid}")
        ctls = (rec or {}).get("controls") or []
        if not isinstance(ctls, list):
            raise IncidentCodingError(f"{iid}: controls 는 목록이어야 함 (받음: {ctls!r})")
        bad = [c for c in ctls if c not in CONTROL_IDS]
        if bad:
            raise IncidentCodingError(f"{iid}: 모르는 통제 {bad}")
        out[iid] = {c: c in ctls for c in CONTROL_IDS}
    return out


def incident_vectors(first: dict[str, list[str]], second: dict[str, dict[str, bool]]) -> tuple[list[bool], list[bool], list[tuple[str, str]], dict[str, tuple[list[bool], list[bool]]]]:
    """1차 {incident: [controls]} · 2차 {incident: {control: bool}} → 공통 사건의 (사건, 통제) 참/거짓 벡터.
    셋째 값 = 불일치 (사건, 통제), 넷째 = 통제별 벡터(통제마다 κ 용)."""
    a: list[bool] = []
    b: list[bool] = []
    diff: list[tuple[str, str]] = []
    per: dict[str, tuple[list[bool], list[bool]]] = {c: ([], []) for c in CONTROL_IDS}
    for iid in sorted(set(first) & set(second)):
        for c in CONTROL_IDS:
            x = c in (first[iid] or [])
            v = (second[iid] or {}).get(c)
            if v is not None and not isinstance(v, bool):
                # bool("false") = True 였다 — 진짜 bool 만 받는다
                raise IncidentCodingError(f"{iid}.{c}: 참/거짓이어야 함 (받음: {v!r})")
            y = v is True
            a.append(x)
            b.append(y)
            per[c][0].append(x)
            per[c][1].append(y)
            if x != y:
                diff.append((iid, c))
    return a, b, diff, per


def render_incident_agreement(first: dict[str, list[str]], second: dict[str, dict[str, bool]], coder_b: str,
                              basis: dict[str, str] | None = None) -> str:
    a, b, diff, per = incident_vectors(first, second)
    k = kappa_mod.cohen_kappa(a, b)
    common = set(first) & set(second)
    n_inc = len(common)
    only_first = sorted(set(first) - set(second))
    only_second = sorted(set(second) - set(first))

    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = [
        f"# 사건 × 통제 코딩 일치도 — 1차(finder) vs `{coder_b}`",
        "",
        f"공통 사건 {n_inc}건 × 통제 7 = 셀 {len(a)}. 관측 일치율 {f(k.observed_agreement)} · κ {f(k.kappa)} ({k.landis_koch()})",
        "",
        "'둘 다 참' 은 두 코더가 모두 이 통제의 실패를 본 사건 수 — 코더에 덜 기대는 보수적인 숫자다.",
        "",
        "| 통제 | 1차 참 | 2차 참 | 둘 다 참 | 일치율 | κ |",
        "|---|---|---|---|---|---|",
    ]
    for c in CONTROL_IDS:
        x, y = per[c]
        kc = kappa_mod.cohen_kappa(x, y)
        both = sum(1 for p, q in zip(x, y) if p and q)
        lines.append(f"| {c} | {sum(x)} | {sum(y)} | {both} | {f(kc.observed_agreement)} | {f(kc.kappa)} |")
    if basis:
        thin = sorted(i for i in common if basis.get(i) == "summary_only")
        if thin:
            lines += ["", f"2차 코더가 원문을 못 읽고 요약으로만 판단한 사건 {len(thin)}건: " + ", ".join(f"`{i}`" for i in thin)]
    if only_first or only_second:
        lines += ["", f"한쪽에만 있는 사건 — 1차만 {len(only_first)} · 2차만 {len(only_second)} (κ 에서 뺐다)"]
    lines += ["", f"## 불일치 {len(diff)}칸", ""]
    for iid, c in diff:
        side = "1차만 참" if c in (first.get(iid) or []) else "2차만 참"
        lines.append(f"- `{iid}` × {c} — {side}")
    return "\n".join(lines) + "\n"
