import type { Trip, TripChange, TripGateway, TripMessage, TripStop, TripWarning } from "../../features/trip/model";
import { translator, type Language, type Translate } from "../i18n";
import { api, currentKey, LiveError } from "./client";

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
  other_options?: { key: string; name: string }[];
  customer_pinned?: boolean;
  place_info?: ServerPlaceInfo | null;
  map_url?: string | null;
}
/** ★`[2026-09-29]` 서버에 요청한 모양(요식 원장·관광공사에서 읽은 장소 사실). 서버가 아직 안 보내면 상세에 안 나온다. */
interface ServerPlaceInfo {
  address?: string | null; phone?: string | null; category?: string | null;
  hours?: { day?: string; open?: string; close?: string; closed?: boolean; last_order?: string | null; last_entry?: string | null }[] | null;
  /** Opening-hours text as the source wrote it (places outside the dining ledger). */
  hours_text?: string[] | string | null;
  /** Conditions the server could not turn into a weekly table, in the source's words. */
  hours_conditions?: string[] | null;
  tags?: string[] | null; michelin?: { level?: string; year?: number } | null; source_note?: string | null;
}
interface ServerHistory { version: number; reason: string; at: string; causes?: Record<string, unknown>[] }
interface ServerWarning { code?: string; date?: string | null; reason?: string; remedy?: string | null }
interface ServerTrip {
  trip_id: string; title: string; version: number; items: ServerItem[]; plan_url: string;
  history?: ServerHistory[]; warnings?: ServerWarning[];
  map?: { days?: { date?: string; app_route_urls?: unknown[]; legs?: { from_item_id?: unknown; to_item_id?: unknown; url?: unknown }[] }[] } | null;
}

/** ★Only Google Maps links are opened from the screen — anything else from the server is not shown as a map link. */
function mapLink(value: unknown): string | undefined {
  return typeof value === "string" && value.startsWith("https://www.google.com/maps/") ? value : undefined;
}
/** One row of `GET /v1/web/trips`. */
interface ServerTripRow { trip_id: string; title: string; version: number; created_at: string }

const MESSAGES_PREFIX = "tripilot.web.live.messages:";

/** Seoul wall-clock date and time of an ISO instant ("2026-10-15", "09:00"). */
export function seoul(iso: string): { date: string; time: string } {
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
    pinned: item.customer_pinned === true,
    otherOptions: (item.other_options ?? []).filter((option) => typeof option?.key === "string" && typeof option?.name === "string"),
    placeInfo: placeInfo(item.place_info, t),
    mapUrl: mapLink(item.map_url),
  };
}

const text = (value: unknown): string | undefined => (typeof value === "string" && value.trim() ? value.trim() : undefined);

/** The server's place facts, keeping only what it actually sent — an empty field is left out, not shown as "unknown". */
export function placeInfo(raw: ServerPlaceInfo | null | undefined, t: Translate = translator("ko")): TripStop["placeInfo"] {
  if (!raw || typeof raw !== "object") return null;
  const hours = Array.isArray(raw.hours)
    ? raw.hours.map((rule) => [text(rule?.day),
      rule?.closed === true ? t("휴무", "Closed") : text(rule?.open) && text(rule?.close) ? `${rule.open}–${rule.close}` : undefined,
      rule?.closed !== true && text(rule?.last_order) ? t(`(주문 마감 ${rule.last_order})`, `(last order ${rule.last_order})`) : undefined,
      rule?.closed !== true && text(rule?.last_entry) ? t(`(입장 마감 ${rule.last_entry})`, `(last entry ${rule.last_entry})`) : undefined,
    ].filter(Boolean).join(" ")).filter(Boolean)
    : [];
  const lines = (value: unknown): string[] =>
    (Array.isArray(value) ? value : [value]).map(text).filter((line): line is string => !!line);
  // ★With a weekly table the source text only adds its conditions; without one, the source text is the hours.
  const hoursNotes = hours.length ? lines(raw.hours_conditions) : [...lines(raw.hours_text), ...lines(raw.hours_conditions)];
  const level = text(raw.michelin?.level);
  const info = {
    address: text(raw.address), phone: text(raw.phone), category: text(raw.category), hours, hoursNotes: [...new Set(hoursNotes)],
    tags: Array.isArray(raw.tags) ? raw.tags.filter((tag): tag is string => typeof tag === "string" && !!tag) : [],
    michelin: level ? { level, year: typeof raw.michelin?.year === "number" ? raw.michelin.year : undefined } : null,
    sourceNote: text(raw.source_note),
  };
  const empty = !info.address && !info.phone && !info.category && !hours.length && !info.hoursNotes.length && !info.tags.length && !info.michelin;
  return empty ? null : info;
}

/** A cause in the server's own words: its summary/message when it has one, else what kind of thing it was. */
function causeText(cause: Record<string, unknown>): string {
  for (const field of ["summary", "message"]) if (typeof cause[field] === "string" && cause[field]) return cause[field] as string;
  return ["category", "type", "kind"].map((field) => cause[field]).filter((value): value is string => typeof value === "string").join(" · ");
}

function change(row: ServerHistory): TripChange {
  const at = seoul(row.at);
  return { version: row.version, reason: row.reason, at: `${at.date} ${at.time}`, causes: (row.causes ?? []).map(causeText).filter(Boolean) };
}

/** ★A warning with no reason is dropped, not invented: without the server's sentence there is nothing true to show. */
function warning(row: ServerWarning): TripWarning | null {
  if (typeof row.reason !== "string" || !row.reason) return null;
  return { code: row.code ?? "", date: row.date ?? null, reason: row.reason, remedy: typeof row.remedy === "string" && row.remedy ? row.remedy : null };
}

interface ServerTurn { role?: string; text?: string; case_id?: string | null; at?: string }

/**
 * ★`[2026-09-29]` The conversation is the server's record (`GET /v1/web/trips/{id}/chat`) — it follows the customer to
 * another tab or device. This tab's own copy only adds what the record does not keep (the last answer's choices and,
 * in development mode, its basis). If the record cannot be read, this tab's copy is shown.
 */
async function conversation(tripId: string, language: Language): Promise<TripMessage[]> {
  const local = readMessages(tripId);
  let turns: ServerTurn[];
  try { turns = (await api<{ turns?: ServerTurn[] }>(`/v1/web/trips/${encodeURIComponent(tripId)}/chat?limit=40`, language)).turns ?? []; }
  catch { return local; }
  const extras = new Map(local.filter((message) => message.role === "assistant").map((message) => [message.text, message]));
  const recorded = turns.filter((turn) => typeof turn.text === "string" && turn.text).map((turn, index) => {
    const role = turn.role === "customer" ? "user" as const : "assistant" as const;
    const kept = role === "assistant" ? extras.get(turn.text as string) : undefined;
    return { id: `chat-${turn.case_id ?? "x"}-${index}`, role, text: turn.text as string, createdAt: turn.at ?? "",
      ...(kept?.choices ? { choices: kept.choices } : {}), ...(kept?.basis ? { basis: kept.basis } : {}),
      ...(kept?.changedTo ? { changedTo: kept.changedTo } : {}),
      ...(kept?.choicesTitle ? { choicesTitle: kept.choicesTitle } : {}), ...(kept?.more ? { more: kept.more } : {}) };
  });
  // ★The record can lag the reply this tab just got (the server may finish writing it after answering). What this tab
  //   sent or received after the record's last turn is kept at the end — never dropped, never shown twice.
  //   ☆2026-09-29 real server: right after sending, the latest answer vanished and an older one showed in its place.
  // ★Matched by content, not by clock: the record's time is when the server wrote the answer, which can be a moment
  //   *before* this tab received it — a time rule showed every answer twice (2026-09-29 real server, user report).
  //   A question and its answer from this tab are added only when the answer is not in the record yet.
  const answered = new Set(recorded.filter((message) => message.role === "assistant").map((message) => message.text));
  const tail: TripMessage[] = [];
  for (let index = 0; index < local.length; index += 1) {
    const message = local[index];
    const reply = message.role === "user" ? local[index + 1] : undefined;
    if (message.role === "user" && reply?.role === "assistant") {
      if (!answered.has(reply.text)) tail.push(message, reply);
      index += 1;
    } else if (message.role === "assistant" && !answered.has(message.text)) tail.push(message);
  }
  return [...recorded, ...tail];
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
 * ★`[2026-09-28]` The server now puts an `answer` on every result (chat always answers), so the screen must not
 *   fill in its own “we passed it to a person” line for `escalated`: that branch was removed on purpose.
 */
/** Rule sections behind an answer (`basis_sources`) — present only in development mode (`web.dev_mode`); a string or `{source}` each. */
function basisOf(raw: unknown[] | null | undefined): string[] {
  return (raw ?? []).map((entry) => (typeof entry === "string" ? entry : typeof (entry as { source?: unknown })?.source === "string" ? (entry as { source: string }).source : ""))
    .filter((source) => source.trim() !== "");
}

/** 「다음 중 하나인가요?」 — only choices with a sentence to send are kept. */
function choicesOf(raw: { label?: unknown; message?: unknown }[] | null | undefined): { label: string; message: string }[] {
  return (raw ?? []).flatMap((choice) => typeof choice?.message === "string" && choice.message.trim()
    ? [{ label: typeof choice.label === "string" && choice.label.trim() ? choice.label : choice.message, message: choice.message }] : []);
}

function replyFor(result: { status?: string; case_status?: string; answer?: string }, t: Translate): string {
  if (result.answer) return result.answer;           // the server's own customer sentence (`itinerary_team.ANSWERS`)
  switch (result.status) {
    case "adjusted": return t("일정을 바꿨어요. 바뀐 일정을 확인해 주세요.", "Your itinerary was changed. Please check the updated stops.");
    case "asked": return t("바꾸기 전에 확인이 필요해요. 여행계획서에서 안을 골라 주세요.", "We need your choice before changing anything. Pick an option on your plan page.");
    case "rolled_back": return t("이전 일정으로 되돌렸어요.", "Your itinerary was rolled back.");
    case "kept": return t("일정은 그대로 두었어요.", "Your itinerary was kept as it is.");
    case "no_alternate": return t("바꿀 만한 다른 안을 찾지 못해 일정은 그대로예요.", "No suitable alternative was found, so nothing changed.");
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
    messages: await conversation(tripId, language),
    planUrl: server.plan_url || undefined,
    version: typeof server.version === "number" ? server.version : undefined,
    history: (server.history ?? []).map(change),
    warnings: (server.warnings ?? []).map(warning).filter((item): item is TripWarning => item !== null),
    dayRoutes: Object.fromEntries((server.map?.days ?? []).flatMap((day) => {
      const urls = (day.app_route_urls ?? []).map(mapLink).filter((url): url is string => !!url);
      return typeof day.date === "string" && urls.length ? [[day.date, urls]] : [];
    })),
    legs: Object.fromEntries((server.map?.days ?? []).flatMap((day) => (day.legs ?? []).flatMap((leg) => {
      const url = mapLink(leg?.url);
      return url && typeof leg.from_item_id === "string" && typeof leg.to_item_id === "string" ? [[`${leg.from_item_id}>${leg.to_item_id}`, url]] : [];
    }))),
  };
}

/** Live adapter over `/v1/web/*`. Registration goes through the intake screen, not `createTrip`. */
export function createLiveGateway(): TripGateway {
  return {
    createTrip: (_input, language) => Promise.reject(new LiveError("use_intake", translator(language)(
      "실제 연결에서는 계획 읽기 화면으로 등록해요.", "In live mode, plans are registered through the reading screen."))),
    async listTrips(language) {
      // ★No stored key means this browser has registered nothing. Asking would issue a key — a new server user — only to
      //   list nothing, so we do not ask.
      if (!currentKey()) return [];
      const { trips } = await api<{ trips: ServerTripRow[] }>("/v1/web/trips", language);
      return trips.map((row) => ({ id: row.trip_id, title: row.title, createdAt: row.created_at, version: row.version }));
    },
    getTrip: read,
    retryVerification: read,
    startTrip: read,
    async sendMessage(tripId, message, language, itemId) {
      const t = translator(language);
      const now = new Date().toISOString();
      const requestId = `web-${now}-${Math.random().toString(36).slice(2, 8)}`;
      const result = await api<{ status?: string; case_status?: string; answer?: string; basis_sources?: unknown[] | null; choices?: { label?: unknown; message?: unknown }[] | null;
        outcome?: { status?: string; version?: unknown } | null; more?: unknown; choices_title?: unknown }>(`/v1/web/trips/${encodeURIComponent(tripId)}/messages`, language, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: requestId, message, ...(itemId ? { item_id: itemId } : {}) }),
      });
      const log = [...readMessages(tripId),
        { id: `${requestId}-q`, role: "user" as const, text: message, createdAt: now },
        { id: `${requestId}-a`, role: "assistant" as const, text: replyFor(result, t), createdAt: new Date().toISOString(),
          ...(basisOf(result.basis_sources).length ? { basis: basisOf(result.basis_sources) } : {}),
          ...(choicesOf(result.choices).length ? { choices: choicesOf(result.choices) } : {}),
          ...(typeof result.choices_title === "string" && result.choices_title.trim() ? { choicesTitle: result.choices_title.trim() } : {}),
          ...(typeof result.more === "string" && result.more.trim() ? { more: result.more.trim() } : {}),
          // ★A change the customer asked for in chat can be undone from the answer (user decision 2026-09-29).
          ...(result.status === "adjusted" && typeof result.outcome?.version === "number" && result.outcome.version > 1
            ? { changedTo: result.outcome.version } : {}) }];
      writeMessages(tripId, log);
      return read(tripId, language);
    },
  };
}
