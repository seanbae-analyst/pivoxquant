"""명령줄: pivoxpolicy <check|matrix|gaps|timeline|kappa|fetch|watch|report>"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
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
from .schema import SchemaError, coding_version, independent_v2, primary_coder, validate_adjudication, validate_coding


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
        for p in validate_coding(coding, docs, controls) + validate_adjudication(coding, codings):
            print(f"✗ codings/{coder}: {p}")
            problems += 1
    from . import agreement as agreement_mod
    inc_ids = {i.id for i in incidents_mod.load_incidents(control_ids={c.id for c in controls})}
    for coder, raw in agreement_mod.load_incident_codings().items():
        if agreement_mod.is_incident_v2(raw):
            corpus = SNAPSHOT_DIR / "incident_content"   # 받아 둔 원문이 있으면 인용도 대조
            for p in (agreement_mod.validate_incident_v2(raw, inc_ids, corpus if corpus.exists() else None)
                      + agreement_mod.validate_incident_adjudication(raw, agreement_mod.load_incident_codings())):
                print(f"✗ incident_codings/{coder}: {p}")
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
    if args.csv:  # 층을 안 고르면 AI·에이전트 층 (논문의 본 표)
        sys.stdout.write(matrix_mod.render_csv(ms["agent"], controls))
        return 0
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
    # 인자가 없으면 두 층(v2) 독립 코더 둘을 먼저(조정본은 독립 판단이 아니라 뺀다), 없으면 이름순 첫 둘
    v2 = independent_v2(codings)
    default = v2[:2] if len(v2) >= 2 else sorted(codings)[:2]
    a = args.a or default[0]
    b = args.b or default[1]
    if a not in codings or b not in codings:
        print(f"있는 코더: {', '.join(sorted(codings))}")
        return 2
    print(kappa_mod.render_compare(kappa_mod.compare(codings[a], codings[b], docs, controls)))
    return 0


def _note_sources(codings: dict[str, Any], coding: dict[str, Any]) -> list[dict[str, Any]]:
    """borderline 표시를 찾을 코딩 — 조정본이면 원본 둘도."""
    return [coding] + [codings[s] for s in (coding.get("adjudicates") or []) if s in codings]


def cmd_sensitivity(args: argparse.Namespace) -> int:
    from . import sensitivity as sens_mod
    controls, docs, codings = _load_all()
    coder, coding = _pick_coder(codings, args.coder)
    if coding_version(coding) != 2:
        print(f"{coder} 는 한 층(v1) 코딩 — 민감도는 두 층 코딩만")
        return 2
    print(sens_mod.render(sens_mod.flips(docs, controls, coding, _note_sources(codings, coding)), controls, coder))
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
    v2 = agreement_mod.independent_incident_v2(raws)
    if not args.coder and len(v2) >= 2:   # 코드북 v2 코더 둘 — 관점별 κ
        print(agreement_mod.render_incident_v2_agreement(raws[v2[0]], raws[v2[1]], v2[0], v2[1], set(first)))
    return 0


def cmd_incident_corpus(args: argparse.Namespace) -> int:
    from . import incident_corpus as ic
    controls = load_controls()
    incs = incidents_mod.load_incidents(control_ids={c.id for c in controls})
    data = ic.build(incs, only=set(args.ids) if args.ids else None)
    bad = {k: v for k, v in data["documents"].items() if v.get("http_status") != 200}
    thin = sorted(k for k, v in data["documents"].items() if v.get("thin"))
    print(f"사건 {len(data['documents'])} · 받지 못함 {len(bad)} · 얇음(2,500자 미만) {len(thin)} → {ic.MANIFEST}")
    for k, v in bad.items():
        print(f"  ✗ {k}: HTTP {v.get('http_status')}")
    for k in thin:
        print(f"  · thin {k}")
    return 1 if bad else 0


def cmd_pending(_: argparse.Namespace) -> int:
    from . import sim as sim_mod
    rows = sim_mod._all_pending()
    text = sim_mod.render_pending(rows)
    (sim_mod.OUT_DIR / "pending-regulations.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_sim(_: argparse.Namespace) -> int:
    from . import sim as sim_mod
    for p in sim_mod.build():
        print(f"wrote {p}")
    return 0


def cmd_site(_: argparse.Namespace) -> int:
    from . import landing as landing_mod
    from . import sim as sim_mod
    p = site_mod.build()
    print(f"wrote {p}")
    for q in sim_mod.build():   # 대시보드 메뉴의 '모의 테스트' 가 가리키는 페이지 — 같이 낸다
        print(f"wrote {q}")
    print(f"wrote {landing_mod.build()}")   # 첫 화면 — 모의 테스트 이력까지 반영한 뒤에
    from . import bundle as bundle_mod
    for q in bundle_mod.build():             # 오프라인 사본 — 위 세 페이지를 파일 하나씩으로
        print(f"wrote {q}")
    return 0


def cmd_serve(a: argparse.Namespace) -> int:
    from .runtime import server
    server.serve(a.host, a.port, a.db)
    return 0


def cmd_bundle(_: argparse.Namespace) -> int:
    from . import bundle as bundle_mod
    for q in bundle_mod.build():
        print(f"wrote {q}")
    return 0


def cmd_diagnose(a: argparse.Namespace) -> int:
    """에이전트 명세서 → 진단 보고서 한 벌. 서버 없이(샌드박스) 돈다."""
    from . import diagnosis, intake
    try:
        r = intake.build(Path(a.spec).read_text(encoding="utf-8"))
    except (OSError, intake.IntakeError) as e:
        print(f"명세를 읽지 못했다: {e}", file=sys.stderr)
        return 2
    agent = {"id": "agt_diagnose", "status": "active", "expires_at": None, **r["agent"], "compliance": r["compliance"], "cases": r["cases"],
             "intake": {"tools": r["tools"], "warnings": r["warnings"], "skipped": r["skipped"]}}
    D = diagnosis.diagnose(agent, r["components"], company=a.company)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {"report.html": diagnosis.to_html(D), "report.md": diagnosis.to_markdown(D), "rcm.csv": diagnosis.rcm_csv(D),
             "obligations.csv": diagnosis.obligations_csv(D)}
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    s, rs = D["assessment"]["summary"], D["attack"]["summary"]
    print(f"{agent['name']}: 걸리는 조문 {s['applicable']}(강제 {s['binding']}) · 구성상 저촉 {s['conflict']} · 미충족 {s['unmet']} · "
          f"시나리오 미차단 {rs['defect']} · 승인 의존 {rs['held']}")
    for w in r["warnings"]:
        print(f"  확인: {w}")
    print(f"→ {out}/ ({', '.join(files)})")
    return 0


def cmd_llm_redteam(a: argparse.Namespace) -> int:
    """실제 모델로 회사 에이전트의 프롬프트 · 도구를 돌린다(ANTHROPIC_API_KEY 또는 `ant auth login` 필요, 비용이 든다)."""
    import json as _json

    from . import intake
    from . import obligations as obl
    from .runtime import llm_redteam
    try:
        import anthropic
    except ImportError:
        print('Anthropic SDK 가 없다: pip install "anthropic>=2.8"', file=sys.stderr)
        return 2
    src = Path(a.spec).read_text(encoding="utf-8")
    try:
        built = intake.build(src)
    except intake.IntakeError as e:
        print(f"명세를 읽지 못했다: {e}", file=sys.stderr)
        return 2
    if a.levels == "spec":
        levels = None
    elif a.levels in ("all", "none"):
        levels = {c: (2 if a.levels == "all" else 0) for c in built["agent"]["levels"]}
    else:
        levels = obl.assess(obl.load_library(), built["compliance"])["levels"][a.levels]
    print(f"모델 {a.model} · 시나리오마다 {a.trials}회 · 통제 {a.levels} · 승인자 {a.approver} · 모델 호출 최대 {a.max_calls}회(비용이 든다)", file=sys.stderr)
    try:
        r = llm_redteam.run(anthropic.Anthropic(), src, trials=a.trials, levels=levels, approver=a.approver, model=a.model,
                            effort=a.effort, max_calls=a.max_calls, log=(lambda s: print(s, file=sys.stderr)) if a.verbose else (lambda s: None))
    except anthropic.AuthenticationError:
        print("Anthropic 인증 실패 — ANTHROPIC_API_KEY 또는 `ant auth login` 을 확인한다", file=sys.stderr)
        return 1
    except anthropic.APIStatusError as e:
        print(f"Anthropic API 오류 {e.status_code}: {e.message}", file=sys.stderr)
        return 1
    except TypeError as e:                     # 자격 증명이 아예 없으면 SDK 가 요청 때 TypeError 를 낸다
        if "authentication" not in str(e):
            raise
        print("Anthropic 자격 증명이 없다 — ANTHROPIC_API_KEY 를 넣거나 `ant auth login` 을 한다", file=sys.stderr)
        return 1
    except anthropic.APIConnectionError:
        print("Anthropic API 에 연결하지 못했다", file=sys.stderr)
        return 1
    md = llm_redteam.to_markdown(r)
    print(md)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md, encoding="utf-8")
        Path(a.out).with_suffix(".json").write_text(_json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
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

    se = sub.add_parser("sensitivity", help="칸 하나를 뒤집으면 바뀌는 관할 점수 (◆ = borderline 판정)")
    se.add_argument("--coder")
    se.set_defaults(fn=cmd_sensitivity)

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
    dg = sub.add_parser("diagnose", help="에이전트 명세서(도구 정의) → 진단 보고서(HTML · Markdown · RCM CSV · 조문 CSV). 서버 없이")
    dg.add_argument("spec", help="명세 YAML · JSON (예: examples/agent_spec_order.yaml)")
    dg.add_argument("--out", default="out/diagnosis", help="보고서를 쓸 폴더")
    dg.add_argument("--company", help="보고서 머리말에 넣을 회사 이름")
    dg.set_defaults(fn=cmd_diagnose)
    lr = sub.add_parser("llm-redteam", help="실제 LLM 으로 회사 에이전트의 프롬프트 · 도구를 돌려 숨은 지시를 따르는지와 런타임이 막는지를 잰다"
                                            " (ANTHROPIC_API_KEY 필요, 비용 발생)")
    lr.add_argument("spec", help="명세 YAML · JSON (agent.system_prompt 가 있으면 그것을 쓴다)")
    lr.add_argument("--trials", type=int, default=3, help="시나리오마다 반복 횟수")
    lr.add_argument("--levels", default="spec", choices=["spec", "all", "none", "binding_explicit", "binding_interpretive", "guideline"],
                    help="통제 수준: 명세의 지금 수준 · 모두 · 없음 · 적용 조문 모드")
    lr.add_argument("--approver", default="refuse", choices=["refuse", "approve"], help="사람 승인 요청에 승인자가 거부할지 · 승인할지(속은 승인자)")
    lr.add_argument("--model", default="claude-opus-5-5")
    lr.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    lr.add_argument("--max-calls", type=int, default=60, help="모델 호출 상한(비용 안전장치)")
    lr.add_argument("--out", help="결과 Markdown 경로(같은 이름의 .json 도 쓴다)")
    lr.add_argument("-v", "--verbose", action="store_true")
    lr.set_defaults(fn=cmd_llm_redteam)
    sub.add_parser("incidents", help="AI 에이전트 보안 사건 × 통제 교차표").set_defaults(fn=cmd_incidents)
    ik = sub.add_parser("incident-kappa", help="사건 × 통제 코딩 일치도 (1차 related_controls vs registry/incident_codings)")
    ik.add_argument("coder", nargs="?")
    ik.set_defaults(fn=cmd_incident_kappa)
    icp = sub.add_parser("incident-corpus", help="사건 source_url → 고정 원문(snapshots/incident_content/) + incident_corpus.json")
    icp.add_argument("ids", nargs="*", help="이 사건만 다시 받기 (나머지 고정본은 그대로)")
    icp.set_defaults(fn=cmd_incident_corpus)
    sub.add_parser("pending", help="자동 수집 피드에서 아직 레지스트리에 없는 새 규제·가이드라인 후보 → out/pending-regulations.md").set_defaults(fn=cmd_pending)
    sub.add_parser("sim", help="out/sim.html 모의 테스트 페이지 + out/simulation.md 프리셋 표").set_defaults(fn=cmd_sim)
    sub.add_parser("site", help="out/ 정적 사이트 — index.html 첫 화면 · dashboard.html 대시보드 · sim.html 모의 테스트 (+ offline/)").set_defaults(fn=cmd_site)
    sv = sub.add_parser("serve", help="런타임 서버(프로토타입) — 에이전트 등록 · 도구 호출 판정 · 승인 · 즉시 중단 · 레드팀, 콘솔 /admin")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8787)
    sv.add_argument("--db", default="runtime.db", help="SQLite 파일 (기본 runtime.db — 저장소에 올리지 않는다)")
    sv.set_defaults(fn=cmd_serve)
    sub.add_parser("bundle", help="out/offline/ — 서버 없이 더블클릭으로 여는 파일 하나짜리 사본").set_defaults(fn=cmd_bundle)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
