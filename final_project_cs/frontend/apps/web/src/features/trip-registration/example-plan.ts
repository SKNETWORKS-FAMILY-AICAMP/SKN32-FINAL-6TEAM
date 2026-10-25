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
 * server like anything they typed; nothing is answered from it here. The dates start tomorrow (Seoul), so the plan is never in the past.
 * ★`[2026-10-25 사용자 지시 — 하루 세 곳 · 우리가 보기에 가장 좋은 일정]` Three stops a day, each with an end time, and only places that open every
 * day of the week (no palace — 경복궁 closes on Tuesdays, 창덕궁 on Mondays — so a weekday never stops the check) and whose hours the server reads.
 */
export function examplePlan(language: Language, now: Date = new Date()): string {
  const first = addDays(seoulToday(now), 1);
  const second = addDays(first, 1);
  return language === "ko"
    ? `1일차 · ${first}
10:00 국립현대미술관 서울 · 현대미술 전시, 11:30 종료
12:00 인사동 · 점심, 13:30 종료
14:00 북촌한옥마을 · 한옥 골목 산책, 15:30 종료

2일차 · ${second}
09:30 국립중앙박물관 · 상설전시 관람, 11:30 종료
12:30 명동 · 점심, 14:00 종료
16:00 N서울타워 · 전망대 · 예약 있음, 18:00 종료`
    : `DAY 1 · ${first}
10:00 MMCA Seoul · Contemporary art exhibition, ends 11:30
12:00 Insadong · Lunch, ends 13:30
14:00 Bukchon Hanok Village · Walk through the hanok alleys, ends 15:30

DAY 2 · ${second}
09:30 National Museum of Korea · Permanent collection, ends 11:30
12:30 Myeongdong · Lunch, ends 14:00
16:00 N Seoul Tower · Observatory · booked, ends 18:00`;
}
