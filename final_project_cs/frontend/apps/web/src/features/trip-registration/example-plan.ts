import type { Language } from "@/lib/i18n";
import { seoulToday } from "./model";

/** `YYYY-MM-DD` plus `days` calendar days (done in UTC, so a time zone never moves the date). */
function addDays(date: string, days: number): string {
  const moved = new Date(`${date}T00:00:00Z`);
  moved.setUTCDate(moved.getUTCDate() + days);
  return moved.toISOString().slice(0, 10);
}

/**
 * What 「예시 불러오기」 puts in the text box: a two-day Seoul plan written the way the box asks for (a date on each day's title, a start time and
 * a place on each line, 「예약 있음」 for a booked stop). ★It is only text in the customer's own box — they read it, change it, and it goes to the
 * server like anything they typed; nothing is answered from it here. The dates start a week from today (Seoul), so the plan is never in the past,
 * and every place is one the server can look up (a palace, a museum, a market, a tower — no shop whose name is a guess).
 */
export function examplePlan(language: Language, now: Date = new Date()): string {
  const first = addDays(seoulToday(now), 7);
  const second = addDays(first, 1);
  return language === "ko"
    ? `1일차 · ${first}
09:00 호텔 조식
10:00 경복궁 · 한복 체험, 12:00 종료
12:30 광장시장 · 점심
15:00 국립중앙박물관 · 전시 관람
19:00 N서울타워 · 예약 있음

2일차 · ${second}
09:00 호텔 조식
10:00 북촌한옥마을 · 산책
12:00 인사동 · 점심
14:00 창덕궁 · 후원 관람
17:00 청계천 · 산책`
    : `DAY 1 · ${first}
09:00 Hotel breakfast
10:00 Gyeongbokgung Palace · Hanbok experience, ends 12:00
12:30 Gwangjang Market · Lunch
15:00 National Museum of Korea · Exhibition visit
19:00 N Seoul Tower · booked

DAY 2 · ${second}
09:00 Hotel breakfast
10:00 Bukchon Hanok Village · Walk
12:00 Insadong · Lunch
14:00 Changdeokgung Palace · Secret Garden tour
17:00 Cheonggyecheon Stream · Walk`;
}
