"""명령줄: pivoxpolicy <check|matrix|gaps|timeline|kappa|fetch|watch|report>"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from . import assess as assess_mod
from . import fetch as fetch_mod
from . import incidents as incidents_mod
from . import intel as intel_mod
from . import kappa as kappa_mod
from . import matrix as matrix_mod
from . import report as report_mod
from . import rubric as rubric_mod
from . import site as site_mod
from .registry import SNAPSHOT_DIR, load_codings, load_controls, load_documents, load_sources
from .schema import SchemaError, coding_version, primary_coder, validate_coding


def _load_all() -> tuple[Any, Any, Any]:
    controls = load_controls()
    docs = load_documents()
    codings = load_codings()
    return controls, docs, codings


def cmd_check(_: argparse.Namespace) -> int:
    try:
        controls, docs, codings = _load_all()
    except SchemaError as e:
        print(f"✗ 스키마 오류: {e}")
        return 1
    problems = 0
    for coder, coding in codings.items():
        for p in validate_coding(coding, docs, controls):
            print(f"✗ codings/{coder}: {p}")
            problems += 1
    n_url = sum(1 for d in docs.values() if d.url)
    n_verified = sum(1 for d in docs.values() if d.url_verified)
    print(f"통제 {len(controls)} · 문서 {len(docs)} (URL {n_url}, 검증 {n_verified}) · 코더 {len(codings)}: {', '.join(codings) or '없음'}")
    if problems:
        print(f"✗ 코딩 문제 {problems}건")
        return 1
    print("✓ 통과")
    return 0


def _pick_coder(codings: dict[str, Any], name: str | None) -> tuple[str, Any]:
    if not codings:
        raise SystemExit("코딩 파일이 없음 (registry/codings/*.yaml)")
    if name:
        if name not in codings:
            raise SystemExit(f"코더 {name!r} 없음. 있는 코더: {', '.join(codings)}")
        return name, codings[name]
    k = primary_coder(codings)
    assert k is not None
    return k, codings[k]


def cmd_matrix(args: argparse.Namespace) -> int:
    controls, docs, codings = _load_all()
    coder, coding = _pick_coder(codings, args.coder)
    ms = matrix_mod.layer_matrices(docs, controls, coding)
    layer = getattr(args, "layer", None)
    if "" in ms:  # v1 코딩 — 층이 없다
        if layer:
            print(f"`{coder}` 는 한 칸(v1) 코딩이라 층이 없다 — --layer 를 빼라.")
            return 2
        m = ms[""]
        sys.stdout.write(matrix_mod.render_csv(m, controls) if args.csv else matrix_mod.render_markdown(m, controls, coder, docs) + "\n")
        return 0
    if layer:
        m = ms[layer]
        sys.stdout.write(matrix_mod.render_csv(m, controls) if args.csv
                         else matrix_mod.render_markdown(m, controls, coder, docs, layer) + "\n")
        return 0
    if args.csv:
        print("두 층 코딩의 CSV 는 층을 골라야 한다: --layer analog | agent")
        return 2
    print(matrix_mod.render_layers(ms["analog"], ms["agent"], controls, coder))
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    controls, docs, codings = _load_all()
    coder, coding = _pick_coder(codings, args.coder)
    ms = matrix_mod.layer_matrices(docs, controls, coding)
    if "" in ms:
        print(report_mod.render_gaps(ms[""], controls, coder))
    else:
        print(report_mod.render_layer_gaps(ms["analog"], ms["agent"], controls, coder))
    return 0


def cmd_timeline(_: argparse.Namespace) -> int:
    _, docs, _ = _load_all()
    print(report_mod.render_timeline(docs))
    return 0


def cmd_kappa(args: argparse.Namespace) -> int:
    controls, docs, codings = _load_all()
    if len(codings) < 2:
        print("코더가 둘 이상 필요. registry/codings/TEMPLATE.yaml 을 복사해 두 번째 코더 파일을 만들어라.")
        return 2
    # 인자가 없으면 두 층(v2) 코더 둘을 먼저, 없으면 이름순 첫 둘
    v2 = sorted(k for k, c in codings.items() if coding_version(c) == 2)
    default = v2[:2] if len(v2) >= 2 else sorted(codings)[:2]
    a = args.a or default[0]
    b = args.b or default[1]
    if a not in codings or b not in codings:
        print(f"있는 코더: {', '.join(sorted(codings))}")
        return 2
    print(kappa_mod.render_compare(kappa_mod.compare(codings[a], codings[b], docs, controls)))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    _, docs, _ = _load_all()
    manifest = fetch_mod.load_manifest()
    only = set(args.ids) if args.ids else None
    events = fetch_mod.snapshot_documents(docs, manifest, only=only)
    fetch_mod.save_manifest(manifest)
    sys.stdout.write(fetch_mod.render_events(events))
    print(f"매니페스트: {SNAPSHOT_DIR / 'manifest.json'}")
    return 0


def cmd_watch(_: argparse.Namespace) -> int:
    sources = load_sources()
    manifest = fetch_mod.load_manifest()
    events = fetch_mod.watch_sources(sources, manifest)
    fetch_mod.save_manifest(manifest)
    sys.stdout.write(fetch_mod.render_events(events))
    return 0


def cmd_intel(args: argparse.Namespace) -> int:
    feeds = intel_mod.load_feeds()
    if not feeds:
        print("registry/feeds.yaml 이 없거나 비어 있음")
        return 2
    known = intel_mod.load_items()
    new, status = intel_mod.collect(feeds, known, only_matching=not args.all)
    if not args.dry_run:
        intel_mod.append_items(new)
    sys.stdout.write(intel_mod.render_new(new, status))
    if args.dry_run:
        print("(dry-run — 저장 안 함)")
    return 0


def cmd_rubric(args: argparse.Namespace) -> int:
    rub = rubric_mod.load_rubric()
    if args.codebook:
        print(rubric_mod.render_codebook(rub))
        return 0
    if args.check:
        problems = 0
        for name, a in rubric_mod.load_assessments().items():
            for p in rubric_mod.validate_assessment(a, rub):
                print(f"✗ assessments/{name}: {p}")
                problems += 1
        asmts = rubric_mod.load_assessments()
        print(f"차원 {len(rub.dimensions)} · 평가 {len(asmts)}: {', '.join(asmts) or '없음'}"
              + (" · provisional" if rub.provisional else ""))
        if problems:
            print(f"✗ 평가 문제 {problems}건")
            return 1
        print("✓ 통과")
        return 0
    # 루브릭 자체를 보여 준다
    for g, dims in rub.groups().items():
        print(f"## {g}")
        for d in dims:
            print(f"  {d.num} {d.name_ko} ({d.name_en}) — {d.question}")
        print()
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    rub = rubric_mod.load_rubric()
    asmts = rubric_mod.load_assessments()
    if not asmts:
        print("평가 파일이 없음 (registry/assessments/*.yaml). TEMPLATE.yaml 을 복사해 만든다.")
        return 2
    if args.compare:
        profiles = [assess_mod.build_profile(a, rub) for a in asmts.values()]
        print(assess_mod.render_comparison(profiles, rub))
        return 0
    if args.subject:
        if args.subject not in asmts:
            print(f"평가 {args.subject!r} 없음. 있는 것: {', '.join(asmts)}")
            return 2
        items = [(args.subject, asmts[args.subject])]
    else:
        items = list(asmts.items())
    for _, a in items:
        print(assess_mod.render_profile(assess_mod.build_profile(a, rub), rub))
    return 0


def cmd_assess_kappa(args: argparse.Namespace) -> int:
    rub = rubric_mod.load_rubric()
    asmts = rubric_mod.load_assessments()
    if args.a not in asmts or args.b not in asmts:
        print(f"두 평가가 필요. 있는 것: {', '.join(asmts)}")
        return 2
    res = assess_mod.compare_assessors(asmts[args.a], asmts[args.b], rub)
    print(assess_mod.render_kappa(res))
    return 0


def cmd_incidents(_: argparse.Namespace) -> int:
    controls = load_controls()
    print(incidents_mod.render_markdown(incidents_mod.load_incidents(control_ids={c.id for c in controls}), controls))
    return 0


def cmd_incident_kappa(args: argparse.Namespace) -> int:
    from . import agreement as agreement_mod
    controls = load_controls()
    incs = incidents_mod.load_incidents(control_ids={c.id for c in controls})
    first = {i.id: list(i.related_controls) for i in incs}
    raws = agreement_mod.load_incident_codings()
    names = [args.coder] if args.coder else sorted(raws)
    if not names or any(n not in raws for n in names):
        print(f"registry/incident_codings/ 에 있는 코더: {', '.join(sorted(raws)) or '(없음)'}")
        return 2
    for n in names:
        raw = raws[n]
        try:
            second = agreement_mod.second_controls(raw, set(first))
        except agreement_mod.IncidentCodingError as e:
            print(f"{n}: {e}")
            return 1
        basis = {k: (v or {}).get("basis", "") for k, v in (raw.get("incidents") or {}).items()}
        print(agreement_mod.render_incident_agreement(first, second, n, basis))
    return 0


def cmd_site(_: argparse.Namespace) -> int:
    p = site_mod.build()
    print(f"wrote {p}")
    return 0


def cmd_report(_: argparse.Namespace) -> int:
    controls, docs, codings = _load_all()
    for p in report_mod.write_all(docs, controls, codings):
        print(f"wrote {p.relative_to(p.parents[1])}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pivoxpolicy", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="레지스트리·코딩 스키마 검사").set_defaults(fn=cmd_check)

    m = sub.add_parser("matrix", help="통제 × 관할 점수 매트릭스")
    m.add_argument("--coder")
    m.add_argument("--layer", choices=["analog", "agent"], help="두 층(v2) 코딩에서 한 층만 — 없으면 두 층을 나란히")
    m.add_argument("--csv", action="store_true")
    m.set_defaults(fn=cmd_matrix)

    g = sub.add_parser("gaps", help="구속력 2 미만·미코딩 셀")
    g.add_argument("--coder")
    g.set_defaults(fn=cmd_gaps)

    sub.add_parser("timeline", help="발표일 순 연표").set_defaults(fn=cmd_timeline)

    k = sub.add_parser("kappa", help="코더 두 명의 일치도")
    k.add_argument("--a")
    k.add_argument("--b")
    k.set_defaults(fn=cmd_kappa)

    f = sub.add_parser("fetch", help="문서 URL 스냅숏·변경 감지")
    f.add_argument("ids", nargs="*", help="특정 문서 id 만")
    f.set_defaults(fn=cmd_fetch)

    sub.add_parser("watch", help="발표 목록 페이지에서 새 글 찾기").set_defaults(fn=cmd_watch)

    i = sub.add_parser("intel", help="RSS/Atom/JSON 피드에서 AI 에이전트 관련 새 항목 수집 → snapshots/intel.jsonl")
    i.add_argument("--all", action="store_true", help="키워드 필터 없이 전부")
    i.add_argument("--dry-run", action="store_true", help="저장하지 않고 보기만")
    i.set_defaults(fn=cmd_intel)

    ru = sub.add_parser("rubric", help="내부통제 평가 루브릭. --codebook 로 채점 절차 전문, --check 로 평가 스키마 검사")
    ru.add_argument("--check", action="store_true")
    ru.add_argument("--codebook", action="store_true")
    ru.set_defaults(fn=cmd_rubric)

    asm = sub.add_parser("assess", help="기관 내부통제 평가 프로필 (단일 등급 없음)")
    asm.add_argument("subject", nargs="?", help="특정 평가 파일 stem")
    asm.add_argument("--compare", action="store_true", help="모든 평가를 기관 × 차원 격자로")
    asm.set_defaults(fn=cmd_assess)

    ak = sub.add_parser("assess-kappa", help="같은 기관을 평가한 두 평가자의 일치도")
    ak.add_argument("a")
    ak.add_argument("b")
    ak.set_defaults(fn=cmd_assess_kappa)
    sub.add_parser("report", help="out/ 에 매트릭스·연표·공백·kappa 전부 쓰기").set_defaults(fn=cmd_report)
    sub.add_parser("incidents", help="AI 에이전트 보안 사건 × 통제 교차표").set_defaults(fn=cmd_incidents)
    ik = sub.add_parser("incident-kappa", help="사건 × 통제 코딩 일치도 (1차 related_controls vs registry/incident_codings)")
    ik.add_argument("coder", nargs="?")
    ik.set_defaults(fn=cmd_incident_kappa)
    sub.add_parser("site", help="out/index.html 정적 대시보드 생성 (Pivox 디자인)").set_defaults(fn=cmd_site)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
