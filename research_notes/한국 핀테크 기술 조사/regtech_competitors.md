# 한국 핀테크 레그테크·경쟁 제품 기술 스택 조사 (2026-10-28 기준)

> 범위: (1) 비인가 투자 기록·회고 앱이 지켜야 할 규제 경계와 그 안에 머무는 기술 관행, (2) 국내·해외 유사 제품의 공개 스택·가격·팀 규모, (3) 1인 창업자의 비용·절차.
> 원칙: 공개 근거 없는 스택은 "확인 불가". 법 해석은 변호사 자문이 아님. 검색·열람은 2026-10-28 에 수행.

---

## KQ1. 유사투자자문업 신고 vs 자본시장법 §101 — 2024-08 개정 이후 '기록·회고 앱'이 신고 없이 가능한 범위, 그리고 이를 지키는 기술 관행

### Takeaway
2024-08-14 시행 개정법에서 §101 신고 대상의 핵심 요건은 **"고객으로부터 일정한 대가를 받고" + "개별성 없는 조언"** 이다. 무료이고 조언을 제공하지 않는 기록·회고 앱은 요건 두 개 모두에 걸리지 않을 가능성이 높지만, 유료 구독을 붙이는 순간 "대가" 요건이 살아나므로 **그때 남는 방어선은 "조언이 아니다"는 것뿐**이고, 그걸 코드로 보증하는 것이 금지어 필터·면책 자동 삽입·응답 스크럽이다. 양방향 채널(오픈채팅·SNS) 유료 운영은 투자자문업(등록제)으로 간주된다.

### Cited Findings
- 금융위 보도자료(2024-08-14): 유사투자자문업자는 **불특정 다수에게 "단방향 채널"로 "개별성 없는 조언"만** 제공 가능. 단방향 채널 예시 = "수신자가 채팅을 입력할 수 없는 채팅방, 푸시 메시지, 알림톡". SNS·오픈채팅방 등 **양방향 채널에서 유료 회원제로 영업하면 투자자문업자로 규율**, 미등록 시 3년 이하 징역 또는 1억원 이하 벌금 — [금융위원회 보도자료 「오늘(8.14일)부터 자본시장법이 시행됩니다」](https://fsc.go.kr/edu/news/83077?curPage=1)
- 같은 보도자료: 유사투자자문업자 의무 = 유사투자자문업자임·개별 상담 불가·원금손실 가능성 고지. 금지 = 손실보전·이익보장 약정, 금융회사 오인 광고, 허위·미실현 수익률, 유리한 기간만의 수익률, 불확실한 사항의 단정적 판단. 신고 유효기간 5년(만료 3개월~1개월 전 갱신). 거짓·부정 신고 = 1년 이하 징역 또는 3천만원 이하 벌금 — [금융위원회](https://fsc.go.kr/edu/news/83077?curPage=1)
- 조문 변경(대륜 뉴스레터 요약): **§101①** 정의가 "불특정 다수인을 대상으로 하여 발행되는 간행물, 전자우편 등" → **"고객으로부터 일정한 대가를 받고 간행물·출판물·통신물 또는 방송 등을 통하여 행하는"** 으로 바뀜. **§7③**: 간행물·방송 등을 통한 조언은 원칙적으로 투자자문업에서 제외되나 "온라인에서 대가를 낸 고객과 의견을 주고받을 수 있으면 투자자문업". **§101의2(신설)** 손실보전·이익보장 금지 준용, **§101의3(신설)** 표시·광고에 ①개별 상담·자금운용 불가 ②원금손실 가능성·투자자 귀속 ③정식 금융투자업자 아님 을 포함해야 함. 벌칙 §446 17호의3(거짓 신고), §449① 34호의3(표시·광고 위반 과태료) 신설 — [법무법인 대륜 뉴스레터 「개정 자본시장과 금융투자업에 관한 법률[시행 2024.8.14]」](https://www.daeryunlaw.com/newsletter/news/53)
- 변호사 해설(조윤상, 로톡): 대가성 판단 기준은 "투자자로부터 금융투자상품의 투자조언과 관련하여 직접적으로 대가를 수령하였는지 여부". **"누구나 같은 투자조언을 무료로 받을 수 있는 경우에는 직접적인 대가를 받았다고 보기 어려워 신고가 필요하지 않다"**. 플랫폼 광고수익만 얻거나 자발적 후원을 간헐적으로 받는 경우는 신고 대상 아님. **정기 구독료 등 유료 회원제를 운영하면서 투자조언을 하면 신고 대상**, 유료회원 1:1 상담은 투자자문업 등록 필요 (게시일 미표시, 2024 개정 반영 여부 불명) — [로톡 「유튜브로 주식방송, 유사투자자문업 신고 해야할까?」](https://www.lawtalk.co.kr/posts/34923)
- 다른 변호사 칼럼: 신고 여부는 "콘텐츠 수위가 아니라 수익 구조"에서 갈림. "일정 금액 이상 후원자에게만 별도 정보를 주는 방식"은 형식만 후원이고 사실상 대가 — [로톡 「유튜브 종목추천 방송…」](https://www.lawtalk.co.kr/posts/172444)
- 언론(메트로, 2024-07-22): 금감원 안내로 "무료 회원에게 대가 없이 운용한다면 양방향 채널 운용이 가능" — [메트로신문](https://www.metroseoul.co.kr/article/20240722500350) (본문 재열람 시 503 — 검색 스니펫 기준, 원문 재확인 필요)
- 2024-08-06 이투데이: "14일부터 오픈채팅방·SNS 영업 금지…대안 찾는 유사투자자문업계" — [이투데이](https://www.etoday.co.kr/news/view/2387577)
- 신고 수리 거부·직권말소 사유에 **방문판매법·전자상거래법 위반**이 추가됨(시정조치 미이행 등) — [금융위원회](https://fsc.go.kr/edu/news/83077?curPage=1)

**기술 관행 — PivoxQuant 리포 내부 실측 (공개 사례는 KQ1 Gaps 참조):**
- `services/legal_filter.py` 헤더: "자본시장법 §17 + §101 리스크 방어선", `_REPLACEMENTS` 정규식 42패턴으로 "매수 권고/매도 권고" 등 advisory 동사를 safe alternative 로 **surgical 치환**(hard-drop 아님), `_PROHIBITED_PATTERNS` 은 치환 불가 구조적 위반을 로그 경고. 통합점 = `routes/decorators.py::@legal_scrub_response` 로 약 12 엔드포인트 응답 전체 딥 스크럽, `services/alert.py` 의 알림 title/body. 2026-09-01 이후 이 정규식이 **유일한** 방어선 (소스 엔진 삭제) — `/home/user/pivoxquant/services/legal_filter.py` 1~60행
- 동일 리포: 금지어 동기화·면책 SoT·딥스캔 테스트 7종 (`tests/test_disclaimer_sot.py`, `test_forbidden_terms_sync.py`, `test_legal_deep_scan_local.py`, `test_legal_filter*.py`, `test_legal_scrub_decorator.py`), pre-commit `legal-guard` 는 **추가된 줄만** 검사, 예외 표기 `// legal-ok` — `/home/user/pivoxquant/CLAUDE.md` 함정 4·6
- 동일 리포: 시그널 라벨 POSITIVE/NEGATIVE/NEUTRAL 강제(BUY/SELL/HOLD 금지), "AI Coach"·"투자 코치"·추천·조언 어휘 금지, `DisclaimerBanner` 는 `(dashboard)/layout.tsx` 에서 경로별 1회 마운트 — `/home/user/pivoxquant/CLAUDE.md` 「중요 원칙」

### Inferences
- 개정법 구조상 **무료 + 조언 없음**인 기록·회고 앱은 §101 의 두 요건(대가·조언) 모두 밖에 있다. 유료화하면 "대가" 요건이 충족되므로, 그 시점부터는 **앱 출력이 "조언"이 아님을 입증하는 구조**(기록의 되비춤·통계만, 종목별 매수/매도 방향 표시 없음)가 유일한 경계선이 된다. §101의3 고지 3종(개별 상담 불가·원금손실·금융투자업자 아님)은 신고 대상이 아니더라도 면책 문구로 **선제 채택**하는 것이 비용이 거의 없는 방어다.
- "양방향 채널" 규율은 유료 **커뮤니티/채팅**에 걸린다. 살래말래처럼 매매일지+커뮤니티를 결합한 모델은 유료화 시 이 조항을 직접 맞는다(KQ4 참조). PivoxQuant 는 커뮤니티가 없어 이 리스크가 없다.
- 공개된 한국 핀테크의 "금지어 필터·응답 스크럽" 구현 사례는 **찾지 못했다**. 이는 업계가 안 한다는 뜻이 아니라 공개하지 않는다는 뜻으로 읽힌다 — 비교 대상이 없으므로 PivoxQuant 의 `legal_filter` 는 독자 설계로 봐야 하고, 변호사 검토 없이는 "충분"을 주장할 근거가 없다.

### Gaps
- 금융위·금감원이 **"무료 정보 제공 앱"** 에 대해 낸 유권해석·비조치의견서는 검색으로 찾지 못했다. (CLAUDE.md 에 적힌 "무료 운영은 §101 밖인가"는 여전히 변호사 질문 목록에 남겨야 한다.)
- 금지어 필터·면책 자동 삽입·응답 스크럽을 **공개적으로 설명한 국내 핀테크 기술 블로그·논문은 발견하지 못했다.** 토스·카카오페이증권·뱅크샐러드 채용 공고·블로그 어디에도 법률 필터 레이어 언급 없음.
- 2025~2026 년 유사투자자문업 추가 개정(폐지 논의 등)은 이번 검색 범위에서 확인되지 않음.
- 생성형 AI 로 투자 정보를 제공할 때의 금융위 가이드라인(2025)은 검색으로 원문을 찾지 못함 — 로보어드바이저 테스트베드·IRP 샌드박스(계좌당 연 900만원 한도) 기사만 확인 — [전자신문 2025-04-24](https://www.etnews.com/20250424000040)

---

## KQ2. 표시광고법·금소법 카피 제약, 금융광고 사전심의 적용 여부

### Takeaway
금소법 §22 광고 규제와 협회 사전심의는 **"금융상품 또는 금융상품판매업자등의 업무"** 광고에 걸린다. 금융상품을 팔거나 중개하지 않는 기록 앱의 자체 서비스 광고는 금소법 광고 주체 제한의 1차 대상이 아니라는 것이 가이드라인 구조상 읽히지만, **표시광고법은 모든 사업자에 적용**되고, 비교·추천 기능이 들어가면 "중개"로 재분류될 수 있다는 2021 년 금융위 판단이 유효하다.

### Cited Findings
- 금융위 금융광고규제 가이드라인(2021-06): "금소법(§22)에서는 금융상품판매업자등이 아닌 자의 광고를 엄격히 제한하고 있으며, 광고할 수 있는 자를 법령에 열거". "온라인 포털, 핀테크 업체는 그 역할이 광고 매체가 아니라 판매과정에 적극 개입하는 광고 주체에 해당하는 경우에는 반드시 금융상품판매업자로 등록". 광고 시 "표시광고법, 방송법, 대부업법 등 다른 법령 위배 여부"도 확인. 금소법상 광고 = "금융상품이나 업무에 관한 사항을 소비자에게 널리 알리거나 제시하는 행위"이며 표시광고법이 함께 적용. 사전심의는 금융업권 협회가 담당 — [금융위원회 보도자료 76045](https://www.fsc.go.kr/no010101/76045)
- 2021-09 금융당국: 핀테크 플랫폼의 금융상품 **비교·추천은 단순 광고가 아니라 금소법상 "중개"** — 계도기간 종료 후 비교·추천하려면 판매대리·중개업자 등록 필요. 업계: "자본시장법상 투자권유대행인 등록은 개인만 허용되어 법인인 핀테크 회사는 투자상품 중개업자로 등록 자체가 불가능" — [블록미디어 2021-09](https://www.blockmedia.co.kr/archives/193194); [아주경제 2021-09-15](https://www.ajunews.com/view/20210915030933437)
- 유사투자자문업자 표시·광고 금지 항목(금융회사 오인, 허위·미실현 수익률, 유리한 기간만의 수익률, 단정적 판단)과 필수 고지 3종 — KQ1 의 §101의2·§101의3 참조 — [대륜](https://www.daeryunlaw.com/newsletter/news/53)

### Inferences
- 기록 앱이 **금융상품(증권·펀드·계좌)을 광고·비교·추천하지 않는 한** 금소법 §22 의 광고 주체 제한과 협회 사전심의는 걸리지 않는 구조다. 반대로 "증권사 계좌 개설 링크", "ETF 비교" 같은 기능은 즉시 중개·광고 이슈로 전환된다 — 제휴 수익 모델을 넣을 때의 레드라인.
- 표시광고법은 일반법이므로 "수익률 개선", "손실 방지" 류 카피는 §101의2 의 허위·미실현 수익률 금지와 표시광고법 기만 광고 양쪽에 걸릴 수 있다. CLAUDE.md 의 "없는 기능을 파는 카피 금지"는 이 두 법의 교집합을 코드 규칙으로 옮긴 것이다.

### Gaps
- 2021 가이드라인 이후 2026 년까지의 개정 여부, 그리고 **비금융 사업자의 "투자 기록 앱" 자체 광고**에 대한 당국 판단 사례는 찾지 못했다.
- 금융광고 사전심의의 **구체적 적용 대상 범위(금융투자협회 심의 규정 원문)** 는 열람하지 못함.

---

## KQ3. 규제 샌드박스(혁신금융서비스), 핀테크지원센터·K-Startup 무료 법률 자문 — 1인 창업자가 쓸 수 있는 제도와 기간

### Takeaway
혁신금융서비스는 분기별 정기 접수 + 법정 심사 최대 120일, 지정 유효 2년(+최대 2년 연장) 구조이고 무료 사전 컨설팅(핀테크지원센터 전문지원단 73명)이 붙는다. 기록 앱이 **규제를 면제받을 필요가 없다면 샌드박스는 불필요**하고, 당장 쓸 수 있는 건 K-Startup 법률 자문(2026-03-30~12-31 상시, 850건 내외)과 핀테크지원센터 무료 컨설팅이다.

### Cited Findings
- 2026-3분기 정기신청: 2026-09-14 09:00 ~ 09-30 18:00 금융규제 샌드박스 홈페이지 온라인 접수. "법률, 특허, 회계, 기술 분야 전문가 73명으로 구성된 전문지원단"이 신청 서류 작성 등 단계별 **무료 컨설팅**. 법정 심사기간 **최대 120일**, 혁신금융심사위원회 심사 후 금융위 정례회의에서 지정 결정 — [KDI 경제정보센터(금융위 자료)](https://eiec.kdi.re.kr/policy/materialView.do?num=286746)
- 2026-2분기 정기신청(6월 30일 마감): "단계별 컨설팅을 무료로 제공", 심사 단계·일자는 샌드박스 홈페이지에서 확인 — [아시아경제 2026-06-15](https://view.asiae.co.kr/article/2026061411451820307); [헤럴드경제 2026-06-14](https://www.heraldk.com/article/2026061413000075037)
- 전문지원단 매칭형 "실질적 요건 컨설팅은 중·소 핀테크 기업만 이용 가능" (2026 보도). 신청: sandbox.fintech.or.kr → 제도신청 → 컨설팅 신청 — [스마트투데이](https://www.smarttoday.co.kr/ko-kr/articles/111548)
- 지정 유효기간: 현행법 2년 + 1회 2년 이하 연장(최대 4년). 2024년 발의된 특별법 개정안은 4년+연장 최장 6년 — [국민참여입법센터 입법예고](https://opinion.lawmaking.go.kr/gcom/nsmLmSts/out/2202889/detailRP) (통과 여부 미확인)
- K-Startup 스타트업 법률지원사업 2026(수정 공고): 지원기간 **2026-03-30 ~ 2026-12-31 연중 상시, 예산 소진 시 조기종료**. 대상 "기술창업기반 예비창업자 및 창업기업", K-Startup 회원가입 후 '원스톱 지원센터'에서 신청, 자문단 변호사 1:1. 규모 **850건 내외(국내 700, 해외 150)**. 문의 창업진흥원 원스톱지원실 044-410-1747/1750 — [중기부 공고 PDF(thevc 미러)](https://grant-documents.thevc.kr/299360_2026%EB%85%84_%EC%8A%A4%ED%83%80%ED%8A%B8%EC%97%85_%EB%B2%95%EB%A5%A0%EC%A7%80%EC%9B%90%EC%82%AC%EC%97%85_%EC%B0%B8%EC%97%AC%EA%B8%B0%EC%97%85_%EB%AA%A8%EC%A7%91_%EA%B3%B5%EA%B3%A0(%EC%88%98%EC%A0%95).pdf); [창업진흥원](https://www.kised.or.kr/menu.es?mid=a10212020000)
- 2025 공고 기준 수치(연 1,000건·기업당 300만원 한도)는 2025 년 것 — 2026 조건과 다를 수 있음 — [중기부 2025 공고](https://lawschool.wku.ac.kr/wp-content/uploads/sites/91/2025/04/붙임1중소벤처기업부공고제2025_257호2025년스타트업법률지원사업법률자문단모집공고.pdf)
- 리포 내부: 2026-06-05 에 이미 "상담A K-Startup 약관·처리방침 검토의뢰서"와 "상담B 핀테크센터 자본시장법 §101 검토의뢰서"가 작성되어 있음 — `/home/user/pivoxquant/docs/legal/상담A_Kstartup_약관처리방침_검토의뢰서.md`, `/home/user/pivoxquant/docs/legal/상담B_핀테크센터_자본시장법101_검토의뢰서.md`

### Inferences
- 샌드박스는 "규제 특례가 필요한 서비스"용이다. 기록 앱이 면제받을 규제가 없다면 지정 신청은 시간(접수~지정 최대 120일 + 분기 대기)만 쓰고 얻는 게 없다. 다만 **시세·거래내역 연동(마이데이터 대체)** 같은 데이터 쪽 특례가 필요해지면 그때 고려 대상.
- 1인 창업자에게 가장 빠른 경로는 K-Startup 법률 자문(상시) → 핀테크지원센터 컨설팅(법률 전문가 포함) 순. 두 제도 모두 "창업기업" 자격이 필요하므로 **사업자 등록**이 선행 조건이다(공고 상 명시, 세부 요건은 Gaps).

### Gaps
- K-Startup 2026 **기업당 지원 한도·회수** 미확인. 핀테크지원센터 컨설팅의 **대기 기간** 공개 자료 없음.
- 특별법 개정안(유효기간 4년) 통과 여부 미확인 — 국가법령정보센터 확인 필요.

---

## KQ4. 경쟁·유사 제품 기술 스택·가격·팀 규모 (공개 정보만)

### Takeaway
국내 대형(토스증권·카카오페이증권·뱅크샐러드)은 **JVM(Kotlin/Java)+Spring+Kubernetes+MySQL** 이 공통 분모이고 일부 Go 가 섞인다. 국내 소형 기록 앱(살래말래·도미노)은 스택이 공개되지 않았다. 해외 기록 앱은 1인~8인 팀이 10만~60만 유저를 운영한 사례(Tradervue 1인/10만+, Sharesight 개발팀 8인/60만+)가 공개되어 있고, 가격은 무료 티어 + 월 $10~35 / 연 $197 범위.

### Cited Findings

**국내 대형**
- **토스증권**: 채용 공고 — Kotlin, Java, Gradle, Spring MVC/WebFlux/Boot/Cloud, JPA/Hibernate, MySQL, MongoDB, Redis, Kubernetes, Istio; Market Platform 공고는 Go, Netty, Kafka, NATS 병기 — [토스 채용 Server Developer (Platform)](https://toss.im/career/job-detail?gh_jid=4168349003); [토스증권 Market Platform 공고(인디스워크 미러)](https://inthiswork.com/?p=323617). 토스 서버 챕터 FAQ(2022-02-22): Java/Kotlin + Spring Boot, JPA/Hibernate, DB = MySQL·MongoDB·Elasticsearch; "서버 개발자의 93%는 이전 직장이 비금융권" — [토스피드](https://toss.im/tossfeed/article/toss-serverchapter-faq10)
- **카카오페이증권**: 공고 — Java/Kotlin JVM 웹앱, Spring, AWS, Kubernetes 기반 컨테이너 인프라·CI/CD·Observability 담당 DevOps 팀 — [리멤버 공고](https://career.rememberapp.co.kr/job/posting/282605); [원티드 공고](https://www.wanted.co.kr/wd/339967)
- **뱅크샐러드**: 공고 — "gRPC 위에서 Go, Kotlin 또는 Python", "대부분의 서비스가 AWS 환경 위에 구축된 Kubernetes에서 운영", DB "주로 MySQL 또는 DynamoDB", CI/CD GitHub Actions/ArgoCD/Helm, 관측 Datadog·Amplitude·Sentry — [리멤버 공고](https://career.rememberapp.co.kr/job/posting/297517); [원티드](https://www.wanted.co.kr/wd/344632)
- **핀크(Finnq)**: 공고 — 백엔드 Java, Spring, MyBatis, JPA; 프론트 Vue, React; DB Oracle, MariaDB + 캐시; 필수 태그 Nexcore (클라우드 언급 없음, 하나금융 계열) — [리멤버 공고 292268](https://career.rememberapp.co.kr/job/posting/292268)
- **월급쟁이부자들(월부)**: 2025-05 22개 직군 공채, 2025-10 CPO·FE 리드·BE 리드·데이터 리드 채용, "IT 플랫폼 기업 전환" 추진. **스택 공개 없음** — [유니콘팩토리 2025-05-15](https://www.unicornfactory.co.kr/article/2025051516354554238); [경향 2025-10-27](https://sports.khan.co.kr/article/202510272239003)

**국내 소형·직접 경쟁**
- **살래말래 (주식 매매일지 & 커뮤니티)**: iOS 최초 출시 **2025-11-20**, 최신 6.2026.001(2026-06-05). 개발자 IMGOBOT(임고봇), 저작권 "© 2026 FinTrendBeacon INC.", 사이트 fintrendbeacon.com. **무료, 인앱 구매 항목 없음**, 연령 19+, 요소에 "광고·메시지 및 채팅·사용자 생성 콘텐츠". 설명: 종목명·매수가·수량 기록, 종목별·기간별 패턴, 매매일지 선택 공개·피드백(커뮤니티), 복기 알림. 1.0.6(2025-12-21)에 "국내·미국 주식, 암호화폐 종목 정보 최신화, 종목명 자동완성". 수집: 이메일·사용자 ID·광고 데이터, 타사 광고 용도. iPhone 전용 79.8MB, iOS 16.4+ — [App Store](https://apps.apple.com/kr/app/id6755510192?l=ko)
- **도미노 (패스트포워드)**: 국내·해외주식·펀드·채권·외환·부동산 통합 관리, "연동 한 번으로 투자 내역", 실시간 시세·급등락 알림, "미국 시세는 나스닥 데이터 연동으로 무료". **무료 + 인앱 '플러스 멤버십' ₩9,900**. v2.14.9(9월 3일), 139.6MB, iOS 15+. 연동 방식(마이데이터/인증서/스크래핑)은 페이지에 미기재 — [App Store](https://apps.apple.com/kr/app/id1540576519). 투자: 한국투자파트너스·하나벤처스·스톤브릿지·스프링캠프 **Pre-A 80억원**, 2023-09 코리아 핀테크 위크 IR 1위, "투자관리 서비스 최초 마이데이터 사업자 신청" — [벤처스퀘어](https://www.venturesquare.net/894635); [넥스트유니콘](https://www.nextunicorn.kr/content/d6e6ccd09ff172d8)
- **키움 "자동매매일지"**: 독립 서비스로는 확인 안 됨. 가장 가까운 것은 영웅문4 화면 1300 "영웅결정전 TOP10 자동일지차트"(2023-11, 실전투자대회 상위 10인 매매동향 열람) — [뉴스토마토](https://newstomato.com/ReadNews.aspx?no=1207773). 키움 REST API 는 "계좌 평가잔고 현황, 주식 분봉 차트" 조회 가능, 2025-08 거래 이벤트 시즌2 — [한국경제 2025-08-25](https://www.hankyung.com/amp/202508258969P)
- **증권사 Open API 동향**: KB증권 2026-08 개인 고객 오픈API(잔고·체결 내역 조회 포함, 약관 동의 절차) — [머니투데이 2026-08-04](https://www.mt.co.kr/stock/2026/08/04/2026080414364184356); [AlgoLab 가이드](https://algolab.co.kr/blog/kb-securities-open-api-personal-2026). 한국투자증권 REST API 공식 문서·커뮤니티 래퍼 다수 — [wikidocs](https://wikidocs.net/313950)

**해외 비교군**
- **Tradervue**: 2011 년 Greg Reinacker 창업, **2021 SureSwift Capital 인수 시점에 "lone employee"로 10만+ 활성 트레이더** 운영 — [tech.mn 2021-03-30](https://tech.mn/news/2021/03/30/sureswift-capital-acquires-tradervue). 무료 티어 + Pro 약 $29/월(비교 블로그 수치) — [lunefi 2026](https://lunefi.com/blog/best-tradervue-alternatives-2026-top-7-trading-journals). 스택 **확인 불가**
- **Edgewonk**: 공식 가격 **연 $197("save 53%") / 월 $35**, 단일 플랜, 무료 체험 없음(14일 환불), VAT 별도. 운영사 "© 2026 Quantum Trade Solutions GmbH". 팀·스택 미기재 — [edgewonk.com/pricing](https://edgewonk.com/pricing)
- **TradesViz**: Georgia Tech 재학 중 Pavitra Kumar(PK) 프로젝트로 시작, Tradier 제휴 글에 "PK (Founder) and his team" — [Tradier 블로그](https://blog.tradier.com/blog/tradesviz-partnership-announcement). 무료 플랜(월 3,000 trade 한도)·유료 $19/월(비교 블로그) — [pineify 2026](https://pineify.app/trading-journal/best-trading-journal-software). 스택 **확인 불가**
- **Sharesight**: 2017-09 CTO Q&A — 모바일 앱은 **Ember.js 웹앱을 Apache Cordova 로 래핑**, OAuth RESTful API, **전체 인프라 AWS**, DB **MySQL → Amazon Aurora** 이전, "real-time performance calculations are quite CPU and memory intensive", **"8 full-time staff on the Sharesight development team in Wellington"**, 초기 외주 견적 $50k~$500k, 첫 버전은 Abletech(지분 투자자)와 구축 — [Sharesight 블로그](https://www.sharesight.com/blog/qa-with-sharesight-co-founder-and-cto-scott-ryburn-on-10-years-of-sharesight). Abletech 는 Ruby on Rails 를 주력으로 명시 — [Sharesight 파트너 페이지](https://sharesight.com/partners/abletech/). 2008 첫 유료 유저, 2015 고객 대상 $2m 조달, 현재 "600,000+ investors, 150+ countries" — [About](https://www.sharesight.com/about-us/). 가격: 무료 10종목, Investor $15/월·Expert $24/월(비교 블로그, 지역별 상이) — [allinvestview 2026](https://www.allinvestview.com/portfolio-tracker-comparison/)
- **Delta**: 2019-11 eToro 인수(비공개, 업계 추정 $5M), 벨기에 팀(Nicolas Van Hoorde), 당시 6,000+ 크립토·180+ 거래소 — [TechCrunch 2019-11-06](https://techcrunch.com/2019/11/06/investment-platform-etoro-acquires-crypto-portfolio-tracker-app-delta). Free / Pro $9.99/월(비교 블로그) — [work-club 2026](https://work-club.com/best-portfolio-tracker-apps-2026/amp/)
- **Kubera**: Rohit Nadhani 공동창업·CEO — [premieralts 프로필](https://www.premieralts.com/people/rohit-nadhani). 전작 CloudMagic 은 전액 부트스트랩(벵갈루루) — [Inc42](https://inc42.com/?p=142741). Kubera 자체의 팀 규모·스택·2026 가격 **확인 불가** (가격 인상 리뷰만 존재 — [mezzi](https://www.mezzi.com/blog/kubera-price-hike-worth-it-alternatives-compared))

### Inferences
- 국내 **직접 경쟁(살래말래·도미노)** 은 둘 다 iOS 네이티브 앱스토어 배포 + 광고/인앱 결제 모델이다. 살래말래는 커뮤니티+광고(19+, 타사 광고 수집), 도미노는 시세·연동+₩9,900 멤버십. PivoxQuant 의 PWA·시세 미표시·광고 없음은 이 둘과 정반대 축이다.
- 해외 사례는 **1인(Tradervue)~8인(Sharesight 개발팀)** 으로 10만~60만 유저가 가능함을 보여준다. 공통점: 브로커 가져오기(CSV/API)가 핵심 기능이고, 시세는 모두 표시한다. 즉 "시세 미표시"는 해외 기준으로도 비표준이다(KQ7).
- 국내 대형의 JVM+K8s 스택은 **팀 규모와 규제 감사(망분리·금융보안원)** 가 전제다. 1인 창업자가 같은 스택을 택할 이유는 없고, Sharesight(초기 Rails + Cordova 래핑, 나중에 AWS/Aurora)가 더 가까운 참고 모델이다.

### Gaps
- 살래말래·도미노·월부·핀크 의 **클라우드·백엔드 스택은 공개 근거 없음 → 확인 불가**.
- Tradervue·TradesViz·Edgewonk·Kubera·Delta 의 **현재 스택은 확인 불가**. StackShare 류 결과는 동명이인 페이지였다.
- 도미노의 **증권사 연동 방식(마이데이터 허가 취득 여부)** 미확인 — "신청" 보도만 존재.
- 해외 가격은 대부분 비교 블로그 인용(공식 페이지는 Edgewonk 만 직접 열람). Sharesight·Tradervue·TradesViz 공식 가격 페이지는 미열람.

---

## KQ5. 결제·구독 기술 — 통신판매업 신고, PG(토스페이먼츠·포트원·Stripe), 앱스토어 인앱결제·PWA 예외

### Takeaway
월 구독 유료화 시 (a) 통신판매업 신고(직전년 50회 미만·간이과세자는 면제, 단 PG 가 신고번호를 요구), (b) 국내 PG(토스페이먼츠 가입비 22만원·연 11만원·카드 3.4%, 영세 등급 시 0.4~1.45%로 환급), (c) **Stripe 는 한국 법인 직접 가입 불가가 중론**, (d) 네이티브 앱으로 앱스토어 배포 시 인앱결제 의무(한국 제3자 결제 시에도 26% 수수료), **PWA/웹은 앱스토어 가이드라인 적용 밖**(단 가이드라인에 PWA 라는 단어는 없음).

### Cited Findings
- **통신판매업 신고 면제**: 전자상거래법 §12 + 공정위 고시 — "직전년도 통신판매 거래횟수 50회 미만 또는 부가가치세법상 간이과세자" 면제(청약철회 거래 제외). 2020 고시 개정 전 기준은 "최근 6개월 20회 미만 또는 1,200만원 미만" — [뉴시스 2020-07-29](https://www.newsis.com/view/NISX20200729_0001111296); [thecheck 해설](https://thecheck.co.kr/mail-order-business-report-exemption/). 면제여도 "오픈마켓 입점이나 PG 신청 과정에서 신고번호를 요구할 수 있음" — [동일](https://thecheck.co.kr/mail-order-business-report-exemption/). 등록면허세 2026: 인구 50만 이상 시 40,500원 / 그 밖의 시 22,500원 / 군 12,000원 — [hometax-go](https://hometax-go.kr/mailorder-costs/)
- **토스페이먼츠 공식 요금**: 가입비 220,000원(최초 1회), 연관리비 110,000원, 신용·체크카드 일반 3.4%, 계좌이체 2.0%(최저 200원), 가상계좌 400원/건, 간편결제 3.4%, 휴대폰 디지털 콘텐츠 7.0%, 페이팔 4.0%+$0.3, VAT 별도, 정산 평균 5일, 1,000만원까지 보증보험 면제. **구독·자동결제(빌링) 요금은 페이지에 없음** — [tosspayments.com/about/fee](https://www.tosspayments.com/about/fee)
- 영세·중소 우대수수료(2026-08-14 적용): 연매출 3억 이하 영세, 30억 이하 중소; 신용 0.4%~1.45%, 체크 0.15%~1.15%; PG 하위가맹점 199.9만 곳 포함. 신규 사업자는 "일반" 등급으로 시작, 반기마다 국세청 명단으로 자동 반영·**환급은 신규 사업자 1회** — [금융위 86274](https://fsc.go.kr/no010101/86274?curPage=4); [토스페이먼츠 블로그](https://www.tosspayments.com/blog/articles/53691)
- **포트원**: 토스페이먼츠 연관리비 11만원 언급, "포트원 패키지로 가입하면 평균 22만원 가입비 면제" (포트원 자사 주장) — [포트원 블로그 2026 PG 비교](https://blog.portone.io/opi_pg-comparison2026/)
- **Stripe KR**: "한국에 법인을 두면 Stripe 계정 자체가 안 열린다 … 대부분의 한국 SaaS 창업자들은 해외 법인(델라웨어 C-Corp·싱가포르)을 만들어 Stripe를 씀" — [브런치 @chunja07](https://brunch.co.kr/@chunja07/196); 크몽 "Stripe는 현재 한국에서 직접 계정 생성이 제한적" — [크몽](https://kmong.com/gig/749461). 반대 주장(zenind 2026-04 "fully supported")은 근거 불명 — [zenind](https://www.zenind.com/help/post/how-to-open-and-manage-a-stripe-account-in-south-korea). Stripe 공식 문서는 한국 로컬 결제수단(PAYCO·Samsung Pay)만 — [docs.stripe.com/payments/payco](https://docs.stripe.com/payments/payco)
- **Apple 한국 제3자 결제(2022-06)**: 한국 전용 바이너리 + StoreKit External Purchase Entitlement 신청, 월별 매출 보고, **수수료 26%**(통상 30% 대비 -4%p), 승인 PG = KCP·Inicis·Toss·NICE, Ask to Buy·가족 공유 불가 — [CNBC 2022-06-30](https://www.cnbc.com/2022/06/30/apple-opens-up-third-party-app-payments-in-korea-will-take-26percent-cut-.html); [MacStories](https://www.macstories.net/linked/app-developers-can-apply-to-use-third-party-payment-processors-in-south-korea-with-limitations/)
- **Google 한국**: 제3자 결제 허용하되 최대 26% + 아웃링크 금지; 업계는 콘텐츠 가격 15~20% 인상; "PG·카드 수수료 감안하면 오히려 30% 이상" 지적. 방통위 2023-10 과징금 계획(구글 475억·애플 205억)이 2024-05 까지 미확정 — [아주경제 2024-05-28](https://www.ajunews.com/view/20240528141755313). 2026-03 여야 전기통신사업법 보완 개정안 발의 보도 — [비즈워치 2026-03-24](https://news.bizwatch.co.kr/article/mobile/2026/03/24/0043)
- **Apple 가이드라인 원문**: 3.1.1 "If you want to unlock features or functionality within your app (… subscriptions …), you must use in-app purchase." 3.1.1(a) 미국 외 스토어프론트는 외부 결제 유도 버튼·링크 금지. 3.1.3(b) Multiplatform: "may allow users to access content, subscriptions, or features they have acquired … on other platforms or your web site, … provided those items are also available as in-app purchases within the app." 4.2 "beyond a repackaged website", 4.2.7(e) "Thin clients for cloud-based apps are not appropriate". 서문: "we provide Safari for a great web experience too." **PWA 라는 단어는 없음** — [developer.apple.com 가이드라인](https://developer.apple.com/app-store/review/guidelines/)

### Inferences
- PWA(앱스토어 미배포)는 Apple·Google 가이드라인·수수료 체계의 **적용 대상 자체가 아니다**. 가이드라인이 PWA 를 명시하지 않는 것은 "예외 조항"이 있어서가 아니라 스토어 밖이기 때문이다. 다만 나중에 네이티브 래퍼를 올리면 3.1.1 이 즉시 적용되고(구독은 IAP 의무), 웹에서 결제한 유저는 3.1.3(b) 로 접근만 허용된다.
- 한국에서 월 구독 과금의 현실적 경로 = 국내 PG 빌링(토스페이먼츠/포트원 경유) + 통신판매업 신고 + 사업자 등록. 초기 고정비 ≈ 가입비 22만원(포트원 경유 시 면제 주장) + 연 11만원 + 등록면허세 2~4만원. 변동비 = 일반 3.4% → 영세 0.4~1.45%(반기 후 환급).
- PivoxQuant 의 Stripe 통합(현재 `BUSINESS_REGISTRATION_PENDING` 503 게이트)은 **한국 법인/개인사업자로는 계정 개설이 막힐 가능성이 높다**는 공개 증언이 다수다 → 국내 PG 로의 교체 또는 해외 법인이 전제. 이는 코드보다 법인 구조 결정이 먼저인 사안.

### Gaps
- 토스페이먼츠 **빌링(정기결제) 전용 요율**과 포트원 자체 플랫폼 요금은 공개 페이지에서 확인 못 함.
- Stripe 의 **공식** 한국 사업자 지원 여부 문서 미확인 — 블로그·커뮤니티 증언뿐.
- Apple·Google 의 한국 외부결제 수수료가 **2025~2026 에 변경됐는지** 확인 못 함(검색 결과 전부 2022 기준). 방통위 과징금 최종 확정 여부 미확인.

---

## KQ6. 1인 창업 핀테크의 전형적 월 비용 구조 (인프라·데이터·인증·법무)

### Takeaway
"핀테크 1인 개발자가 월 운영비를 공개한" 국내 사례는 **찾지 못했다**. 확인 가능한 것은 플랫폼 공식 가격(Vercel Pro $20/seat, Supabase Pro $25+컴퓨트, Render 요금표는 열람 실패)과 국내 결제·신고 고정비(KQ5)뿐이며, 이것으로 조립한 최소 구조는 **월 $45~60 + 결제 수수료 + 법무 0원(공공 자문)** 수준이다. 시세 데이터는 무료·재배포 가능한 소스가 없다는 리포 내부 판정(2026-09-19)이 있다.

### Cited Findings
- **Vercel**: Hobby $0 — "Our Hobby plan is for personal, non-commercial use", 추가 사용량 구매 불가; Pro **$20/월 per developer seat**, Fast Data Transfer 1TB 포함 후 $0.15/GB, Origin Transfer $0.06/GB — [vercel.com/pricing](https://vercel.com/pricing)
- **Supabase**: Pro **$25/월/organization**, 컴퓨트 별도(월 $10 크레딧 포함, Micro 1개 커버). 예시 "Pro org with 2 projects on Micro = $25 + $10 + $10 − $10 = $35/월". Team $599/월 — [supabase.com/pricing](https://supabase.com/pricing); [schematichq 해설](https://schematichq.com/blog/supabase-pricing)
- Vercel Pro + Supabase Pro 진입가 합 ≈ **월 $45** + 사용량 — [jetadmin 2026-09](https://www.jetadmin.io/blog/vercel-vs-supabase/)
- **Render**: 요금표 본문이 동적 로드라 열람 실패(페이지에 "Deploy websites for free, forever", 마이그레이션 크레딧 최대 $10K 문구만) — [render.com/pricing](https://render.com/pricing)
- **PG 고정비**: 토스페이먼츠 가입비 22만원 + 연 11만원 (KQ5) — [tosspayments.com/about/fee](https://www.tosspayments.com/about/fee)
- **통신판매업 등록면허세**: 12,000~40,500원/년 (KQ5) — [hometax-go](https://hometax-go.kr/mailorder-costs/)
- **법무**: K-Startup 법률 자문 무료(2026 상시), 핀테크지원센터 컨설팅 무료 (KQ3)
- **마이데이터 경로 비용**: 최소 자본금 5억원, 해킹 방지·망분리 보안설비, 100만명 이상 시 금융보안원 관제 가입, 클라우드 전산설비 허용 — [금융위 74324](https://fsc.go.kr/no010101/74324?curPage=77); [GeekNews 요약](https://news.hada.io/topic?id=2074)
- **시세 데이터**: 리포 내부 — "무료·재배포 가능한 종가 소스는 국내·미국 모두 없다(2026-09-19 약관 실측)", FMP §2.2.2 Data Display Agreement 미체결로 벤더 시세 유저 표시 기본 꺼짐 — `/home/user/pivoxquant/CLAUDE.md` 「기술 스택 Data」, `/home/user/pivoxquant/docs/legal/R7_kis_market_data_options_2026-06-09.md`
- 참고(해외): Sharesight 창업 초기 외주 견적 **$50k~$500k** — [Sharesight 블로그](https://www.sharesight.com/blog/qa-with-sharesight-co-founder-and-cto-scott-ryburn-on-10-years-of-sharesight)

### Inferences
- 조립 추정(출처 수치만 합산, 사용량·VAT 제외): Vercel Pro $20 + Supabase Pro $25(+Micro 컴퓨트 포함) + Render(미확인) ≈ **$45~60/월** 인프라. 결제 켜면 초기 22만원 + 연 11만원 + 등록면허세. 법무는 공공 자문으로 0원 가능하나 **의견서 수준**은 유료 변호사 필요(가격 자료 없음).
- 비용 구조에서 가장 큰 변수는 **데이터**다. 시세 표시(Data Display Agreement)나 계좌 연동(마이데이터 5억 자본금)은 1인 창업 규모를 벗어난다. "시세 미표시 + 유저 직접 입력/캡처"는 비용 회피 설계로 합리적이지만, KQ4 의 모든 경쟁 제품이 시세를 보여준다는 점에서 제품 경쟁력 비용을 치른다.

### Gaps
- **국내 핀테크 1인 개발자의 실제 월 비용 공개 사례 없음.** 해외 인디해커 사례도 핀테크 특화로는 못 찾음.
- Render 공식 요금표, 본인확인(PASS/휴대폰 인증) 단가, Google/Kakao OAuth 비용(일반적으로 무료이나 공식 확인 안 함), 법무 의견서 시장가 — 미확인.

---

## KQ7. PivoxQuant 스택 vs 업계 표준 — 벗어난 점과 위험/이점

### Takeaway
PivoxQuant(Flask+SQLAlchemy / Supabase Postgres 서울 / Next.js 16 + Vercel / Render 백엔드 / PWA / Google·Kakao OAuth / 시세 미표시 / AI 기본 꺼짐)는 국내 대형(JVM+K8s+AWS)과는 완전히 다르고, 해외 1~8인 팀 사례(Rails/Ember+Cordova, AWS)와는 "매니지드 PaaS 위의 모놀리스"라는 점에서 같은 계열이다. 비표준인 점은 ① 네이티브 앱 없음(PWA) ② 시세 미표시 ③ 브로커 자동 연동 없음 ④ 백엔드·DB·프론트가 3개 벤더에 분산 — 이 중 ①②③은 **규제·비용 회피의 대가로 제품 비교 열위**를 감수하는 선택이다.

### Cited Findings (비교 근거는 KQ4·KQ5·KQ6 의 출처를 그대로 사용)
- 국내 대형 공통: Kotlin/Java+Spring, Kubernetes, MySQL(+MongoDB/DynamoDB), AWS(카카오페이증권·뱅크샐러드) — [토스](https://toss.im/career/job-detail?gh_jid=4168349003), [카카오페이증권](https://career.rememberapp.co.kr/job/posting/282605), [뱅크샐러드](https://career.rememberapp.co.kr/job/posting/297517)
- 국내 직접 경쟁 둘 다 iOS 네이티브 + 광고/인앱 — [살래말래](https://apps.apple.com/kr/app/id6755510192?l=ko), [도미노](https://apps.apple.com/kr/app/id1540576519)
- 해외 소규모: Sharesight = 웹앱(Ember)+Cordova 래핑, AWS, Aurora, 개발팀 8명 — [Sharesight](https://www.sharesight.com/blog/qa-with-sharesight-co-founder-and-cto-scott-ryburn-on-10-years-of-sharesight); Tradervue = 1인 운영 10만+ — [tech.mn](https://tech.mn/news/2021/03/30/sureswift-capital-acquires-tradervue)
- Apple 3.1.1 구독 IAP 의무·3.1.3(b) 멀티플랫폼 조항 — [Apple](https://developer.apple.com/app-store/review/guidelines/); 한국 제3자 결제도 26% — [CNBC](https://www.cnbc.com/2022/06/30/apple-opens-up-third-party-app-payments-in-korea-will-take-26percent-cut-.html)
- Stripe 한국 법인 가입 제한 증언 — [브런치](https://brunch.co.kr/@chunja07/196)
- 리포 내부 사실: 시세 표시 플래그 기본 꺼짐(`MARKET_DATA_DISPLAY_ENABLED`), AI 는 캡처·체결 문자 판독만·기본 꺼짐(`AI_READ_ENABLED`), 브로커 연동 `BROKER_LINKING_AVAILABLE=false`, `SESSION_COOKIE_DOMAIN` 비움(host-only), legal_filter 단일 방어선 — `/home/user/pivoxquant/CLAUDE.md`, `/home/user/pivoxquant/services/legal_filter.py`

### Inferences (항목별 위험/이점)
| 항목 | 업계 표준 | PivoxQuant | 이점 | 위험 |
|---|---|---|---|---|
| 배포 형태 | 네이티브 iOS/Android (살래말래·도미노·Delta) | PWA | 앱스토어 IAP·26% 수수료·심사 회피, 웹 PG 직결 가능 | 한국 유저 획득 채널(앱스토어 검색·푸시 신뢰도) 열위, iOS 푸시·홈화면 설치 마찰 |
| 시세 | 전부 표시 | 기본 미표시(취득가 기준) | Data Display Agreement·R7 리스크 0, 데이터 비용 0 | 포트폴리오 화면의 체감 가치 하락, 경쟁 제품 대비 "덜 완성" 인상 |
| 계좌 연동 | 도미노(마이데이터 신청), 해외는 브로커 CSV/API | 수동 입력 + 캡처 판독(AI 옵션) | 마이데이터(5억 자본금·보안설비) 불필요, KIS read-only 만 | 입력 마찰 → "한국 개인투자자가 기록을 하긴 하는가" 질문에 불리한 편향 |
| 백엔드 | JVM+K8s(대형) / Rails·Node 모놀리스(소형) | Flask 모놀리스 on Render | 1인 유지 가능, 테스트 스위트 보유 | Render·Vercel·Supabase 3벤더 분산 = 장애 지점 3개, 리전 불일치(Supabase 서울 vs Render 리전 미확인) → 레이턴시·데이터 국외 이전 설명 부담 |
| DB | MySQL/Aurora/DynamoDB | Supabase Postgres(서울, session pooler) | 국내 리전으로 PIPA 국외 이전 설명 단순 | pooler 필수·롤 분리 등 운영 함정(CLAUDE.md 기록) |
| 결제 | 국내 PG(토스/포트원) 또는 IAP | Stripe(게이트) | 코드 완성도 | **한국 법인으로 Stripe 개설 불가 중론** → PG 교체 또는 해외 법인 필요 |
| AI | 경쟁 제품 대부분 AI 기능 마케팅(TradesViz 등) | 추출 전용·기본 꺼짐 | §101 "조언" 리스크·국외 이전 고지 최소화 | 차별화 포인트 포기 |
| 법률 스크럽 | 공개 사례 없음 | 정규식 42패턴 + 데코레이터 + 테스트 7종 | 재현 가능한 방어선 | 단일 방어선·정규식 한계, 외부 검증(변호사) 없음 |

- 종합: PivoxQuant 의 비표준 선택들은 서로 **같은 방향**(규제 표면 최소화·데이터 비용 0·1인 운영)을 향하고 있어 일관성은 있다. 대가는 "제품 비교 열위"로 한 곳에 모이며, 그 열위가 치명적인지는 KQ4 경쟁 제품이 아니라 CLAUDE.md 가 던진 질문("기록을 하긴 하는가")의 답에 달려 있다.

### Gaps
- Render 백엔드 리전(싱가포르/오레곤 등)과 Supabase 서울 간 실제 레이턴시는 리포 문서에서 확인하지 못했다(측정 필요).
- 경쟁 제품들의 **법적 스크럽·면책 구현**은 전부 비공개라 PivoxQuant 방어선의 상대적 수준은 평가 불가.
