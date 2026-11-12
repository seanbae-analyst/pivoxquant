# 조정 — `ai_v2a_2026-11-11` + `ai_v2b_2026-11-11` → `consensus_2026-11-12`

두 코더가 갈린 칸 **7** 개의 판정. 나머지 칸은 두 코더가 같아 그대로 옮겼다 (`check` 가 검사한다).
조정본은 독립 코더가 아니라 κ 에 넣지 않는다. 조정자도 AI 다 — 사람 코더가 들어오면 다시 본다.

| 문서 | 통제 | 층 | 판정 | 따른 쪽 |
|---|---|---|---|---|
| `intl-fsb-ai-sound-practices-2026-10` | inventory | analog | False | `ai_v2b_2026-11-11` |
| `intl-fsb-ai-sound-practices-consultation-2026-06` | inventory | analog | False | `ai_v2b_2026-11-11` |
| `kr-fsc-ai-guidelines-2026-06` | inventory | analog | True | `ai_v2b_2026-11-11` |
| `us-nydfs-letter-2024-10-16` | human_approval | analog | False | `ai_v2b_2026-11-11` |
| `us-nydfs-letter-2026-09-10` | human_approval | analog | False | `ai_v2b_2026-11-11` |
| `us-treasury-fs-ai-rmf-2026-02` | vendors | analog | False | `ai_v2a_2026-11-11` |
| `us-nist-ir-8596-cyber-ai-profile` | human_approval | agent | subject: agent | `ai_v2a_2026-11-11` |

## intl-fsb-ai-sound-practices-2026-10 × inventory (analog)

SP11 의 '인터넷에 연결된 시스템과 그 연결의 필요성을 문서화' 는 노출 점검 절차다. 자산·시스템 목록을 유지·관리하라는 문언이 없다 — false_if '한 번 식별·분류·평가하라는 절차'. A 도 borderline 으로 적었다.

코드북 보강: inventory.analog.false_if 에 '자산의 한 속성(인터넷 연결 여부·연결 필요성 등)을 확인·문서화하라는 것만' 추가

## intl-fsb-ai-sound-practices-consultation-2026-06 × inventory (analog)

최종본과 같은 문장(SP11, 초안 쪽 번호만 다름). 같은 판정.

## kr-fsc-ai-guidelines-2026-06 × inventory (analog)

7.7 망분리 대체 통제 '참고' 상자는 '아래와 같은 망분리 대체 통제를 적용한다' 로 시작하는 규범 본문이다(PDF 86쪽, 2026-11-12 원문 재확인). '접속 단말기 및 사용자ㆍ관리자 등록ㆍ관리' 는 사람·기기를 등록대장으로 유지하라는 요구 — 대상이 AI 를 이용하는 사람·단말기라 G3 에 따라 analog.

코드북 보강: inventory.analog.true_if 에 '사용자·관리자·접속 단말기를 등록·관리하라 (계정·기기 등록대장)' 추가

## us-nydfs-letter-2024-10-16 × human_approval (analog)

조항이 요구하는 것은 교육 내용('trainings should address …')이다. 사람 검토를 넣은 확인 절차를 두라는 요구가 아니라 그런 절차가 있다는 전제에서 무엇을 가르칠지다.

코드북 보강: human_approval.analog.false_if 에 '승인·확인을 교육·훈련 주제로 다루라는 것만 (승인 절차를 두라는 문언 없음)' 추가

## us-nydfs-letter-2026-09-10 × human_approval (analog)

'경영진이 위험을 수용한 경우를 문서에 남기라' 는 이미 내려진 결정의 기록 요구다. 위험 수용에 책임자 승인을 받으라는 문언이 아니다 — true_if 의 '위험 수용' 은 승인 자체를 요구할 때만.

코드북 보강: human_approval.analog.false_if 에 '이미 내린 결정(위험 수용 등)을 기록·문서화하라는 것만' 추가

## us-treasury-fs-ai-rmf-2026-02 × vendors (analog)

MG-3.1.5 의 표제는 'Third-Party AI Risk Monitoring' 이고 감시 대상은 'AI risks … associated with third-party resources' 다(2026-11-12 Guidebook 원문 재확인). consultants·contractors 는 AI 수명주기에 쓰이는 제3자 자원의 예시로 나온다 — 제3자 일반이 아니라 AI 공급망이다(G3: 조항·표제가 AI 를 이름 붙이면 agent).

코드북 보강: vendors.analog.false_if 에 'AI 위험을 이유로 AI 수명주기의 제3자(사람 포함)를 관리하라는 조항 (→ agent)' 추가

## us-nist-ir-8596-cyber-ai-profile × human_approval (agent)

둘 다 true. A 가 함께 인용한 PR.PS-05 Secure 'AI agent systems … subject to approval' 이 에이전트를 이름 붙인다 — subject agent. (binding 1 문서라 점수는 1 그대로.)
