import type { Trip, TripChange, TripGateway, TripGuardian, TripMessage, TripMove, TripSafety, TripStop, TripWarning } from "../../features/trip/model";
import { translator, type Language, type Translate } from "../i18n";
import { api, hasSession, LiveError } from "./client";
import { streamApi } from "./stream";

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
  badges?: { code: string; label: string; source: string }[];
  place_info?: ServerPlaceInfo | null;
  map_url?: string | null;
  /** `[2026-10-06]` Falls in a disaster pause. */
  paused?: boolean;
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
/** `safety` of the trip view (rest-endpoints 「재난 시 일정 정지」): `{paused: false}` or the pause with its resume. */
interface ServerSafety {
  paused?: unknown; level?: unknown; phase?: unknown; label?: unknown; since?: unknown; until?: unknown; day?: unknown; released?: unknown;
  resume?: { label?: unknown; path?: unknown } | null;
}
interface ServerTrip {
  trip_id: string; title: string; version: number; items: ServerItem[]; plan_url: string;
  history?: ServerHistory[]; warnings?: ServerWarning[];
  safety?: ServerSafety | null;
  /** `guardian` of the trip view (rest-endpoints 「항로 지킴이」): `{enabled, since, via}`. */
  guardian?: { enabled?: unknown; since?: unknown; via?: unknown } | null;
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
    // A badge without its label or source is dropped — the screen does not show a mark of unknown origin.
    badges: (item.badges ?? []).filter((badge) => [badge?.code, badge?.label, badge?.source].every((value) => typeof value === "string" && value !== ""))
      .map(({ code, label, source }) => ({ code, label, source })),
    placeInfo: placeInfo(item.place_info, t),
    mapUrl: mapLink(item.map_url),
    ...(item.paused === true ? { paused: true } : {}),
  };
}

/** An instant of the pause in Seoul time ("2026-10-06 14:05"); something that is not an instant (a plain date) is shown as it came. */
function whenOf(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  if (!Number.isFinite(Date.parse(value)) || !/T|\d:\d/.test(value)) return value;
  const at = seoul(value);
  return `${at.date} ${at.time}`;
}

/** The server's `guardian` of a trip. No object (an older server) is null - the icon is then not drawn; a field it did not send is null, and `enabled` is only ever the server's `true`. */
export function guardianOf(raw: ServerTrip["guardian"] | undefined): TripGuardian | null {
  if (!raw || typeof raw !== "object" || typeof raw.enabled !== "boolean") return null;
  return { enabled: raw.enabled, since: typeof raw.since === "string" ? raw.since : null, via: typeof raw.via === "string" ? raw.via : null };
}

/** The server's `safety` of a trip, as the screen reads it. Nothing is made up: a field the server did not send is null, and no `safety` at all is null (an older server). */
export function safetyOf(raw: ServerSafety | null | undefined): TripSafety | null {
  if (!raw || typeof raw !== "object") return null;
  const label = typeof raw.resume?.label === "string" && raw.resume.label.trim() ? raw.resume.label.trim() : null;
  return {
    paused: raw.paused === true,
    level: raw.level === "day" || raw.level === "trip" ? raw.level : null,
    phase: raw.phase === "in_progress" || raw.phase === "upcoming" ? raw.phase : null,
    label: typeof raw.label === "string" && raw.label.trim() ? raw.label.trim() : null,
    since: whenOf(raw.since), until: whenOf(raw.until),
    day: typeof raw.day === "string" && raw.day ? raw.day : null,
    released: raw.released === true,
    resume: raw.resume && typeof raw.resume === "object" ? { label: label ?? "" } : null,
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
      ...(kept?.choicesTitle ? { choicesTitle: kept.choicesTitle } : {}), ...(kept?.more ? { more: kept.more } : {}),
      ...(kept?.needsLocation ? { needsLocation: true } : {}) };
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

/** This tab's copy of a deleted trip's conversation goes with it. */
function forgetMessages(tripId: string) {
  try { window.sessionStorage.removeItem(MESSAGES_PREFIX + tripId); }
  catch { /* nothing kept */ }
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
  // ★`[2026-10-04]` A trip has an owner: a browser with no session (a link someone kept, or a guest session that ended) is not made a new guest just to be
  //   told "not yours". It is told so at once, with the way back — a login brings an account's trips back; a guest's trips are gone.
  if (!await hasSession(language)) {
    throw new LiveError("not_found", t("이 여행을 찾지 못했어요. 창을 닫았거나 시간이 지나 게스트 여행이 사라졌을 수 있어요. 계정에 보관한 여행이라면 마이페이지에서 로그인하면 다시 열려요.", "We could not find this trip. A guest trip cannot be continued after the window is closed, and is deleted after a while. If it is kept with an account, sign in on My page to open it again."));
  }
  const server = await api<ServerTrip>(`/v1/web/trips/${encodeURIComponent(tripId)}`, language);
  // ★이동 항목(kind mobility — 출발 시각 = 다음 일정 시작 − 이동 − 여유)은 일정 목록에 섞지 않는다(☆2026-09-28 「A → B」가 일정처럼 끼어 보였다).
  //   `[2026-10-07]` 여행 화면이 일정 사이의 이동 줄로 그리므로 앞뒤 일정과 함께 `moves` 로 따로 둔다(전에는 다음 일정 메모의 「몇 시 출발」이었다). 출발 알림은 서버가 그 시각에 보낸다(D-020).
  const stops: TripStop[] = [];
  const moves: TripMove[] = [];
  for (const item of server.items) {
    if (item.kind !== "mobility") { stops.push(stop(item, t)); continue; }
    const depart = seoul(item.starts_at);
    moves.push({ id: item.item_id, fromId: stops.at(-1)?.id ?? null, toId: null, date: depart.date, departAt: depart.time,
      arriveAt: item.ends_at ? seoul(item.ends_at).time : null, title: item.title });
  }
  // The stop after each move is the next stop in the plan.
  for (const move of moves) {
    const at = server.items.findIndex((item) => item.item_id === move.id);
    move.toId = server.items.slice(at + 1).find((item) => item.kind !== "mobility")?.item_id ?? null;
  }
  // ★The server judged the plan when it was registered (`_create_trip`) — what it found is `warnings`, not a separate check to run.
  return {
    id: server.trip_id, title: text(server.title), stops, moves,
    messages: await conversation(tripId, language),
    planUrl: server.plan_url || undefined,
    version: typeof server.version === "number" ? server.version : undefined,
    safety: safetyOf(server.safety),
    guardian: guardianOf(server.guardian),
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

/**
 * A message whose send failed, by trip. Sending the same text again reuses its `request_id`, so a message the server
 * did receive (the reply was lost on the way back) is not acted on twice — the server answers a known `request_id` with
 * the first result (`open_case`). Cleared once the server answers.
 */
const unanswered = new Map<string, { message: string; itemId: string | null; requestId: string }>();

/**
 * ★`[2026-10-03]` 여행 삭제 — 서버에 아직 없다(`DELETE`도 `POST …/delete`도 `app/` 의 라우트에 없음, 백엔드 요청서
 *   `wiki/records/plans/2026-10-03_1920_웹_실서버_전환_백엔드_요청.md`). 웹은 요청한 모양 그대로 연결해 둔다:
 *   `POST /v1/web/trips/{id}/delete`(본인 여행만, 이미 없으면 404 `not_found`). 서버에 그 경로가 없으면 FastAPI 가 본문
 *   `{"detail":"Not Found"}` 의 404(`HTTP_404`)를 주므로 — 여행이 없다는 서버 문장(`not_found`)과 갈라 — 「지원하지 않음」으로 말한다.
 *   (실서버 8042 에서 확인: 없는 경로 POST → 404 `{"detail":"Not Found"}`.) `POST` 로 한 것은 서버 CORS 가 GET·POST·PUT 만 열어서다.
 */
async function removeTrip(tripId: string, language: Language): Promise<void> {
  const t = translator(language);
  try { await api<unknown>(`/v1/web/trips/${encodeURIComponent(tripId)}/delete`, language, { method: "POST" }); }
  catch (error) {
    // A 2xx answer with no JSON body is still a success (the server deleted it): only `api`'s body read fails.
    if (error instanceof SyntaxError) { forgetMessages(tripId); return; }
    if (error instanceof LiveError && (error.code === "HTTP_404" || error.code === "HTTP_405")) {
      throw new LiveError("delete_unsupported", t("서버가 아직 여행 삭제를 지원하지 않아요. 지원되면 바로 쓸 수 있어요.", "The server does not support deleting trips yet. It will work as soon as the server does."));
    }
    if (error instanceof LiveError && error.code === "not_found") { forgetMessages(tripId); return; }   // already gone
    throw error;
  }
  forgetMessages(tripId);
}

/** Live adapter over `/v1/web/*`. Registration goes through the plan-check screen (`lib/live/intake*.ts`), not through here. */
export function createLiveGateway(): TripGateway {
  return {
    async listTrips(language) {
      // ★No session means this browser has registered nothing. Asking with the list would make a guest session — a new server user —
      //   only to list nothing, so we only ask who this browser is (`hasSession`) and stop there when nobody.
      if (!await hasSession(language)) return [];
      const { trips } = await api<{ trips: ServerTripRow[] }>("/v1/web/trips", language);
      return trips.map((row) => ({ id: row.trip_id, title: row.title, createdAt: row.created_at, version: row.version }));
    },
    getTrip: read,
    deleteTrip: removeTrip,
    async sendMessage(tripId, message, language, itemId, location, onProgress) {
      const t = translator(language);
      const now = new Date().toISOString();
      const earlier = unanswered.get(tripId);
      const requestId = earlier && earlier.message === message && earlier.itemId === (itemId ?? null)
        ? earlier.requestId : `web-${now}-${Math.random().toString(36).slice(2, 8)}`;
      unanswered.set(tripId, { message, itemId: itemId ?? null, requestId });
      // ★`[2026-10-02]` Asked as a stream, the server says what it is doing while the model works (`stream.ts`); a lost line
      //   sends the same `request_id` again, which the server answers without acting twice.
      const result = await streamApi<{ status?: string; case_status?: string; answer?: string; basis_sources?: unknown[] | null; choices?: { label?: unknown; message?: unknown }[] | null;
        outcome?: { status?: string; version?: unknown } | null; more?: unknown; choices_title?: unknown; needs_location?: unknown }>(`/v1/web/trips/${encodeURIComponent(tripId)}/messages`, language, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ request_id: requestId, message, ...(itemId ? { item_id: itemId } : {}),
          // ★Only when the customer pressed 「내 위치 알려 주고 다시 묻기」 — never attached on its own.
          ...(location ? { location: { lat: location.lat, lng: location.lng, accuracy_m: location.accuracyM, at: location.at } } : {}) }),
      }, onProgress);
      unanswered.delete(tripId);
      const sent: TripMessage[] = [
        { id: `${requestId}-q`, role: "user" as const, text: message, createdAt: now },
        { id: `${requestId}-a`, role: "assistant" as const, text: replyFor(result, t), createdAt: new Date().toISOString(),
          ...(basisOf(result.basis_sources).length ? { basis: basisOf(result.basis_sources) } : {}),
          ...(choicesOf(result.choices).length ? { choices: choicesOf(result.choices) } : {}),
          ...(typeof result.choices_title === "string" && result.choices_title.trim() ? { choicesTitle: result.choices_title.trim() } : {}),
          ...(typeof result.more === "string" && result.more.trim() ? { more: result.more.trim() } : {}),
          ...(result.needs_location === true && !location ? { needsLocation: true } : {}),
          // ★A change the customer asked for in chat can be undone from the answer (user decision 2026-09-29).
          ...(result.status === "adjusted" && typeof result.outcome?.version === "number" && result.outcome.version > 1
            ? { changedTo: result.outcome.version } : {}) }];
      writeMessages(tripId, [...readMessages(tripId), ...sent]);
      // ★Sending and re-reading are two steps (2026-09-30, teammate question Q-05). The server has answered; a failed
      //   re-read must not turn that into "not sent" — the customer would send again and the change would run twice.
      //   The caller shows the reply it got (`detail.sent`) and re-reads later.
      try { return await read(tripId, language); }
      catch { throw new LiveError("reply_kept", t("답은 받았어요. 최신 일정을 다시 불러오지 못해 잠시 뒤 다시 읽고 있어요.", "The reply arrived. The latest plan did not load, so it is being read again shortly."), { sent }); }
    },
  };
}
