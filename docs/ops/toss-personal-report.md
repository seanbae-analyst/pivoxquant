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
./venv/bin/python scripts/pivox_report.py                # 이력 730일 + 최근 90일 거울 → reports/personal/pivox_report_<날짜>.md + .json
./venv/bin/python scripts/pivox_report.py --since 1500   # 첫 줄이 "일치"가 아니면 이력을 더 넓혀서
./venv/bin/python scripts/pivox_report.py --days 30
./venv/bin/python scripts/pivox_report.py --dump-raw /tmp/raw.json   # 응답 원본 보관 (계좌번호 원문 포함, 토큰 없음)
./venv/bin/python scripts/pivox_report.py --from-raw /tmp/raw.json   # 네트워크 없이 재렌더
```

`reports/personal/` 은 gitignore 다.

## 리포트 구성 (v2, 2026-09-10 — 실계좌 첫 실행 뒤 재구성)

첫 실행에서 본 것: 이 계좌의 이야기는 잔고가 아니라 **경로**에 있었다. 보유 9종목 중 6종목은
90일간 손대지 않았고 손실이 거기 몰려 있었으며, 체결은 두 종목에 몰려 있었다. 잔고 표는
그걸 말하지 못한다. 그래서 v2는 주문 이력 전체(`--since`, 기본 730일)를 받아 포지션을
되짚고, **제품이 `/journal` 에서 쓰는 거울 함수 그대로**를 이 계좌에 댄다.

| 절 | 내용 | 계산 주체 |
|---|---|---|
| 이 리포트가 딛고 선 이력 | 되짚은 수량·평균단가가 토스 잔고와 **일치하는가**. 불일치 종목과 사유 | `services/toss/history.py::reconcile` |
| 평가 | 평가액·매입·미실현·**실현 누계(수수료·세금 차감)** | 토스 응답 + 재구성 |
| 거울 — 최근 N일 / 전체 이력 | 회전(체결 수·거래대금·보유일) · 추가매수(평균단가 대비 아래/위/같음) · 손익처분(이익 실현 vs 손실 실현의 보유일·수익률 중앙값) | 전체 = `services/behavior/{turnover,averaging_down,profit_loss}_mirror` 그대로 / 최근 = 전체 이력 취득단가 위에서 창만 제한 |
| 집중 | 종목 수 · 가장 큰 종목 비중 · 30% 선 · 국내/해외 | 평가액 가중 |
| 보유 종목의 이력 | 보유 시작일 · 보유일 · 매수/매도 횟수 · 마지막 체결 · 평단 · 비중 · 손익률 | 재구성 |
| 떠난 종목 | 완전히 정리한 종목의 실현손익·매도 수익률 중앙값 | 재구성 |
| 이 숫자가 말하지 않는 것 | 예수금 부재 · 표시환율 · Open API 미지원 호가 · 세후 차이 | — |

**"일치"가 먼저다.** 실현손익은 취득단가가 맞을 때만 의미가 있다. 리포트 첫 줄이 "토스 잔고와
전부 일치"가 아니면 `--since` 를 넓혀 다시 받아라. 넓혀도 안 맞으면 Open API 로 볼 수 없는
주문(시간외단일가 등)·입출고·권리락이 있는 것이고, 리포트는 그 종목을 이름 붙여 "부분"이라고
말한다. 억지로 맞추지 않는다.

**v1 에 있었고 v2 에서 뺀 것**: HHI, 평가액 대비 거래대금 비율, "물타기" 라는 단어. 제품
거울은 개수·일수·수익률만 내고 사람을 채점하는 지수는 내지 않는다 (DECISIONS.md — AI 점수화
폐기). 이 리포트도 그 선을 따른다.

없는 것 — 응답에 없어서 만들지 않은 것:
- **예수금** (holdings 는 KR·US 주식만) → "평가액"은 주식 평가액이다
- 시간외단일가 등 Open API 미지원 호가로 낸 주문 — 이력 불일치의 흔한 원인
- 다음에 뭘 하라는 문장. 거울이지 조언이 아니다 (자본시장법 경계는 여기서도 같다)

## 안전장치 — 어디에 있고 무엇을 막는가

- `services/toss/client.py::READ_ONLY_PATHS` — GET 허용 경로 9개. 그 밖의 경로는
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
