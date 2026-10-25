"""한국 회사 공시 — 금융감독원 OpenDART ``list.json`` (공시검색).

키는 ``DART_API_KEY`` 하나. 없으면 한국 공시는 조용히 꺼진다 (``api_key()``).

이용 근거 (2026-10-25 원문 확인): OpenDART 이용약관(시행 2020-01-21)에 상업적
이용·영리·재배포·재가공·출처를 다루는 조항이 없다(전문 키워드 검색). 회원은
인증키를 제3자에게 쓰게 하면 안 된다 — 서버만 쓴다. 금감원 보도자료(2020-04-20)는
"민간기업 등이 공시정보를 활용한 새로운 서비스를 개발할 수 있도록" 연다고 했다.

고르는 공시 (개발가이드 list.json 의 공시유형)
---------------------------------------------
* ``A`` 정기공시 (사업·반기·분기보고서) · ``B`` 주요사항보고
* ``I001`` 수시공시 · ``I002`` 공정공시 (잠정실적이 여기 있다)
* 빼는 것: 지분공시(D · I004 — 임원·주요주주·대량보유, '따라 사기' 신호로
  읽힌다), 발행공시(C), 펀드(G) 등. 철회(``rm`` 에 "철")된 공시도 뺀다.

보고서명(``report_nm``)은 금감원이 붙인 공식 이름이라 그대로 보여 준다. 실적
발표 = 이름에 "잠정"과 "실적"이 함께 있는 원본(정정 "[" 접두 제외).
날짜는 접수일(``rcept_dt``, 한국 날짜)만 쓴다 — 시각이 없다.
"""
from __future__ import annotations

import io
import logging
import os
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta

from .sec import ParsedFiling

logger = logging.getLogger(__name__)

BASE = "https://opendart.fss.or.kr/api"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
TIMEOUT = 8
LOOKBACK_DAYS = 730
MAX_PAGES = 3
CORP_MAP_TTL = 7 * 86400
CORP_MAP_RETRY = 600

# (공시유형, 공시상세유형) → 화면 이름. 저장은 코드("A", "B", "I001", "I002").
QUERIES = (("A", None), ("B", None), (None, "I001"), (None, "I002"))
TYPE_NAMES = {"A": "정기공시", "B": "주요사항보고", "I001": "수시공시", "I002": "공정공시"}

_lock = threading.Lock()
_corp_map: dict[str, str] = {}   # 6자리 종목코드 → 8자리 고유번호
_corp_map_at = 0.0
_corp_map_failed_at = 0.0


def api_key() -> str:
    return os.environ.get("DART_API_KEY", "").strip()


def is_earnings(title: str | None) -> bool:
    t = (title or "").strip()
    return bool(t) and not t.startswith("[") and "잠정" in t and "실적" in t


def parse_corp_codes(zip_bytes: bytes) -> dict[str, str]:
    """corpCode.xml (ZIP) → {종목코드: 고유번호}. 상장사(종목코드 있는 행)만."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        xml = zf.read(zf.namelist()[0])
    out: dict[str, str] = {}
    for item in ET.fromstring(xml).iter("list"):
        stock = (item.findtext("stock_code") or "").strip()
        corp = (item.findtext("corp_code") or "").strip()
        if stock and corp:
            out[stock] = corp
    return out


def parse_list(rows: list[dict] | None, form: str) -> list[ParsedFiling]:
    """list.json 의 ``list`` → 공시 행 (철회 제외)."""
    out: list[ParsedFiling] = []
    for r in rows or []:
        rcept_no = str(r.get("rcept_no") or "").strip()
        raw_day = str(r.get("rcept_dt") or "").strip()
        title = str(r.get("report_nm") or "").strip()
        if not rcept_no or len(raw_day) != 8 or not title or "철" in str(r.get("rm") or ""):
            continue
        try:
            filed_on = date(int(raw_day[:4]), int(raw_day[4:6]), int(raw_day[6:]))
        except ValueError:
            continue
        out.append(ParsedFiling(
            accession=rcept_no, form=form, items="", filed_on=filed_on,
            url=f"{VIEWER}{rcept_no}", title=title[:200],
        ))
    return out


def _get(path: str, params: dict, timeout: float):
    import requests

    resp = requests.get(f"{BASE}/{path}", params={**params, "crtfc_key": api_key()}, timeout=timeout)
    resp.raise_for_status()
    return resp


def corp_code_for(stock_code: str) -> str | None:
    """종목코드 → 고유번호. corpCode.xml 을 7일 들고 있고, 실패하면 10분 뒤 다시."""
    global _corp_map, _corp_map_at, _corp_map_failed_at
    now = time.time()
    with _lock:
        fresh = _corp_map and now - _corp_map_at < CORP_MAP_TTL
        if not fresh and now - _corp_map_failed_at >= CORP_MAP_RETRY:
            try:
                _corp_map = parse_corp_codes(_get("corpCode.xml", {}, timeout=20).content)
                _corp_map_at = now
            except Exception as exc:  # 네트워크·ZIP — 이 종목은 공시 없이 뜬다
                _corp_map_failed_at = now
                logger.warning("dart: corpCode.xml failed: %s", exc)
        return _corp_map.get(stock_code)


def fetch(stock_code: str, *, today: date | None = None) -> tuple[str | None, list[ParsedFiling]] | None:
    """종목코드의 최근 2년 공시 → ``(고유번호, 행)``. 키·고유번호가 없거나 실패하면 None."""
    if not api_key():
        return None
    corp = corp_code_for(stock_code)
    if not corp:
        return None
    today = today or date.today()
    span = {"corp_code": corp, "bgn_de": (today - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d"),
            "end_de": today.strftime("%Y%m%d"), "page_count": 100}
    rows: list[ParsedFiling] = []
    for ty, detail in QUERIES:
        form = detail or ty
        q = {**span, **({"pblntf_ty": ty} if ty else {"pblntf_detail_ty": detail})}
        for page in range(1, MAX_PAGES + 1):
            data = _get("list.json", {**q, "page_no": page}, timeout=TIMEOUT).json()
            status = str(data.get("status") or "")
            if status == "013":  # 조회된 데이터 없음
                break
            if status != "000":
                logger.warning("dart: list.json %s for %s (%s)", status, stock_code, data.get("message"))
                return None
            rows.extend(parse_list(data.get("list"), form))
            if page >= int(data.get("total_page") or 1):
                break
    return corp, rows


__all__ = ["TYPE_NAMES", "api_key", "corp_code_for", "fetch", "is_earnings", "parse_corp_codes", "parse_list"]
