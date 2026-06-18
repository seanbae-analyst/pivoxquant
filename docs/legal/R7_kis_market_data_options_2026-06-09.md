# R7 — KIS 시세 재배포 라이선스 갭: 4안 의사결정 자료 (2026-06-09)

> 출처: legal-kr-fintech 리서치(WebSearch, 2026-06-09) + lead 코드앵커 실측 검증.
> ⚠️ 일부 수치는 외부 페이지 접근 제한으로 **확인불가** — CEO 직접확인 항목 명시.

## 문제 (R7)
`services/data/kis_market_adapter.py` 가 KIS Open API 로 임의 KR 종목/지수 시세를 받아
**전 유저** 대시보드(/market)·PDF·시그널에 표출(`fetcher` "KR: KIS primary"). KIS 앱키 =
**본인 계좌 조회용**, **상업적 재배포 권한 아님**. 유료결제 활성화 시 = 상업 재배포 성립
→ KRX/KOSCOM 정보이용계약 필요.

## 코드 실측 (검증됨)
- `routes/market.py:1201-1207` — KOSPI/KOSDAQ 지수도 KIS 경유. **`KR_INDEX_KIS_ENABLED` 게이트 이미 존재**(default `"1"`, `=0` 으로 즉시 차단 가능). 주석에 "SHIP_BLOCKERS R7" 명시.
- `routes/market.py:193` + `kis_market_adapter.py:7-12` — 코드가 재배포갭을 **자가 문서화**.
- `services/data/fetcher.py:1211` — `.KS`/`.KQ` → `_get_history_kis()` 1순위, 실패 시 FMP fallback.
- 표면1(본인계좌 read-only, `broker/user_kis_service.py`) ↔ 표면2(임의종목 시세) **코드 분리**, 단 **동일 `KIS_APP_KEY`** 공유.

## 4안 비교 (2026-06-09 WebSearch)

| | 옵션1 FMP 상위플랜 | 옵션2 금융위 공공데이터 T+1 | 옵션3 KOSCOM 라이선스 | 옵션4 KR 라우팅 제거 |
|---|---|---|---|---|
| **비용** | Starter $22 / Premium $59 / Ultimate $149(개인용·재배포불가). 상업재배포=Build/Ent 커스텀견적(가격표 403, **확인불가**) | **무료**(cc-zero 추정, **확정필요**) | 미공개(fintechdata@koscom). 스타트업 36개월 기본료 면제 가능성 | 0원 |
| **KR 커버** | Starter/Premium KR **미서빙**(2026-06-03+오늘 재확인). 상위플랜 KR 여부 **확인불가** | 코스피·코스닥 전종목+지수(별도 API) | 전종목+실시간 | 없음(KR 화면 비활성) |
| **실시간** | KR 커버 확인불가 | T+1(익영업일 오후), 실시간X | 실시간 가능 | N/A |
| **재배포 적법** | Build/Ent + Display·Licensing 계약 필요 | cc-zero면 OK, **공공누리 2유형이면 상업금지**(동일기관 다른셋이 2유형 확인됨→확정필요) | 라이선스 = 가장 확실 | 문제소멸 |
| **구현** | fallback 배선 이미 존재, 키 교체만 | 신규 클라이언트(중간) | 신청절차+신규 클라이언트(수주~수개월) | `KR_INDEX_KIS_ENABLED=0` env 토글 1회(낮음) |
| **리스크** | KR 커버 미확인 상태 업그레이드=비용만↑ | 라이선스 유형 확정 전 사용=위반 위험 | 비제도권 적격성 불확실+일정 영향 | KR 유저 시세 전면중단=UX 타격 |

## 법적 판단
- **무료 베타에서 R7 이 지금 blocker 인가**: 유료화는 R3(통신판매업)+R4(Stripe)로 이중 차단 → **R7 은 유료화 전까지 실질 우선도 낮음.** 단 영리법인 플랫폼의 제3자 표출은 무료라도 회색지대 → "무료 베타 비해당" 사인을 변호사가 서면으로 줘야 안전.
- **옵션2 가 법적 최클린**(cc-zero 확정 시): KRX 원천 공공개방, 별도계약·비용 0. 단 라이선스 유형 **직접 확인 필수**.
- **옵션3 가 적법성 최확실**이나 비용·일정·적격성 불확실.
- **표면1(본인계좌)는 KIS 약관상 허용** — 유지 OK.

## 추천: 옵션2(금융위 T+1) 확정 후 적용 + 단기 브릿지로 옵션4
1. **CEO 5분 액션**: `data.go.kr/data/15094808/openapi.do` 직접 접속 → 라이선스 유형 눈으로 확인. cc-zero면 진행, 공공누리 2유형이면 변호사 확인.
2. 변호사 큐에 **Q-KIS1** 추가: "금융위 공공데이터 주식시세(15094808)를 SaaS 임베드·유료표출이 상업이용금지 해당?"
3. cc-zero 확정 시 엔지니어링: `services/data/kr_public_market_adapter.py` 신설(T+1 OHLCV) → fetcher fallback 순서 KIS→금융위→FMP.
4. **유료화(R4)는 R7 해제 후로 순서 유지.**
5. 실시간이 비즈니스 필수면 옵션3(KOSCOM, fintechdata@koscom.co.kr / 02-767-7583) 재검토 — 신청 전 법인 적격성 변호사 확인.

> 미확인 항목(CEO/변호사 확인 필요): ① FMP 상위플랜 KR 커버 여부 ② 금융위 15094808 라이선스 유형(cc-zero vs 공공누리2) ③ KOSCOM 비제도권 스타트업 적격성.
