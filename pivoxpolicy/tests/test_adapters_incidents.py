"""커스텀 API 어댑터(2026-11-11 실측 응답 모양) · 사건 레지스트리 · 레벨 0 출처 규칙."""

import json
import re
from datetime import datetime, timezone

import pytest

from pivoxpolicy.fetch import FetchResult
from pivoxpolicy.incidents import IncidentError, Incident, control_counts, load_incidents
from pivoxpolicy.intel import FeedParseError, _request_for, collect, parse_adapter
from pivoxpolicy.registry import load_controls
from pivoxpolicy.rubric import load_assessments, load_rubric, validate_assessment

KEV = {"title": "CISA KEV", "count": 2, "vulnerabilities": [
    {"cveID": "CVE-2025-3248", "vendorProject": "Langflow", "product": "Langflow",
     "vulnerabilityName": "Langflow Missing Authentication Vulnerability", "dateAdded": "2025-05-05",
     "shortDescription": "Langflow contains a missing authentication vulnerability."},
    {"cveID": "CVE-2020-29583", "vendorProject": "Zyxel", "product": "Multiple Products",
     "vulnerabilityName": "Zyxel Hard-Coded Credentials", "dateAdded": "2021-11-03",
     "shortDescription": "uses a user agent string"}]}
NVD = {"totalResults": 1, "vulnerabilities": [{"cve": {"id": "CVE-2026-18655", "published": "2026-08-03T20:17:17.557",
       "descriptions": [{"lang": "en", "value": "Improper restriction in the Amazon MQ MCP Server."}]}}]}
FR = {"count": 1, "results": [{"title": "RFI Regarding Security Considerations for AI Agents",
      "html_url": "https://www.federalregister.gov/documents/2026/01/08/2026-00206/x", "publication_date": "2026-01-08",
      "abstract": "CAISI seeks input."}]}
ASM = {"nzmimeepazxkubdpn": [{"head": [{"list_total_count": 1}, {"RESULT": {"CODE": "INFO-000"}}]},
       {"row": [{"BILL_NAME": "전자금융거래법 일부개정법률안", "PROC_RESULT": None, "COMMITTEE": "정무위원회",
                 "PROPOSER": "의원 등 10인", "PROPOSE_DT": "2026-08-13",
                 "DETAIL_LINK": "http://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_X"}]}]}
FSI = {"resultCode": "200", "resultData": [{"bbsNo": 12144, "title": "금융보안원, 상시평가 시스템 &quot;정보&quot; 유출 차단",
       "regDate": "2026-11-10", "contents": "<p>본문</p>"}]}


def b(x):
    return json.dumps(x, ensure_ascii=False).encode("utf-8")


def test_each_adapter_parses_the_measured_shape():
    kev = parse_adapter("kev", b(KEV), "k")
    assert kev[0].link == "https://nvd.nist.gov/vuln/detail/CVE-2025-3248#cisa-kev"
    assert kev[0].published == "2025-05-05T00:00:00Z" and "Langflow" in kev[0].title
    nvd = parse_adapter("nvd", b(NVD), "n")
    assert nvd[0].published == "2026-08-03T20:17:17Z" and "MCP" in nvd[0].summary
    fr = parse_adapter("federalregister", b(FR), "f")
    assert fr[0].link.startswith("https://www.federalregister.gov/") and fr[0].published.startswith("2026-01-08")
    asm = parse_adapter("assembly", b(ASM), "a")
    assert asm[0].title == "전자금융거래법 일부개정법률안 (계류)" and "정무위원회" in asm[0].summary
    fsi = parse_adapter("fsi_bbs", b(FSI), "s", {"menu_no": 69})
    assert fsi[0].link == "https://www.fsec.or.kr/bbs/detail?menuNo=69&bbsNo=12144"
    assert '"정보"' in fsi[0].title and fsi[0].summary == "본문"
    with pytest.raises(FeedParseError):  # collect 가 잡아 그 피드만 '실패' 로 적는다
        parse_adapter("kev", b"not json", "k")


def test_nvd_request_gets_a_rolling_90_day_window_and_fsi_posts():
    today = datetime(2026, 11, 11, tzinfo=timezone.utc)
    url, kw = _request_for({"adapter": "nvd", "url": "https://services.nvd.nist.gov/rest/json/cves/2.0?"
                            "keywordSearch=prompt%20injection&pubStartDate=2020-01-01T00:00:00.000"}, today)
    assert "pubStartDate=2026-08-13T00%3A00%3A00.000" in url and "pubEndDate=2026-11-11T23%3A59%3A59.999" in url
    assert url.count("pubStartDate") == 1 and kw == {}
    url, kw = _request_for({"adapter": "fsi_bbs", "url": "https://www.fsec.or.kr/bbs/list", "menu_no": 221}, today)
    assert kw["method"] == "POST" and json.loads(kw["body"])["menuNo"] == "221"


def test_collect_routes_adapter_feeds_and_post_kwargs():
    calls = []

    def fetcher(url, **kw):
        calls.append((url, kw))
        return FetchResult(200, b(KEV) if "cisa" in url else b(FSI), "application/json")

    feeds = [
        {"id": "kev", "url": "https://www.cisa.gov/kev.json", "adapter": "kev", "issuer": "CISA", "kind": "primary",
         "jurisdiction": "US", "topic": "threat_intel", "keywords": ["langflow", "litellm"]},
        {"id": "fsi", "url": "https://www.fsec.or.kr/bbs/list", "adapter": "fsi_bbs", "keep_all": True,
         "issuer": "FSI", "kind": "primary", "jurisdiction": "KR", "topic": "mixed"},
    ]
    new, status = collect(feeds, [], fetcher=fetcher, now="2026-11-11T00:00:00Z")
    assert [i.feed_id for i in new].count("kev") == 1          # Zyxel(user agent) 는 키워드 밖
    assert any(i.feed_id == "fsi" for i in new)
    assert calls[1][1]["method"] == "POST"
    assert all(s.get("error") is None for s in status)


def test_incident_registry_loads_and_counts_by_evidence():
    controls = load_controls()
    incs = load_incidents(control_ids={c.id for c in controls})
    assert len(incs) >= 40
    # 모든 출처는 받아 본 날짜와 HTTP 200 이 적혀 있어야 한다 (2026-11-12 에 출처를 바꾼 사건은 그날 날짜)
    assert all(re.match(r"\d{4}-\d{2}-\d{2} HTTP 200", i.source_checked) for i in incs), [i.id for i in incs if not re.match(r"\d{4}-\d{2}-\d{2} HTTP 200", i.source_checked)]
    cc = control_counts(incs)
    assert cc["least_privilege"]["total"] == sum(cc["least_privilege"][k] for k in ("primary", "vendor", "press"))
    with pytest.raises(IncidentError):
        Incident.from_dict({"id": "x", "date": "2026", "title": "t", "jurisdiction": "KR", "ai_role": "bogus",
                            "evidence_level": "primary", "source_url": "u"}, {"inventory"})
    with pytest.raises(IncidentError):
        Incident.from_dict({"id": "x", "date": "2026", "title": "t", "jurisdiction": "KR", "ai_role": "none",
                            "evidence_level": "primary", "source_url": "u", "related_controls": ["nope"]}, {"inventory"})


def test_level_zero_requires_sources_checked():
    rub = load_rubric()
    a = dict(load_assessments()["example-worked_2026"])
    assert validate_assessment(a, rub) == []
    a.pop("sources_checked")
    assert any("sources_checked" in p for p in validate_assessment(a, rub))


def test_fsb_final_correction_is_in_the_seed_coding():
    import yaml
    from pivoxpolicy.registry import REGISTRY_DIR
    c = yaml.safe_load((REGISTRY_DIR / "codings" / "deck_2026-11-01.yaml").read_text(encoding="utf-8"))
    cell = c["items"]["intl-fsb-ai-sound-practices-2026-10"]["unique_id"]
    assert cell["covered"] is True and "p.30" in cell["evidence"]
