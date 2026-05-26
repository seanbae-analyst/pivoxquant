/**
 * business-info.ts — 전자상거래법 §13 사업자 정보 단일 SoT (Single Source of Truth).
 *
 * WHY: 같은 데이터(대표자/사업자등록번호/통신판매업 신고번호 등)를 두 컴포넌트가
 * 서로 다른 NEXT_PUBLIC_* env 키로 읽고 있었다:
 *   - landing-v2.tsx SiteFooter: NEXT_PUBLIC_BUSINESS_REPRESENTATIVE /
 *     NEXT_PUBLIC_BUSINESS_REGISTRATION_NUMBER / NEXT_PUBLIC_TELESELLER_REGISTRATION_NUMBER ...
 *   - support/business-info.tsx: NEXT_PUBLIC_BUSINESS_OWNER /
 *     NEXT_PUBLIC_BUSINESS_REG_NO / NEXT_PUBLIC_BUSINESS_MAILORDER_NO ...
 * → 신고번호 env 하나만 설정해도 한쪽만 켜지는 함정. 이 모듈로 양쪽을 통일한다.
 *
 * 안전책: prod Vercel 에 이미 설정된 env 키를 모르므로, canonical 키를 먼저 읽되
 * 기존 두 벌 키를 모두 fallback OR 체인으로 읽는다. CEO 가 어느 키 한 벌만
 * 설정해도 모든 서피스가 동시에 켜진다.
 *
 * ⚠️ env 변수명을 rename 하지 않는다(prod 에서 값 증발 위험). 추가/병합만 한다.
 *
 * 표시 철학은 호출부가 결정한다:
 *   - raw 접근자(undefined 가능): landing footer 의 elide 철학용
 *   - withDefaults() : business-info 블록의 default 표시 철학용
 */

/** trim 후 빈 문자열이면 undefined 로 정규화. */
function read(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

/** 여러 env 후보 중 첫 번째로 채워진 값(없으면 undefined). */
function firstOf(...values: (string | undefined)[]): string | undefined {
  for (const v of values) {
    const r = read(v);
    if (r) return r;
  }
  return undefined;
}

/**
 * raw — env 가 설정된 항목만 채워지고, 미설정이면 undefined.
 * landing footer 처럼 "없으면 미노출(elide)" 하는 서피스가 사용한다.
 *
 * NOTE: process.env.NEXT_PUBLIC_* 는 Next.js 빌드 타임 인라인 대상이므로
 * 반드시 정적 멤버 접근(process.env.X)으로 작성해야 한다(동적 키 접근 금지).
 */
export const businessInfoRaw = {
  /** 상호 */
  name: read(process.env.NEXT_PUBLIC_BUSINESS_NAME),
  /** 대표자 — REPRESENTATIVE(landing) ?? OWNER(business-info) */
  representative: firstOf(
    process.env.NEXT_PUBLIC_BUSINESS_REPRESENTATIVE,
    process.env.NEXT_PUBLIC_BUSINESS_OWNER,
  ),
  /** 사업자등록번호 — REGISTRATION_NUMBER(landing) ?? REG_NO(business-info) */
  registrationNumber: firstOf(
    process.env.NEXT_PUBLIC_BUSINESS_REGISTRATION_NUMBER,
    process.env.NEXT_PUBLIC_BUSINESS_REG_NO,
  ),
  /** 통신판매업 신고번호 — TELESELLER_REGISTRATION_NUMBER(landing) ?? MAILORDER_NO(business-info) */
  telesellerNumber: firstOf(
    process.env.NEXT_PUBLIC_TELESELLER_REGISTRATION_NUMBER,
    process.env.NEXT_PUBLIC_BUSINESS_MAILORDER_NO,
  ),
  /** 업태 */
  businessType: read(process.env.NEXT_PUBLIC_BUSINESS_TYPE),
  /** 종목 */
  businessSubtype: read(process.env.NEXT_PUBLIC_BUSINESS_SUBTYPE),
  /** 주소 (두 서피스가 동일 키 사용) */
  address: read(process.env.NEXT_PUBLIC_BUSINESS_ADDRESS),
  /** 연락처(전화) */
  phone: read(process.env.NEXT_PUBLIC_BUSINESS_PHONE),
  /** 문의 이메일 — SUPPORT_EMAIL */
  supportEmail: read(process.env.NEXT_PUBLIC_SUPPORT_EMAIL),
  /** 개인정보보호책임자 (미설정 시 대표자로 폴백) */
  privacyOfficer: firstOf(
    process.env.NEXT_PUBLIC_BUSINESS_PRIVACY_OFFICER,
    process.env.NEXT_PUBLIC_BUSINESS_REPRESENTATIVE,
    process.env.NEXT_PUBLIC_BUSINESS_OWNER,
  ),
} as const;

export type BusinessInfoRaw = typeof businessInfoRaw;

/** business-info 블록이 쓰는 default 값들 (env 미설정 시 표시). */
const DEFAULTS = {
  name: "피복스퀀트 (PivoxQuant)",
  representative: "배상현",
  registrationNumber: "459-01-03808",
  telesellerNumber: "신고 진행 중",
  address: "대한민국 (사업장 주소는 문의 시 안내)",
  phone: "이메일 문의 우선",
  supportEmail: "support@pivoxquant.com",
  privacyOfficer: "배상현",
} as const;

/**
 * withDefaults — env 가 없으면 합리적 default 로 채운 표시용 값.
 * business-info.tsx 처럼 "항상 표시" 하는 서피스가 사용한다.
 */
export function businessInfoWithDefaults() {
  return {
    name: businessInfoRaw.name ?? DEFAULTS.name,
    representative: businessInfoRaw.representative ?? DEFAULTS.representative,
    registrationNumber:
      businessInfoRaw.registrationNumber ?? DEFAULTS.registrationNumber,
    telesellerNumber:
      businessInfoRaw.telesellerNumber ?? DEFAULTS.telesellerNumber,
    address: businessInfoRaw.address ?? DEFAULTS.address,
    phone: businessInfoRaw.phone ?? DEFAULTS.phone,
    supportEmail: businessInfoRaw.supportEmail ?? DEFAULTS.supportEmail,
    privacyOfficer: businessInfoRaw.privacyOfficer ?? DEFAULTS.privacyOfficer,
  };
}

export type BusinessInfoResolved = ReturnType<typeof businessInfoWithDefaults>;

/** 공통 default 문의 이메일 (하드코딩 산재 방지). */
export const SUPPORT_EMAIL_DEFAULT = DEFAULTS.supportEmail;

/**
 * 공정거래위원회 통신판매사업자 정보공개 조회 URL.
 *
 * ⚠️ URL 형식 미확정: FTC bizCommPop 조회 페이지의 정확한 쿼리 파라미터 규격을
 * 공식 문서로 확인하지 못했다(통신판매업 신고 완료 후에야 조회 가능). 따라서
 * 신고번호(telesellerNumber)가 설정된 경우에만 링크를 노출하고, 그마저도 CEO 가
 * 실제 조회되는 URL 을 검증한 뒤 NEXT_PUBLIC_BUSINESS_FTC_LINK 로 덮어쓰는 것을
 * 우선한다. env 가 있으면 그 값을, 없으면 undefined 를 반환(=링크 미노출).
 *
 * 참고용 추정 형식(검증 필요): https://www.ftc.go.kr/bizCommPop.do?wrkr_no={사업자번호 하이픈제거}
 */
export function ftcBizInfoUrl(): string | undefined {
  // 1순위: CEO 가 검증한 완성 URL 을 env 로 직접 지정.
  const explicit = read(process.env.NEXT_PUBLIC_BUSINESS_FTC_LINK);
  if (explicit) return explicit;
  // 2순위 없음: 추측 URL 자동 생성은 깨진 링크 위험 → 하지 않는다.
  return undefined;
}
