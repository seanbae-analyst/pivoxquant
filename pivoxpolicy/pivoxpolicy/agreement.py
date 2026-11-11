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


def second_controls(raw: dict[str, Any], incident_ids: set[str] | None = None) -> dict[str, dict[str, bool]]:
    """incident_codings YAML({incidents:{iid:{controls:[...]}}}) → {iid:{ctl:bool}}.
    모르는 통제는 오류, incident_ids 를 주면 모르는 사건도 오류(오타가 '불일치' 로 섞이지 않게)."""
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
