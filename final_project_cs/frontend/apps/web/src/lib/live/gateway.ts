import type { Trip, TripGateway, TripMessage, TripStop } from "../../features/trip/model";
import { translator, type Language, type Translate } from "../i18n";
import { api, LiveError } from "./client";

/** Server trip view (`GET /v1/web/trips/{id}`) — only the fields the web reads. */
interface ServerItem {
  item_id: string;
  seq: number;
  kind: string;
  title: string;
  place: string | null;
  starts_at: string;
  ends_at: string | null;
  changed: boolean;
  lat?: number | null;
  lon?: number | null;
  booked?: boolean;
}
interface ServerTrip { trip_id: string; title: string; version: number; items: ServerItem[]; plan_url: string }

const MESSAGES_PREFIX = "tripilot.web.live.messages:";

/** Seoul wall-clock date and time of an ISO instant ("2026-10-15", "09:00"). */
function seoul(iso: string): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(new Date(iso));
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return { date: `${get("year")}-${get("month")}-${get("day")}`, time: `${get("hour")}:${get("minute")}` };
}

function stop(item: ServerItem, t: Translate): TripStop {
  const start = seoul(item.starts_at);
  const coordinates = typeof item.lat === "number" && typeof item.lon === "number" ? { lat: item.lat, lng: item.lon } : null;
  const notes = [item.place && item.place !== item.title ? t(`장소: ${item.place}`, `Place: ${item.place}`) : "",
    item.changed ? t("지켜보다 바뀐 일정이에요.", "This stop was changed while we watched your trip.") : ""].filter(Boolean).join(" · ");
  return {
    id: item.item_id, date: start.date, time: start.time, endTime: item.ends_at ? seoul(item.ends_at).time : undefined,
    title: item.title, booking: item.booked ? "booked" : "unknown", notes, coordinates,
  };
}

function readMessages(tripId: string): TripMessage[] {
  try { return JSON.parse(window.sessionStorage.getItem(MESSAGES_PREFIX + tripId) ?? "[]") as TripMessage[]; }
  catch { return []; }
}

function writeMessages(tripId: string, messages: TripMessage[]) {
  try { window.sessionStorage.setItem(MESSAGES_PREFIX + tripId, JSON.stringify(messages.slice(-60))); }
  catch { /* the conversation is shown for this page only */ }
}

/**
 * What the server did with a message, in fixed words. The server returns a status, not a sentence;
 * we do not invent an answer — an unknown status is shown by its own name.
 */
function replyFor(result: { status?: string; case_status?: string; answer?: string }, t: Translate): string {
  if (result.answer) return result.answer;           // the server's own customer sentence (`itinerary_team.ANSWERS`)
  switch (result.status) {
    case "adjusted": return t("일정을 바꿨어요. 바뀐 일정을 확인해 주세요.", "Your itinerary was changed. Please check the updated stops.");
    case "asked": return t("바꾸기 전에 확인이 필요해요. 여행계획서에서 안을 골라 주세요.", "We need your choice before changing anything. Pick an option on your plan page.");
    case "rolled_back": return t("이전 일정으로 되돌렸어요.", "Your itinerary was rolled back.");
    case "kept": return t("일정은 그대로 두었어요.", "Your itinerary was kept as it is.");
    case "no_alternate": return t("바꿀 만한 다른 안을 찾지 못해 일정은 그대로예요. 담당자가 확인해요.", "No suitable alternative was found, so nothing changed. A person will review it.");
    case "escalated": return t("자동으로 처리할 수 없어 담당자에게 넘겼어요.", "This could not be handled automatically and was passed to a person.");
    case "duplicate": return t("같은 요청을 이미 받았어요.", "We already received this request.");
    default: return t(`요청을 받았어요 (상태: ${result.status ?? result.case_status ?? "?"}).`, `Request received (status: ${result.status ?? result.case_status ?? "?"}).`);
  }
}

async function read(tripId: string, language: Language): Promise<Trip> {
  const t = translator(language);
  const server = await api<ServerTrip>(`/v1/web/trips/${encodeURIComponent(tripId)}`, language);
  // ★이동 항목(kind mobility — 출발 시각 = 다음 일정 시작 − 이동 − 여유)은 일정 목록에 섞지 않고 **다음 일정의 메모**로
  //   붙인다. 출발 알림은 서버가 그 시각에 보낸다(D-020). ☆2026-09-28 실제 화면: 「A → B」가 일정처럼 끼어 보였다.
  const stops: TripStop[] = [];
  let leave: string | null = null;
  for (const item of server.items) {
    if (item.kind === "mobility") { leave = seoul(item.starts_at).time; continue; }
    const next = stop(item, t);
    if (leave) next.notes = [t(`${leave} 출발`, `Leave at ${leave}`), next.notes].filter(Boolean).join(" · ");
    stops.push(next);
    leave = null;
  }
  const dates = stops.map((item) => item.date).sort();
  return {
    id: server.trip_id, source: "", startDate: dates[0] ?? "", endDate: dates.at(-1) ?? "", status: "active", stops,
    // ★The server judged the plan when it was registered (`_create_trip`): there is no separate check to run here.
    verification: { status: "completed", progress: 100, stages: [], results: [] },
    messages: readMessages(tripId),
  };
}

/** Live adapter over `/v1/web/*`. Registration goes through the intake screen, not `createTrip`. */
export function createLiveGateway(): TripGateway {
  return {
    createTrip: (_input, language) => Promise.reject(new LiveError("use_intake", translator(language)(
      "실제 연결에서는 계획 읽기 화면으로 등록해요.", "In live mode, plans are registered through the reading screen."))),
    getTrip: read,
    retryVerification: read,
    startTrip: read,
    async sendMessage(tripId, message, language) {
      const t = translator(language);
      const now = new Date().toISOString();
      const requestId = `web-${now}-${Math.random().toString(36).slice(2, 8)}`;
      const result = await api<{ status?: string; case_status?: string; answer?: string }>(`/v1/web/trips/${encodeURIComponent(tripId)}/messages`, language, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: requestId, message }),
      });
      const log = [...readMessages(tripId),
        { id: `${requestId}-q`, role: "user" as const, text: message, createdAt: now },
        { id: `${requestId}-a`, role: "assistant" as const, text: replyFor(result, t), createdAt: new Date().toISOString() }];
      writeMessages(tripId, log);
      return read(tripId, language);
    },
  };
}
