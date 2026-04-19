# PivoxQuant 도메인 세팅 체크리스트

**상태:** `pivoxquant.com` → 307 → `www.pivoxquant.com` 리다이렉트 루프 의심  
**임시 운영 도메인:** `https://pivoxquant.vercel.app` (베타 유저 여기로 접속 중)  
**최종 목표:** `pivoxquant.com` 을 Primary Domain 으로 고정, `www` 는 apex 로 301 리다이렉트

---

## 왜 리다이렉트 루프가 생기는가

가비아 DNS 와 Vercel Domains 양쪽이 서로를 "가리키는" 상태가 되면 루프가 생긴다.
대표 원인 4가지:

1. **가비아 A 레코드** `@ → 76.76.21.21` 만 설정되어 있고 `www` CNAME 가 빠졌다.  
   Vercel 은 `www` 로 오는 요청이 없으니 `www.pivoxquant.com` 을 자기가 서비스하지 못하고, apex 는 `www` 로 재리다이렉트 → 무한 루프.
2. **Primary Domain** 이 `www.pivoxquant.com` 으로 설정되어 있어 apex 로 접속하면 www 로 리다이렉트되는데, DNS 가 www 를 못 찾아서 결국 apex 로 되돌아온다.
3. **브라우저 HSTS 캐시** 가 이전 (localhost 에서 테스트한) HTTPS 설정을 들고 있어 무조건 `https://www.pivoxquant.com` 으로 가려 한다.
4. **가비아의 "도메인 포워딩"** 기능과 Vercel 리다이렉트가 이중으로 걸려 있다.

---

## Vercel 설정 (CEO 수동)

1. **Vercel Dashboard → Project (pivoxquant) → Settings → Domains** 진입
2. 세 도메인이 모두 등록되어 있는지 확인:
   - `pivoxquant.com`          ← Primary 로 설정할 대상
   - `www.pivoxquant.com`      ← Redirect to `pivoxquant.com` (Permanent / 308)
   - `pivoxquant.vercel.app`   ← 자동 등록 (건드리지 말 것, 베타 유저 접속 중)
3. **`pivoxquant.com`** 우측 점 세 개 메뉴 → **"Set as Production Domain"** 클릭
   - 이 옵션이 Primary Domain 을 apex 로 고정한다.
4. **`www.pivoxquant.com`** 우측 메뉴 → **"Redirect to"** → `pivoxquant.com` 선택, Redirect Code 는 `308 Permanent`
5. 저장 후 **상단 상태 표시가 모두 "Valid Configuration" 초록색** 이 될 때까지 대기 (최대 수 분)

> Vercel 이 apex TXT 레코드 검증을 요구하면 가비아에서 `_vercel.pivoxquant.com` TXT 를 추가해야 한다. 이미 된 상태라면 스킵.

---

## 가비아 DNS 설정 (CEO 수동)

가비아 → My가비아 → 도메인 통합관리 → `pivoxquant.com` → DNS 관리 → DNS 설정

| 타입    | 호스트 | 값/위치                        | TTL |
|---------|--------|--------------------------------|-----|
| A       | `@`    | `76.76.21.21`                  | 600 |
| CNAME   | `www`  | `cname.vercel-dns.com.`        | 600 |
| TXT     | `_vercel` | (Vercel 이 알려준 검증 문자열) | 600 |

중요:
- **가비아의 "도메인 포워딩" 기능은 반드시 OFF.** 켜져 있으면 Vercel 리다이렉트와 충돌해 루프를 만든다.
- **CNAME 값 끝에 점 (`.`) 포함.** 가비아 UI 는 점을 자동으로 붙여주는 경우와 그렇지 않은 경우가 있다 → 저장 후 다시 확인.
- **AAAA (IPv6) 레코드는 추가하지 않는다.** Vercel apex 는 IPv4 로만 응답, AAAA 에 아무거나 넣으면 브라우저가 IPv6 로 먼저 시도하다 실패.

---

## 검증 절차

DNS 전파 확인 (터미널):
```bash
# apex — 76.76.21.21 이 나와야 함
dig +short pivoxquant.com A

# www — cname.vercel-dns.com. 이 나와야 함
dig +short www.pivoxquant.com CNAME

# TLS — 유효한 인증서 체인 확인
curl -sI https://pivoxquant.com | head -5
curl -sI https://www.pivoxquant.com | head -5  # Location: https://pivoxquant.com/ 가 나와야 함

# OG 메타 — 크롤러 UA 로 확인 (베타 게이트 bypass 동작 검증)
curl -s -A "facebookexternalhit/1.1" https://pivoxquant.com/ | \
  grep -Eo '<meta[^>]*(og:|twitter:)[^>]*>' | head -10
```

브라우저 검증:
1. **시크릿 창** 으로 `https://pivoxquant.com` 접속 → CFO 랜딩 페이지가 떠야 함.
2. `https://www.pivoxquant.com` 접속 → 주소창이 `pivoxquant.com` 으로 바뀌고 1회만 리다이렉트.
3. Facebook Sharing Debugger (`https://developers.facebook.com/tools/debug/`) 에서 `https://pivoxquant.com` 입력 → OG 이미지 + 타이틀 + 설명 모두 렌더.
4. Twitter Card Validator, LinkedIn Post Inspector 도 동일 확인.

---

## 롤백 플랜

만약 apex primary 전환 이후 서비스가 다운되면:
1. Vercel → Settings → Domains → `pivoxquant.vercel.app` 는 여전히 살아있음 (베타 fallback).
2. Vercel Primary Domain 을 다시 `pivoxquant.vercel.app` 으로 내리고 apex 는 **Redirect to** `pivoxquant.vercel.app` 으로 설정.
3. 베타 공지 채널에 `pivoxquant.vercel.app` 링크 재공유.
4. 가비아 DNS 는 그대로 둬도 무방 — Vercel 쪽 설정만 바꾸면 즉시 복구.

---

## 참고

- Vercel 공식: https://vercel.com/docs/projects/domains/add-a-domain
- 가비아 DNS 가이드: https://customer.gabia.com/manual/dns
- HSTS preload 리스트 제거: 만약 브라우저 HSTS 에 걸렸으면 `chrome://net-internals/#hsts` 에서 `pivoxquant.com` delete
