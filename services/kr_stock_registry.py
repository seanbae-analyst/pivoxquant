"""
PivoxQuant — Korean Stock Registry (Top KOSPI/KOSDAQ)

Static mapping of common Korean tickers (~250 names) used for search,
display, and currency routing. Sourced from KRX market cap top lists.
Schema: {ticker_with_suffix: (english_name, korean_name)}.

Why static instead of pykrx/web scrape:
  - KRX listings change rarely (months); refresh manually each release
  - No external API dependency at request time
  - Search latency stays sub-millisecond

For tickers NOT in this registry, search/lookup still works:
  - Any 6-digit code is auto-suffixed (.KS by default)
  - Real price comes from KIS API at lookup time
"""

# (english_name, korean_name)
KR_STOCKS: dict[str, tuple[str, str]] = {
    # ── KOSPI Mega Cap ────────────────────────────────────────────────
    "005930.KS": ("Samsung Electronics", "삼성전자"),
    "000660.KS": ("SK Hynix", "SK하이닉스"),
    "373220.KS": ("LG Energy Solution", "LG에너지솔루션"),
    "207940.KS": ("Samsung Biologics", "삼성바이오로직스"),
    "005380.KS": ("Hyundai Motor", "현대자동차"),
    "005935.KS": ("Samsung Electronics Pref", "삼성전자우"),
    "000270.KS": ("Kia Corp", "기아"),
    "068270.KS": ("Celltrion", "셀트리온"),
    "035420.KS": ("NAVER", "네이버"),
    "012450.KS": ("Hanwha Aerospace", "한화에어로스페이스"),
    "105560.KS": ("KB Financial", "KB금융"),
    "005490.KS": ("POSCO Holdings", "포스코홀딩스"),
    "329180.KS": ("HD Hyundai Heavy Industries", "HD현대중공업"),
    "055550.KS": ("Shinhan Financial", "신한지주"),
    "138040.KS": ("Meritz Financial", "메리츠금융지주"),
    "035720.KS": ("Kakao", "카카오"),
    "028260.KS": ("Samsung C&T", "삼성물산"),
    "012330.KS": ("Hyundai Mobis", "현대모비스"),
    "086790.KS": ("Hana Financial", "하나금융지주"),
    "010130.KS": ("Korea Zinc", "고려아연"),
    "267260.KS": ("HD Hyundai Electric", "HD현대일렉트릭"),
    "006400.KS": ("Samsung SDI", "삼성SDI"),
    "402340.KS": ("SK Square", "SK스퀘어"),
    "316140.KS": ("Woori Financial Group", "우리금융지주"),
    "066570.KS": ("LG Electronics", "LG전자"),
    "051910.KS": ("LG Chem", "LG화학"),
    "017670.KS": ("SK Telecom", "SK텔레콤"),
    "352820.KS": ("HYBE", "하이브"),
    "003670.KS": ("Posco Future M", "포스코퓨처엠"),
    "032830.KS": ("Samsung Life Insurance", "삼성생명"),
    "009540.KS": ("HD Korea Shipbuilding", "HD한국조선해양"),
    "034020.KS": ("Doosan Enerbility", "두산에너빌리티"),
    "015760.KS": ("KEPCO", "한국전력"),
    "030200.KS": ("KT Corp", "KT"),
    "033780.KS": ("KT&G", "KT&G"),
    "024110.KS": ("Industrial Bank of Korea", "기업은행"),
    "000810.KS": ("Samsung Fire & Marine", "삼성화재"),
    "009150.KS": ("Samsung Electro-Mechanics", "삼성전기"),
    "323410.KS": ("Kakao Bank", "카카오뱅크"),
    "377300.KS": ("Kakao Pay", "카카오페이"),
    "010140.KS": ("Samsung Heavy Industries", "삼성중공업"),
    "096770.KS": ("SK Innovation", "SK이노베이션"),
    "047050.KS": ("Posco International", "포스코인터내셔널"),
    "402340.KS": ("SK Square", "SK스퀘어"),
    "003550.KS": ("LG Corp", "LG"),
    "004020.KS": ("Hyundai Steel", "현대제철"),
    "003490.KS": ("Korean Air", "대한항공"),
    "047810.KS": ("Korea Aerospace Industries", "한국항공우주"),
    "006800.KS": ("Mirae Asset Securities", "미래에셋증권"),
    "088980.KS": ("Macquarie Korea Infra", "맥쿼리인프라"),
    "036570.KS": ("NCsoft", "엔씨소프트"),
    "259960.KS": ("Krafton", "크래프톤"),
    "086280.KS": ("Hyundai Glovis", "현대글로비스"),
    "010950.KS": ("S-Oil", "에쓰오일"),
    "011200.KS": ("HMM", "HMM"),
    "011170.KS": ("Lotte Chemical", "롯데케미칼"),
    "180640.KS": ("Hanjin Kal", "한진칼"),
    "023530.KS": ("Lotte Shopping", "롯데쇼핑"),
    "139480.KS": ("E-Mart", "이마트"),
    "004990.KS": ("Lotte Holdings", "롯데지주"),
    "078930.KS": ("GS Holdings", "GS"),
    "001040.KS": ("CJ Corp", "CJ"),
    "097950.KS": ("CJ CheilJedang", "CJ제일제당"),
    "035250.KS": ("Kangwon Land", "강원랜드"),
    "002790.KS": ("Amorepacific Group", "아모레G"),
    "090430.KS": ("Amorepacific", "아모레퍼시픽"),
    "051900.KS": ("LG Household & Health Care", "LG생활건강"),
    "271560.KS": ("Orion", "오리온"),
    "000080.KS": ("Hite Jinro", "하이트진로"),
    "271940.KS": ("Iljin Hysolus", "일진하이솔루스"),
    "021240.KS": ("Coway", "코웨이"),
    "047040.KS": ("Daewoo E&C", "대우건설"),
    "375500.KS": ("DL E&C", "DL이앤씨"),
    "000720.KS": ("Hyundai E&C", "현대건설"),
    "036460.KS": ("Korea Gas Corp", "한국가스공사"),
    "267250.KS": ("HD Hyundai", "HD현대"),
    "079550.KS": ("LIG Nex1", "LIG넥스원"),
    "272210.KS": ("Hanwha Systems", "한화시스템"),
    "000880.KS": ("Hanwha", "한화"),
    "009830.KS": ("Hanwha Solutions", "한화솔루션"),
    "402340.KS": ("SK Square", "SK스퀘어"),
    "108860.KS": ("Cheil Industries", "셀바스AI"),
    "010620.KS": ("Hyundai Mipo Dockyard", "HD현대미포"),
    "079160.KS": ("CJ CGV", "CJ CGV"),
    "031430.KS": ("F&F", "F&F"),
    "020150.KS": ("Lotte Energy Materials", "롯데에너지머티리얼즈"),
    "112610.KS": ("CS Wind", "CS윈드"),
    "298050.KS": ("Hyosung Advanced Materials", "효성첨단소재"),
    "298020.KS": ("Hyosung TNC", "효성티앤씨"),
    "298000.KS": ("Hyosung Chemical", "효성화학"),
    "004800.KS": ("Hyosung", "효성"),
    "001230.KS": ("Dongkuk Steel Mill", "동국제강"),
    "001450.KS": ("Hyundai Marine & Fire", "현대해상"),
    "002270.KS": ("Lotte Foods", "롯데푸드"),
    "069960.KS": ("Hyundai Department Store", "현대백화점"),
    "008770.KS": ("Hotel Shilla", "호텔신라"),
    "004170.KS": ("Shinsegae", "신세계"),
    "000100.KS": ("Yuhan Corporation", "유한양행"),
    "128940.KS": ("Hanmi Pharm", "한미약품"),
    "069620.KS": ("Daewoong Pharmaceutical", "대웅제약"),
    "170900.KS": ("Dong-A ST", "동아에스티"),
    "000150.KS": ("Doosan", "두산"),
    "042660.KS": ("Hanwha Ocean", "한화오션"),
    "010620.KS": ("Hyundai Mipo Dockyard", "현대미포조선"),
    "302440.KS": ("SK Bioscience", "SK바이오사이언스"),
    "326030.KS": ("SK Biopharmaceuticals", "SK바이오팜"),
    "145720.KS": ("Dentium", "덴티움"),
    "035250.KS": ("Kangwon Land", "강원랜드"),

    # ── KOSDAQ Top ────────────────────────────────────────────────────
    "247540.KQ": ("Ecopro BM", "에코프로비엠"),
    "086520.KQ": ("Ecopro", "에코프로"),
    "091990.KQ": ("Celltrion Healthcare", "셀트리온헬스케어"),
    "196170.KQ": ("Alteogen", "알테오젠"),
    "066970.KQ": ("L&F", "엘앤에프"),
    "041510.KQ": ("SM Entertainment", "에스엠"),
    "035900.KQ": ("JYP Entertainment", "JYP Ent."),
    "122870.KQ": ("YG Entertainment", "와이지엔터테인먼트"),
    "112040.KQ": ("Wemade", "위메이드"),
    "293490.KQ": ("Kakao Games", "카카오게임즈"),
    "263750.KQ": ("Pearl Abyss", "펄어비스"),
    "095660.KQ": ("Neowiz", "네오위즈"),
    "194480.KQ": ("Devsisters", "데브시스터즈"),
    "036570.KS": ("NCsoft", "엔씨소프트"),
    "058470.KQ": ("LEENO Industrial", "리노공업"),
    "240810.KQ": ("Wonik IPS", "원익IPS"),
    "278280.KQ": ("Cheonbo", "천보"),
    "357780.KQ": ("Solbrain", "솔브레인"),
    "095340.KQ": ("ISC", "ISC"),
    "067310.KQ": ("Hana Micron", "하나마이크론"),
    "402030.KQ": ("HPSP", "HPSP"),
    "166090.KQ": ("Hana Materials", "하나머티리얼즈"),
    "298540.KQ": ("Daemyung Energy", "더블유게임즈"),
    "039030.KQ": ("Eo Technics", "이오테크닉스"),
    "319660.KQ": ("Pi Solution", "피에스케이"),
    "108860.KQ": ("Selvas AI", "셀바스AI"),
    "214150.KQ": ("Classys", "클래시스"),
    "048410.KQ": ("Hyundai Bioscience", "현대바이오"),
    "145020.KQ": ("Hugel", "휴젤"),
    "195940.KQ": ("HK inno.N", "HK이노엔"),
    "237690.KQ": ("Esticpharma", "에스티팜"),
    "086900.KQ": ("Medytox", "메디톡스"),
    "141080.KQ": ("Legochembio", "리가켐바이오"),
    "065350.KQ": ("Shinsung E&G", "신성이엔지"),
    "079980.KQ": ("Huons", "휴온스"),
    "950140.KQ": ("Jinyou Wonderfine", "잉글우드랩"),
    "112610.KQ": ("CS Wind", "CS윈드"),
    "112040.KQ": ("Wemade", "위메이드"),
    "036930.KQ": ("Jusung Engineering", "주성엔지니어링"),
    "131970.KQ": ("Test Tech", "테스나"),
    "192410.KQ": ("Hyundai Vias", "현대비에스앤씨"),
    "215000.KQ": ("Golfzon", "골프존"),
    "099190.KQ": ("ISU Petasys", "이수페타시스"),
    "068760.KQ": ("Celltrion Pharm", "셀트리온제약"),
    "035600.KQ": ("KG Inicis", "KG이니시스"),
    "046890.KQ": ("Seo Sung TIC", "서울반도체"),
    "060720.KQ": ("KH Vatec", "KH바텍"),
    "121600.KQ": ("Nano Medics", "나노신소재"),
    "025900.KQ": ("Donghwa Industry", "동화기업"),
    "131290.KQ": ("TSE", "티에스이"),
    "036620.KQ": ("CHA Biotech", "차바이오텍"),
    "078340.KQ": ("Com2uS", "컴투스"),
    "194700.KQ": ("Aprogen Bio", "아프로젠H&G"),
    "003380.KQ": ("Harim Holdings", "하림지주"),
    "097520.KQ": ("M Cnet", "엠씨넥스"),
    "060280.KQ": ("Curocom", "큐렉소"),
    "048260.KQ": ("Osstem Implant", "오스템임플란트"),
    "078600.KQ": ("Daejoo Electronic Materials", "대주전자재료"),
    "086450.KQ": ("DongKook Pharmaceutical", "동국제약"),
    "053610.KQ": ("Procom", "프로텍"),
    "058610.KQ": ("Esttec", "에스피지"),
    "950130.KQ": ("Eco Friend Holdings", "엑세스바이오"),
    "950220.KQ": ("Naibu", "나스미디어"),
    "032500.KQ": ("KMW", "케이엠더블유"),
    "043150.KQ": ("Vatech", "바텍"),
}

# Sector mapping (subset; fall through to "Industrials" for unknown)
KR_SECTORS: dict[str, str] = {
    "005930.KS": "Technology", "000660.KS": "Technology",
    "373220.KS": "Industrials", "207940.KS": "Healthcare",
    "005380.KS": "Consumer Cyclical", "000270.KS": "Consumer Cyclical",
    "068270.KS": "Healthcare", "035420.KS": "Communication Services",
    "012450.KS": "Industrials", "105560.KS": "Financial Services",
    "005490.KS": "Basic Materials", "329180.KS": "Industrials",
    "055550.KS": "Financial Services", "138040.KS": "Financial Services",
    "035720.KS": "Communication Services", "028260.KS": "Industrials",
    "012330.KS": "Consumer Cyclical", "086790.KS": "Financial Services",
    "010130.KS": "Basic Materials", "066570.KS": "Technology",
    "051910.KS": "Basic Materials", "017670.KS": "Communication Services",
    "352820.KS": "Communication Services", "032830.KS": "Financial Services",
    "030200.KS": "Communication Services", "323410.KS": "Financial Services",
    "377300.KS": "Financial Services", "036570.KS": "Communication Services",
    "259960.KS": "Communication Services", "086280.KS": "Industrials",
    "010950.KS": "Energy", "047810.KS": "Industrials",
    "036460.KS": "Utilities", "015760.KS": "Utilities",
    "247540.KQ": "Technology", "086520.KQ": "Technology",
    "091990.KQ": "Healthcare", "196170.KQ": "Healthcare",
    "041510.KQ": "Communication Services", "035900.KQ": "Communication Services",
    "122870.KQ": "Communication Services", "293490.KQ": "Communication Services",
    "263750.KQ": "Communication Services",
}


# ── Full KRX master (loaded from JSON, ~2,770 stocks) ──
import json as _json
import os as _os
_FULL_PATH = _os.path.join(_os.path.dirname(__file__), "kr_stocks_data.json")
try:
    with open(_FULL_PATH, "r", encoding="utf-8") as _f:
        KR_STOCKS_FULL: dict[str, dict] = _json.load(_f)
except FileNotFoundError:
    KR_STOCKS_FULL = {}


def search(query: str, limit: int = 15) -> list[dict]:
    """Return matching KR stocks for a query string.

    Searches both:
      - KR_STOCKS (curated, with English names + sector) — priority
      - KR_STOCKS_FULL (full KRX listing, Korean only) — fallback for breadth
    """
    q = (query or "").strip()
    if not q:
        return []
    ql = q.lower()
    results: list[dict] = []
    seen: set[str] = set()

    # Priority 1: curated registry (English + Korean searchable, sector available)
    for ticker, (name_en, name_kr) in KR_STOCKS.items():
        code = ticker.split(".")[0]
        if (ql in code.lower()
                or ql in name_en.lower()
                or q in name_kr):
            results.append({
                "ticker":   ticker,
                "name":     f"{name_kr} ({name_en})" if name_kr else name_en,
                "name_en":  name_en,
                "name_kr":  name_kr,
                "exchange": "KOSDAQ" if ticker.endswith(".KQ") else "KOSPI",
                "currency": "KRW",
                "is_korean": True,
            })
            seen.add(ticker)
            if len(results) >= limit:
                return results

    # Priority 2: full KRX master (Korean name only)
    for ticker, info in KR_STOCKS_FULL.items():
        if ticker in seen:
            continue
        code = ticker.split(".")[0]
        name_kr = info.get("name", "")
        if ql in code.lower() or q in name_kr:
            results.append({
                "ticker":   ticker,
                "name":     name_kr,
                "name_en":  "",
                "name_kr":  name_kr,
                "exchange": info.get("market", "KOSPI" if ticker.endswith(".KS") else "KOSDAQ"),
                "currency": "KRW",
                "is_korean": True,
            })
            if len(results) >= limit:
                break
    return results


def get_name(ticker: str) -> "str | None":
    """Return preferred Korean name. Prefer curated, fallback to full master.

    Suffix-toggle fallback (2026-05-10, Bug B-02)
    --------------------------------------------
    KIS API has been observed returning some KOSDAQ tickers with the
    ``.KS`` suffix (and vice-versa) — e.g. ``124500.KS`` is delivered for
    아이티센글로벌 even though the row only exists as ``124500.KQ`` in our
    registry. Without a fallback, every alert/serializer for those tickers
    rendered with the bare ticker as the "name" ("124500.KS (124500.KS) —
    Score …").

    Safety: the curated + full registries contain **zero** 6-digit codes
    that appear on both KOSPI and KOSDAQ at once (verified by audit
    2026-05-10), so toggling the suffix on miss can never resolve to a
    *different* company. We try the input as-given first, then the toggled
    form, then return ``None`` so callers keep the same ticker fallback.
    """
    if not ticker:
        return None
    t = ticker.upper()

    # Primary lookup — input ticker exactly as provided.
    entry = KR_STOCKS.get(t)
    if entry:
        name_en, name_kr = entry
        return name_kr or name_en
    full = KR_STOCKS_FULL.get(t)
    if full:
        return full.get("name")

    # Suffix-toggle fallback — only for canonical KRX tickers
    # (XXXXXX.KS or XXXXXX.KQ). Anything else falls through to None.
    if len(t) == 9 and t[6] == ".":
        if t.endswith(".KS"):
            alt = t[:-3] + ".KQ"
        elif t.endswith(".KQ"):
            alt = t[:-3] + ".KS"
        else:
            alt = None
        if alt:
            entry = KR_STOCKS.get(alt)
            if entry:
                name_en, name_kr = entry
                return name_kr or name_en
            full = KR_STOCKS_FULL.get(alt)
            if full:
                return full.get("name")
    return None


def get_sector(ticker: str) -> "str | None":
    return KR_SECTORS.get(ticker.upper())
