# 문 앞의 한 줄 (Doorway Pause) — 2026-10-15

## 1. 왜

「멈춤」(`/pre-trade`)은 유저가 **사기 전에 PivoxQuant 를 스스로 열어야** 작동한다.
그런데 충동은 증권 앱(MTS)을 여는 순간 시작되고, 거래도 거기서 끝난다. 그래서 멈춤은
이미 망설이는 거래에만 쓰인다 — `services/pre_trade/friction_outcome.py` 가 스스로
"선택 편향"이라고 적어 둔 한계다.

문 앞의 한 줄은 멈춤을 **목적지에서 문턱으로** 옮긴다. 유저 폰의 자동화가 증권 앱이
열릴 때 한 질문을 묻는다:

> **뭘 하러 왔어요?** — 그냥 보기 / 살 게 있음 / 팔 게 있음 (+ 종목·이유 한 줄)

근거: one sec 현장실험 (Grüning, Riedel, Lorenz-Spreen, *PNAS* 2023, 280명·6주,
doi 10.1073/pnas.2213114120) — 앱을 열 때 거는 자기 넛지로 열기 시도의 **36%** 가
그 자리에서 접혔고 열기 시도 자체가 **37%** 줄었다. (회사 홈페이지의 57% 는 논문
수치가 아니다 — 인용 금지.)

해자와의 관계: 증권사는 앱이 열린 건 알지만 의도는 모른다. one sec 같은 범용 앱은
의도는 묻지만 체결을 모른다. 둘을 잇는 데 필요한 체결 웹훅(`routes/imports.py`
`/webhook`)과 폰 자동화 안내가 이미 있다. 남은 진짜 자산인 "일어나지 않은 거래"
(`docs/claude/product-premise.md`)가 손으로 쓰는 기록에서 자동으로 쌓이는 표본이 된다.

베타 질문과의 관계: *"한국 개인투자자가 기록을 하긴 하는가"* 를 7문항이 아니라 **한
탭 응답률**로 잰다. 한 탭에도 답하지 않으면 기록 제품 전제가 틀린 것이고, 그것도 답이다.

## 2. 흐름

```
증권 앱 열림 ─▶ 폰 자동화가 묻는다 ─▶ POST /api/doorway/webhook (Bearer 가져오기 토큰)
                 (아이폰 단축어 메뉴)        └▶ doorway_checks 1행
              또는 웹 문 /pre-trade/door ─▶ POST /api/doorway/checks (세션)
                 (안드로이드 MacroDroid 가 연다)

체결 ─▶ (기존) 체결 자동 기록 웹훅 → pending_trades / 승인 → trade_history

거울 /mirror 「문 앞」 ◀── GET /api/doorway/summary — 읽을 때 열림 × 체결을 맞춘다
```

- **아이폰**: 단축어 '앱 → 열 때' 자동화 → '메뉴에서 선택'(3항목) → 항목별 '텍스트'
  (`보기` / `살 [매번 묻기]` / `팔 [매번 묻기]`) → 'URL 콘텐츠 가져오기'
  `{"text": 메뉴 결과, "app": "toss"}`. 서버가 머리말을 읽는다 (`parse_text`).
- **안드로이드**: MacroDroid '앱 실행' 트리거 → '웹 사이트 열기' `/pre-trade/door?app=…`.
  브라우저 로그인 세션으로 답하고, 뒤로 가기로 증권 앱에 돌아간다.
- 두 경로 모두 **시험 중**으로 표시 — OS 메뉴 문서대로 썼지만 모든 버전 실기기 확인은 안 됐다.

## 3. 데이터

`doorway_checks` (migration `064_doorway_checks`)

| 칸 | 내용 |
|---|---|
| `intent` | `look` / `buy` / `sell` (소문자 데이터 값) |
| `ticker` | 한 줄에서 읽은 종목 — 국내 종목명 정확 일치 → 미국 종목 한글 이름(`us_kr_names.json`) → 6자리 코드 → 대문자 기호. 가져오기와 같은 마스터. 못 읽으면 null |
| `note` | 한 줄, `EncryptedText`, 200자에서 자름 |
| `app` | 자동화가 붙인 앱 꼬리표 (`toss`, `kiwoom`… 한글 이름도 받아 정규화) |
| `source` | `automation`(토큰) / `web`(세션) |
| `created_at` | 문을 연 시각 (naive UTC) |

하루(KST) 100건 상한 — 고장 난 자동화가 표를 덮지 않게 (`DOORWAY_DAILY_LIMIT` 429).

## 4. 맞추는 규칙 (`services/doorway/service.py::summarize`, 순수 함수)

- 체결 하나는 **그 체결 직전의 열림 하나**에만 잇는다: 체결 시각 기준 60분 안에서 가장
  늦게 연 열림. 체결 문자는 분 단위라 60초 앞선 체결까지 그 열림에 잇는다.
- 체결 = 기록된 체결(등록 행 제외) + 대기 목록의 체결 (`my_rules.month_fill_count` 와 같은 단위).
- 결과: 그냥 보기 → `traded` / `none`. 살·팔 → `as_said`(말한 방향 + 종목을 적었으면 같은
  종목) / `other` / `none`.
- **일어나지 않은 거래**: 종목을 적고 `none` 으로 끝난 살·팔 열림 → 그 뒤 30일 안에 같은
  종목을 같은 방향으로 체결했나 (`later` / `never` / 아직 30일 전 `open`).
- **문을 거친 체결**: 첫 열림 이후 창 안의 체결 중 열림에 이어진 비율 — 자동화가 실제로
  도는지의 사실.
- `caveats` 4줄을 그대로 내보낸다 (창 규칙, 다른 기기 거래, 대기 체결 포함, 인과 아님).

## 5. 법·개인정보

- 점수·등급·연속 기록·지시 없음. 개수와 유저 본인의 한 줄만.
- 증권 앱·계정·주문에 닿지 않는다. 유저 폰의 OS 자동화가 유저 본인의 토큰으로 보낸다.
- 시세를 부르지 않는다 (behavior/* 와 같은 규율).
- `note` 만 `legal_scrub_response(skip_keys=("note",))` 로 원문 유지 — research_notes 와 같은 이유.
- PIPA: 탈퇴 삭제(`account_erasure`) · 열람권 export(`doorway_checks`) · 키 회전 스윕
  (`scripts/reencrypt_user_text.py`) 편입. 처리방침 §1.2 · §2-2 · §3 · §4 반영,
  가져오기 토큰 동의 문구에 문 앞 기록 추가.
- 한 줄은 URL 에 넣지 않는다 — 「멈춤」으로 넘길 때도 `?ticker=` 만.

## 6. 화면

- `/mirror` 「문 앞」 카드 (`components/mirror/doorway-panel.tsx`) — 열린 횟수, 답 3종 막대,
  사실 문장, 시간대 막대(KST), 최근 5건, "이렇게 셉니다". 설정 전엔 데스크톱에서만 초대 한 줄,
  폰 카드 줄에는 설정한 뒤에만 들어간다.
- `/settings?s=doorway` 안내 (`components/settings/doorway-section.tsx`).
- `/pre-trade/door` 웹 문 — 답하기 + 최근 기록 지우기.
- `/pre-trade?ticker=` — 문에서 넘어온 종목을 빈 칸에만 채운다.

## 7. 다음

- 올해의 기록(연말 회고)에 문 앞 집계를 넣는다 — 그 PR 의 `doorway` 키.
- 2주 실험: CEO 본인 폰 + 지인 3~5명. 응답률 · '그냥 보기' 비율 · 의도 → 체결 전환.
  **본인이 1주 안에 자동화를 끄면 컨셉 폐기.**
