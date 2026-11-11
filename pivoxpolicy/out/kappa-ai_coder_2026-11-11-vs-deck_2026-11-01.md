# 코더 간 일치도 — `ai_coder_2026-11-11` vs `deck_2026-11-01`

A = `ai_coder_2026-11-11` · B = `deck_2026-11-01`

| 단위 | 칸 | A 참 | B 참 | 둘 다 참 | 관측 일치율 | κ | 점수 κ (가중) | Landis–Koch |
|---|---|---|---|---|---|---|---|---|
| 커버 여부 | 80 | 49 | 37 | 37 | 0.850 | **0.705** | 0.764 (0.647) | substantial |

칸 = 둘 다 true/false 로 코딩한 문서 × 통제. 점수 κ 는 문서의 binding 이 같아 커버 κ 보다 높게 나온다 — 커버 κ 가 재현성 지표다.

## 불일치 12칸 — 커버 여부

- `kr-efsr-art13` × `inventory` — A 만 다룸
- `kr-efsr-art13` × `human_approval` — A 만 다룸
- `kr-efsr-art13` × `kill_switch` — A 만 다룸
- `kr-efsr-art37-2` × `human_approval` — A 만 다룸
- `kr-outsourcing-regulation` × `least_privilege` — A 만 다룸
- `kr-outsourcing-regulation` × `human_approval` — A 만 다룸
- `us-cisa-bod-22-01` × `inventory` — A 만 다룸
- `us-cisa-bod-22-01` × `vendors` — A 만 다룸
- `us-cisa-bod-22-01` × `kill_switch` — A 만 다룸
- `us-nist-csf-2-0` × `kill_switch` — A 만 다룸
- `us-nydfs-part500` × `human_approval` — A 만 다룸
- `us-nydfs-part500` × `kill_switch` — A 만 다룸
