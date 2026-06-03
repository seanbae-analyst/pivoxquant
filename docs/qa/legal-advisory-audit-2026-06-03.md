# 투자자문(자본시장법 §17 / §101) 리스크 전수조사 — PDF 아티팩트 중심

**작성일** 2026-06-03 · **방법** legal 4-agent 병렬(legal-kr-fintech / legal / compliance-gatekeeper / regulatory-monitor) + 메인 실측 검증
**대상** 18 아티팩트(23 PDF/이메일 템플릿) + AI 런타임 출력 7경로 + 면책/금지어/필터 인프라 + 2026 외부 규제 델타
**성격** 내부 참고용 — 법률자문 아님. 🔴/🟠 항목은 변호사 사인 또는 코드 수정 후 재감사 필요.

---

## 0. TL;DR (검증 후 종합)

- **무료 출시에 대한 신규 하드 BLOCKER 없음.** 유료/마케팅 활성화는 이미 외부 의존(변호사 Q1-Q15·Q-S1, 통신판매업 신고)으로 게이트됨 — 이번 감사가 그 게이트를 새로 추가하지는 않음.
- **컴플라이언스 아키텍처는 견고함**: forbidden_terms(SoT) + legal_filter(regex) + 이중 scrub + 면책 매트릭스 20/23 clean + §101③ 채팅 격리 + POSITIVE/NEGATIVE/NEUTRAL 강제. 발견된 건 **시스템 실패가 아니라 엣지·문구 수준**.
- **변호사 없이 지금 고칠 수 있는 확정 결함 4건(🟠 HIGH)** — Alpaca 출처 문자열, 적중률 라벨, earnings "Action 권장", earnings AI 페르소나.
- **양방향 AI Chat 규제 리스크는 실재하나 이미 방어됨** — `AI_CHAT_ENABLED` 기본 OFF(§101③ 주석 명시). 변호사 Q-R1 답 전까지 **켜지 말 것**.
- **변호사 큐 신규 2건** — Q-R1(양방향 채팅 면제 영향), Q-R2(AI기본법 §31① 사전고지).

심각도: 🔴 BLOCKER(무인가 자문 직접·라이브 노출) / 🟠 HIGH(강한 해석위험 또는 확정 결함) / 🟡 MED(문구·프레이밍, 해석 의존) / 🟢 LOW(경미·이미 완화)

---

## 1. 변호사 없이 지금 수정 가능 (🟠 HIGH × 4)

### H1 🟠 earnings_prebrief — 연결 안 된 Alpaca를 데이터 출처로 표시 (표시광고법 §3)
- **위치** `services/artifacts/earnings_prebrief_service.py:1198, 1206`
- **증거** `return "FMP · Alpaca · SEC EDGAR"` (data_sources 비었을 때 폴백, 2곳)
- **문제** Alpaca 통합은 2026-05-27 제거(`CLAUDE.md`). 신규 유저는 Alpaca 미연결인데 폴백이 Alpaca를 출처로 인쇄. **회사에 이걸 막으려고 만든 전용 모듈 `data_source_resolver.py`가 존재**(docstring: "self-reporting to the user they're connected to Alpaca when [not]")인데 `_format_sources`가 이를 우회하고 옛 기본값을 하드코딩.
- **법규** 표시광고법 §3① 기만적 표시 (※§17 자문 아님 — 데이터 출처 사칭)
- **수정** 폴백을 `"FMP · SEC EDGAR"`로 교체, Alpaca 문자열 완전 제거. 가능하면 `data_source_resolver` 경유로 통일.
- **검증** ✅ 실측 확정. 콜로폰 경로(line 717-725)는 `_has_active_alpaca` 게이트로 정상이나, `_format_sources` 폴백만 누락.

### H2 🟠 "적중률" 정적 템플릿 하드코딩 — 자사 금지어 블록리스트와 모순
- **위치** `brag_card.html:101`, `insider_mirror.html:245`, `self_audit.html:74` (모두 `{% else %}적중률{% endif %}` KPI 라벨)
- **증거** `services/legal/forbidden_terms.py:102`에 `"적중률"`이 **FORBIDDEN_DIRECTIVE_TERMS로 이미 등록**. 그런데 정적 HTML이라 런타임 scrub 경로를 안 타서 그대로 출고됨.
- **문제** 성과 적중률 강조 = §101 면제 ④(매매 권유) 인접 + 자사 SoT 위반. brag_card는 line 80에서 같은 값을 "본인 결정 일치 비율 (과거 기록)/Decision consistency (historical)"로 **순화해 놓고** line 101 KPI 라벨만 "적중률"로 남김(불일치).
- **법규** 자본시장법 §17/§101 ④ + 내부 컴플라이언스 정합성
- **수정** 3개 라벨을 "과거 기록 통계(참고용)" 등 중립어로 교체. insider_mirror:62의 "(참고용 backtest, 미래 수익 보장 아님)" 디스클레이머는 유지.
- **검증** ✅ 실측 확정 (3개 파일 + forbidden_terms 등록 모두 확인).

### H3 🟠 earnings_prebrief — Scenario "Action" 열 + "재확인 권장" 문구
- **위치** `services/artifacts/earnings_prebrief_service.py:1147, 1156, 1165` + 템플릿 `earnings_prebrief.html:226, 239` (`<th>Action</th>`)
- **증거** `"action": "본인 룰 기준 시점 — 사전 정의된 한도와 시나리오 재확인 권장"` (Bull/Base/Bear 3종)
- **문제** 실적 발표 직전 타이밍 + "Action" 열 제목 + "권장"(권유 유사어)이 결합. "권장"은 forbidden_terms에 **없어** 필터를 통과. 단, 실체는 **유저 본인이 사전 설정한 한도 재확인**(line 1126 주석: "§101 회피 — action은 사용자 본인 룰 재확인")이라 특정 종목 매매지시는 아님 → BLOCKER가 아닌 HIGH.
- **법규** 자본시장법 §17 (문구 해석 위험)
- **수정** "Action" → "Observation/관찰 항목", "재확인 권장" → "본인 룰 트리거 직접 확인"(비지시·서술형). "권장" 어휘 제거. (병행) forbidden_terms에 "권장" 추가 검토 — 단 정당 문맥 오탐 주의.
- **검증** ✅ 실측 확정. 선해소 후 H4와 함께 재감사 권고.

### H4 🟠 earnings_prebrief — AI 프롬프트가 "월스트리트 시니어 애널리스트" 역할 부여
- **위치** `services/artifacts/earnings_prebrief_service.py:505-511`
- **증거** `"당신은 월스트리트 시니어 애널리스트. {ticker} 실적 발표 전 투자자가 주목할 질문 5개 작성…"` (+ 출력 필터 `_is_compliant_question`의 금지어가 canonical 54개와 별개로 8개만 관리 → 커버리지 갭)
- **문제** AI에 투자분석가 페르소나 부여 = §17 자문업 역할 수행으로 해석될 여지. 금지표현을 프롬프트에 명시했어도 역할 설정 자체가 리스크.
- **법규** 자본시장법 §17
- **수정** 페르소나를 "재무 데이터 요약 도구(조언 제공 안 함)"로 교체. `_is_compliant_question` 금지어를 canonical `FORBIDDEN_DIRECTIVE_TERMS`로 통일.
- **검증** ✅ 실측 확정.

---

## 2. 정통망법 §50 / 이메일 동의 (마케팅 활성화 게이트 = Q-S1 의존)

### M1 🟠 brag 첫-축하 이메일을 TRANSACTIONAL로 분류 → §50 동의 게이트 우회
- **위치** `services/customer/brag_card_celebration.py:154-164`(분류) + 공유 CTA 본문 / 트리거 `services/artifacts/brag_card_service.py:1146`(라이브)
- **증거** `email_category=EmailCategory.TRANSACTIONAL` (주석: "§50 ① 적용 제외 … short-circuits to allowed even when PIVOX_CS1_CONSENT_ENABLED is true"), subject "첫 brag-card 완성을 축하드려요", 본문에 `share_url`(referral) + return_pct.
- **문제** 거래확인이 아니라 **성과 자랑 + 공유 유도** = 광고성에 가까움. transactional 분류 시 `sender.py`의 default-deny(`marketing_consent_at` NULL 차단)까지 전부 우회. 다른 아티팩트는 INFORMATION으로 게이트를 타는데 이 메일만 우회(분류 불일치).
- **법규** 정통망법 §50① (사전 수신동의)
- **수정** INFORMATION/MARKETING으로 재분류해 동의 게이트 경유, 또는 share CTA 제거해 순수 거래확인으로 강등. **변호사 Q-S1과 연동.**
- **검증** ✅ 분류·트리거 라이브 확정. "축하+공유=광고성?"은 변호사 사인 필요.

### M2 🟡 이메일 2종 면책 누락 — dd_checklist_email / brag_card_email
- **dd_checklist_email.html** — `_disclaimer.html` include 없음. 서비스(`dd_checklist_service.py:473`)가 단문 `"정보 제공 목적이며 투자 권유가 아닙니다."`만 주입. §6 verbatim·§101 footer 없음. (코드 주석: NEEDS_CONFIG.md §11, 변호사 사인 후)
- **brag_card_email.html:177-210** — 2026-04-23 인라인 스냅샷. AI 라벨 있으나 §101 "미신고 면제 트랙" footer 없음 + `_disclaimer.html` 동기화 단절.
- **수정** R1(Q-S1) 해제 시 `_disclaimer.html` include 전환 또는 §101 문구 수동 추가. **`SHIP_BLOCKERS.md`에 A-NEW 추적 항목 추가 권고**(현재 CEO 시야 밖).
- **검증** ✅ 매트릭스 실측(나머지 21종은 면책 완비).

---

## 3. 외부 규제 델타 (2026, 변호사 의존)

### R1 🔵 (확정·이미 방어됨) 유사투자자문 양방향·1:1 상담 금지 (2024-08-14 시행)
- **출처** 금융위 보도자료 82887 (시행 2024-08-14)
- **내용** 온라인 양방향 채널 유료 회원제 영업 = 유사투자자문이 아닌 **투자자문업**으로 규율(미등록 시 3년 이하/1억). 허용은 수신자 입력 불가한 단방향(Push/알림톡)뿐.
- **우리 상태** AI Chat = 양방향 자유입력 구조이나 **`routes/ai.py:68` `AI_CHAT_ENABLED` 기본 OFF**, line 237-240 "§101③ 격리" 주석으로 LLM 호출 전 403. **현재 라이브 노출 NIL.**
- **액션** Q-R1 변호사 답 전까지 채팅 **재활성화 금지**. 면제 트랙의 핵심 균열점이므로 최우선 자문.

### R2 🟡 AI기본법 §31 표시·고지 의무 (2026-01-22 시행)
- **출처** 국가법령정보센터 lsiSeq=268543 (시행 2026-01-22), 계도기간 1년+
- **상태** 코드 주석 "Regulatory ③ (2026-01 시행)" = 실재 규제로 확인. **§31②(결과물 표시)는 양호**(_disclaimer/living_mirror에 "AI 생성 콘텐츠" 라벨). **§31①(사전 고지) 갭** — SWOT/Sector 등 라이브 AI 화면의 "생성형 AI 기반 운용 사전 고지" 라벨 미검출.
- **액션** §31① 약관/화면 충족 여부 확인 + 계도기간 내 보강. (과태료 최대 3천만, 계도 1년+ → MED)

### 기타 모니터링
- 핀플루언서 미신고 단속 + 금감원 AI 24시간 감시체계(2026-04) — "유료구독+양방향+개별응답" 정조준. 우리 방어선(추천어 금지)은 유효하나 R1과 결합 시 노출도 상승 → 지속 감시.
- 표시광고법 §3 백테스트 효능광고 — 마케팅 카피에 "투자 개선/수익 향상" 금지(HANDOVER v55 마케팅 게이트와 일치).
- 자본시장법 시행령 개정 입법예고(2026-01-30~03-11) — 확정본 원문 미확보, §101 영향 **확인 불가(OPEN)**.

---

## 4. 프레이밍 GRAY (🟡 MED, 변호사 판단)

| # | 표면 | 위치 | 이슈 | 수정 방향 |
|---|------|------|------|-----------|
| G1 | quarterly_self_report | `_thesis_checks` 487-518 | 보유 thesis "valid/warning" 판정 = 사후회고(SAFE) 아닌 미래지향 평가(GRAY). 어휘 아닌 의미 리스크 | verdict를 "기록 시점 대비 변동 있음/없음" 사실 라벨로 강등 |
| G2 | capital_allocation / earnings | `capital_allocation.html:173`, `earnings_prebrief.html:215-218` | "Action Points" / "Scenario Playbook·시나리오별 대응" 섹션명이 배분/매매 지시 연상 | "Observation Checklist" / "Scenario Observation·관찰 항목"으로 |
| G3 | year_end / quarterly | `year_end_letter_service.py:377-389` 등 | "tax-loss harvesting 관찰 구간" / "포지션 재점검 구간" = 세무자문 면책과 모순 인상 | "연말 세무 일정 관찰" / "분기 기록 관찰 구간" |

---

## 5. 🟢 LOW (이미 완화 / 경미)
- risk_board ExecSum 폴백 명령형("점검/확인하세요") — Governance에 "매매 지시 아님" 명시, 데이터 있으면 미렌더. 비명령형 권고.
- dividend_income `_forward_expected` 예상 배당 — "추정·지급 보장 안 함·세무자문 아님" 명시로 방어 완료.
- AIRiskSummary `_RISK_SUMMARY_PROMPT` "should be aware of" — 동시 "Do NOT recommend any action" 강제 + scrub. 중립어 권고.
- AI Chat 스트리밍 per-chunk scrub의 청크 경계 분할 갭 — **채널 OFF로 현재 무해**, 재활성화 시 누적버퍼 재-scrub 필요.

---

## 6. CLEAN (검증 후 안전 확인)

- **insider_mirror §101 자기데이터** ✅ — `generate_for_user`(332-359) "보유 종목 한정" 명시, 0종목 empty 가드, featured도 보유분에서만 선정. (검증 완료 — GRAY 우려 해소)
- **면책 매트릭스 20/23 PDF** — `_disclaimer.html`(§6 한+영 verbatim) + `_disclaimer_runner.html`(@page 매 페이지 하단) + AI 라벨 + §101 footer. (예외 2건은 M2)
- **AI 런타임 필터 커버리지** — routes/ai.py 전 200-응답이 `scrub_response` 경유(누락 엔드포인트 0). SWOT/Commentary/Coaching/Competitor/Sector/EarningsTone/RiskSummary 이중 scrub. BUY/SELL/HOLD → POSITIVE/NEGATIVE/NEUTRAL 강제 치환, 직접 노출 경로 미발견.
- **21개 아티팩트 서비스 전부** legal scrub(safe_scrub/detect_prohibited/contains_forbidden_term) 1개 이상 적용.
- **개별 clean**: kpi_dashboard / portfolio_segment / monthly_finance / burn_rate(세무자문 아님 명시) / pre_trade_checklist(전 관찰형, 빌드타임 assert_legal_safe) / sp500_backtest("어떤 전략도 권유 안 함") / credit_rating(self-rating 명시) / capital_allocation(우열 미표시) / living_mirror(점수·등급·순위 없음, 비진단·비치료 disclaimer).
- 금지어 grep 스윕: 23템플릿+서비스 전체 **실질 true-positive 0건**(전 히트가 부정문/면책/DB필드비교). 유일 예외가 H2의 정적 "적중률" 라벨.

---

## 7. 변호사 큐 추가 제안 (legal_question_queue.md)

- **Q-R1 [최우선]** (출처: 금융위 82887, 2024-08-14) — 2024 "유사투자자문 양방향·1:1 상담 금지"가 **미신고 본인데이터 PFM(Personal Capital 모델)**에도 적용되나? 유료구독자 대상 양방향 AI Chat이 미등록 투자자문업으로 재분류될 위험은? POSITIVE/NEGATIVE/NEUTRAL만 써도 "1:1 개별 응답" 자체가 표지인가? → **유료결제 활성화 BLOCKER와 직결.**
- **Q-R2 [1개월 내]** (출처: AI기본법 §31, 2026-01-22) — artifact 표시(§31②)는 구현됨. AI Chat/SWOT 등 라이브 AI 화면의 §31①(사전 고지)이 약관/면책배너로 충족되나?
- **Q-A1** earnings "Action 권장"(H3): 실적 직전 본인-룰 재확인 문구가 §17 "구체적 매매 권유"인가?
- **Q-A2** AI "애널리스트" 페르소나(H4): AI에 분석가 역할 부여 시 위반 주체(회사 vs AI) 판단?
- **Q-A3** "적중률" 과거 통계 라벨(H2) 허용 범위? (Q1-Q15 의견서에 포함)
- **Q-S1 연동** brag 축하 이메일(M1) transactional 분류 가능 여부 / quarterly thesis verdict(G1) §101 ④ 해당 여부.

---

## 8. 권고 실행 순서

1. **지금(변호사 불요·코드)** — H1 Alpaca 출처 / H2 적중률 라벨 / H3 Action·권장 / H4 AI 페르소나 4건 수정 → 재감사. (회귀테스트: forbidden_terms·legal scrub)
2. **SHIP_BLOCKERS.md** — M2 이메일 면책 2건을 A-NEW로 추적 등록.
3. **변호사 큐** — Q-R1(최우선), Q-R2, Q-A1~3 추가.
4. **유지** — AI_CHAT_ENABLED OFF 고정(Q-R1 답 전 재활성화 금지).
5. **마케팅 카피** — 백테스트 효능 주장 금지(HANDOVER v55 게이트), G1~G3 프레이밍 순화는 변호사 판단 후.

---

## 9. 2차 재감사 + 전수 검증 (2026-06-03 추가)

3-agent 재투입(post-fix) + 메인 실측. H1~H4 **검증 PASS**(렌더 directive 금지어 0, H4 canonical 통일 정당질문 19/20·빈브리프 회귀 없음).

**추가 수정 (이번 라운드, 회귀 pass)**
- 위생 2건: dd_checklist AI 프롬프트 "권유 글/권유만"→"안내문/안내만"(`dd_checklist_service.py`), self_audit fallback "매수 결정"→"거래 결정"(`self_audit_service.py:306`, is_compliant False→True).
- 🔴 **신규 H2-i18n**: `_i18n.py`의 "적중률"(FORBIDDEN 등록어) ×2(`win_rate`:110 / `section_winrate`:177) + EN 짝 2개 → "일치율 / Consistency". H2가 템플릿만 고쳐 i18n SoT를 놓쳤던 누락. 현재 dead label(템플릿 미참조)이나 forbidden 용어라 제거. **이제 `services/artifacts` 전체 "적중률" 0건.**
- **AI dead-code 6곳 KILL** (5 서비스): `import ai_service`(reorg 고아, 항상 ModuleNotFoundError→fallback)를 제거하고 deterministic fallback만 남김. dd_checklist/self_audit/quarterly(_thesis_checks+_mdna)/risk_board/year_end. **activate 0건** — 근거: reorg 고아·deterministic fallback이 실제 안전 출력·v55 전략(AI 서사 탈피)·Anthropic 크레딧 0·출시 직전 LLM 컴플라이언스 표면. quarterly _thesis_checks kill로 **G1 AI-verdict 분기 제거**(stored status/pending만). `test_self_audit_scrub_no_corrupt.py`는 죽은 AI 경로 patch 의존이라 safe_scrub SoT 직접검증 + fallback 컴플라이언스 가드로 재작성.

**전수 검증 — 변경 불요 확정 (증거 기반)**
- **승률 / Win Rate / Hit rate**(self_audit·year_end·quarterly cover/label, persona_warnings, daytrader opener): forbidden 미등록 + **유저 본인 거래 회고 통계 = §101 SAFE**. "승률"을 "일치율"로 바꾸면 의미 왜곡(win rate≠consistency) → 보류.
- **sample_data.py Alpaca 8건**: 소비처 = `routes/admin_preview.py`의 `_is_admin()` **fail-closed 게이트**(ADMIN_EMAILS 없으면 전원 차단, 비admin 404)뿐. burn_rate:472는 주석. **유저 비노출 → 출시 이슈 아님**(내부 위생만).
- insider_mirror "Mirror Backtest" KPI: "참고용·미래보장 아님" 고지 기존 → MED 유지(보류 가능).

**잔여 권고**
- `test_i18n_artifact_compliance.py`는 _i18n docstring이 "존재한다"고 주장하나 **실재 없음** — i18n 값의 forbidden-term 가드 테스트 부재(이번 적중률 누락의 근본 원인). 작은 guard 테스트 추가 권장.
- AI 서사 기능을 후일 살리려면(year_end 서한 등): import 수정 + safe_scrub + hard-reject 게이트 + 크레딧 + 컴플라이언스 패스를 동반한 **의도적 post-launch feature**로.

**누적 변경 파일(2일·2라운드)**: earnings_prebrief(svc+tpl) · brag_card/insider_mirror/self_audit tpl · _i18n · dd_checklist/self_audit/quarterly/risk_board/year_end svc · test_self_audit_scrub_no_corrupt · SHIP_BLOCKERS · legal_question_queue(memory). 회귀 그린.

---
*4-agent telemetry: legal-kr-fintech(144k tok, BLOCKER2→재평가 HIGH) · legal(210k, HIGH2) · compliance-gatekeeper(80k, 면책매트릭스) · regulatory-monitor(49k, 규제델타). 메인 검증 5건 grep/read 실측.*
