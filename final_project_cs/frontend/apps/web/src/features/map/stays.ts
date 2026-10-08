import type { LocationStay } from "@/lib/live/location-samples";
import type { StayPoint } from "./model";

/**
 * `[2026-10-05]` Where the server found the customer stayed (`GET /v1/web/trips/{id}/location/stops`) → grey dots on a trip's map. Only what the
 * server gave: no stay is worked out, joined or moved on the page.
 */
const SEOUL_TIME = new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const SEOUL_DATE = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" });
const clock = (iso: string) => SEOUL_TIME.format(new Date(iso));

/** 「머문 곳 · 경복궁 관람 근처 · 14:05–14:20」 — the stop it is near only when the server matched one of `titles` (the stops on this map). */
export function stayLabel(stay: LocationStay, titles: Readonly<Record<string, string>>): string {
  const near = stay.matchedItemId && titles[stay.matchedItemId] ? ` · ${titles[stay.matchedItemId]} 근처` : "";
  const when = stay.endedAt ? `${clock(stay.startedAt)}–${clock(stay.endedAt)}` : `${clock(stay.startedAt)}부터 머무는 중`;
  return `머문 곳${near} · ${when}`;
}

/** The stays of `date` ("YYYY-MM-DD", the day the map shows — Seoul time), or all of them without one. Pure. */
export function toStayPoints(stays: readonly LocationStay[], date: string | undefined, titles: Readonly<Record<string, string>>): StayPoint[] {
  return stays
    .filter((stay) => !date || SEOUL_DATE.format(new Date(stay.startedAt)) === date)
    .map((stay) => ({ id: stay.stopId, coordinates: { lat: stay.lat, lng: stay.lng }, label: stayLabel(stay, titles) }));
}
