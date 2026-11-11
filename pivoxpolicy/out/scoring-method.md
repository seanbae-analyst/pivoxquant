# 평가 코드북 — 어떻게 레벨을 매기나

평가자는 레벨(0~3)을 **직접 고르지 않는다.** 아래 각 신호를 공개 자료에서 확인해
`observed: true/false/null` 과 **증거 수준**(primary/press/vendor)만 적는다. 레벨은 도출된다:

- 신호가 **발화** = `observed: true` 이고 증거 수준이 그 신호의 최소 요건 이상.
- 차원 레벨 = 발화한 신호들의 **최고 레벨**. 하나도 발화 안 했지만 하나라도 `false` 로 확인했으면 **0**.
  모든 신호가 `null`(미확인)이면 **미평가**(분모에서 뺌).
- `[primary 필요]` 신호는 1차 증거라야 발화한다 — **보도만으로는 그 레벨에 도달 못 한다.**

증거 수준: **primary** 공시·제재문·감독기관/회사 원문 · **press** 언론 보도 · **vendor** 보안업체 분석 · **unverified** 미확인.

## agent_control

### 1. 에이전트 인벤토리 (Agent inventory)
- 질문: 회사가 운영 중인 AI 에이전트·그 접근권한·책임자를 등록·관리하는 증거가 있는가
- 어디서 보나: 10-K Item 1C, 사업보고서 정보보호 현황, KISA 정보보호 공시, AI 거버넌스 보도자료
- 근거: FSB SP3 (documentation of AI use) · inventory attributes (PDF p.30-31), NYDFS 500.13(a) asset inventory (owner·location·classification·support expiration·RTO), OWASP ASI04 Agentic Supply Chain (구성요소 가시성), COSO Control Activities, Basel PSMOR P6 identification and assessment
- 신호:
    - **L1** `mentions_ai_governance`: AI 활용·거버넌스를 공개 자료에서 언급하는가
    - **L2** `discloses_ai_usecases` `[primary 필요]`: AI 사용 사례·책임 부서를 구체적으로 공개하는가(예: 10-K Item 1C)
    - **L3** `verified_inventory` `[primary 필요]`: 제3자 점검·감독기관 보고로 에이전트 인벤토리 존재가 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 2. 공급자·제3자 AI (Vendor / third-party AI)
- 질문: 외부 AI·에이전트 공급자에 대한 취약점 통지·로그·계약 통제 증거가 있는가
- 어디서 보나: IT 위탁 공시, 제재 공개안의 위탁 관련 지적, 10-K 제3자 리스크
- 근거: FSB SP12 Third-party AI risk management, NYDFS 500.11 Third-party service provider security policy, OWASP ASI04 Agentic Supply Chain Vulnerabilities, MAESTRO Layer 7 Agent Ecosystem, Basel PSMOR P10 ICT risk (third-party dependencies), 금융회사 정보처리 업무 위탁 규정(KR, 에이전트 미언급 — 레지스트리 kr-outsourcing-regulation)
- 신호:
    - **L1** `mentions_third_party_risk`: 외주·제3자 리스크 관리를 언급하는가
    - **L2** `specifies_ai_vendor_controls` `[primary 필요]`: AI 공급자 계약·점검 항목(취약점 통지·로그 제공 등)을 구체화하는가
    - **L3** `verified_vendor_review` `[primary 필요]`: 위탁 점검 결과·감독기관 확인이 공개되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 3. 고유 식별자 (Unique agent ID)
- 질문: 에이전트마다 별도 계정·식별자를 두고 사람 신원에 연결하는 증거가 있는가
- 어디서 보나: 정보보호 공시 접근통제 항목, 제재 공개안 로그 지적
- 근거: FSB §2.3 Visibility — individual unique identifiers to each AI agent (PDF p.30, 원문 대조), NIST NCCoE agent identity concept paper (identification·authentication·authorization, link to user identities), OWASP ASI03 Identity and Privilege Abuse, 전자금융감독규정 §13①1 (개인별 인증수단 — 사람 기준), NYDFS 500.7 Access privileges
- 신호:
    - **L1** `mentions_access_control`: 계정·접근통제 원칙을 언급하는가
    - **L2** `separates_agent_accounts` `[primary 필요]`: 에이전트·서비스 계정을 사람 계정과 구분해 관리한다고 구체화하는가
    - **L3** `verified_agent_identity` `[primary 필요]`: 로그·점검에서 에이전트 계정이 사람과 식별됨이 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 4. 최소 권한 (Least privilege)
- 질문: 신뢰할 수 없는 입력이 섞일 때 에이전트의 외부 전송·실행을 막는 증거가 있는가
- 어디서 보나: 정보보호 공시, 레드팀 결과 공개, 제재 공개안
- 근거: FSB §3.7 agent-specific: isolation, limit interaction with external environment, FSI 17개 항목 중 '실행 권한 및 격리 관리' (press, fnnews 2026-10-07), OWASP ASI02 Tool Misuse · ASI03 Identity and Privilege Abuse · ASI05 Unexpected Code Execution, NYDFS 500.7, FIDES 정보흐름통제(덱 슬라이드 13 — 벤치마크, 은행 배치 아님), 전자금융감독규정 §13①1 (최소권한 — 사람 기준)
- 신호:
    - **L1** `mentions_least_privilege`: 최소권한 원칙을 언급하는가
    - **L2** `specifies_source_based_limits` `[primary 필요]`: 출처 기반 행위 차단·도구 권한 제한(샌드박스 등)을 구체화하는가
    - **L3** `redteam_verified_isolation` `[primary 필요]`: 레드팀·점검에서 권한 격리가 검증되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 5. 사람 승인 (Human approval)
- 질문: 고위험 행위에 사람 승인 게이트를 두는 증거가 있는가(모든 행위 승인은 피로를 부름)
- 어디서 보나: AI 가이드라인 수용 공시, 내부통제 보고
- 근거: FSB §3.7 risk-based triggers for human approval · SP10 Human oversight, FSI '도구 실행 및 승인 통제' (press), OWASP ASI09 Human-Agent Trust, EU AI Act Art.14 Human oversight, FINRA 2026 Oversight Report (autonomous action without human validation — 레지스트리 us-finra-2026-oversight-report), 금융위 금융분야 AI 가이드라인 2026-06 보조적 역할 원칙(자율)
- 신호:
    - **L1** `mentions_human_in_loop`: 사람 개입·보조적 역할 원칙을 언급하는가
    - **L2** `specifies_risk_based_approval` `[primary 필요]`: 고위험 행위에 승인이 필요하다는 위험 기반 트리거를 구체화하는가
    - **L3** `verified_approval_gate` `[primary 필요]`: 승인 로그·점검으로 게이트 작동이 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 6. 감사 기록 (Audit trail)
- 질문: 에이전트의 입력·출처·도구 호출을 기록하는 증거가 있는가
- 어디서 보나: 정보보호 공시 로그 항목, 제재 공개안(로그 평문·미보존 지적)
- 근거: FSB §2.3 Traceability (what triggered · what accessed · what steps · within permissions), NIST NCCoE (logging, data-flow·provenance tracking), NYDFS 500.6 Audit trail, EU AI Act Art.12 Record-keeping (automatic logs over lifetime), OWASP ASI01 Goal Hijack · ASI06 Memory & Context Poisoning (입력 출처 기록 필요), 전자금융감독규정 §13①9 · ② (사람 기준)
- 신호:
    - **L1** `mentions_logging`: 로그 보존 원칙을 언급하는가
    - **L2** `specifies_agent_log_items` `[primary 필요]`: 입력·출처·도구 호출 등 에이전트별 로그 항목을 구체화하는가
    - **L3** `verified_log_retention` `[primary 필요]`: 로그 보존·분석이 점검·제재문에서 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 7. 즉시 중단 (Kill switch)
- 질문: 에이전트를 즉시 멈추고 권한을 회수하는 수단과 그 정기 테스트 증거가 있는가
- 어디서 보나: 레드팀 결과, 비상대응 훈련 공개
- 근거: FSB §3.7 'implementing and testing risk-based kill-switch mechanisms' · 'stop safely' red teaming, EU AI Act Art.14(4)(e) stop button → halt in a safe state, FSI '자율 실행 제한 및 중단 여부' (press), OWASP ASI08 Cascading Failures · ASI10 Rogue Agents, NYDFS 500.16 Incident response and BCM
- 신호:
    - **L1** `mentions_emergency_stop`: 비상 중단·대응 체계를 언급하는가
    - **L2** `specifies_kill_switch` `[primary 필요]`: 즉시 중단·권한 회수 수단과 책임을 구체화하는가
    - **L3** `tested_kill_switch` `[primary 필요]`: 중단 메커니즘 테스트 결과가 확인되는가(FSI 레드팀 등)
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

## connection

### 8. 경고 수신·전달 (Warning receipt & relay)
- 질문: 감독기관·AI회사의 경고가 내부로 전달되고 조치로 이어진 기록이 있는가
- 어디서 보나: 보도자료, 국회 제출자료, 제재 공개안, 사고 경위 발표
- 근거: 덱 슬라이드 5 '경고→조치 연결 실패'(FSC 09-03 경고, 09-17 세미나, 09-27 공격), COSO Information and Communication, Basel PSMOR P8 monitoring and reporting, CISA BOD 26-04(2026-06-10 — BOD 22-01 을 대체한 현행 패치 기한 지침, 레지스트리 us-cisa-bod-26-04), NYDFS 500.4(d)(3) senior governing body regularly receiving reports, 전자금융감독규정 §37-2(이행계획만, 기한 없음)
- 신호:
    - **L1** `acknowledged_warning`: 감독기관·AI회사 경고를 인지·공유했다고 언급하는가
    - **L2** `relayed_to_action` `[primary 필요]`: 경고→부서 전달→조치 결정 경로가 구체적으로 확인되는가
    - **L3** `verified_action_taken` `[primary 필요]`: 조치 이행이 제3자·감독기관 자료로 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 9. 보고·에스컬레이션 (CISO-to-management escalation)
- 질문: 보안 책임자(CISO)의 보고가 경영진 결정·조치로 이어진 기록이 있는가
- 어디서 보나: 제재 공개안(롯데카드: CISO 보고 뒤 경영진 조치 없음), 내부통제 보고
- 근거: 덱 슬라이드 5·14 노트 '내부통제 연결 실패', NYDFS 500.4(b)(c)(d) CISO annual written report · board oversight, COSO Control Environment · Information and Communication, Basel PSMOR P1 board · P5 senior management, FSB SP1·SP2 board and senior management roles, 전자금융거래법 §21-2 CISO · 전자금융감독규정 §8-2 정보보호위원회
- 신호:
    - **L1** `mentions_reporting_line`: CISO 보고 체계가 있다고 언급하는가
    - **L2** `management_acted_on_report` `[primary 필요]`: 보고 후 경영진 조치가 구체적으로 확인되는가
    - **L3** `verified_report_action_record` `[primary 필요]`: 보고·조치 기록이 제재문·감사에서 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

## testing

### 10. 테스트 빈도 (Test frequency)
- 질문: 침투·모의 테스트를 얼마나 자주 하는가(상시 AI 테스트에 가까운가)
- 어디서 보나: FSS·FSI 운영기준, 국회 제출자료, 정보보호 공시
- 근거: 덱 슬라이드 15 테스트 4요소 중 ①빈도 ②범위 ④AI 활용, FSB SP11 (AI cyber scenarios into tests and exercises) · SP9 testing and ongoing monitoring, NIST IR 8596 Defend/Thwart, FSI 17개 항목(레드티밍 기준, press) · CSA Agentic AI Red Teaming Guide · MAESTRO 7 layers, NYDFS 500.5 Vulnerability management, EU AI Act Art.9 risk management (testing), 전자금융감독규정 §37-2 · 금감원·금보원 2026 침투테스트 운영기준(04-29, 원문 미확보)
- 신호:
    - **L1** `mentions_periodic_test`: 정기 점검·침투테스트를 한다고 언급하는가
    - **L2** `discloses_cadence` `[primary 필요]`: 연 N회 등 테스트 주기가 공개되는가
    - **L3** `verified_continuous_testing` `[primary 필요]`: 상시·AI 기반 테스트 수행이 수치·감독기관 자료로 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 11. 테스트 범위 (Test scope)
- 질문: 인증 범위 밖 외부접점(브로커·영업지원 등)까지 테스트하는가
- 어디서 보나: 사고 경위(침입 경로), 인증 범위 공개, 보도
- 근거: 덱 슬라이드 15 테스트 4요소 중 ①빈도 ②범위 ④AI 활용, FSB SP11 (AI cyber scenarios into tests and exercises) · SP9 testing and ongoing monitoring, NIST IR 8596 Defend/Thwart, FSI 17개 항목(레드티밍 기준, press) · CSA Agentic AI Red Teaming Guide · MAESTRO 7 layers, NYDFS 500.5 Vulnerability management, EU AI Act Art.9 risk management (testing), 전자금융감독규정 §37-2 · 금감원·금보원 2026 침투테스트 운영기준(04-29, 원문 미확보)
- 신호:
    - **L1** `mentions_core_scope`: 주요 시스템을 점검한다고 언급하는가
    - **L2** `includes_external_touchpoints` `[primary 필요]`: 외부접점·주변 시스템을 테스트 범위에 포함한다고 구체화하는가
    - **L3** `verified_full_touchpoint_coverage` `[primary 필요]`: 전체 외부접점 테스트 수행이 확인되는가(사고 경로가 커버되었나)
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 12. 사후조치 (Remediation follow-up)
- 질문: 발견한 취약점을 기한 내 조치하고 재점검하는가
- 어디서 보나: FSS 미조치 취약점 자료, 제재 공개안(패치 미실시)
- 근거: 덱 슬라이드 15 ③ 사후조치(패치 기한+재테스트), CISA BOD 26-04 (노출·KEV·자동화·영향 4변수로 3일/14일/60일 — BOD 22-01 의 '2주' 를 2026-06-10 대체), NYDFS 500.5 Vulnerability management · 2026-10-22 PHP Alert, Basel PSMOR P7 change management, 전자금융감독규정 §37-2(기한 없음), COSO Monitoring Activities
- 신호:
    - **L1** `mentions_remediation_plan`: 취약점 보완조치 계획을 세운다고 언급하는가
    - **L2** `specifies_patch_deadline` `[primary 필요]`: 패치 기한·재점검 절차를 구체화하는가
    - **L3** `verified_timely_remediation` `[primary 필요]`: 기한 내 조치·재점검 완료가 수치로 확인되는가(미조치 건수 등)
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 13. AI 활용·공동훈련 (AI coverage / joint drills)
- 질문: 테스트에 AI를 쓰는가, 소규모 기관은 공동훈련으로 보완하는가
- 어디서 보나: 국회 제출자료(AI 활용 침투테스트 수), FSI 공동훈련
- 근거: 덱 슬라이드 15 테스트 4요소 중 ①빈도 ②범위 ④AI 활용, FSB SP11 (AI cyber scenarios into tests and exercises) · SP9 testing and ongoing monitoring, NIST IR 8596 Defend/Thwart, FSI 17개 항목(레드티밍 기준, press) · CSA Agentic AI Red Teaming Guide · MAESTRO 7 layers, NYDFS 500.5 Vulnerability management, EU AI Act Art.9 risk management (testing), 전자금융감독규정 §37-2 · 금감원·금보원 2026 침투테스트 운영기준(04-29, 원문 미확보)
- 신호:
    - **L1** `mentions_ai_security_intent`: 테스트에 AI 보안을 활용할 의향을 언급하는가
    - **L2** `specifies_ai_test_or_drill` `[primary 필요]`: AI 기반 테스트·공동훈련 참여를 구체화하는가
    - **L3** `verified_ai_test_count` `[primary 필요]`: AI 테스트·공동훈련 수행이 수치로 확인되는가(78건 중 9건 등)
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

## response

### 14. 탐지 소요시간 (Detection latency)
- 질문: 공격 시작부터 인지까지 걸린 시간을 알 수 있고, 짧은가
- 어디서 보나: 사고 경위 발표, 국회 제출 탐지시간 자료
- 근거: 덱 슬라이드 5 탐지 시간 행 · 슬라이드 4 'AI 회사가 탐지', AcciMap ④ 수준 '늦은 탐지'(fin-breach_ai-cases-accimap K-e), NIST IR 8596 Defend, NYDFS 500.14 Monitoring · 500.17 72h notice(기준 시점 = 'determining' 이후), 금융위 12개 점검항목 '24시간 관제 미구축'(2026-10-14), Basel PSMOR P8
- 신호:
    - **L1** `mentions_monitoring`: 24시간 모니터링 등 탐지 체계가 있다고 언급하는가
    - **L2** `discloses_detection_time` `[primary 필요]`: 공격 시작→인지 소요시간이 공개되는가(시간 단위)
    - **L3** `verified_fast_detection` `[primary 필요]`: 짧은 탐지시간이 사고 경위·국회자료로 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 15. 공개·신고 (Disclosure & notification)
- 질문: 사고를 신고·공시·고객 안내했는가, 시점이 적절한가
- 어디서 보나: DART·EDGAR 공시, 개인정보위 신고 공표, 사과문
- 근거: 전자금융감독규정 §37-4 24시간 내 금융위 보고(레지스트리 kr-efsr-art37-2 관련) · 전자금융거래법 §21-5, NYDFS 500.17(a) 72 hours, SEC Reg S-K Item 106 · Form 8-K Item 1.05, Basel PSMOR P12 public disclosures, NIS2 Art.23 24h/72h/1개월(EU 비교), AcciMap ↑ 되먹임(incident reports)
- 신호:
    - **L1** `mentions_notification`: 고객 안내·신고를 했다고 언급하는가
    - **L2** `specifies_disclosure_timing` `[primary 필요]`: 신고·공시·안내의 시점과 내용이 구체적인가
    - **L3** `verified_timely_disclosure` `[primary 필요]`: 적시 신고·공시가 감독기관·공시시스템으로 확인되는가(DART·8-K)
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).

### 16. 재발방지 (Remediation & recurrence prevention)
- 질문: 재발방지 대책을 세우고 이행이 확인되는가
- 어디서 보나: 제재 공개안 개선요구, 재발방지 대책 공개
- 근거: AcciMap 사고 뒤 ③·④ 요인(fin-breach_coinbase-accimap §3·§5), COSO Monitoring Activities · Risk Assessment, Basel PSMOR P7 change management · P9 control environment, NYDFS 500.16 incident response (lessons learned), FSB SP4 Organisational adaptability, EU AI Act Art.9 (iterative risk management)
- 신호:
    - **L1** `mentions_prevention`: 재발방지 방침을 언급하는가
    - **L2** `specifies_prevention_plan` `[primary 필요]`: 재발방지 대책이 대상·일정까지 구체적인가
    - **L3** `verified_prevention_implemented` `[primary 필요]`: 이행·개선이 감독기관 점검으로 확인되는가
- 레벨 0 = 위 신호를 공개 자료에서 하나도 확인 못 함 (증거 없음 ≠ 통제 없음).
