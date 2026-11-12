# 민감도 — 칸 하나로 바뀌는 관할 점수 (코더 `ai_v2a_2026-11-11`)

문서 × 통제 × 층 칸을 하나씩 뒤집어 관할 × 통제 점수가 바뀌는 경우만 적었다. **◆ = 코더 note 에 borderline** — 결론이 애매하다고 적힌 판정에 기댄다.

- 아래로(그 칸 하나가 점수를 받침): **28** · 그중 ◆ 7
- 위로(그 칸 하나가 true 가 되면 점수가 오름): **61** · 그중 ◆ 5

## 아래로 — 점수를 받치는 문서가 하나뿐

| 층 | 관할 | 통제 | 점수 | 빼면 | 받치는 칸 | |
|---|---|---|---|---|---|---|
| AI·에이전트 | EU | 5 사람 승인 | 2 | 0 | `eu-ai-act-art14` |  |
| AI·에이전트 | EU | 7 즉시 중단 | 2 | 0 | `eu-ai-act-art14` |  |
| AI·에이전트 | INTL | 1 인벤토리 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` | ◆ |
| AI·에이전트 | INTL | 2 공급자 관리 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` |  |
| AI·에이전트 | INTL | 3 고유 식별자 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` |  |
| AI·에이전트 | INTL | 4 최소 권한 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` |  |
| AI·에이전트 | INTL | 5 사람 승인 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` |  |
| AI·에이전트 | INTL | 6 감사 기록 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` | ◆ |
| AI·에이전트 | INTL | 7 즉시 중단 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` |  |
| AI·에이전트 | KR | 1 인벤토리 | 1 | 0 | `kr-fsc-ai-guidelines-2026-06` | ◆ |
| AI·에이전트 | KR | 5 사람 승인 | 2 | 1 | `kr-ai-basic-act` |  |
| 일반 통제 | EU | 1 인벤토리 | 2 | 0 | `eu-dora-2022-2554` |  |
| 일반 통제 | EU | 2 공급자 관리 | 2 | 0 | `eu-dora-2022-2554` |  |
| 일반 통제 | EU | 4 최소 권한 | 2 | 0 | `eu-dora-2022-2554` |  |
| 일반 통제 | EU | 5 사람 승인 | 2 | 0 | `eu-dora-2022-2554` | ◆ |
| 일반 통제 | EU | 6 감사 기록 | 2 | 0 | `eu-dora-2022-2554` | ◆ |
| 일반 통제 | EU | 7 즉시 중단 | 2 | 0 | `eu-dora-2022-2554` |  |
| 일반 통제 | INTL | 1 인벤토리 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` | ◆ |
| 일반 통제 | INTL | 6 감사 기록 | 1 | 0 | `intl-fsb-ai-sound-practices-2026-10` | ◆ |
| 일반 통제 | KR | 1 인벤토리 | 2 | 1 | `kr-efsr-art13` |  |
| 일반 통제 | KR | 2 공급자 관리 | 2 | 1 | `kr-outsourcing-regulation` |  |
| 일반 통제 | KR | 3 고유 식별자 | 2 | 1 | `kr-efsr-art13` |  |
| 일반 통제 | KR | 4 최소 권한 | 2 | 1 | `kr-efsr-art13` |  |
| 일반 통제 | KR | 6 감사 기록 | 2 | 1 | `kr-efsr-art13` |  |
| 일반 통제 | KR | 7 즉시 중단 | 2 | 1 | `kr-efsr-art13` |  |
| 일반 통제 | US | 4 최소 권한 | 2 | 1 | `us-nydfs-part500` |  |
| 일반 통제 | US | 5 사람 승인 | 2 | 1 | `us-nydfs-part500` |  |
| 일반 통제 | US | 6 감사 기록 | 2 | 1 | `us-nydfs-part500` |  |

## 위로 — 판정 하나로 점수가 오를 자리

| 층 | 관할 | 통제 | 점수 | true 면 | 뒤집을 칸 | |
|---|---|---|---|---|---|---|
| AI·에이전트 | EU | 1 인벤토리 | 0 | 2 | `eu-ai-act-art14` |  |
| AI·에이전트 | EU | 1 인벤토리 | 0 | 2 | `eu-dora-2022-2554` |  |
| AI·에이전트 | EU | 2 공급자 관리 | 0 | 2 | `eu-ai-act-art14` |  |
| AI·에이전트 | EU | 2 공급자 관리 | 0 | 2 | `eu-dora-2022-2554` |  |
| AI·에이전트 | EU | 3 고유 식별자 | 0 | 2 | `eu-ai-act-art14` |  |
| AI·에이전트 | EU | 3 고유 식별자 | 0 | 2 | `eu-dora-2022-2554` | ◆ |
| AI·에이전트 | EU | 4 최소 권한 | 0 | 2 | `eu-ai-act-art14` |  |
| AI·에이전트 | EU | 4 최소 권한 | 0 | 2 | `eu-dora-2022-2554` |  |
| AI·에이전트 | EU | 6 감사 기록 | 0 | 2 | `eu-ai-act-art14` |  |
| AI·에이전트 | EU | 6 감사 기록 | 0 | 2 | `eu-dora-2022-2554` | ◆ |
| AI·에이전트 | KR | 1 인벤토리 | 1 | 2 | `kr-ai-basic-act` |  |
| AI·에이전트 | KR | 1 인벤토리 | 1 | 2 | `kr-efsr-art13` |  |
| AI·에이전트 | KR | 1 인벤토리 | 1 | 2 | `kr-efsr-art37-2` |  |
| AI·에이전트 | KR | 1 인벤토리 | 1 | 2 | `kr-outsourcing-regulation` |  |
| AI·에이전트 | KR | 2 공급자 관리 | 1 | 2 | `kr-ai-basic-act` |  |
| AI·에이전트 | KR | 2 공급자 관리 | 1 | 2 | `kr-efsr-art13` |  |
| AI·에이전트 | KR | 2 공급자 관리 | 1 | 2 | `kr-efsr-art37-2` |  |
| AI·에이전트 | KR | 2 공급자 관리 | 1 | 2 | `kr-outsourcing-regulation` |  |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 2 | `kr-ai-basic-act` |  |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 2 | `kr-efsr-art13` |  |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 2 | `kr-efsr-art37-2` |  |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 1 | `kr-fsc-ai-guidelines-2026-06` | ◆ |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 1 | `kr-fsc-frontier-ai-guide-2026-07` |  |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 1 | `kr-fsi-agent-criteria-2026-10` |  |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 1 | `kr-fss-fsi-pentest-standards-2026` |  |
| AI·에이전트 | KR | 3 고유 식별자 | 0 | 2 | `kr-outsourcing-regulation` |  |
| AI·에이전트 | KR | 4 최소 권한 | 1 | 2 | `kr-ai-basic-act` |  |
| AI·에이전트 | KR | 4 최소 권한 | 1 | 2 | `kr-efsr-art13` |  |
| AI·에이전트 | KR | 4 최소 권한 | 1 | 2 | `kr-efsr-art37-2` |  |
| AI·에이전트 | KR | 4 최소 권한 | 1 | 2 | `kr-outsourcing-regulation` |  |
| AI·에이전트 | KR | 6 감사 기록 | 1 | 2 | `kr-ai-basic-act` |  |
| AI·에이전트 | KR | 6 감사 기록 | 1 | 2 | `kr-efsr-art13` |  |
| AI·에이전트 | KR | 6 감사 기록 | 1 | 2 | `kr-efsr-art37-2` |  |
| AI·에이전트 | KR | 6 감사 기록 | 1 | 2 | `kr-outsourcing-regulation` |  |
| AI·에이전트 | KR | 7 즉시 중단 | 1 | 2 | `kr-ai-basic-act` |  |
| AI·에이전트 | KR | 7 즉시 중단 | 1 | 2 | `kr-efsr-art13` |  |
| AI·에이전트 | KR | 7 즉시 중단 | 1 | 2 | `kr-efsr-art37-2` |  |
| AI·에이전트 | KR | 7 즉시 중단 | 1 | 2 | `kr-outsourcing-regulation` |  |
| AI·에이전트 | US | 1 인벤토리 | 1 | 2 | `us-cisa-bod-26-04` |  |
| AI·에이전트 | US | 1 인벤토리 | 1 | 2 | `us-nydfs-part500` |  |
| AI·에이전트 | US | 2 공급자 관리 | 1 | 2 | `us-cisa-bod-26-04` |  |
| AI·에이전트 | US | 2 공급자 관리 | 1 | 2 | `us-nydfs-part500` |  |
| AI·에이전트 | US | 3 고유 식별자 | 1 | 2 | `us-cisa-bod-26-04` |  |
| AI·에이전트 | US | 3 고유 식별자 | 1 | 2 | `us-nydfs-part500` |  |
| AI·에이전트 | US | 4 최소 권한 | 1 | 2 | `us-cisa-bod-26-04` |  |
| AI·에이전트 | US | 4 최소 권한 | 1 | 2 | `us-nydfs-part500` |  |
| AI·에이전트 | US | 5 사람 승인 | 1 | 2 | `us-cisa-bod-26-04` |  |
| AI·에이전트 | US | 5 사람 승인 | 1 | 2 | `us-nydfs-part500` |  |
| AI·에이전트 | US | 6 감사 기록 | 1 | 2 | `us-cisa-bod-26-04` |  |
| AI·에이전트 | US | 6 감사 기록 | 1 | 2 | `us-nydfs-part500` |  |
| AI·에이전트 | US | 7 즉시 중단 | 1 | 2 | `us-cisa-bod-26-04` | ◆ |
| AI·에이전트 | US | 7 즉시 중단 | 1 | 2 | `us-nydfs-part500` |  |
| 일반 통제 | EU | 3 고유 식별자 | 0 | 2 | `eu-ai-act-art14` |  |
| 일반 통제 | EU | 3 고유 식별자 | 0 | 2 | `eu-dora-2022-2554` | ◆ |
| 일반 통제 | INTL | 2 공급자 관리 | 0 | 1 | `intl-fsb-ai-sound-practices-2026-10` |  |
| 일반 통제 | INTL | 3 고유 식별자 | 0 | 1 | `intl-fsb-ai-sound-practices-2026-10` |  |
| 일반 통제 | INTL | 4 최소 권한 | 0 | 1 | `intl-fsb-ai-sound-practices-2026-10` |  |
| 일반 통제 | INTL | 5 사람 승인 | 0 | 1 | `intl-fsb-ai-sound-practices-2026-10` |  |
| 일반 통제 | INTL | 7 즉시 중단 | 0 | 1 | `intl-fsb-ai-sound-practices-2026-10` |  |
| 일반 통제 | US | 3 고유 식별자 | 1 | 2 | `us-cisa-bod-26-04` |  |
| 일반 통제 | US | 3 고유 식별자 | 1 | 2 | `us-nydfs-part500` |  |
