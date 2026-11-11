# 코더 간 일치도 — `ai_coder_2026-11-11` vs `deck_2026-11-01`

공통 코딩 셀: **80** (둘 다 null 이 아닌 문서 × 통제)

| 지표 | 관측 일치율 | κ (비가중) | κ (선형가중) | Landis–Koch |
|---|---|---|---|---|
| 커버 여부 (true/false) | 0.850 | 0.705 | – | substantial |
| 셀 점수 (0–3) | 0.850 | 0.764 | 0.647 | substantial |

점수 κ 는 문서의 binding·names_agents 가 같으므로 커버 여부 κ 와 같거나 가깝다. 두 값이 벌어지면 코딩 범위가 달라서다.

## 불일치 셀

- `kr-efsr-art13` × `inventory`
- `kr-efsr-art13` × `human_approval`
- `kr-efsr-art13` × `kill_switch`
- `kr-efsr-art37-2` × `human_approval`
- `kr-outsourcing-regulation` × `least_privilege`
- `kr-outsourcing-regulation` × `human_approval`
- `us-cisa-bod-22-01` × `inventory`
- `us-cisa-bod-22-01` × `vendors`
- `us-cisa-bod-22-01` × `kill_switch`
- `us-nist-csf-2-0` × `kill_switch`
- `us-nydfs-part500` × `human_approval`
- `us-nydfs-part500` × `kill_switch`
