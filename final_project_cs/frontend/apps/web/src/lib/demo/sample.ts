import type { Language } from "../i18n";

/** Public demonstration plans from the 2026-09-23 journey mockup. */
export const SAMPLE_PLANS: Record<Language, string> = {
  ko: `1일차 · 2026-09-15
09:00 호텔 조식
10:00 잠실 스카이타워 · 10:45 종료
11:00 성수동 쇼핑 · 향수, K-뷰티
13:00 성수 예약 식당 · 예약 있음
15:00 경복궁 · 한복 체험, 17:00 종료
18:00 서울역 인근 저녁 식당 · 예약 없이 방문
19:30 롯데마트 서울역점 · 식료품 쇼핑

2일차 · 2026-09-16
09:00 호텔 조식
10:00 국립중앙박물관 · 전시 관람
12:00 이촌동 점심 식당 · 예약 있음
14:00 이태원 소품숍 · 기념품 구경
16:00 이촌 한강공원 · 산책
18:00 용산 저녁 식당 · 예약 없이 방문
20:00 호텔 복귀 · 짐 정리`,
  en: `DAY 1 · 2026-09-15
09:00 Hotel breakfast
10:00 Jamsil Sky Tower · ends 10:45
11:00 Seongsu shopping · Perfume and K-beauty
13:00 Seongsu restaurant · booked
15:00 Gyeongbokgung Palace · Hanbok experience, ends 17:00
18:00 Dinner near Seoul Station · no reservation
19:30 Lotte Mart Seoul Station · Grocery shopping

DAY 2 · 2026-09-16
09:00 Hotel breakfast
10:00 National Museum of Korea · Exhibition visit
12:00 Lunch in Ichon-dong · booked
14:00 Itaewon gift shops · Souvenir browsing
16:00 Ichon Hangang Park · Walk
18:00 Dinner in Yongsan · no reservation
20:00 Return to the hotel · Packing`,
};

export function isSamplePlan(source: string) {
  const text = source.replace(/\r\n?/g, "\n").trim();
  return text === SAMPLE_PLANS.ko || text === SAMPLE_PLANS.en;
}
