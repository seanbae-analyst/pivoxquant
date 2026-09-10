# PivoxReport — 내 토스증권 계좌를 read-only 로 읽어 거울 리포트 만들기

> 2026-09-10 작성. 대상은 **운영자 본인 계좌 하나**다. 유저용 브로커 연동이 아니다.
> `BROKER_LINKING_AVAILABLE=false` 는 그대로다 (사유: `frontend/src/app/(auth)/onboarding/broker/page.tsx` 주석).

## 왜 이게 되는가, 왜 유저용은 안 되는가

| | 본인 계좌 (이 문서) | 다른 유저 계좌 |
|---|---|---|
| 키 소유 | 운영자 본인 → 본인 서버 env | 유저가 우리 서비스에 붙여넣기 |
| 토스 약관 §5② (앱키 제3자 대여·양도·누설 금지, 접근매체) | 토스가 "ChatGPT·Claude 에 키 연결" 을 직접 홍보한 것과 같은 범주 | **유저가 자기 증권사 약관을 어기게 만드는 구조** — 변호사 답 전엔 보류 |
| scope | 없음 — 조회 토큰으로 주문도 됨 | 동일. 우리가 유저의 주문 가능 자격증명을 보관하게 됨 |

시세 관점의 의미: PivoxQuant 에서 시세가 필요한 화면은 `/portfolio` 평가액뿐이다.
평가액을 유저 본인 계좌에서 받으면 FMP §2.2.2 와 R7 이 함께 닫힌다 (CLAUDE.md §제품).
이 스크립트는 그 경로의 첫 실증이다 — 단, 아직 운영자 1명에 한해서.

## 준비 (1회)

1. 토스증권 **PC 웹(WTS) 로그인 → 설정 → Open API** 에서 `client_id` / `client_secret` 발급.
2. 같은 화면의 **허용 IP** 에 이 스크립트를 돌릴 머신의 공인 IP 등록.
   REST 도 허용 IP 가 적용된다 — 빠지면 403 `edge-blocked`.
3. `.env` 에 추가 (`.env.example` 의 TOSS 블록 참조):
   ```
   TOSS_CLIENT_ID=...
   TOSS_CLIENT_SECRET=...
   ```
   Render 에는 넣지 않는다. 서버가 읽을 이유가 없고, 주문 가능한 자격증명을 서버에 두는 것이다.

## 실행

```bash
./venv/bin/python scripts/pivox_report.py                # 최근 90일 → reports/personal/pivox_report_<날짜>.md + .json
./venv/bin/python scripts/pivox_report.py --days 30
./venv/bin/python scripts/pivox_report.py --dump-raw /tmp/raw.json   # 응답 원본 보관 (계좌번호 원문 포함, 토큰 없음)
./venv/bin/python scripts/pivox_report.py --from-raw /tmp/raw.json   # 네트워크 없이 재렌더
```

`reports/personal/` 은 gitignore 다.

## 리포트에 있는 것 / 없는 것

있는 것 — 전부 토스 응답값의 재배열이다. 재계산·재가격 없음:
- 평가액 (KRW + USD×토스 표시환율), 매입총액, 미실현 손익·율(비용 차감 포함), 당일 손익
- 보유 종목표 (평가액 KRW 순, 비중), 집중도 (상위1·상위3·HHI·국내/해외·30% 초과)
- 최근 N일 활동: 체결/취소/거부 건수, 주당 체결, 거래일, 거래대금과 평가액 대비 회전율,
  수수료+세금, 자주 체결된 종목, 보유했지만 손대지 않은 종목, 평단 아래 추가매수 체결(물타기 근사)

없는 것 — 응답에 없어서 만들지 않은 것:
- **예수금** (holdings 는 KR·US 주식만) → "평가액"은 주식 평가액이다
- **실현손익** (매도 시점 취득단가 부재)
- 시간외단일가 등 Open API 미지원 호가로 낸 주문
- 다음에 뭘 하라는 문장. 거울이지 조언이 아니다 (자본시장법 경계는 여기서도 같다)

## 안전장치 — 어디에 있고 무엇을 막는가

- `services/toss/client.py::READ_ONLY_PATHS` — GET 허용 경로 8개. 그 밖의 경로는
  **요청 전에** `TossReadOnlyViolation`. 주문·정정·취소·조건주문·매수가능금액은 목록에 없다.
  테스트: `tests/test_toss_readonly_client.py` (denied path 7종이 소켓을 열지 않음을 확인).
- 토큰은 메모리에만 있다. 디스크에 쓰지 않는다. 로그는 `redact()` 를 거친다.
- 토스는 **client 당 유효 토큰 1개**다. 두 프로세스가 같은 client 로 돌면 서로 무효화한다.
  cron 에 넣을 거면 하나만.
- 계좌번호는 출력에서 마스킹된다 (`***8901`). `--dump-raw` 파일에는 원문이 들어간다.

## 스펙 출처

- `https://openapi.tossinvest.com/openapi-docs/latest/openapi.json` (v1.2.15, 2026-09-10 기준)
- `https://openapi.tossinvest.com/openapi-docs/overview.md` — rate limit (AUTH 5/s, ACCOUNT 1/s), 에러 코드, 허용 IP
- 픽스처 `tests/fixtures/toss/sample_raw.json` 은 위 문서의 예시 응답을 그대로 옮긴 것이다.
