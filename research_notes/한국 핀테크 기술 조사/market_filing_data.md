# 시세·공시·기업 데이터 공급 기술과 라이선스 — 한국·미국 주식, 개인투자자용 앱의 이용자 표시 기준 (조사일 2026-10-28)

> 표기 규칙: 모든 수치는 **확인 날짜(2026-10-28)** 기준이며, 페이지 원문을 직접 읽은 항목과 검색 스니펫·2차 자료에 의존한 항목을 구분했다. 접근 실패(403/503/404/DNS 차단)한 페이지는 "확인 불가"로 명시. 가격은 통화·플랜명을 함께 적었다.
> 내부 선행 조사(`docs/legal/R7_kis_market_data_options_2026-06-09.md`, 2026-09-19 추기)의 결론 "무료·합법으로 시세를 유저에게 표시할 경로는 국내·미국 모두 없다"는 이번 조사에서도 **유지**된다. 다만 미국 쪽은 **유료 재표시 라이선스가 명시적으로 공개된 벤더가 2곳 이상**(Tiingo, Financial Datasets; Intrinio는 2차 자료) 확인됐다.

---

## 1. 국내 시세 — KRX·코스콤·증권사 Open API·금융위 공공데이터의 제3자 재표시 조건과 비용

### Takeaway
국내 상장주식 시세를 **제3자 앱 이용자에게 표시**하려면 사실상 코스콤(KRX 정보분배 독점 사업자)과 "정보이용계약"을 맺는 길 하나뿐이다. 무료 경로 3개(금융위 공공데이터 15094808, KRX Open API, 증권사 개인용 Open API)는 모두 약관으로 **제3자 제공·상업 이용을 명시 금지**한다. 코스콤 오픈API플랫폼은 법인만 가능하고, 업력 7년 미만 중소기업에 **기본료 36개월 면제** 정책이 있으나 **종량·단말 요금과 실제 금액은 비공개**(문의 필요)다.

### Cited Findings

**(a) 금융위원회 주식시세정보 (공공데이터포털 15094808) — 원문 확인 2026-10-28**
- 이용허락범위: **"출처표시, 상업적 이용금지, 변경금지 (제 4유형)"** (공공누리 4유형) — [data.go.kr/data/15094808](https://www.data.go.kr/data/15094808/openapi.do)
- 명시 문구: **"본 데이터는 상업적 목적 여부와 상관 없이 제3자 무단 제공 및 재배포가 엄격히 금지됩니다."** 상업 이용 시 "원천 소유자인 한국거래소의 KRX Data Marketplace(data.krx.co.kr)에서 유료로 구매하여야 합니다." 상업적 활용은 "가공을 통한 독창적 저작물 생산이나 제3자 방문·가입을 통한 간접 수익 창출 목적"에만 허용(KRX 구매 전제). 문의 krxdata@krx.co.kr — [같은 페이지](https://www.data.go.kr/data/15094808/openapi.do)
- 갱신: 상세설명 "하루 1회", 금융위 설명 "기준일 다음 영업일 오후 1시 이후" (이용조건 란엔 "실시간"으로 표기돼 페이지 내 모순). 개발계정 일 10,000건, 운영계정은 활용사례 등록 후 증설 신청. **52주 고가/저가 필드 없음**(시가·종가·고가·저가·거래량만). 페이지 수정일 2026-10-28, 등록일 2021-11-16 — [같은 페이지](https://www.data.go.kr/data/15094808/openapi.do)
- 금융위 금융공공데이터 FAQ: 개발계정 일 10,000건 / 운영계정 일 100,000건, "API 데이터가 실시간이 아닙니다" — [fsc.go.kr/in060501](https://fsc.go.kr/in060501)
- 같은 기관 KRX상장종목정보(15094775)도 동일 문구("제3자 무단 제공 및 재배포가 엄격히 금지") — [data.go.kr/data/15094775](https://www.data.go.kr/data/15094775/openapi.do)

**(b) KRX Open API (openapi.krx.co.kr) 이용약관 — 원문 확인 2026-10-28**
- 제6조②: **"API 이용자는 API 서비스를 비상업적인 목적으로만 이용할 수 있으며, API 서비스를 이용한 결과에 대한 대가를 제3자에게 청구해서는 아니된다."** — [KRX Open API 이용약관](https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO002.jsp)
- 제11조②: **"API 이용자는 한국거래소로부터 제공받은 정보를 제3자에게 제공할 수 없다."** — 같은 출처
- 제10조③ 출처표시: "해당 화면에 '한국거래소 통계정보'를 사용한 결과임을 명시해야 한다." 제12조③: 편집해 부가정보를 만들면 KRX는 책임지지 않음. **시행일 2025-12-26** — 같은 출처

**(c) KRX 실시간 시장정보 상품·라이선스 (KRX Data Marketplace 브로셔 PDF, 2025년판) — 원문 확인 2026-10-28**
- 정보상품: 증권A(유가증권 주식), 증권B(코스닥·코넥스), 증권C(ETF·ETN·ELW), 파생A, KRX종합주가지수(코스피·코스피200·코스닥) 등 — [Market Data Product Brochure.pdf](https://data.krx.co.kr/inc/datasale/Market%20Data%20Product%20Brochure.pdf?v=20250732)
- 외부제공사: **"외부제공사가 실시간 KRX 시장정보를 수신 및 재분배 하려면 코스콤과 '일반 정보이용계약'을 체결해야 합니다."** 외부제공권한 옵션: **[옵션1] 일반용**(내부 이용 + 전문가/개인 가입자 제공), **[옵션2] 소매사업 전용**(개인 가입자 한정), **[옵션3] 웹사이트 체결가서비스용 — "웹사이트 및 모바일용 애플리케이션을 통해 일반대중에게 체결가 정보 제공, 사용자 수에 관계없이 정액제 적용"**, [옵션4] 방송매체 전용 — 같은 PDF
- 최종이용사: 내부 이용 목적이라도 "최종이용사 정보이용계약" 필요, 정보사업자 경유 수신도 동일 — 같은 PDF
- **요금 금액은 브로셔에 없음**. 문의 코스콤 시장데이터사업부 marketdata@koscom.co.kr — 같은 PDF
- 계약 절차: KRX 이용 승인 → 코스콤과 계약서 작성, 계약년도 말일 기준 1년 자동연장. "시장정보로 유사시장을 개설하는 행위는 법으로 금지" — [KRX Data Marketplace 이용안내](https://data.krx.co.kr/contents/MDC/INFO/informationController/MDCINFO002.cmd) (검색 스니펫; 안내 페이지 자체는 메뉴만 노출)

**(d) 코스콤 오픈API플랫폼 (BaaS) — gitbook FAQ 원문 확인 2026-10-28**
- **"주식시세의 경우 정보시세 라이센스에 따라 과금 됩니다. 단, 핀테크 활성화를 위해 오픈API플랫폼을 통한 시세 사용의 경우 중소기업 업력 7년 미만의 기업에게는 기본료 면제 (36개월간) 정책을 적용 하고 있습니다."** — [koscom.gitbook.io/open-api/faq/oppf](https://koscom.gitbook.io/open-api/faq/oppf)
- 시세API 사용은 **오픈API플랫폼 이용계약보다 시세라이센스 계약이 먼저** 진행돼야 함. 문의: API플랫폼팀 open@koscom.co.kr / 02-767-7933, 정보시세 라이선스: 시장데이터영업팀 fintechdata@koscom.co.kr / 02-767-7537 — 같은 출처
- 이용 대상 "법인"만, 개인사업자·일반인·학생 불가 — [검색 스니펫, 같은 FAQ](https://koscom.gitbook.io/open-api/faq/oppf); 2차 확인 [AlgoLab 블로그 2026-08-07](https://algolab.co.kr/blog/broker-api-fees-cost-guide-2026)
- 구체 원화 요율: **확인 불가**(FAQ·브로셔·블로그 어디에도 없음). 2017년 뉴스핌 보도는 당시 "서비스 개시 후 1년 또는 앱 다운로드 1만건까지 무료" 정책과 유료화 검토를 전함(옛 자료) — [newspim 2017-02-02](https://www.newspim.com/news/view/20170202000289)
- 코스콤 공식 fintech 페이지(koscom.co.kr/portal/fintech/fintechOpenApi.do)는 본문이 비어 돌아와 **확인 불가**.

**(e) 한국투자증권 KIS Developers — 제휴 안내 원문 확인 2026-10-28**
- 제휴 대상: "KIS Developers 오픈 API 서비스를 활용하여 제3자에게 서비스를 제공하고자 하는 법인". **"제도권금융회사(투자일임업, 투자자문업)이 아닌 경우 제휴 불가(ex. 핀테크사)"** — [apiportal.koreainvestment.com/provider](https://apiportal.koreainvestment.com/provider)
- "제3자 서비스 제공 목적이 아닌 법인 소유 계좌를 통한 KIS Developers 서비스 이용은 제휴없이 사용 가능합니다." — 같은 출처
- 시세: **"시세정보 API 이용의 경우, KRX 및 해외거래소와의 정보이용계약을 체결하셨는지 확인을 부탁드립니다."** 코스콤이 "사전에 코스콤과 정보이용계약 체결이 안 되어 있으면" 제휴사 자체 앱에 시세 표출 불가라고 통보했다는 설명 포함 — 같은 출처
- 주문 API: 비제도권은 절차가 매우 까다로워 혁신금융서비스(샌드박스) 신청 권고 — 같은 출처
- 2차 자료: 증권사 개인용 Open API 시세는 "해당 증권사 계좌를 가진 개인이 자기 자산 투자에 쓰는 범위", **"제3자 제공은 불가"**, 법인은 "코스콤 등 거래소와 별도의 시세정보 이용계약을 반드시 체결" — [AlgoLab 2026-08-07](https://algolab.co.kr/blog/broker-api-fees-cost-guide-2026)

**(f) 코스콤 CHECK API / 금융 데이터 라이선스**
- CHECK API 자체의 재배포 요금·조건은 검색 결과에서 **확인 불가** (CHECK Expert+ 단말 소개 기사만 검색됨) — [검색 결과 요약](https://www.ajunews.com/view/20140929114257419)

### Inferences
- 국내는 "무료+합법+제3자 표시"가 성립하는 조합이 없다. 법인 설립 후 코스콤 정보이용계약(브로셔 옵션3 "웹사이트 체결가서비스용 정액제"가 소규모 앱에 가장 근접) + 오픈API플랫폼(기본료 36개월 면제)이 유일한 제도권 경로이며, **금액은 코스콤 시장데이터영업팀에 직접 견적**해야 한다.
- 금융위 15094808은 T+1(최대 T+3)·52주 필드 없음·변경금지까지 겹쳐 "취득가 기준 운영" 대비 얻는 이득이 거의 없다.
- KIS 제휴는 핀테크사 불가이므로, PivoxQuant의 "운영자 본인 계좌 read-only"(제휴 없이 허용)와 "유저 본인 계좌 연동" 외의 KIS 시세 경로는 없다. 유저가 **자기 KIS 키**를 앱에 넣어 시세를 받는 패턴은 실제 앱 사례(§6)가 있으나 KIS 약관상 적법성 근거는 찾지 못했다.

### Gaps
- 코스콤 정보시세 라이선스·오픈API플랫폼의 **원화 요율표**: 어디에도 공개돼 있지 않음(문의 필수).
- KRX Data Marketplace 과거 데이터(일별 종가) 상품의 **재배포 조건·가격**: "데이터 구입 안내/데이터 라이센스" 하위 페이지 미열람.
- 코스콤 "지연시세(15~20분)" 무료·저가 상품 존재 여부: 검색으로 확인 불가.
- 코스콤 공식 오픈API 안내 페이지(koscom.co.kr): 본문 미수신.

---

## 2. 미국 시세 — 벤더별 상업 재표시 허용 플랜·월 비용·'personal use only' 원문

### Takeaway
개인용(self-serve) 플랜은 전 벤더가 "personal, non-commercial, 재배포·제3자 표시 금지"다. **표시 라이선스를 가격까지 공개한 곳**은 Tiingo(EOD+IEX Display Redistribution **USD 250/월 스타트업**), Financial Datasets(Professional **USD 2,000/월**, 재배포 포함), Intrinio(2차 자료 Startup **USD 333/월~**, 표시 허용·원시 재배포 불가)다. FMP는 Data Display and Licensing Agreement가 필수이나 가격 비공개(Enterprise 영업). Massive(구 Polygon)·Alpha Vantage·Finnhub·EODHD·Twelve Data·Databento·Nasdaq Data Link는 **상업 표시 가격이 비공개 또는 거래소 요금 pass-through**다.

### Cited Findings

**FMP (Financial Modeling Prep)** — ToS·가격 페이지 원문 curl로 확인 2026-10-28 (WebFetch는 403)
- Services Subscription Agreement "Last updated: August 1, 2023" — [FMP ToS](https://site.financialmodelingprep.com/terms-of-service)
- §2.2.1 Personal Use: **"This license may only be used by a Customer who is an individual, and strictly for their own personal, non-business and non-commercial purposes… may not… integrate the Data or Services into any tools or applications accessible by any third parties, or use the Services to host, share, display, or provide content for others."** — 같은 출처
- §2.2.2 Data Display: **"Without a specific agreement with FMP, customers are prohibited from showcasing FMP Services or Data on platforms including but not limited to websites, blogs, software products, or applications designed for utilization by multiple individuals, irrespective of whether such usage is complimentary or paid, and whether it pertains to internal or external organizational purposes."** — 같은 출처
- 가격(2026-10-28 페이지): Basic **USD 0**(250 calls/day, EOD historical), Starter **USD 29/월**(연납 19, 300 calls/min, "US Coverage", 5년), Premium **USD 69/월**(연납 49, 750/min, UK·Canada, 30년), Ultimate **USD 139/월**(연납 99, 3,000/min, "Global Coverage"). 페이지 하단: **"Displaying or redistributing data sourced from FMP requires a specific Data Display and Licensing Agreement with FMP."** 대역폭 한도: Free 500MB / Starter 20GB / Premium 50GB / Ultimate 150GB / **Build 100GB / Enterprise 1TB+** — [FMP Pricing](https://site.financialmodelingprep.com/pricing-plans)
- FMP 해설 페이지: 무료·유료 불문 표시엔 Agreement 필요, 출처표기는 허가 대체 불가 — [FMP Insights](https://site.financialmodelingprep.com/insights/platform/can-you-use-fmp-data-in-a-public-app-website-or-client-dashboard) (403으로 원문 미열람, 검색 요약)
- Data Display Agreement **가격: 공개 자료 없음**(Enterprise 영업 통해 견적) — [검색 종합](https://www.findmymoat.com/tools/financial-modeling-prep-fmp)
- Starter/Premium 의 KR 종목 커버 여부: 가격표상 Starter "US Coverage", Ultimate "Global Coverage"만 표기 — 한국 종목 포함 여부 **확인 불가**.

**Massive (구 Polygon.io)** — Individuals ToS 원문 확인 2026-10-28
- "Last Updated: July 18, 2025". 전문: **"you may not use any of the Services labeled for individual or personal use"**(사업·상업 사용자). §2: **"solely for your own personal, non-commercial, and non-business purposes."** §3.3 계정·API 키 공유 금지. §6.1(f)(ix) "for any commercial or unauthorized purpose" 금지. §1이 별도 Market Data Terms 를 편입(미열람) — [Massive Individuals ToS](https://massive.com/legal/individuals-terms-of-service)
- 약관 구조: Individuals ToS = "personal, individual, and non-business use of any service or product labeled for 'Individual Use'", Businesses ToS = "labeled for 'Business Use'" — [massive.com/terms](https://massive.com/terms)
- 가격(개인용, 2026-10-28 페이지): **Stocks Advanced USD 199/월 "Individual use only"**, Financials & Ratios USD 29/월. Starter/Developer 가격은 페이지에서 미노출 — [massive.com/pricing](https://massive.com/pricing). 2차: Starter USD 29 / Developer USD 79 / Advanced USD 199 (2026-09 apicostcalc), Developer USD 99 (2026-05 스냅숏) — [apicostcalc](https://apicostcalc.com/blog/polygon-massive-rebrand-api-pricing.html); [qveris](https://qveris.ai/guides/polygon-pricing-optimized/)
- Business 가격 페이지(/pricing/business) **404 → 확인 불가**.

**Alpha Vantage** — ToS PDF 원문 확인 2026-10-28
- §2.a: 라이선스는 **"for personal, non-commercial use, unless you and Alpha Vantage have agreed otherwise in writing"**. commercial use 정의 iii: **"You plan to use or provide information accessed through the Alpha Vantage Platform as part of any type of commercial activity that allows individuals or entities other than User to access information directly or indirectly"** → 상업 문의 premium@alphavantage.co — [Alpha Vantage ToS](https://www.alphavantage.co/terms_of_service/)
- Premium 가격(2026-10-28): 75 req/min **USD 49.99/월**, 150 → 99.99, 300 → 149.99, 600 → 199.99, 1200 → 249.99 (연납 499~2,499). 상업·재배포 가격 미표기 — [Alpha Vantage Premium](https://www.alphavantage.co/premium/)

**Tiingo** — 가격·상품 페이지 원문 확인 2026-10-28
- Free(Starter) **USD 0**, Power **USD 30/월**, 둘 다 License **"Internal Use Only"**; "Internal use means you may only use the data for your own personal use… you may not display or share the data with another person or organization." Commercial(internal) **USD 50/월 또는 499/년** — [Tiingo Pricing](https://www.tiingo.com/about/pricing)
- **EOD + IEX Redistribution: "$250/month for startups" / "$500/month for enterprise"**, 라이선스 라벨 **"Display Redistribution"** — [Tiingo EOD product](https://www.tiingo.com/products/end-of-day-stock-price-data) (표가 깨져 열 매핑은 추정)
- 무료 한도: 50 req/hr, 1,000 req/day, 500 unique symbols/월; Power 10,000/hr, 100,000/day — [Tiingo Pricing](https://www.tiingo.com/about/pricing)

**Finnhub** — ToS 원문 확인, 가격 페이지는 JS 렌더로 본문 없음
- "All plan listed on Finnhub website is strictly for personal use unless explicitly stated otherwise." "Personal plan can't be used by any business even internally without a written approval." **"You hereby agree to not redistribute or share access to data or derived results… with anyone or any 3rd party without written approval from Finnhub."** 구독 종료 시 데이터 삭제 의무 — [Finnhub ToS](https://finnhub.io/terms-of-service)
- 가격: 공식 페이지 **확인 불가**(빈 본문). 2차 자료는 All-in-One USD 1,000/월(TrustRadius) vs ~USD 50/월(비교 사이트)로 상충 — [TrustRadius](https://tr-web.dev.trustradius.com/products/finnhub-stock-apis/pricing); [apicostcalc](https://apicostcalc.com/blog/stock-market-data-api-cost.html)

**EODHD** — 가격 페이지 원문 확인 2026-10-28
- Free USD 0(20 calls/day), Historian(EOD All-World) **USD 19.99/월**, Active trader USD 29.99, Equity analyst(Fundamentals) USD 59.99, All-In-One **USD 99.99/월**; 모두 100,000 calls/day, 1,000/min. 플랜 라벨 "Personal use" vs Commercial "Startups · Teams · Business"(영업 문의, 가격 미표기). 재배포·표시 조항 가격 페이지에 없음. 한국 거래소 커버는 페이지에 미기재("150,000+ tickers worldwide") — [EODHD Pricing](https://eodhd.com/pricing)

**Twelve Data** — 가격 페이지 원문 확인 2026-10-28
- Basic USD 0(800/day, "Internal non-display usage"), Grow **USD 79/월**("Internal display data access", 20+ markets), Pro USD 229, Ultra USD 999("Internal non-display"). 애드온: "Pricing depends on your license type: personal or commercial." 외부(엔드유저) 표시·재배포 가격 미표기. 페이지 JSON-LD는 Grow 29/Pro 99/Ultra 329 로 표시돼 **값 상충** — [Twelve Data Pricing](https://twelvedata.com/pricing)

**Databento** — 가격 페이지 원문 + 도움말 검색 2026-10-28
- 사용량 과금(구독 불필요, GB당), 신규 USD 125 크레딧(6개월 만료); Standard **USD 199/월**("No license fees"), Plus **USD 1,750/월**(연계약, "External distribution" 포함), Unlimited USD 4,500/월. "Your redistribution rights depend on the dataset." 대부분 24시간 후 재배포 가능 — [Databento Pricing](https://databento.com/pricing)
- 라이브는 라이선스 필요·과거 데이터는 불필요; 거래소 요금 마크업 없이 pass-through(+Stripe 2.9%). Nasdaq Basic w/ NLS Plus: 상업 전용 USD 1,600/firm + 13.50/user (신판 1,680 + 14.10). "Databento Equities Basic"(표시·재배포 무료 번들)은 **2025-01-13 폐지**, 현재 US Equities Mini가 "no license fees… display platforms, redistribution" 대상으로 홍보됨 — [Databento 도움말](https://help.databento.com/en/articles/8914894-licensing-and-live-data); [Databento 블로그](https://databento.com/blog/databento-us-equities-mini-now-available)

**Nasdaq Data Link** — 가격 페이지 404
- 무료 WIKI EOD는 2018년 이후 갱신 중단; 유료 EOD(QuoteMedia End of Day US Prices, 코드 EOD) 가격은 "View Pricing/Contact Sales" — 공개 금액 **확인 불가** — [docs.data.nasdaq.com](https://docs.data.nasdaq.com/docs/data-organization); [marketparquet 비교](https://marketparquet.com/vs/quandl)

**Intrinio** (참고 벤치마크) — 도움말 원문 확인 2026-10-28
- Individual: "Display Intrinio data in a customer-facing application" 불가. **Startup: 상업 제품 사용 + "Data can be shown to your application's users" 허용**, 원시 데이터 재배포·화이트라벨 불가. 거래소 데이터는 추가 승인·요금 — [Intrinio Licensing](https://help.intrinio.com/licensing-data-usage-requirements)
- 가격(2차, 상충): Startup USD 333/월 시작 → 666 → 999 또는 1,499 — [multiples.vc](https://multiples.vc/compare/intrinio-api-alternatives/md)

**Financial Datasets** — 가격 페이지 원문 확인 2026-10-28
- Credits USD 20 일회(1,000 req, Personal), Personal **USD 200/월**(100,000 req, "for their own personal, non-business purposes"), **Professional USD 2,000/월(2,000,000 req, Commercial, "Serve our data to your own users inside your product, with attribution")**, Enterprise 커스텀 — [financialdatasets.ai/pricing](https://www.financialdatasets.ai/pricing)

### Inferences
- 미국 EOD 종가·52주 범위를 유저에게 보여주는 **최저가 합법 경로는 Tiingo EOD+IEX Display Redistribution USD 250/월(스타트업)** 이다(한국 종목 미포함). FMP 전환 비용은 Agreement 체결 전까지 알 수 없다.
- "personal use only" 벤더를 유저 표시에 쓰는 것은 전부 약관 위반이며, 유·무료를 가리지 않는다(FMP §2.2.2 "irrespective of whether such usage is complimentary or paid").
- 실시간(15분 미만)·호가는 거래소 비전문가/전문가 요금이 별도 pass-through되므로 EOD 또는 15분 지연 데이터로 범위를 한정하는 것이 비용 통제의 핵심이다.

### Gaps
- FMP Data Display and Licensing Agreement의 **가격·최소 약정**: 비공개(R8 접수건 회신 대기).
- Massive Business 가격, Finnhub 가격, Nasdaq Data Link EOD 가격: 페이지 404/빈 본문.
- EODHD·Twelve Data의 **상업(엔드유저 표시) 가격**: 영업 문의 전용.
- Tiingo 재배포 USD 250/월에 **한국 종목**이 포함되는지: 미확인(US/중국 중심).

---

## 3. 환율 — 상업 이용 가능한 무료/저가 소스와 출처표시 조건

### Takeaway
**ExchangeRate-API Open Access(open.er-api.com)**는 상업 이용 허용·출처 링크 필수·1일 1회 갱신·재배포 금지다. **한국수출입은행 환율 API**는 공공데이터포털에 "이용허락범위 제한 없음"으로 등록돼 있고(도메인 oapi.koreaexim.go.kr로 이전, 구 도메인 2026-04-30 종료). 한국은행 ECOS는 페이지가 JS 렌더라 약관·한도를 **확인 불가**.

### Cited Findings
- ExchangeRate-API Open Access: **"We require attribution on the pages you're using these rates with the link below: `<a href="https://www.exchangerate-api.com">Rates By Exchange Rate API</a>`"**; "for either personal or commercial currency conversion purposes", **"You are, however, not allowed to re-distribute it."** 갱신 24시간 1회, 429 후 20분 대기. 유료 Pro **USD 10/월**(30k req/월, 60분 갱신), Free API 키 1.5k req/월 — [exchangerate-api.com/docs/free](https://www.exchangerate-api.com/docs/free)
- 동 서비스 약관: "both Free Plan and paid ExchangeRate-API accounts are suitable for either commercial or personal use", 재배포 불허 — [exchangerate-api.com/terms](https://www.exchangerate-api.com/terms)
- open.er-api.com 직접 접속: 세션 네트워크 차단(DNS) → 원문 **확인 불가**; 위 docs 페이지로 대체.
- 한국수출입은행 현재환율 API(공공데이터포털 3068846): **"이용허락범위 제한 없음"**, 갱신주기 "실시간" 표기, 트래픽은 "해당 기관의 정책에 따라 트래픽 수는 상이", 비고 **"기존 도메인(www.koreaexim.go.kr)은 2026.4.30 종료 예정이니 신규 도메인(oapi.koreaexim.go.kr)으로 변경"**, 수정일 2026-04-30 — [data.go.kr/data/3068846](https://www.data.go.kr/data/3068846/openapi.do)
- 수출입은행 공식 API 페이지(koreaexim.go.kr/ir/HPHKIR020M01): 503 → 일 1,000건 한도·11시 갱신 등 세부는 **확인 불가**(2차 자료에서 "1,000 calls/day"는 ECOS 인증키 기준이라는 지적 있음) — [검색 요약](https://clawhub.ai/chloepark85/korea-eximbank-exchange-cli)
- 한국은행 ECOS Open API(ecos.bok.or.kr/api): 본문 미수신 → 약관·한도 **확인 불가**. 2차(Apify 액터 설명)는 "일 약 1,000건, 약관 제3조가 출처표시 조건 재배포 허용"이라 주장하나 원문 인용 아님 — [apify nexgendata](https://apify.com/nexgendata/korea-bok-monetary-policy-ecos)

### Inferences
- 평가액 환산용 일 1회 USD/KRW 환율은 ExchangeRate-API Open Access(출처 링크 1줄) 또는 수출입은행 API(제한 없음)로 **무료·합법** 충족 가능. 둘 다 "재배포"가 아닌 "앱 내 환산 표시"는 허용 범위로 읽힌다(수출입은행은 명시 조건 없음).

### Gaps
- ECOS 약관 원문·호출 한도.
- 수출입은행 API의 일 호출 한도·갱신 시각(공식 페이지 503).

---

## 4. 공시 — OpenDART 이용약관, SEC EDGAR 이용 조건, 국내 재가공 사업자

### Takeaway
OpenDART 약관(2020-01-21 시행)에는 **상업 이용·재배포 금지 조항이 없다**. 요금 "원칙적으로 무료"(제11조), 호출 허용량은 "홈페이지에 게시"(제10조④), 저작권은 "저작권법 및 공공데이터법에 따름"(제16조④). SEC EDGAR는 공공 데이터로 **"free to access and reuse"**, 10 req/s 상한·User-Agent(회사명+이메일) 선언 요구. 국내 재가공 사업자(에프앤가이드·딥서치 등)의 스타트업 가격은 **확인 불가**.

### Cited Findings
- OpenDART 이용약관(curl 원문 확인 2026-10-28): 제10조④ **"오픈API 서비스는 이용횟수에 허용량 제한이 있으며, 이를 홈페이지에 게시합니다."** 제11조① **"금융감독원이 제공하는 서비스는 원칙적으로 무료입니다."** 제16조① "오픈API 서비스 및 관련 프로그램의 저작권은 금융감독원에 있습니다." ④ **"약관에 명시되지 않은 저작권과 관련된 사항은 저작권법 및 공공데이터법에 따릅니다."** 제19조⑤ "ID 및 인증키를 2개 이상 발급 받을 수 없습니다." 제23조① 공시정보 정확성은 공시제출인 책임. 부칙 **"이 약관은 2020년 1월 21일 부터 시행합니다."** — [opendart.fss.or.kr/intro/terms.do](https://opendart.fss.or.kr/intro/terms.do)
- 약관 전문에 "상업", "영리", "재배포", "제3자 제공 금지" 문구 **없음**(제3자 언급은 인증키 대여 금지·회원정보 보호·분쟁 면책뿐) — 같은 출처(grep 실측)
- OpenDART 안내: "공시보고서의 원문을 XML형식으로 다운로드받아 원하는 자료를 자유롭게 추출하여 사용할 수 있습니다." — [opendart 소개](https://opendart.fss.or.kr/intro/main.do) (검색 스니펫; 페이지 자체는 503)
- 일일 호출 한도 수치: 개발가이드 페이지 503 → **확인 불가**(널리 알려진 "일 20,000건"은 이번 조사에서 원문 미확인).
- SEC: **"our current maximum access rate is 10 requests per second"**, User-Agent "Sample Company Name AdminContact@<sample company domain>.com" 형식 선언, Accept-Encoding gzip/deflate, Host www.sec.gov. **"All Government-created content on sec.gov and EDGAR public filing content are free to access and reuse."** — [SEC Webmaster FAQ](https://www.sec.gov/os/webmaster-faq)
- SEC developer: "limit each user to a total of no more than 10 requests per second", 과다 요청 IP 차단, "unclassified" 봇 크롤 불허 — [SEC Developer Resources](https://www.sec.gov/about/developer-resources)
- data.sec.gov API: submissions / XBRL companyconcept / companyfacts / **frames** (`/api/xbrl/frames/us-gaap/{tag}/USD/CY2019Q1I.json`), 실시간 갱신(XBRL 1분 내), 벌크 ZIP 매일 03:00 ET, **인증·API 키 불필요, CORS 미지원** — [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- 국내 재가공 사업자: 에프앤가이드는 "DB, API 형태 및 시각화 된 ASP 형태로 제공"(IR 자료), 가격 비공개 — [검색 요약](https://file.alphasquare.co.kr/media/pdfs/company-ir/20240821에프앤가이드_국내_NDR(Non_Deal_Roadshow)_진행.pdf). 딥서치·와이즈리포트 등의 스타트업 요율은 검색으로 **확인 불가**.

### Inferences
- 국내 공시·재무제표는 OpenDART로 **무료·상업 사용 가능**하다고 읽힌다(약관이 금지하지 않고 공공데이터법으로 귀속). 다만 "금지 조항 부재 = 허용"은 추론이므로 변호사 큐에 "OpenDART 데이터의 유료 서비스 내 표시"를 넣는 게 안전.
- 미국 재무·배당 원천은 SEC XBRL(companyfacts/frames)이 무료·재사용 가능하고 레이트리밋만 지키면 된다. 벤더(FMP statements 등)를 유저 표시에 쓰려면 §2의 표시 라이선스가 동일하게 필요하다.

### Gaps
- OpenDART 일 호출 한도 수치·초과 에러코드(개발가이드 503).
- DART 외 국내 공시 재가공 사업자(에프앤가이드·딥서치·NICE 등)의 API 가격·재배포 조건.

---

## 5. 배당·재무 — OpenDART 재무제표 API, SEC XBRL frames, 벤더 라이선스

### Takeaway
배당·재무는 §4의 공공 원천(OpenDART 상장기업 재무정보·배당 관련 공시, SEC companyfacts/frames)으로 **무료·재사용 가능**하다. 벤더 재무 데이터(FMP statements, Massive Financials USD 29/월, EODHD Fundamentals USD 59.99/월, Twelve Data 애드온)는 **모두 개인용 라벨**이라 유저 표시엔 §2의 상업·표시 라이선스가 그대로 적용된다.

### Cited Findings
- SEC XBRL frames/companyfacts: 무료·키 불필요·"free to access and reuse" — [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces); [SEC Webmaster FAQ](https://www.sec.gov/os/webmaster-faq)
- OpenDART: 요금 원칙 무료, 재배포 금지 조항 없음(§4) — [OpenDART 약관](https://opendart.fss.or.kr/intro/terms.do)
- Massive "Financials & Ratios" **USD 29/월 "Individual use only"** — [massive.com/pricing](https://massive.com/pricing)
- EODHD "Equity analyst (Fundamentals Data Feed)" **USD 59.99/월**, Personal 라벨 — [EODHD Pricing](https://eodhd.com/pricing)
- FMP: Starter "Annual Fundamentals and Ratios", Premium "Full Fundamentals and Ratios", 표시엔 Agreement 필요 — [FMP Pricing](https://site.financialmodelingprep.com/pricing-plans)
- Financial Datasets Professional USD 2,000/월에 재배포 포함("with attribution") — [financialdatasets.ai/pricing](https://www.financialdatasets.ai/pricing)

### Inferences
- 재무·배당은 시세와 달리 공공 원천만으로 유저 표시가 가능하며 거래소 라이선스 이슈가 없다. 국내 배당은 OpenDART 공시(배당결정·사업보고서 배당 항목)에서 추출해야 하므로 파싱 비용이 든다.

### Gaps
- OpenDART "배당에 관한 사항" API 의 구체 엔드포인트·필드: 개발가이드 503로 이번 조사에서 미확인.

---

## 6. 실제 사례 — 한국 소형 핀테크/개인개발 앱의 조합·비용, '취득가 기준(시세 미표시)' 운영 사례

### Takeaway
공개된 "소형 핀테크 시세 라이선스 비용 사례"는 찾지 못했다. 개인개발 앱이 쓰는 회피 패턴 하나는 확인됐다: **유저 본인의 한국투자증권 API 키**를 앱에 넣어 실시간 시세를 받고, 키가 없으면 **Yahoo Finance 20분 지연**으로 대체(앱 "주식 위젯", 2026). **"취득가 기준·시세 미표시" 운영 사례는 검색으로 확인 불가**(PivoxQuant 자체 결정 2026-09-19 외).

### Cited Findings
- iOS 앱 "주식 위젯 - 실시간 국내 주식 수익률"(개발자 김재융, v1.0.2, 2026): **"한국투자증권 공식 API 완벽 지원 개인 API 키 연동으로 15분 지연 없는 '진짜' 실시간 시세를 제공합니다."** / **"API 키가 없어도 야후 파이낸스 데이터를 통해 전 세계 주식 정보를 기본 제공합니다. (20분 지연 시세)"** / "실시간 시세 이용을 위해서는 한국투자증권 계좌 및 API 키 발급이 필요". 시세 라이선스 고지 없음 — [App Store](https://apps.apple.com/kr/app/id6759692289)
- 토스증권: "국내 시세 정보는 한국거래소로부터 제공받는다"(정식 라이선스 경로, 비용 비공개) — [byline.network 2022-06](https://byline.network/2022/06/10-234/)
- 2014년 기사: 증권사들은 1989년부터 코스콤·KRX에 시세정보료를 정기 납부, 25년 만의 산정기준 변경 협상 — [etnews 2014-12-04](https://english.etnews.com/20141204200002)
- 개발자 블로그: 크롤링은 "저작권 침해 소지", API 우선 권고; 네이버 금융은 해외 IP 차단+JS 렌더로 접근 곤란 — [검색 요약, wikidocs](https://wikidocs.net/313949)
- 2017년: 코스콤 오픈API 당시 무료 정책(1년 또는 1만 다운로드)과 유료화 검토 — [newspim](https://www.newspim.com/news/view/20170202000289)
- 마이데이터: 타인 금융정보 수집 사업자는 본허가 필요(2021년 기준 45곳); 소형 개발자 예외 경로는 검색에서 **확인 불가** — [fnnews 2021-12-06](https://www.fnnews.com/news/202112061816017793)

### Inferences
- "유저 본인 키" 패턴은 데이터가 유저↔증권사 사이에서 오가므로 앱이 재배포자가 아니라는 논리를 세울 수 있지만, KIS Developers 약관이 이를 허용한다는 원문은 없다(개인 Open API는 "본인 자산 투자 범위" 한정). 변호사 확인 항목.
- 취득가 기준 운영은 공개 사례가 없는 만큼, 베타 유저에게 "시세는 라이선스 체결 전까지 표시하지 않는다"는 고지가 UX상 더 중요하다.

### Gaps
- 한국 소형 핀테크의 코스콤 계약 실제 금액·후기: 블로그·커뮤니티에서 0건.
- 취득가 기준으로 운영한 국내 투자 기록 앱 사례: 0건.
- Yahoo Finance 비공식 API의 상업 표시 적법성(앱 사례가 쓰지만 Yahoo 약관은 조사 범위 밖).

---

## 부록 — 접근 실패 목록 (2026-10-28)
- 403: site.financialmodelingprep.com (WebFetch; curl UA 지정으로 우회 성공)
- 503: opendart.fss.or.kr/intro/main.do, /guide/main.do, koreaexim.go.kr/ir/HPHKIR020M01
- 404: massive.com/terms/individuals(→ /legal/individuals-terms-of-service 성공), massive.com/pricing/business, data.nasdaq.com/pricing
- 빈 본문(JS 렌더): finnhub.io/pricing, ecos.bok.or.kr/api, koscom.co.kr fintech 페이지, data.krx.co.kr 이용안내
- DNS 차단: open.er-api.com
