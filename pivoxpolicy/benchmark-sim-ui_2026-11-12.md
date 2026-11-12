# 모의 테스트 UI·시각화 벤치마킹 — 2026-11-12

대상 6개: ServiceNow IRM(+ AI Control Tower) · Microsoft Purview(Compliance Manager · DLP 시뮬레이션 · DSPM for AI) · Diligent AuditAI · Rutile · Microsoft Agent Governance Toolkit(AGT).
GABA · IRAME 은 이 이름으로 찾지 못했다(아래 '못 찾은 것').
**읽은 범위**: 공식 문서·제품 페이지의 글. 화면 캡처는 볼 수 없었다 — 색·차트 모양은 문서가 글로 적은 것만 옮겼다. Diligent 는 자사 제품 페이지가 404 라 보도 기사 2건 기준(벤더 주장).

---

## 1. 제품별로 본 것

### ServiceNow IRM — Risk heatmap workbench
출처: [Risk heatmap workbench](https://www.servicenow.com/docs/r/Z61H6JNUJXKe8NNPQzK7MQ/8K8kJpbtJ138PhjVD0w8Hg) (Australia 릴리스 문서, 2026-04-28 갱신)
- **영향(X) × 가능성(Y) 히트맵.** 칸 표시를 고른다 — 위험 개수 / 위험 ID / 위험 이름.
- **이동 표시: 고유(inherent) → 잔여(residual) → 목표(target).** 통제 전 · 통제 후 · 도달하려는 수준을 한 그림에.
- **추세:** 최근 5번 평가의 점수 이동(끄고 켤 수 있다). 위험 성향(appetite) 상태도 히트맵 위에.
- **상호작용:** 위험에 마우스 → 요약(담당자·조직·분류), 칸 안의 위험을 고르면 **오른쪽 패널**에 상세, 축 값을 누르면 그 조합만. '360° 보기'(조직·통제·평가·대응 작업 연결).
- 상위 N 필터 · 조직 필터 · 조건 필터 저장 · 이미지 내려받기 · 데이터 복사 · 확대(immersive) 보기.

### Microsoft Purview — Compliance Manager
출처: [compliance-manager-setup](https://learn.microsoft.com/en-us/purview/compliance-manager-setup) · [scoring](https://learn.microsoft.com/en-us/purview/compliance-score-calculation) · [assessments](https://learn.microsoft.com/en-us/purview/compliance-manager-assessments)
- **점수가 맨 위에 크게:** "featured prominently at the top" — 개선 조치 점수의 합으로 낸 백분율.
- **점수 분해 두 가지:** 범주별(정보 보호 · 기기 관리 …) / 평가(규제 템플릿)별 진행률.
- **핵심 개선 조치(Key improvement actions):** 지금 할 수 있는 상위 조치 목록 → '전체 보기'.
- **조치 가중치:** 예방 의무 27 · 예방 재량 9 · 탐지 의무 3 · 탐지 재량 1 · 교정 의무 3 · 교정 재량 1. 같은 조치가 평가 두 개에 걸리면 두 번 센다.
- **평가(규제 템플릿) 화면:** 진행 막대 · 통제 상태 분해 차트(통제군별) · 통제 표(제목·상태·ID·획득 점수·내 조치·MS 조치) · 상태 이름 Passed / Failed / None / Out of scope / In progress. 템플릿 360개 이상.
- **규제 템플릿이 바뀌면:** 평가 옆에 "Pending update" 표시 + 상세 화면 배너 "Review update" → 플라이아웃에 **점수·진행·바뀐 조치·통제 수에 미치는 영향**을 보여 주고 '수락' 또는 '나중에'. 수락 전까지 표시가 남는다.
- 필터를 걸면 점수가 바로 다시 계산되고 "얻은 점수 / 가능한 점수" 로 보인다.

### Microsoft Purview — DLP 시뮬레이션 모드 · DSPM for AI
출처: [DLP simulation mode](https://learn.microsoft.com/en-us/purview/dlp-simulation-mode-learn) · [DSPM for AI (classic)](https://learn.microsoft.com/en-us/purview/dspm-for-ai)
- **시뮬레이션은 실제 집행과 화면을 나눈다.** 탭 3개: 시뮬레이션 개요(상태 · 스캔 항목 수 · 일치 수 · 위치별) / 검토할 항목(일치한 항목 목록) / 경보(실제 경보 콘솔과 같은 모양, 그러나 실제 콘솔로는 안 감).
- **복사 → 고친 사본을 시뮬레이션 → 좋으면 원본 끄고 사본 집행.** "v1 → v2" 조정 흐름.
- DSPM for AI: 시작하기 → **권장 조치(one-click 정책)** → 보고서 → 정책 → **앱·에이전트 목록**(에이전트마다 접근한 민감 데이터와 걸린 정책) → 활동 탐색기(이벤트 표) → 데이터 위험 평가(Overview · Identify · Protect · Monitor 탭).

### Diligent — AuditAI (2026-03, 보도 기준)
출처: [fintech.global](https://fintech.global/2026/03/11/diligent-introduces-auditai-for-ai-driven-internal-audits/) · [Accounting Today](https://www.accountingtoday.com/news/diligent-launches-auditai-for-proactive-compliance)
- 감사 계획 제안 · **"기존 통제와 테스트에 영향을 주는 규제 변경을 표시"** · 규제 공백에 통제 추천 · 증거 요청 자동화.
- **위험 → 통제 → 감사 → 발견사항 관계 추적**, 식별부터 이사회 보고까지.
- 사람 승인 · 추적성을 "workflow 안에" — 화면 설명은 없음. 수치(관리 시간 70% 감소 등)는 벤더 주장.

### Rutile — Agentic IAM
출처: [rutile-landing.pages.dev](https://rutile-landing.pages.dev/) · [/product](https://rutile-landing.pages.dev/product/) · [/docs](https://rutile-landing.pages.dev/docs/) · [/ai-governance](https://rutile-landing.pages.dev/ai-governance/)
(같은 이름의 GitHub [Lercas/rutile](https://github.com/Lercas/rutile) 은 '에이전트용 비밀 브로커' CLI 로, 이 사이트와 연결 근거가 없다.)
- **제어 흐름 한 줄:** 에이전트 요청 → 정책 검사 → JIT 허가 → 감사 기록. 제품 흐름: 등록 → 평가 → 허가 → 감시.
- **요청 한 건을 카드로:** Agent ID · Subject(Procurement-Agent) · Action(Read_Supplier_Risk) · TTL 15m · "JIT Approved" · "Policy seal / Delegation verified".
- **결정 종류:** 허용 · 거부 · 가림 · 승인 요청 · 속도 제한 · 격리 · 회수 · 종료. 기본은 거부.
- 위험 카드 5개(섀도 에이전트 · 과권한 · 도구 오용 · 감사 사슬 없음 · 킬 스위치 없음), 위협 → 통제 → 기능 표, 프레임워크 매핑은 정성적(조항 ID 없음).
- 대시보드 화면 설명은 없음 — 마케팅 사이트.

### Microsoft Agent Governance Toolkit (AGT, 오픈소스, 2026-04)
출처: [블로그](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit/) · [README](https://github.com/microsoft/agent-governance-toolkit) · OWASP 매핑 문서 · 감사 명세 · governance-dashboard 예제
- **결정:** allow / deny / escalate(사람 승인) / warn(허용하되 표시). 로그에 **이유(reason) · 걸린 규칙(matched_rule) · 정책 버전**.
  예: `Action denied by policy rule 'block-destructive': Destructive operations require human approval`
- **OWASP Agentic Top 10 커버리지 표:** `ASI ID | Risk Title | Coverage | Primary Component` — ✅ Full / ⚠ Partial / Gap. 자체 평가 "7/10 Full, 3/10 Partial, 0 Gaps"(ASI04·06·09 Partial) — 인증 아님을 스스로 밝힌다.
- **거버넌스 대시보드(예제, 모의 데이터):** Fleet Overview(KPI 카드 · 유형/상태/위험/담당별 에이전트) · Shadow Agents · Lifecycle · **Policy Feed(허용/거부/승인 요청 수, 가장 많이 거부된 행위)** · **Trust Heatmap(에이전트 × 에이전트 신뢰 점수 행렬)**.
- 준수 보고서 필드: 통제 충족 · 부분 · 실패 · 미평가 수 → `compliance_score = met / total × 100`. 드라이런·섀도 모드는 없다.

---

## 2. 공통 패턴 — 여섯 곳이 같은 말을 한다

| 패턴 | 어디서 | 우리 모의 테스트에 지금 있나 |
|---|---|---|
| **맨 위 한 줄 자세(posture)** — 큰 숫자 하나 + 분해 | Purview 점수 · AGT Fleet KPI | 없음 — 결과가 섹션마다 흩어져 있다 |
| **통제 전 → 지금 → 목표 이동** | ServiceNow inherent → residual → target | 없음 — '지금' 한 상태만 |
| **행렬 히트맵 + 칸 클릭 → 옆 패널** | ServiceNow 히트맵 · AGT Trust Heatmap | 원형 표는 있으나 관할 비교가 따로, 색 행렬 없음 |
| **개선 조치 순위 — 효과·종류·의무 여부** | Purview 조치(예방 27 / 탐지 3 / 교정 3, 의무/재량) · DSPM 권장 | '다음에 켤 통제' 목록이 있으나 효과·종류·규제 근거가 한 줄에 없음 |
| **현재 vs 변경안 비교** | DLP 시뮬레이션 v1 → v2 | 없음 — 바꾸면 원래 값이 사라진다 |
| **결정 로그 — 결정 · 걸린 규칙 · 이유** | AGT reason/matched_rule · Rutile 결정 8종 · 요청 카드 | 단계 설명은 있으나 '결정' 형식이 아님 |
| **프레임워크 커버리지 표 Full / Partial / Gap** | AGT OWASP 표 · Rutile 매핑 · Purview 템플릿 | 없음 — OWASP 근거가 원형에만 적혀 있다 |
| **규제 변경 → 영향 미리보기 → 수락** | Purview Pending update · Diligent 규제 변경 표시 | 이력·반영 대기는 있으나 '이 후보가 들어오면 무엇이 바뀌나' 는 없음 |
| **추적 사슬** | Diligent 위험→통제→감사→발견 · ServiceNow 360° | 사건 → 실패 통제는 있으나 → 규제 조문 → 원형까지 한 화면에 없음 |

## 3. 제안 — 우리 모의 테스트에 가져올 것 (우선순위)

디자인 원칙은 그대로(Vantablack + Bronze · Pretendard · 알약·글로우 없음 · 빨강/초록 없음). 색은 결과 4단계를 브론즈 명도로만.

1. **자세 띠 (Purview 점수 + ServiceNow 이동)** — 맨 위 한 줄에 KPI 3개, 각각 '통제 없음 → 지금 → 모두 AI 까지' 이동:
   원형 11개 결과(막힘·축소·발생·공격면 없음 개수) · 실제 사건 막힘 범위(/25) · OWASP ASI 커버리지(Full/Partial/Gap).
2. **원형 × 프리셋 히트맵 (ServiceNow + AGT)** — 행 = 원형 11개, 열 = 통제 없음 · 한국 강제/가이드 · 미국 · EU · 국제 · 모두 AI · **지금 설정**.
   칸 색 = 결과, 칸을 누르면 **오른쪽 서랍**에 단계별 결정 로그. 지금의 원형 표와 '프리셋 비교' 를 이것 하나로.
3. **개선 조치 표 (Purview)** — 조치(실무 문장) · 통제·층 · 종류(예방 / 탐지 / 교정 = 우리 단계 배치 전·사용 중 / 감사 / 중단) ·
   효과(사건 막힘 +N · 바뀌는 원형 k개) · 규제(한국·미국·EU 강제/자율/없음) · [변경안에 넣기]. Purview 처럼 '의무(구속력)' 조치를 먼저.
4. **결정 로그 형식의 단계 (AGT · Rutile)** — 원형 맨 위에 '에이전트 요청 카드'(에이전트 · 행위 · 대상 · 도구 권한),
   단계마다 결정(차단 / 승인 요청 / 범위 제한 / 기록 / 격리·회수) · 걸린 통제 · 이유 한 줄.
5. **OWASP Agentic Top 10 커버리지 표 (AGT)** — ASI01~10 × 지금 설정: 그 위험의 원형이 막힘 = Full, 축소 = Partial, 발생 = Gap.
   AGT 처럼 '자체 계산 · 인증 아님' 을 적는다.
6. **현재 vs 변경안 (DLP 시뮬레이션)** — '변경안 만들기' 를 누르면 지금 설정이 복사되고, 바꾼 만큼 모든 숫자 옆에 차이(+3 · 막힘→축소)를 보인다.
7. **규제 반영 영향 미리보기 (Purview Pending update)** — 반영 대기 후보마다 '반영 대기' 표시. 실제 코딩 전에는 영향을 계산할 수 없으니,
   이력 쪽에 '이 갱신으로 바뀐 것' 을 Purview 의 Review update 플라이아웃 모양으로 보여 주는 데까지.

가져오지 않을 것: 단일 점수 하나로 회사를 등급 매기기(우리 평가 프로필 원칙 — 단일 등급 없음), 신뢰 점수 0~1000(근거 없는 수치),
AI 자동 추천 문구(코딩·판정이 사람+두 팀 블라인드인 것과 섞이면 안 된다).

## 4. 기능 비교 — 무엇을 할 수 있나

추가 출처: ServiceNow [IRM 제품](https://servicenow.com/products/integrated-risk-management.html) · [GRC](https://www.servicenow.com/grc) · AI Control Tower [보도자료](https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-expands-AI-Control-Tower-to-discover-observe-govern-secure-and-measure-AI-deployed-across-any-system-in-the-enterprise/default.aspx)(2026-05, Discover · Govern · Secure · Observe · Measure, 'AI Passport' — 에이전트별 허용 행위·접근 시스템·책임자, 데모에서 '25달러 미만 환불만') ·
Purview [개선 조치 작업](https://learn.microsoft.com/purview/compliance-manager-improvement-actions)(담당 지정 · 증거 업로드 · 자동 테스트 · 경보) · Diligent [One Platform 개요](https://help.highbond.com/helpdocs/highbond/en-us/Content/diligent_one_platform_overview.htm).
✓ = 문서에 있음 · ~ = 부분이거나 벤더 주장만 · — = 찾지 못함. ServiceNow 칸은 IRM + AI Control Tower 를 합쳐 본다.

| 기능 | ServiceNow | Purview | Diligent | Rutile | MS AGT | **우리 지금** |
|---|---|---|---|---|---|---|
| 에이전트·AI 인벤토리 | ✓ Control Tower Discover | ✓ DSPM 앱·에이전트 목록 | — | ✓ 등록부(ID·담당·목적·도구·위험 등급·만료) | ✓ Fleet · Shadow AI 발견 | 가상 프로필 8개만 |
| 규제·프레임워크 템플릿 | ✓ 권한 문서(SOC2·ISO …) | ✓ 템플릿 360+ (AI 템플릿 별도) | ~ | ~ 정성 매핑 | ✓ OWASP · EU AI Act · SOC2 매핑 | ✓ 문서 32 × 7통제 × 두 층 + 조문 |
| 규제 변경 → 영향 | ~ 규제 소스 연결 | ✓ Pending update + 점수 영향 미리보기 → 수락 | ~ '기존 통제에 영향 주는 변경 표시'(주장) | — | — | ✓ 감지 · 이력 · 케이스 경고 / 미리보기 — |
| 통제 테스트 · 증거 | ✓ 자동 테스트 · KRI/KCI 지표 | ✓ 자동 테스트 + 증거 업로드 + 테스터 역할 | ✓ SOX 테스트 · 연속 통제 감시 | ✓ 감사 증거 | ✓ `agt verify --evidence` | — (설정만, 증거 없음) |
| 개선 조치 · 우선순위 | ✓ 실패 통제 → 이슈 자동 생성·담당 | ✓ 가중치(예방 27·탐지 3·교정 3, 의무/재량) | ~ 통제 추천(주장) | — | ~ 권고 최대 10개 | ✓ '다음에 켤 통제'(효과 기준) / 담당·기한 — |
| 담당 · 워크플로 · 승인 | ✓ | ✓ 할당 · 변경 경보 | ✓ 승인 · 추적성 | ~ 승인 입력 | ✓ 승인 백엔드 | — (저장 없음 — 의도) |
| **what-if · 시뮬레이션** | ~ 고유→잔여→목표(평가 값) | ✓ DLP: 실제 데이터에 집행 없이 정책 적용 | — | — | ~ 모의 데이터 대시보드, 드라이런 없음 | ✓ **원형 11 × 설정 · 실제 사건 45 반사실** |
| 런타임 집행 · 킬 스위치 | ✓ 권한 초과 에이전트 실시간 중단 | ✓ DLP 집행 | — | ✓ JIT · MCP/A2A 프록시 · 격리 | ✓ 정책 엔진 <0.1ms | — (범위 밖) |
| 프레임워크 커버리지 보고 | ~ | ✓ 평가별 진행 | ~ | ~ | ✓ ASI01–10 Full/Partial/Gap | — (원형에 근거만) |
| 보고 · 내보내기 | ✓ 이미지 · 데이터 복사 | ✓ Excel 내보내기 · 6개월 보고서 | ✓ 이사회 보고 | — | ✓ 준수 보고서 필드 | ✓ 인쇄·PDF · 링크 / CSV — |
| 추세 · 이력 | ✓ 최근 5회 평가 | ✓ 점수 이력 | ~ | — | ~ | ✓ 규제 이력 / 자기 설정 이력 — |
| 추적 사슬 | ✓ 360° 보기 | ~ | ✓ 위험→통제→감사→발견(주장) | ~ 감사 필드 | ✓ 해시 사슬 감사 로그 | ~ 사건→실패 통제, 조문은 따로 |
| **실제 사건 근거** | — | — | — | — | — | ✓ 45건, 두 팀 블라인드 코딩 |
| **판정 방법 공개(κ · 조정)** | — | ~ 점수 규칙 공개 | — | — | ~ '자체 평가, 인증 아님' | ✓ |

**읽는 법.** 여섯 제품은 대부분 **집행·운영 도구**(실제 에이전트를 등록하고, 정책을 걸고, 증거를 모은다)다. 우리는 **평가·연습 도구**다.
겹치지 않는 곳이 우리 자리다 — 공격 시나리오로 돌리는 what-if, 실제 사건으로 검증한 반사실, 규제 조문까지 내려가는 근거, 판정 방법 공개.
그 대신 실무자가 결과를 **가져가서 쓰는 기능**(실행 계획 · 증거 · 보고서 형식)이 비어 있다.

## 5. 기능 제안 (우선순위) — 집행 도구를 흉내 내지 않고, 평가 결과를 들고 나가게

1. **개선 조치 → 실행 계획 내보내기 (Purview 조치 · 내보내기)** — 조치 · 통제·층 · 종류(예방/탐지/교정) · 효과 · 관할별 규제 근거 · 담당·기한 빈칸을 CSV 로. 서버 저장 없이 담당자가 엑셀로 가져간다.
2. **OWASP Agentic Top 10 커버리지 보고 (AGT)** — 지금 설정에서 ASI01~10 마다 Full / Partial / Gap 와 근거 원형. '자체 계산 · 인증 아님'.
3. **현재 vs 변경안 비교 (DLP v1 → v2)** — 변경안의 모든 숫자에 차이. 개선 조치 표의 [변경안에 넣기] 와 이어진다.
4. **추적 사슬 패널 (Diligent · ServiceNow 360°)** — 원형이나 사건을 누르면 한 패널에 '공격 단계 → 걸린 통제 → 관할별 규제 조문 → 개선 조치'.
5. **규제 반영 what-if (Purview Pending update)** — 반영 대기 후보 하나를 골라 '이 문서가 ○○ 통제를 AI 층 구속력으로 요구한다면' 을 가정해 프리셋을 다시 계산 → 차이를 보이고, '가정' 이라고 적는다. 실제 반영은 지금처럼 코딩 후.
6. **자가 진단 + 증거 메모 (Purview 증거)** — 통제마다 상태(구현 / 부분 / 계획 / 없음)와 근거 한 줄. 브라우저 밖으로 안 보내고 **JSON 파일로 내보내기·불러오기**만.
7. (선택) **정책 초안 내보내기 (AGT · Rutile 정책 코드)** — 지금 설정을 'AI 까지' 통제별 체크리스트 + AGT 식 YAML 뼈대로. 집행 도구로 넘어가는 다리 — 다만 그대로 쓰면 안 되는 초안임을 크게 밝혀야 해서 마지막.

**하지 않을 것**: 실제 에이전트 발견·등록, 런타임 집행, 서버에 담당·워크플로 저장, 실제 시스템 자동 테스트, AI 가 만든 추천 문구 — 우리 제품의 범위(평가·연습)와 판정 방법(사람 + 두 팀 블라인드)에 맞지 않는다.

## 못 찾은 것
- **GABA** — 웹 검색 · GitHub 저장소 검색 모두 해당 제품 없음.
- **IRAME** — GitHub 의 `CI-SSLab/IRAME` 은 '해양 환경 위험 평가(Interpretable Risk Assessment in Marine Environments)' 로 다른 것으로 보인다. AI 에이전트 위험 평가 쪽으로는 AURA(arXiv 2510.15739) · TrustX ARC 가 가까운 이름이다.
- 링크를 주면 같은 방식으로 본다.
