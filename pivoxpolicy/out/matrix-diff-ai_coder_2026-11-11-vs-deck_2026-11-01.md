# 매트릭스 민감도 — `ai_coder_2026-11-11` vs `deck_2026-11-01`

관할 × 통제 28칸 중 점수가 다른 칸 **12** — 둘 다 코딩했는데 판단이 갈린 칸 **6** · 한쪽만 코딩한 칸(?) 6. 판단이 갈린 칸의 결론(예: '미국은 사람 승인 0')은 코더 한 명의 판단에 기대고 있으니 논문에서는 둘을 함께 쓰거나 판정 규칙을 먼저 정한다.

| 관할 | 통제 | ai_coder_2026-11-11 | deck_2026-11-01 | ai_coder_2026-11-11 최고 문서 | deck_2026-11-01 최고 문서 |
|---|---|---|---|---|---|
| KR | inventory | 2 | 0 | `kr-efsr-art13` | `kr-efsr-art13`, `kr-efsr-art37-2`, `kr-outsourcing-regulation` |
| KR | human_approval | 2 | 1 | `kr-ai-basic-act`, `kr-efsr-art13`, `kr-efsr-art37-2` | `kr-fsc-ai-guidelines-2026-06`, `kr-fsi-agent-criteria-2026-10` |
| KR | kill_switch | 2 | 1 | `kr-efsr-art13` | `kr-fsi-agent-criteria-2026-10` |
| US | unique_id | 2 | 1 | `us-nydfs-part500` | `us-nist-csf-2-0`, `us-nist-nccoe-agent-identity-2026-02` |
| US | human_approval | 2 | 0 | `us-nydfs-part500` | `us-nydfs-part500`, `us-fed-sr-26-2`, `us-nist-csf-2-0` |
| US | kill_switch | 2 | 0 | `us-nydfs-part500` | `us-nydfs-part500`, `us-fed-sr-26-2`, `us-nist-csf-2-0` |
| EU | inventory | 0 | ? | `eu-ai-act-art14` | – |
| EU | vendors | 0 | ? | `eu-ai-act-art14` | – |
| EU | unique_id | 0 | ? | `eu-ai-act-art14` | – |
| EU | least_privilege | 0 | ? | `eu-ai-act-art14` | – |
| EU | human_approval | 2 | ? | `eu-ai-act-art14` | – |
| EU | audit_trail | 0 | ? | `eu-ai-act-art14` | – |
