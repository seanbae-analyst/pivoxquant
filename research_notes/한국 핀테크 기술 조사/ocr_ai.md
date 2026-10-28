# OCR·AI·LLM 기술이 개인투자자용 기록·자산관리 앱에서 쓰이는 방식 (2026-10-28 조사)

> 조사 시각: 2026-10-28. 가격은 각 벤더 공식 페이지에서 조사 당일 읽은 값이며 통화·단위를 그대로 적었다. 환율 환산은 하지 않았다(필요 시 1 USD ≈ 1,400 KRW 가정이라고 명시해 쓸 것).
> 참고 — 이 저장소의 현재 구현: 브라우저 Tesseract.js(`frontend/package.json`: `tesseract.js ^6.0.1`, `@tesseract.js-data/kor`) → `lib/fill-ocr/mask.ts` 로 계좌·식별 줄 제거 → 텍스트만 서버로 → `services/ai_read.py` 가 `claude-opus-5-5` 에 **텍스트**(이미지 아님)를 보내 추출 JSON 을 받고, 읽었다는 숫자가 원문에 없으면 버린다. 기본 꺼짐(`AI_READ_ENABLED`). 아래 비용 모델은 이 구조(이미지 미전송)와 "이미지를 직접 LLM 에 보내는 구조" 둘 다 계산했다.

---

## KQ1. OCR 선택지 — 브라우저 내 OCR / 클라우드 OCR / LLM 비전 (한국어 정확도·건당 비용·국외이전·레이아웃 변화 대응)

### Takeaway
공식 건당 단가가 공개된 것은 Upstage(페이지당 $0.01/$0.03), Google Document AI(1,000페이지당 $1.50), AWS Textract(페이지당 $0.0015~$0.07)이고, Naver CLOVA OCR 은 "종량제·콘솔에서 확인"이라 공개 페이지에서 원화 단가를 읽을 수 없었다. LLM 비전은 토큰 과금이라 스크린샷 1장이 Haiku 5.5 기준 약 $0.0002, Opus 5.5 기준 약 $0.01~0.02 수준으로 떨어진다(계산 근거는 KQ5). 온디바이스 선택지 중 한국어가 공식 지원되는 것은 Android ML Kit v2(한국어 스크립트 명시)와 Tesseract(kor traineddata)이며, Apple Vision 은 초기 리비전에선 한국어 미지원이었고 iOS 18.1 에서 한국어가 지원 목록에 올랐다는 개발자 보고가 있다. 한국어 전용 헤드투헤드 벤치마크는 공개 자료로 찾지 못했다.

### Cited Findings

**클라우드 OCR 가격(공식)**
- Upstage Document Parse: Standard **$0.01/페이지**, Enhanced **$0.03/페이지** (Enhanced 는 표·차트·체크박스 등 시각 요소가 많은 문서용) — [Upstage pricing](https://upstage.ai/pricing); [AWS Marketplace 설명](https://aws.amazon.com/marketplace/pp/prodview-lv5bnpdco7xoq). 월 100페이지 무료 티어는 서드파티 디렉터리에만 있고 공식 페이지에서 확인 못 함 — [devtoollab](https://devtoollab.com/ai-tools/upstage-ai) (미검증).
- Google Document AI Enterprise Document OCR: **$1.50 / 1,000페이지**(월 1~500만 페이지), OCR 애드온 $6 / 1,000페이지, 커스텀 프로세서 호스팅 시간당 $0.05 — [Google Cloud Document AI pricing](https://cloud.google.com/document-ai/pricing). 500만 페이지 초과 $0.60/1,000페이지·월 1,000건 무료는 2차 자료만 — [lido.app](https://www.lido.app/blog/google-ocr-options-explained) (미검증).
- AWS Textract(US West 오리건 기준): Detect Document Text **$0.0015/페이지**(첫 100만), 이후 $0.0006; Analyze Document Tables $0.015, Forms $0.05, Queries $0.015, Forms+Tables+Queries $0.070/페이지; 무료 티어 3개월(Detect 1,000페이지/월). **서울 리전 단가는 페이지에 없고, 한국어 지원 언급도 없음** — [AWS Textract pricing](https://aws.amazon.com/textract/pricing/).
- Naver CLOVA OCR: 종량제이며 "정확한 기준은 포털 > AI Services > CLOVA OCR 요금 안내 참조". General OCR·Free 플랜은 호출 없으면 유지비 0, 그 외 Template 플랜은 이용량 없어도 월 요금 청구. Template OCR 1회 호출 = 인식 영역 최대 50개(130개면 3회로 과금). 대량 기준: General 월 100만 건, Template 월 5만 건 이상이면 별도 문의 — [CLOVA OCR FAQ](https://guide.ncloud-docs.com/docs/en/clovaocr-faq); [CLOVA OCR 개요](https://guide.ncloud-docs.com/release-20260917/docs/en/clovaocr-overview). 공개 제품 페이지의 요금표 셀은 "- / 건"으로 비어 있었음 — [ncloud OCR 제품 페이지](https://www.ncloud.com/product/aiService/ocr), [gov-ncloud](https://gov-ncloud.com/product/aiService/ocr) (두 페이지 모두 요금 수치 미표시, 2026-10-28 확인). 2026-04-23 FAQ 갱신은 General OCR 줄바꿈 판단 기준 변경이며 요금 변경 아님 — [CLOVA OCR Release Notes](https://api.ncloud-docs.com/docs/en/ai-application-service-ocr-releasenote).

**LLM 비전 가격(공식)**
- Anthropic Claude(USD/백만 토큰, 기본 입력/출력): Haiku 5.5 **$0.10 / $0.50**(프롬프트 10만 토큰 이하; 초과 시 $0.50/$2.50), Sonnet 5.5 **$2 / $10**, Opus 5.5 **$4 / $20**. Batch API 는 입·출력 50% 할인(Haiku 5.5 $0.05/$0.25, Opus 5.5 $2/$10). `inference_geo` 로 미국 전용 추론을 지정하면 1.1배 — [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- Claude 이미지 토큰: 28×28 픽셀 패치당 1 비주얼 토큰, 즉 `⌈w/28⌉×⌈h/28⌉`. 1000×1000 = 1,296 토큰; 1920×1080 은 표준 티어에서 1456×819 로 축소돼 1,560 토큰, 고해상 티어에선 축소 없이 2,691 토큰. 요청당 최대 600장(200k 컨텍스트 모델은 100장), 20장 초과 시 장당 2000px 제한. 공식 예시: Opus 5.5 고해상 티어에서 1000×1000 이미지 1,000장 ≈ $5.18, 4K 이미지 1,000장 ≈ $19.14. "200px 미만·저화질·회전 이미지에서 환각/오류 가능" — [Claude Vision](https://platform.claude.com/docs/en/build-with-claude/vision).
- Google Gemini(USD/백만 토큰): 2.5 Flash-Lite 입력 $0.10(텍스트·이미지·비디오)/출력 $0.40, 2.5 Flash $0.30/$2.50, 3.1 Flash-Lite $0.25/$1.50, 3.8 Flash $0.75/$3.75(2026-12-31까지, 2027-01-01부터 $1.50/$7.50). **무료 티어 콘텐츠는 "제품 개선에 사용됨: Yes", 유료 티어는 대부분 No** — [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing). 이미지 입력 토큰 산정 규칙은 가격 페이지에 Flash 계열 기준으로 적혀 있지 않음.
- OpenAI GPT-5 계열 이미지 입력 단가: 공식 페이지에서 확인 못 함(검색 결과는 텍스트 단가·집계 사이트뿐) — Gap.

**온디바이스/브라우저 OCR**
- Tesseract.js: Tesseract 의 WebAssembly 포트로 브라우저·Node 에서 동작, 최신 v7(Node 16+). "인식 모델을 수정해 정확도를 높이지 않는다", PDF 미지원, v6 에서 메모리 누수 수정·런타임 감소. 한국어 traineddata 크기는 README 에 없음. 정확도 향상·PDF 가 필요하면 Scribe.js 를 권함 — [tesseract.js GitHub](https://github.com/naptha/tesseract.js).
- 한국어 블로그 노트: "클라우드 모델이 Tesseract 보다 일반적으로 정확하지만 비용·프라이버시 트레이드오프가 있고, 한국어는 영어보다 정확도 낮은 구간이 많아 도메인 사전이 도움된다" — [codingstairs 노트](https://codingstairs.duckdns.org/en/notes/frontend/12-ocr-stt-tts) (비공식 블로그, 벤치마크 아님).
- Android/iOS ML Kit Text Recognition v2: "중국어·데바나가리·일본어·**한국어**·라틴 스크립트 인식 지원", Android·iOS 가이드 별도. 온디바이스 여부·모델 크기·bundled/unbundled 는 해당 페이지에 명시 없음 — [ML Kit Text Recognition v2](https://developers.google.com/ml-kit/vision/text-recognition/v2).
- Apple Vision `VNRecognizeTextRequest`: Apple DTS 엔지니어가 인용한 헤더 주석 기준 Revision1 은 영어만, Revision2 는 영어·중국어·포르투갈어·프랑스어·이탈리아어·독일어·스페인어 — **한국어 없음**, `supportedRecognitionLanguagesForTextRecognitionLevel` 로 런타임 확인 권고 — [Apple Developer Forums 684807](https://developer.apple.com/forums/thread/684807). 이후 스레드에서 한 개발자가 iOS 18.1 에서 한국어·중국어가 지원 목록에 있다고 보고 — [Apple Developer Forums 765905](https://developer.apple.com/forums/thread/765905). (Apple 공식 문서의 한국어 추가 iOS 버전은 확인 못 함.)
- Apple Vision 플러그인 README: "Tesseract 등 다른 온디바이스 엔진 대비 정확도·속도 우수" — [OCRmyPDF-AppleOCR](https://github.com/mkyt/OCRmyPDF-AppleOCR) (영어 중심, 한국어 언급 없음).
- ML Kit vs Tesseract(iOS, 2019 자료): 959장 테스트에서 Tesseract 가 더 빠르고, ML Kit 는 Tesseract 가 실패한 이미지에서 더 정확 — [fritz.ai 비교](https://fritz.ai/comparing-ml-kits-text-recognition-api-on-android-ios/) (오래됨, 한국어 분리 없음).

**스크린샷 레이아웃 변화 대응**
- "깨끗한 디지털 스크린샷은 사진보다 인식률이 높다(앱 대시보드·결제 확인 화면에서 거의 99%)". 기본 OCR 은 글자 위치만 알고 의미를 모르며, 압축 이미지에서 숫자·소수점 오독이 잦다. 앱마다 같은 정보가 다른 위치에 있어 고정 좌표 추출은 깨지기 쉬우므로 **필드명(라벨) 기준 추출**을 권장 — [imagetotable 블로그](https://imagetotable.ai/ko/blog/extract-data-from-screenshots-to-excel); [imagetotable: OCR 이 스크린샷을 읽을 수 있나](https://imagetotable.ai/ko/blog/can-ocr-read-screenshots) (벤더 블로그, 수치는 자사 주장).
- 국내 회계앱 '얼마에요'는 영수증 촬영 → OCR+AI 로 금액·날짜·거래처·항목 추출 후 자동 등록 — [iQuest 블로그](https://blog.iquest.co.kr/entry/%EA%B8%B0%EB%8A%A5%EC%97%85%EB%8D%B0%EC%9D%B4%ED%8A%B8-5) (영수증 사례, 증권 캡처 아님).

### Inferences
- 증권사 앱 캡처는 "깨끗한 디지털 스크린샷"이라 OCR 자체의 문자 인식률보다 **표 구조(행 묶기)와 숫자 열 정렬**이 병목일 가능성이 크다. 이 저장소의 `parse-holdings.ts`/`ai_read.py` 가 "관계식 검증(수량×단가=금액)"을 두는 이유와 일치한다.
- 비용만 보면 LLM 비전(Haiku 5.5·Gemini Flash-Lite)이 전통 클라우드 OCR(Upstage $0.01/페이지)보다 **장당 수십 배 싸다**. 전통 OCR 의 남은 장점은 (a) 토큰 과금이 아닌 예측 가능한 단가, (b) 국내 벤더(Naver·Upstage)로 국외이전 쟁점을 피할 가능성 — 단 둘 다 데이터 처리 위치·학습 미사용 약정은 공식 페이지에서 확인 못 했다(KQ4 Gaps).
- iOS 웹앱(현재 Next.js PWA)에서는 Apple Vision 을 직접 쓸 수 없으므로 브라우저 OCR 은 사실상 Tesseract.js(또는 Scribe.js) 뿐이다. 네이티브 래퍼(Capacitor 등)를 쓰면 ML Kit(Android)·Vision(iOS 18.1+)이 열린다.

### Gaps
- CLOVA OCR General/Document OCR 의 **원화 건당 단가**: 공개 페이지 3곳에서 수치 미표시(콘솔 로그인 필요). 
- 한국어 OCR 헤드투헤드 벤치마크(Tesseract kor vs ML Kit vs Vision vs CLOVA vs LLM): 공개 자료 없음. 증권사 캡처 샘플로 자체 측정 필요.
- PaddleOCR 웹(WASM) 배포판의 한국어 지원·성능: 조사 범위 내 자료 없음.
- OpenAI 이미지 입력 공식 단가: 미확인.
- Apple 공식 문서에서 한국어가 Vision 에 추가된 정확한 iOS/revision 번호.

---

## KQ2. 한국·해외 앱 사례 — 거래를 어떤 기술로 가져오는가 (키움 자동일지, 토스/카카오페이, 살래말래, 도미노, 해외 저널)

### Takeaway
국내에서 "자동 기록"이 확인된 것은 증권사 자체 서비스(키움 2013년 '자동투자일지' — 계좌 연동)뿐이고, 독립 매매일지 앱(살래말래·Trady·고독한 투자자·거래 노트·투자일기)은 모두 **수동 입력**이다. 캡처 OCR 이나 체결 문자 파싱으로 가져오는 국내 앱은 조사에서 확인되지 않았다. 해외 저널(TradesViz·Tradervue·Edgewonk·TradeZella)은 **브로커 CSV 업로드 + 브로커 API 자동 동기화**가 표준이고, TradesViz 는 미지원 포맷을 ChatGPT/Gemini 로 변환하라는 "Convert it with AI" 경로를 두며, 소규모 iOS 앱들(Trading Journal Pro·TraderCater·Traders Diary)이 "스크린샷 OCR/AI 추출"을 내세운다.

### Cited Findings

**국내**
- 키움증권 '오픈스탁'(2013-05): 온라인 매매일지 '자동투자일지' — 키움 계좌와 연결해 매매하면 종목별 매매내역·잔고현황이 일자별 차트·표로 자동 기록 — [아주경제 2013-05-14](https://www.ajunews.com/view/20130514000364). 현재 제공 여부는 확인 못 함.
- 키움 HTS 영웅문4 화면 1300 '영웅결정전 TOP10 자동일지차트'(2023): 실전투자대회 상위 10명의 매매 열람 기능이며 본인 매매 기록 기능이 아님 — [뉴스토마토](https://newstomato.com/ReadNews.aspx?no=1207773).
- 키움 REST API(2025-03 출시, 2025-08 이벤트 시즌2): 계좌 평가잔고 조회 등 지원 — [헤럴드경제 2025-08-24](https://www.heraldk.com/article/2025082416580704490). 영웅문S# 간편모드(2025-10, 누적 170만) 기사에 매매일지 기능 언급 없음 — [한국경제 2026-08-19](https://www.hankyung.com/article/202608198512P).
- 토스증권 오픈API 정식 출시(2026-08-13 보도): 종목 정보·본인 계좌 정보 조회·일반/조건 주문·실시간 시세 제공, **LLM 연동 지원**으로 개발 경험 없는 투자자까지 이용 범위 확대 — [이코노미스트](https://economist.co.kr/article/view/ecn202608130015). 토스증권의 매매일지 기능 출시 보도는 찾지 못함.
- 살래말래(iOS, 주식 매매일지 & 커뮤니티): 종목명·매수가·수량·매수금액 **직접 입력**, 매매 이유·메모 기록, 같은 종목 반복 매매를 한 흐름으로 묶음, 일지 일부 선택 공개로 피드백 — [App Store](https://apps.apple.com/kr/app/%EC%82%B4%EB%9E%98%EB%A7%90%EB%9E%98-%EC%A3%BC%EC%8B%9D-%EB%A7%A4%EB%A7%A4%EC%9D%BC%EC%A7%80-%EC%BB%A4%EB%AE%A4%EB%8B%88%ED%8B%B0/id6755510192?l=en-GB). (동명의 쇼핑앱 '살래말래' 와 혼동 주의.)
- 고독한 투자자(iOS): 계좌·종목코드·단가·수량 직접 입력, "기록은 기기 밖으로 나가지 않으며 현재가 조회 외 인터넷 통신 없음, 회원가입·로그인 불필요" — [App Store](https://apps.apple.com/kr/app/%EA%B3%A0%EB%8F%85%ED%95%9C-%ED%88%AC%EC%9E%90%EC%9E%90/id6448638906?l=en-GB) (검색 스니펫 기준; 페이지 직접 fetch 는 404).
- Trady(국내주식 매매일지): 관심기업 등록 후 매매내역 직접 작성, 문자/알림 읽기 기능 언급 없음 — [App Store](https://apps.apple.com/ch/app/trady-%EA%B5%AD%EB%82%B4%EC%A3%BC%EC%8B%9D-%EB%A7%A4%EB%A7%A4%EC%9D%BC%EC%A7%80/id6443574203?l=en-GB). 거래 노트·투자일기도 수동 입력 — [거래 노트](https://apps.apple.com/kr/app/%EA%B1%B0%EB%9E%98-%EB%85%B8%ED%8A%B8-fx-%EC%A3%BC%EC%8B%9D-%EA%B0%84%ED%8E%B8-%EC%86%90%EC%9D%B5-%EA%B8%B0%EB%A1%9D/id6468945018), [투자일기](https://apps.apple.com/hn/app/%ED%88%AC%EC%9E%90%EC%9D%BC%EA%B8%B0/id6749032183).

**해외**
- TradesViz: 80개 이상 브로커 포맷 + 커스텀 2종 지원; 미지원 포맷은 "Convert it with AI" 로 ChatGPT/Gemini 변환 후 Custom 포맷으로 업로드 — [TradesViz FAQ](https://www.tradesviz.com/product-faq/); [Importing trades 가이드](https://www.tradesviz.com/blog/importing-trades/). Edgewonk 내보내기 파일 업로드 또는 auto-sync — [TradesViz/Edgewonk](https://www.tradesviz.com/brokers/Edgewonk).
- Tradervue: Standard Import(CSV/Excel 업로드) vs Broker Sync(브로커에서 매일 또는 실시간 직접 수집) 두 경로 — [Tradervue Help](https://help.tradervue.com/article/4626-broker-sync-vs-standar-import).
- Edgewonk: Broker Import 탭에서 내보낸 파일 선택, 미지원 브로커는 Excel 일괄 입력 — [Edgewonk import](https://edgewonk.com/import?hsLang=en).
- TradeZella(자사 블로그): 500개 이상 브로커·플랫폼 연결, 자동 동기화 — [TradeZella blog](https://tradezella.com/blog/best-trading-journal-software) (자사 주장).
- 스크린샷 OCR 표방 소규모 앱: Trading Journal Pro(iOS) "OCR 스크린샷 가져오기" — [mwm.ai](https://mwm.ai/apps/trading-journal-pro/6781800832); TraderCater "어떤 브로커든 스크린샷 또는 CSV, AI 가 자동 추출" — [huntscreens](https://huntscreens.com/products/tradercater); Traders Diary "AI 가 거래 정보를 자동 감지해 원탭 기록" — [mwm.ai](https://mwm.ai/apps/traders-dairy-pnl-tracker/6769652253); TradeHelp "로컬 우선 저널 + 오프라인 AI 코치, 화면 녹화로 자동 저널링" — [peerpush](https://peerpush.com/p/tradehelp).
- 세 주요 저널(TradesViz·Edgewonk·Tradervue) 문서 어디에도 스크린샷 OCR 가져오기 언급 없음(위 각 문서 확인).

### Inferences
- 해외 저널의 "AI 활용"은 **포맷 변환(CSV 정규화)** 에 머물고, 이미지 OCR 은 소형 앱의 차별화 포인트로 쓰인다. 국내는 공식 Open API(키움 REST, 토스 오픈API)가 열리면서 "계좌 연동" 경로가 다시 현실적이 되고 있으나, 이 저장소는 `BROKER_LINKING_AVAILABLE=false` 로 유저 연동을 막아두었다(CLAUDE.md) — OCR/문자 경로는 그 공백을 메우는 위치다.
- 국내 독립 매매일지 앱 가운데 "기기 밖으로 안 나간다"를 전면에 내세운 사례(고독한 투자자)가 있어, 온디바이스 처리는 국내 사용자에게도 통하는 메시지다.

### Gaps
- '도미노' 투자 기록 앱: 검색 결과가 전부 Domino's Pizza 주가 기사. 서비스 정체 미확인 — 이름이 정확한지 재확인 필요.
- 카카오페이증권의 '기록' 기능: 확인된 것은 2026년 초 AI 서비스센터 신설·AI 전략(TF 보도)뿐, 매매일지 기능 자체는 미확인 — [더팩트](https://news.tf.co.kr/read/economy/2217584.htm).
- 인베스팅닷컴·시킹알파의 저널 기능: 조사 범위 내 결과 없음.
- 키움 '자동투자일지'의 2026년 현재 존속 여부.

---

## KQ3. 체결 문자·앱 푸시 파싱 — 포맷 규칙성, 포워딩 사례, 정규식 vs LLM

### Takeaway
국내 증권사 체결 문자 포맷을 정리한 공개 문서나 전용 파서 GitHub 저장소는 찾지 못했다(검색 4회). 기술적 경로는 Android 에선 `NotificationListenerService`(API 18+, 사용자가 설정에서 접근 권한을 켜야 함)와 MacroDroid 의 SMS 트리거+HTTP 요청, iOS 에선 단축어 정도이며, MacroDroid 로 "거래 알림을 OCR 로 읽는" 프리랜서 의뢰가 존재해 수요는 확인된다. 정규식은 포맷 변형(타임스탬프·구분자·소수점) 테스트 스위트가 필요하고, LLM 은 규칙이 없는 변형에 강하지만 검증 계층이 필수다.

### Cited Findings
- Android `NotificationListenerService`: API level 18 추가, 알림 게시/제거 시 콜백, **사용자가 설정에서 앱을 활성화하기 전엔 알림 수신 불가** — [Android Developers](https://developer.android.com/reference/android/service/notification/NotificationListenerService). Flutter 패키지(`notification_listener_service`)로 권한 확인·알림 스트림 구독 가능 — [pub.dev](https://pub.dev/packages/notification_listener_service/versions/1.0.0). 서비스 재시작 후 바인딩이 끊겨 리스너가 멈추는 문제 보고 — [Tencent Cloud 개발자 글](https://developer.cloud.tencent.com/article/2059570).
- MacroDroid: 수신 SMS/통화 트리거, 웹훅 트리거, HTTP 요청 액션 제공; 무료판은 매크로 5개 제한 — [SourceForge 설명](https://sourceforge.net/app/macrodroid-device-automation/android/); [APKMirror 릴리스 노트](https://www.apkmirror.com/apk/arlosoft/macrodroid-device-automation-2/macrodroid-device-automation-5-64-5-release/).
- "android auto trade alert macrodroid" — OCR 카테고리로 올라온 프리랜서 의뢰(거래 알림을 MacroDroid+OCR 로 자동 처리) — [freelancer.de](https://www.freelancer.de/projects/optical-character-recognition/android-auto-trade-alert-macrodroid) (의뢰 존재만 확인, 구현 내용 없음).
- 정규식 체결 데이터 정규화 경험담: 타임스탬프 형식 혼재, 구분자·소수점 표기 차이, 종목코드 변형이 주요 실패 원인이며, 변형 케이스를 한 번에 돌리는 테스트 스위트를 권장 — [dev.to](https://dev.to/orthogonalinfo/parsing-trading-data-with-regex-test-a-whole-suite-of-cases-at-once-not-one-string-45p8) (해외 브로커 API 기준).
- 범용 주문 메시지 파서 `findmyorder`(BUY/SELL 키워드 식별, 설정 파일로 키워드 추가) — [PyPI](https://pypi.org/project/findmyorder/1.4.4) (해외 채팅 시그널용, 한국 문자 포맷엔 부적합할 가능성).
- 국내 "체결 문자 자동 인식" 매매일지 앱: 검색 결과 없음(KQ2 의 앱들은 모두 수동 입력).

### Inferences
- 증권사 문자는 발신 주체가 증권사라 포맷이 안정적일 가능성이 높지만, **공개된 포맷 사전이 없으므로** 증권사별 샘플 수집이 선행돼야 한다. 이 저장소의 `services/fill_memo.py`("방금 체결" 푸시)와 `ai_read.py` 의 `fills` kind 가 이미 이 경로를 가정하고 있다.
- iOS 는 서드파티 앱이 SMS/푸시를 읽을 수 없으므로(권한 모델상), 사용자가 **단축어 공유 시트로 문자를 복사·전달**하는 수동 포워딩이 현실적 상한이다. 따라서 "기기 안에서 처리"를 지키려면 iOS 에선 공유 시트 → PWA 텍스트 입력 → 로컬 정규식 → 확인 UI 흐름이 자연스럽다.
- 정규식 1차 + LLM 2차(정규식 실패분만) 구성이 비용·검증 양쪽에서 유리하다. LLM 출력은 KQ5 의 단가대로 건당 1원 미만(Haiku)이라 비용은 문제가 아니고, 문제는 KQ4 의 국외이전 동의다.

### Gaps
- 증권사별(키움·한투·미래에셋·NH·삼성·토스·카카오페이) 체결 문자/푸시 문구 포맷: 공개 자료 없음. 직접 수집 필요.
- 국내 사용자가 MacroDroid/단축어로 체결 문자를 시트에 적재하는 공개 사례: 미발견.
- iOS 단축어로 증권사 푸시를 포워딩한 사례: 미발견.

---

## KQ4. LLM 활용과 규제 — 금융권 생성형 AI 가이드(2024–2026), AI기본법 §31, '추출·요약'의 경계, 국외이전 동의

### Takeaway
(1) 금융위는 2024-12 '금융권 생성형 AI 활용 지원방안' → 2025-12 통합 가이드라인 예고 → **2026-06-18 「금융분야 인공지능 가이드라인」 개정안 발표, 06-22 시행**(7대 원칙: 거버넌스·합법성·보조수단성·신뢰성·금융안정성·신의성실·보안성)으로 이어졌고, 이는 "모든 금융회사"의 **자율규제**다 — 비금융 핀테크 앱(투자자문업 미등록)에 직접 적용되는지는 자료상 불명확. (2) AI기본법은 2026-01-22 시행, §31 은 생성형 AI 기반 서비스임을 **사전 고지**(약관·화면 안내 가능)하고 생성물을 표시하되 "서비스 UI 안에서만 제공되는 결과물"은 결과물별 표시 면제, 1년 이상 계도기간, 사전고지 위반 과태료 3천만 원 이하. (3) 국외이전(PIPA §28-8)은 처리위탁·보관도 포함하며 별도 동의 또는 "계약 이행을 위한 처리위탁"(처리방침 공개로 갈음) 등 5개 근거 중 하나가 필요하다.

### Cited Findings

**금융권 가이드라인 타임라인**
- 2023-04 금융위 「금융분야 AI 보안 가이드라인」 제정; 2024-12 '금융권 생성형 AI 활용 지원방안' 발표, 금융보안원이 사전 기능테스트(PoC) 환경·보안대책 수립 지원 — [바이라인네트워크 2024-12-19](https://byline.network/2024/12/19-423). 2025년 금보원 계획: 'AI 보안성 검증체계'로 제3자 검증, AI 보안 가이드라인 개정 — [파이낸셜뉴스 2025-02-20](https://www.fnnews.com/news/202502201251359465).
- 2025-12-21: 금융위, 금융권 AI 플랫폼 가동·통합 AI 가이드라인 2026년 1분기 시행 예고 — [헤럴드경제](https://www.heraldk.com/article/2025122122194159237).
- 2026-06-18 금융위 '금융권 AX 현장 간담회'(권대영 부위원장)에서 「금융분야 인공지능 가이드라인」 개정안 발표, **2026-06-22 시행**. 7대 원칙 ▲거버넌스 ▲합법성 ▲보조수단성 ▲신뢰성 ▲금융안정성 ▲신의성실 ▲보안성. "AI 는 업무 보조수단, 최종 의사결정과 책임은 임직원", 긴급 정지 기능 등 안전장치, 금융소비자 이익 우선. 업종·업무 불문 AI 를 활용하는 **모든 금융회사가 준수해야 할 자율규제**이며 각사가 자원·위험수준에 따라 적용 수준 자율 결정. 시행일에 '금융분야 AI위험관리프레임워크'·'금융분야 인공지능 보안 안내서' 배포, 안내데스크 운영. 같은 날 망분리 긴급 완화·개인신용정보 동의제도·가명처리 규제 정비 예고 — [연합/다음 2026-06-18](https://v.daum.net/v/20260618150301114); [뉴데일리 2026-06-18](https://biz.newdaily.co.kr/site/data/html/2026/06/18/2026061800173.html); [세종 뉴스레터](https://shinkim.com/kor/media/newsletter/3364). 기사 범위에서 핀테크(비금융회사)·국외이전·고객 고지에 관한 언급은 없음.

**AI기본법 §31**
- 법·시행령 2026-01-22 시행. §31 은 고영향·생성형 AI 사업자에 투명성 확보 의무: (1) 생성형/고영향 AI 기반 제품·서비스임을 **이용 전 사전 고지**(계약서·약관·화면 안내·게시 등 허용), (2) 생성물 표시, (3) 딥페이크는 가시적·가청적 표시 원칙; 예외(§31④, 시행령 §23): 제품명·화면·표시로 AI 활용이 명백한 경우, 내부 업무용 — [세종 2026-02-11 뉴스레터](https://www.shinkim.com/kor/media/newsletter/3114); [법률신문](https://www.lawtimes.co.kr/news/articleView.html?idxno=215368).
- 의무 주체는 이용자에게 AI 제품·서비스를 직접 제공하는 '인공지능사업자'(개발사업자 + 타사 AI 로 서비스하는 **이용사업자** 포함, 해외 사업자 포함). **결과물이 서비스 환경(UI) 안에서만 제공되면 결과물별 표시 의무 없음 — 이용 전/중 AI 활용 사실 안내로 충분**(게임 NPC 예시). 텍스트도 다운로드·공유로 외부 유통되면 표시 대상이 될 수 있으며 메타데이터 등 기계판독 방식 또는 다운로드 시 1회 안내로 가능. 계도기간 1년 이상(사실조사·과태료 유예) — [뉴시스 2026-01-22](https://mobile.newsis.com/view/NISX20260121_0003485509).
- 제재: 표시의무 위반 시정명령, 사전고지 위반 **3천만 원 이하 과태료** — [세종](https://www.shinkim.com/kor/media/newsletter/3114); 블로그 정리(2026-08 기준): 시정명령 → 미이행 시 3천만 원 이하 과태료 — [wikidocs 블로그](https://wikidocs.net/blog/@openwiki/28121/).
- 한 뉴스레터는 "2026-07-21 개정 AI기본법·시행령 시행(생성형 AI 고지·투명성 의무 등)"을 언급 — [DKL 리걸 레이더](https://maily.so/dklnews/posts/g0zml7v7rql); 다른 로펌·언론은 모두 2026-01-22 기준이라 **상충**. 법제처 원문 확인 필요.

**'추출·요약'과 투자판단의 경계**
- 토스증권 'AI 어닝콜': 실적발표를 실시간 문자화하고 핵심 내용·실적 전망을 AI 가 분석·요약 — [헤럴드경제 2026-05-14](https://www.heraldk.com/article/2026051418383462717). 2026-10 '시장' 탭 신설·'실시간 이슈' AI 고도화, "투자자가 정보를 이해하고 투자 판단에 활용하는 과정까지 지원하는 정보 플랫폼" — [아시아경제 2026-10-14](https://core.asiae.co.kr/article/2026101409292455419).
- 업계 AI 가 'AI 투자비서'로 확산 중이라는 기사; AI 요약이 투자자문이 아니라는 점을 규제 관점에서 다룬 공식 자료는 검색에서 못 찾음 — [더팩트](https://news.tf.co.kr/read/economy/2217584.htm).

**국외이전(PIPA §28-8)**
- 국외이전에는 국외 제3자 제공(조회 포함)·**처리위탁·보관**이 모두 포함. 적법 근거 5개: 별도 동의 / 법률·조약 / 정보주체와의 계약 이행을 위한 처리위탁·보관 / 개인정보위 고시 인증(ISMS-P 등) / 국가·국제기구 동등성 인정. 동의 시 고지사항: 이전 항목, 국가·시기·방법, 이전받는 자 명칭·연락처, 이용목적·보유기간, 거부 방법·효과 — [개인정보보호위원회 국외이전 안내](https://pipc.go.kr/np/default/page.do?mCode=D060040000); [itwiki §28-8](https://itwiki.kr/w/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4_%EB%B3%B4%ED%98%B8%EB%B2%95_%EC%A0%9C28%EC%A1%B0%EC%9D%988). 처리방침에는 국외이전 근거와 §28-8② 각 호 사항을 공개해야 함(시행령 §31①) — [nepla 처리방침 작성항목](https://www.nepla.ai/wiki/it-정보-방송통신/개인정보-위치정보-신용정보/개인정보-처리방침/개인정보-처리방침의-작성-항목/개인정보보호법-제28조의8-제1항-제3호-가목-제2항에-따른-개인정보-처리방침-작성-항목-3wo9qrl0nlp4).
- 해외 클라우드 보관은 통상 '위탁'으로 보며, 정보주체와의 계약 이행을 위한 경우 별도 동의 없이 처리방침 공개로 갈음 가능 — [nepla 일문일답](https://www.nepla.ai/wiki/it-정보-방송통신/개인정보-위치정보-신용정보/-일문일답-해외-클라우드-aws-등-에서-개인정보를-보관-처리할-때-정보주체의-동의를-받아야-하는가-54gnvzpe81pr).
- Anthropic: 이전 버전 개인정보처리방침의 한국 섹션에 PIPA §28-8①(iii) 위탁 근거로 미국(Persona 등) 이전을 기재, 이용자는 국외이전 거부를 요청할 수 있으나 서비스 제한 가능 — [conductatlas 캡처](https://conductatlas.com/platform/anthropic/anthropic-privacy-policy/provision/CA-P-054392/korea-data-processor-entrusted-with-personal-data-processing/) (제3자 트래커의 구버전 캡처 — 현행 정책 재확인 필요). 국내 보안회사의 수탁자 목록에 "Anthropic PBC(Claude API), 미국, 프롬프트, ZDR 적용" 기재 — [Theori subprocessors](https://privacy.theori.io/en/subprocessors.html). 2026-06 보도: Anthropic 이 국내 규제환경에 맞춘 데이터 레지던시 옵션 검토 중(계획, 출시 아님) — [sbsstar](https://sbsstar.net/article/N1008615690/anthropic-lands-in-south-korea-amid-fallout-from-mythos-export-controls); 한화솔루션은 AWS Bedrock 경유로 리전 내 거주 요건 충족 — [eCommerceNews Asia](https://ecommercenews.asia/story/anthropic-opens-seoul-office-with-south-korea-deals).
- Claude API 의 `inference_geo` 로 미국 전용 추론 지정 가능(1.1배 과금) — 한국 리전 옵션은 가격 페이지에 없음 — [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing).
- Gemini 무료 티어는 콘텐츠를 제품 개선에 사용(Yes), 유료 티어는 대부분 미사용 — [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

### Inferences
- 이 저장소가 "텍스트만 보내고, 계좌·식별 줄을 기기와 서버에서 두 번 제거"하는 설계는 국외이전 대상 데이터를 **보유 종목·수량·금액**으로 좁히는 효과가 있다. 그래도 특정 개인의 보유내역은 개인정보로 볼 여지가 커서, 현재 코드 주석대로 "국외이전 동의 문구 + 처리방침 개정" 없이는 켤 수 없다는 판단이 자료와 부합한다. 계약 이행 위탁으로 보고 처리방침 공개로 갈음할지, 건별 동의를 받을지는 변호사 판단 영역.
- AI기본법 §31 관점에서, 추출 결과가 앱 UI 안의 '검토 표'로만 제공되고 다운로드되지 않으면 결과물별 표시 의무는 없고 **이용 전 고지(약관·기능 켜는 화면)** 만 갖추면 된다는 해석이 뉴시스 기사의 설명과 맞는다. 다만 PivoxQuant 의 '데이터 내보내기'로 AI 추출 행이 함께 나가면 "외부 유통"에 해당할 수 있다.
- 금융위 가이드라인은 금융회사 자율규제라 비금융 핀테크엔 직접 구속력이 없어 보이지만, "AI 는 보조수단·최종 판단은 사람"·"긴급 정지"·"신의성실" 원칙은 기록 앱의 '추출만' 설계가 그대로 충족한다.

### Gaps
- 2026-06 개정 가이드라인 **원문**(핀테크·전자금융업자 포함 여부, 생성형 AI 조항): 미확인(보도·로펌 요약만).
- AI기본법 시행령 §23 의 정확한 면제 문구와 "서비스 UI 내 결과물" 기준의 법령 근거(기사 설명 수준).
- Anthropic **현행** 개인정보처리방침의 한국 섹션 및 API 데이터 처리 위치 공식 문구; Upstage·Naver CLOVA 의 데이터 보관 위치·보관기간·학습 미사용 약정(공식 페이지에서 미확인).
- OpenAI API 가 '처리위탁'인지 '제3자 제공'인지에 대한 개인정보위 해석: 미발견.

---

## KQ5. 비용 모델 — 유저 1명이 월 N장 캡처를 올릴 때 OCR/LLM 비용

### Takeaway
공식 단가로 계산하면 스크린샷 1장당 비용은 Haiku 5.5 비전 ≈ **$0.0003**, Gemini 2.5 Flash-Lite ≈ $0.0003 이하, Upstage Standard $0.01, Google Document AI $0.0015, Textract Detect $0.0015, Opus 5.5 비전(고해상 티어) ≈ $0.015~0.02 수준이다. 월 30장 기준 유저당 월 비용은 Haiku 약 $0.01, Opus 약 $0.5, Upstage $0.30 이며, 브라우저 OCR 후 텍스트만 보내는 현재 구조에선 Opus 5.5 로도 장당 ≈ $0.006~0.01 이다. 어느 경우든 1,000명 베타에서 월 수백 달러를 넘기 어렵다.

### Cited Findings
(단가 출처는 모두 KQ1 에 인용된 공식 페이지: [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Claude Vision](https://platform.claude.com/docs/en/build-with-claude/vision), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Upstage pricing](https://upstage.ai/pricing), [Document AI pricing](https://cloud.google.com/document-ai/pricing), [Textract pricing](https://aws.amazon.com/textract/pricing/).)

- Claude 이미지 토큰 = ⌈w/28⌉×⌈h/28⌉; 1920×1080 은 표준 티어 1,560 토큰, 고해상 티어 2,691 토큰; 1000×1000 = 1,296 토큰 — [Claude Vision](https://platform.claude.com/docs/en/build-with-claude/vision).
- 공식 예시: Opus 5.5 고해상 티어 1000×1000 이미지 1,000장 ≈ $5.18(장당 $0.00518), 4K 1,000장 ≈ $19.14 — 같은 페이지.
- Haiku 5.5 입력 $0.10/MTok·출력 $0.50/MTok(10만 토큰 이하 프롬프트), Opus 5.5 $4/$20, Sonnet 5.5 $2/$10; Batch 50% 할인 — [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing).

**계산(가정 명시; 조사자 추정)**
- 가정: 스마트폰 캡처 1080×2400(2.59 MP). 표준 티어에서 1920×1080(2.07 MP)이 1,560 토큰으로 캡되는 것을 보아 **표준 티어 ≈ 1,600 토큰/장**, 고해상 티어는 비례 확대(2,691 × 2.59/2.07 ≈ **3,400 토큰/장**)로 가정. 출력 JSON ≈ 400 토큰, 시스템 프롬프트 ≈ 800 토큰(캐시 미적용 보수 계산).
  - Haiku 5.5(이미지 직접): 입력 (1,600+800)×$0.10/1M = $0.00024 + 출력 400×$0.50/1M = $0.0002 → **≈ $0.00044/장**. 월 30장 = $0.013/유저, 1,000명 = $13/월.
  - Opus 5.5(이미지 직접, 고해상): 입력 (3,400+800)×$4/1M = $0.0168 + 출력 400×$20/1M = $0.008 → **≈ $0.025/장**. 월 30장 = $0.75/유저, 1,000명 = $750/월. Batch 적용 시 절반.
  - 현재 구조(브라우저 OCR → 마스킹 텍스트 ≤ 6,000자, `ai_read.py` 주석상 폰 화면 1장 ≈ 1~2k 자 ≈ 1,000~1,500 토큰) Opus 5.5: 입력 (1,500+800)×$4/1M = $0.0092 + 출력 $0.008 → **≈ $0.017/장**; Haiku 5.5 로 바꾸면 ≈ $0.0004/장.
  - Gemini 2.5 Flash-Lite: 입력 $0.10/MTok, 출력 $0.40/MTok — 이미지 토큰 규칙이 페이지에 없어 Claude 와 같은 1,600 토큰으로 가정하면 ≈ $0.0004/장(무료 티어는 데이터 학습 사용 'Yes' 라 제외).
  - Upstage Standard $0.01/장 → 월 30장 $0.30/유저, 1,000명 $300/월. Enhanced 는 3배.
  - Google Document AI OCR $0.0015/장 → 월 30장 $0.045/유저. Textract Detect $0.0015/장(Forms 사용 시 $0.05/장 → $1.5/유저/월).
  - Tesseract.js(브라우저): 서버 비용 0, 정적 자산 전송만.

### Inferences
- 비용은 어느 경로든 의사결정 변수가 아니다(1,000명 베타 월 $13~$750). 실제 선택 변수는 (a) 국외이전·동의 UX(KQ4), (b) 한국어 표·숫자 추출 정확도(KQ1 Gap), (c) 검증 가능한 출력(현재의 관계식 검증).
- 현재 구조에서 모델만 Haiku 5.5 로 내리면 장당 비용이 약 40분의 1 이 되지만, 추출 정확도 차이는 미측정이다 — `ai_read.py` 의 "읽은 숫자는 원문에 있어야 한다" 검증이 있으므로 저가 모델의 오류는 '힌트로 강등'될 뿐 저장되진 않는다는 점이 완충 장치다.

### Gaps
- 스마트폰 세로 캡처(1080×2400 등)의 실제 Claude 토큰 수: 공식 표에 없어 추정. `count_tokens` 로 실측 권장.
- Gemini Flash 계열의 이미지 토큰 산정 규칙: 가격 페이지 미기재.
- CLOVA OCR 원화 단가 → 국내 벤더 비교선 누락.

---

## KQ6. 아첨/판단 회피 설계 — 기록 앱에서 AI 가 '요약·추출만' 하는 제품 사례

### Takeaway
"추출·요약만, 판단 없음"을 **제품 원칙**으로 명문화한 국내 투자 기록 앱 사례는 찾지 못했다. 가장 가까운 것은 (a) 해외 저널의 AI 가 CSV 포맷 변환·스크린샷 추출에 한정되는 구조(TradesViz·TraderCater), (b) 국내 증권사의 AI 가 '어닝콜 요약·실시간 이슈 요약'처럼 정보 요약으로 포지셔닝되는 사례(토스증권), (c) 규제 쪽에서 금융위 가이드라인의 '보조수단성'(AI 는 보조, 최종 판단은 사람) 원칙이다. 이 저장소의 `ai_read.py`(추출 전용·검증·미저장)는 그 원칙을 코드로 구현한 드문 예에 해당한다.

### Cited Findings
- TradesViz 의 AI 활용은 미지원 브로커 파일을 ChatGPT/Gemini 로 **포맷 변환**하는 것에 한정 — [TradesViz FAQ](https://www.tradesviz.com/product-faq/).
- TraderCater·Traders Diary·Trading Journal Pro: AI/OCR 의 역할이 "스크린샷에서 거래 데이터 추출·자동 기록"으로 서술 — [huntscreens](https://huntscreens.com/products/tradercater), [mwm.ai Traders Diary](https://mwm.ai/apps/traders-dairy-pnl-tracker/6769652253), [mwm.ai Trading Journal Pro](https://mwm.ai/apps/trading-journal-pro/6781800832).
- TradeHelp 는 반대 사례: "오프라인 AI 코치"를 표방(판단·코칭 쪽) — [peerpush](https://peerpush.com/p/tradehelp).
- 토스증권 AI 어닝콜은 "실적발표를 문자화하고 핵심 내용·주요 발언·실적 전망을 분석·요약" — [헤럴드경제 2026-05-14](https://www.heraldk.com/article/2026051418383462717); 시장 탭·실시간 이슈 AI 는 "정보 접근성" 프레임 — [아시아경제 2026-10-14](https://core.asiae.co.kr/article/2026101409292455419).
- 금융위 2026-06 가이드라인 '보조수단성': AI 는 업무의 보조수단, 최종 의사결정과 책임은 임직원; '신의성실': 금융소비자 이익 우선 — [뉴데일리](https://biz.newdaily.co.kr/site/data/html/2026/06/18/2026061800173.html); [다음/연합](https://v.daum.net/v/20260618150301114).
- 고독한 투자자(국내 iOS): AI 없이 "기록이 기기 밖으로 나가지 않음"을 가치로 내세움 — [App Store](https://apps.apple.com/kr/app/%EA%B3%A0%EB%8F%85%ED%95%9C-%ED%88%AC%EC%9E%90%EC%9E%90/id6448638906?l=en-GB).

### Inferences
- 시장은 'AI 투자비서'(판단 보조) 방향으로 가고 있어(더팩트), "추출만 하는 AI"는 차별점이라기보다 **규제·신뢰 리스크를 줄이는 방어선**으로 설명하는 편이 정확하다. CLAUDE.md 의 제품 전제("비-아첨은 해자가 아니다")와 일치.
- 구현 패턴으로 일반화하면: (1) 출력 스키마를 고정 JSON(종목·수량·단가·일시)으로 제한, (2) 모델이 '읽었다'는 값은 원문 텍스트/OCR 결과에 존재해야 채택, (3) 산술 관계식으로 교차 검증, (4) 실패분은 사용자 확인 힌트로 강등, (5) 프롬프트·응답 미저장. 이 다섯 항목은 `services/ai_read.py` 주석에 그대로 적혀 있다.

### Gaps
- "AI 는 요약만 한다"를 약관·UI 로 명시한 국내 기록 앱 사례: 미발견.
- 해외 저널(TradeZella·Tradervue)의 AI 기능이 '판단'을 어디까지 하는지(예: AI 피드백 기능) 공식 문서: 조사 범위 내 미확인.
