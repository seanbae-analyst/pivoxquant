# 코더 간 일치도 — `ai_coder_2026-11-11` vs `ai_v2b_2026-11-11`

A = `ai_coder_2026-11-11` · B = `ai_v2b_2026-11-11`

한쪽은 한 칸(v1 covered), 한쪽은 두 층(v2) 코딩이다 — v2 는 '일반 또는 AI 중 하나라도 다룸' 으로 접어 견준다. 기준이 다른 두 코딩의 비교라 κ 는 참고용이다.

| 단위 | 칸 | A 참 | B 참 | 둘 다 참 | 관측 일치율 | κ | 점수 κ (가중) | Landis–Koch |
|---|---|---|---|---|---|---|---|---|
| 둘 중 하나 (일반 ∨ AI) — v1 의 covered 와 견주는 값 | 140 | 91 | 82 | 79 | 0.893 | **0.774** | 0.822 (0.817) | substantial |

칸 = 둘 다 true/false 로 코딩한 문서 × 통제. 점수 κ 는 문서의 binding 이 같아 커버 κ 보다 높게 나온다 — 커버 κ 가 재현성 지표다.

## 불일치 15칸 — 둘 중 하나 (일반 ∨ AI)

- `kr-fsc-ai-guidelines-2026-06` × `unique_id` — B 만 다룸
- `kr-fsc-frontier-ai-guide-2026-07` × `audit_trail` — A 만 다룸
- `kr-outsourcing-regulation` × `least_privilege` — A 만 다룸
- `kr-outsourcing-regulation` × `human_approval` — A 만 다룸
- `us-fed-sr-26-2` × `inventory` — B 만 다룸
- `us-fed-sr-26-2` × `vendors` — B 만 다룸
- `us-nist-csf-2-0` × `kill_switch` — A 만 다룸
- `us-nydfs-letter-2024-10-16` × `unique_id` — A 만 다룸
- `us-nydfs-letter-2024-10-16` × `human_approval` — A 만 다룸
- `us-nydfs-letter-2024-10-16` × `audit_trail` — A 만 다룸
- `us-nydfs-letter-2026-09-10` × `human_approval` — A 만 다룸
- `us-nydfs-letters-2026-05-21` × `inventory` — A 만 다룸
- `us-nydfs-letters-2026-05-21` × `unique_id` — A 만 다룸
- `us-nydfs-part500` × `unique_id` — A 만 다룸
- `us-treasury-fs-ai-rmf-2026-02` × `least_privilege` — A 만 다룸
