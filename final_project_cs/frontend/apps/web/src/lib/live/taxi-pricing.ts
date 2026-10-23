/** 서울 즉시호출 상품 선택. 요금은 cs 프로젝트 서버가 계산합니다. */
export const TAXI_PRODUCTS = [
  { id: "kakao_general", ko: "일반호출", en: "General taxi" },
  { id: "km_blue_immediate", ko: "KM 카카오 T 블루", en: "KM Kakao T Blue" },
  { id: "turu_blue_immediate", ko: "투루 블루파트너스", en: "Turu Blue Partners" },
  { id: "capsi_immediate", ko: "캡시 블루파트너스", en: "Capsi Blue Partners" },
  // 공식 승객약관 https://www.blackpin.co.kr/?mode=policy 제9조.
  // 시행2025-03-05, 관측2026-10-12. 과거 이용 당시 약관 버전 확정 근거는 아닙니다.
  { id: "mycap_immediate", ko: "마이캡", en: "MyCab" },
] as const;

export type TaxiProduct = typeof TAXI_PRODUCTS[number]["id"];
export interface WebTaxiPricing { product: TaxiProduct; quotes: [] }

/** 미지원 상품·견적·손상된 응답을 일반호출0원으로 바꾸지 않습니다. */
export function webTaxiPricingOf(value: unknown): WebTaxiPricing | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const row = value as Record<string, unknown>;
  if (Object.keys(row).sort().join(",") !== "product,quotes" || !TAXI_PRODUCTS.some((p) => p.id === row.product)
    || !Array.isArray(row.quotes) || row.quotes.length !== 0) return null;
  return { product: row.product as TaxiProduct, quotes: [] };
}
