/**
 * `[2026-10-05 사용자 지시]` 동의 항목. 약관 동의는 한 덩어리가 아니라 **항목별**이다 — 필수는 거부하면 앱을 못 쓰고, 선택은 거부해도 앱을 쓸 수 있어야 한다
 * (개인정보 보호법: 필요한 최소한 밖의 정보에 동의하지 않는다는 이유로 서비스를 거부할 수 없다 - 법무 확인 필요).
 *
 *   service_terms  서비스 이용약관                              필수
 *   privacy        개인정보 수집·이용                            필수
 *   sensitive      민감정보(종교·식사 제한 등) 수집·이용          선택
 *   location       개인위치정보 수집·이용(위치기반서비스 약관 포함)   선택
 *   alert_channel  알림 수신 채널 정보(디스코드 웹훅·텔레그램 대화) 수집·이용   선택
 *
 * 항목 이름(코드)은 서버 동의 기록(`/v1/web/consents`)과 같은 값이다 - 바꾸면 서버 계약도 바꿔야 한다.
 */
export const CONSENT_CODES = ["service_terms", "privacy", "sensitive", "location", "alert_channel"] as const;
export type ConsentCode = (typeof CONSENT_CODES)[number];

/** 이것이 모두 동의돼야 앱을 쓸 수 있다. */
export const REQUIRED_CONSENTS: readonly ConsentCode[] = ["service_terms", "privacy"];
export const OPTIONAL_CONSENTS: readonly ConsentCode[] = CONSENT_CODES.filter((code) => !REQUIRED_CONSENTS.includes(code));

export type ConsentMap = Record<ConsentCode, boolean>;

export const noConsents = (): ConsentMap => ({ service_terms: false, privacy: false, sensitive: false, location: false, alert_channel: false });

/** 필수 동의가 모두 있나. */
export function requiredAgreed(consents: Partial<Record<ConsentCode, boolean>>): boolean {
  return REQUIRED_CONSENTS.every((code) => consents[code] === true);
}
