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
 * a place on each line). ★It is only text in the customer's own box — they read it, change it, and it goes to the
 * server like anything they typed; nothing is answered from it here.
 * ★`[2026-10-26 사용자 지시 — 1일차 오늘 · 2일차 내일]` Day 1 is the day it is pressed (Seoul) and day 2 the next day, so a stop earlier today is
 * already over — the server still registers it and leaves it out of the risk check (`not_applicable`). Three stops a day, and only places that
 * open every day of the week (no palace — 경복궁 closes on Tuesdays, 창덕궁 on Mondays — so a weekday never stops the check).
 */
export function examplePlan(language: Language, now: Date = new Date()): string {
  const first = seoulToday(now);
  const second = addDays(first, 1);
  return language === "ko"
    ? `1일차 · ${first}
12:00 인사동 · 점심
15:00 국립현대미술관 서울
18:00 N서울타워

2일차 · ${second}
09:30 국립중앙박물관
12:30 명동 · 점심
14:00 북촌한옥마을`
    : `DAY 1 · ${first}
12:00 Insadong · Lunch
15:00 MMCA Seoul
18:00 N Seoul Tower

DAY 2 · ${second}
09:30 National Museum of Korea
12:30 Myeongdong · Lunch
14:00 Bukchon Hanok Village`;
}
