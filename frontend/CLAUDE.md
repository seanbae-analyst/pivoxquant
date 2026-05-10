# PivoxQuant Frontend — Session Handoff

## 현재 상태 (2026-04-12) — FRONTEND RESET

### 상태: 프론트엔드 전체 리셋 완료
모든 UI 페이지/컴포넌트 삭제됨. 백엔드 인프라(lib/)와 shadcn/ui 기본 컴포넌트만 남음.
새 디자인으로 처음부터 다시 만드는 중.

### 아키텍처
- **Next.js 16** App Router + TypeScript + Tailwind 4
- **SWR** for data fetching (hooks in `src/lib/hooks.ts`)
- **API endpoints** centralized in `src/lib/endpoints.ts`
- **Auth** via `src/lib/auth.tsx` (AuthContext + Flask session cookies)

### 현재 파일 구조 (29개)
```
src/
├── app/
│   ├── layout.tsx       # 루트 레이아웃 (Geist + IBM Plex Mono + Pretendard)
│   ├── page.tsx         # 플레이스홀더 ("Rebuilding something beautiful.")
│   ├── globals.css      # Supanova Vantablack Luxe 테마 토큰
│   ├── manifest.ts      # PWA manifest
│   └── favicon.ico
├── components/ui/       # shadcn/ui 15개 (button, card, dialog, input 등)
└── lib/                 # 백엔드 연동 인프라 (건드리지 말 것)
    ├── api.ts           # apiFetch (CSRF, credentials)
    ├── auth.tsx         # AuthProvider, useAuth
    ├── endpoints.ts     # API URL 상수 (백엔드 1:1 매핑)
    ├── hooks.ts         # SWR 데이터 페칭 훅 17개
    ├── types.ts         # TypeScript 타입 (백엔드 응답 매핑)
    ├── format.ts        # 포맷터 (fmtUsd, fmtPct 등)
    ├── utils.ts         # cn() 유틸
    ├── realtime.tsx     # SSE RealtimeProvider
    └── push.ts          # PWA 푸시 구독
```

### 디자인 시스템 (Supanova Design Skill 기반)
- **Vibe**: Vantablack Luxe (#050505 base)
- **Accent**: Warm Gold (#E2B96F)
- **Cards**: Double-Bezel (ld-bezel + ld-bezel-inner)
- **CTA**: Pill button (rounded-full, no neon glow)
- **Easing**: cubic-bezier(0.16, 1, 0.3, 1) 전체 적용
- **Fonts**: Geist (heading) + Pretendard (body) + IBM Plex Mono (numbers)
- **BANNED**: Inter, violet/purple, neon glow, 3-equal-column, centered Hero

### 백엔드 연동
- 프록시: `next.config.ts` → `/api/*` → `http://localhost:5050/api/*`
- 백엔드 62개 엔드포인트 전부 살아있음
- `lib/hooks.ts`의 17개 SWR 훅으로 연결하면 됨

### 중요 원칙
- **백엔드 코드 건들지 말 것**
- **endpoints.ts URL 변경 금지** — 백엔드 라우트 1:1 매핑
- **hooks.ts SWR 키 변경 금지**
- **types.ts 추가만 가능** — 기존 필드 삭제/이름변경 금지
- **새 페이지는 src/app/ 아래에 생성**
- **Supanova Design Skill 규칙 준수** — THE LILA BAN (no purple/blue AI gradients)

### TODO (새 디자인)
1. [ ] 랜딩 페이지 — Supanova Split Hero + Bento Features
2. [ ] 로그인/회원가입 페이지
3. [ ] 대시보드 메인 — 포트폴리오 overview
4. [ ] 종목 상세 페이지
5. [ ] AI 기능 페이지 (chat, review, ideas)
6. [ ] 설정/프로필 페이지

@AGENTS.md
