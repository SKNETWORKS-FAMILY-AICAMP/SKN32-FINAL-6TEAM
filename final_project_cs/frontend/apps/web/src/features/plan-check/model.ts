import type { Coordinates } from "@/features/map/model";
import type { WebTaxiPricing } from "@/lib/live/taxi-pricing";
import type { ItemRisk } from "@/lib/live/risks";
import type { MoveRoute, RouteChoice } from "@/lib/live/move-options";

/**
 * The plan-check screen (after 「계획 확인하기」), built from the mockup `mockups/tripilot-plan-check-streaming.html`.
 *
 * ★This file is the screen's data contract. The screen draws a `PlanCheckView` snapshot and nothing else; it never calls
 *   the server — the page passes what can change through `PlanCheckActions` (plan-check.tsx). The real route maps the
 *   server's intake onto it (`from-intake.ts`); the preview fills every field from example data. A field or action the
 *   server does not give yet is where the backend connects (PLAN_CHECK_SCREEN.md §4).
 */

/** One check's result (mockup `result`): passed · filled in by the server · warning · must fix · not known yet · not checked yet. */
export type CheckResult = "ok" | "filled" | "warn" | "bad" | "unknown" | "pending";
/** Place checks: place · time · hours · closed. Move checks: route · mode · arrival. */
export type CheckKind = "place" | "time" | "hours" | "closed" | "booking" | "route" | "mode" | "arrival" | "risk" | "dining_check" | "dietary" | "kids" | "payment" | "business";
export interface CheckRow { kind: CheckKind; result: CheckResult; text: string; canAcknowledge?: boolean }
/** `[2026-10-07]` One value read two ways off a photo: the one kept and the other reading. */
export interface Reread { field: "title" | "booking_no"; current: string; other: string }

/** A card's verdict once its checks are in. Null while it is still being checked. */
export type Verdict = "keep" | "adjusted" | "review";

/** A place photo: the server's place data (`url`), or — preview only — an example drawing (`url` null). */
/** A photo the server named (its address is checked before it is kept — `safePhotoUrl`); there are no stand-in pictures. */
export interface PlacePhoto { caption: string; url: string }

/** What a place is and where, for the change screen's cards. Null when the server has not given it. */
export interface PlaceInfo {
  /** e.g. 「관광지 · 고궁」 */
  category: string | null;
  address: string | null;
  photos: PlacePhoto[];
  /** What kind of stop the place is, as the server classes it (a meal place or an activity) — null when it does not say. */
  kind?: "dining" | "activity" | string | null;
  /** Where the server found it: `places` (our list) · `tour_api` (tourism service) · `kakao` (map search) · `customer_pick` … */
  origin?: string | null;
}

export interface PlanItem {
  risk?: ItemRisk | null;
  id: string;
  day: number;
  /** "YYYY-MM-DD", or "" when the server has no date for it. */
  date: string;
  /** "HH:MM" */
  startsAt: string;
  /** "HH:MM", or "" when there is none. */
  endsAt: string;
  /** `[2026-10-13]` "YYYY-MM-DD" of the end when it is another day — a stay (kind lodging) ends on its check-out day. */
  endDate?: string;
  /**
   * What the card is called. ★`[2026-10-03 사용자]` Once the customer picked a place for the stop, this is that place's name —
   * the card used to keep the words they had written ("성수 예약 식당") after the place had changed.
   */
  title: string;
  /** The words as written in the plan, when `title` is the picked place's name instead (the stop editor edits these, not the place). */
  written?: string;
  /** The place's name as the server holds it ("" when none), and whether the customer chose 「장소 없음」. */
  place: string;
  noPlace: boolean;
  /** `[2026-10-07]` What kind of stop the server classes it (`activity` · `dining`), for the tag under the map when its pin is picked — null when it does not say. */
  kind?: string | null;
  /** Place category for the icon; a hotel breakfast remains a dining stop. */
  displayKind?: string | null;
  lodgingGroup?: { id: string; members: string[]; place: string | null };
  /** Null when the place is not settled — it shows as 「위치 미정」 instead of a pin. */
  coordinates: Coordinates | null;
  checks: CheckRow[];
  /** `[2026-10-07]` Values the server read two ways off a photo — the customer picks one (only those with another reading to offer). */
  rereads?: Reread[];
  verdict: Verdict | null;
  /** Fixed by the customer: kept through re-planning and recommendations (mockup 「잠금」 — 「반드시 포함」). */
  locked: boolean;
  /** `[2026-10-04]` The plan says the stop is booked (`true`), says it is not (`false`), or says nothing (`null`; also an older server). */
  booked: boolean | null;
  info: PlaceInfo | null;
  /** The first alternative's name, said under the card's 「자동 추천」 — null when none is known. */
  suggestion: string | null;
  /**
   * `[2026-10-13 사용자 결정 — 수정 모드]` A stop of the registered trip that is not in the edit (its end has passed — `reopen.frozen_item_ids`): one grey line, nothing on it can change,
   * nothing pushes it. Absent on the plan check of a new plan.
   */
  past?: boolean;
  /**
   * `[2026-10-15 ST4F-490]` Why a `past` stop is not in the edit — only `past` is called over; the others say what keeps them out (`reopen.frozen`). Null when the server did not say.
   */
  fixedReason?: "past" | "overnight" | "no_place" | "kind" | null;
  /** `[2026-10-15 사용자 결정 — 연결 유지 + 안내]` Tied to a vendor's booking: unlocking it says the booking is changed with the vendor (`vendor_booking`). */
  vendorBooking?: boolean;
  /**
   * `[2026-10-19 사용자 결정 — 못 찾은 장소]` The server could not find this stop's place and asks (`prefill.questions[]` `kind: "place_not_found"`): the card shows `question` as it is,
   * its candidates, 「직접 고르기」 and 「장소 없이」. `blocked` = the lookup was blocked and searched once more. Absent once the stop has a place or 「장소 없음」.
   */
  unfound?: { question: string; blocked: boolean };
  /**
   * `[2026-10-20 사용자 결정 — 계획 확인 C안]` How the server settled the place (`place_state`: `picked_nearest` = one of several, the nearest taken for now) and how many places
   * matched the name (`candidates_hint`) — what the question asked at the stop says. Absent where the server did not say (the preview, an older server).
   */
  placeState?: string | null;
  placeChoices?: number | null;
  /**
   * `[2026-10-21 사용자 결정 — P6 해석 확인 질문]` Not a stop: the place in the first check's list where it stopped to ask what a line of the plan means (`PlanAsk`) — a card-less question
   * at the line's time. Only the list of the stopped check carries one (`withAskSlot`).
   */
  ask?: PlanAsk;
}

/**
 * ★`[2026-10-21 사용자 결정 — P6 해석 확인 질문]` A line of the plan the reading AI read as something other than a stop where the rule read one (`interpretations[]`, not answered yet): the
 * stop is out for now (the AI's reading) and the first check stops at the line's time to ask (mockup `mockups/tripilot-plan-check-interpretation.html`). The words are the server's.
 */
export interface PlanAsk {
  /** The server's question id (`q-…`). */
  id: string;
  /** The check's id of the stop on that line — what comes back when another option is picked. */
  itemId: string;
  day: number;
  date: string;
  /** "HH:MM" the rule read for the line ("" when none): where the question stands among the stops. */
  startsAt: string;
  /** The stop's name as the rule read it — searched for when the customer picks the place themselves. */
  title: string;
  question: string;
  quote: string;
  options: PlanAskOption[];
}

export interface PlanAskOption {
  id: string;
  label: string;
  recommended: boolean;
  reason: string | null;
  effect: string | null;
  /** Picked, the stop is put in and the change screen's place search opens (`query`). */
  pickMyself: boolean;
  query: string | null;
}

/**
 * A place one stop could change to (mockup scenario 4): one of the alternatives (`rank` 1, 2, 3 …) or a place picked from
 * a search. `checks` are this place checked at the stop's time (empty when they have not been).
 */
export interface PlanCandidate {
  risk?: ItemRisk | null;
  proposedTime?: { date: string | null; startsAt: string | null; endsAt: string | null };
  id: string;
  name: string;
  source: "candidate" | "search";
  rank: number | null;
  /** How far it is from the stops around it, e.g. 0.6 km from 「경복궁」. */
  distance: { km: number; from: string } | null;
  /** `[2026-10-22]` A search result's list: nearest first (`distance`) or best name match first (`relevance`). */
  order?: "distance" | "relevance" | "route";
  coordinates: Coordinates | null;
  info: PlaceInfo | null;
  checks: CheckRow[];
  /** `[2026-10-07]` Which step of the server's ladder it came from, and its one-sentence reason (both only when the server sent them). */
  basis?: "same_kind" | "similar_experience" | "meal_inferred" | "lodging" | "lodging_meal" | "taste" | null;
  /** `[2026-10-21]` The group of a 「비슷한 경험」 alternative (`indoor_exhibit` · `outdoor_walk` …), as the server named it. */
  experience?: string | null;
  /** What kind of stop the place makes (`dining` · `activity`) when the server says so — picked for a stop of another kind, the kind is sent with it. */
  placeKind?: string | null;
  reason?: string | null;
  /** `[2026-10-19]` The way in from the stop before / out to the stop after (whose stop, minutes, the way, a straight-line guess or not). */
  legs?: { before: PlanCandidateLeg | null; after: PlanCandidateLeg | null };
  /** `[2026-10-19]` While the live answer works the card out: the way in / out still being measured, the model's reason still being written. */
  pending?: { before: boolean; after: boolean; reason: boolean };
}

export interface PlanCandidateLeg { with: string; minutes: number; modeLabel: string; estimated: boolean; slackMin: number }

/** The way from one place to the next on the same day. */
export interface PlanMove {
  id: string;
  fromId: string;
  toId: string;
  day: number;
  /** "HH:MM" — leave at. */
  departAt: string;
  /** As the server words it, e.g. 「도보」 · 「지하철」. */
  mode: string;
  /** One line, e.g. 「12분 · 0.8km」. */
  summary: string;
  /** `[2026-10-04]` How many minutes the way takes, as the server counts it — null when it did not say. */
  minutes: number | null;
  /** `[2026-10-04]` "HH:MM" — arrive at, when leaving at `departAt`; "" when the server gave none. */
  arriveAt: string;
  /** `[2026-10-04]` Minutes to spare before the next stop starts (negative = arrives after it started) — null when not known. */
  slackMin: number | null;
  /** `[2026-10-04]` The time is a straight-line guess (`basis` estimate), not a timetable — said so on the screen instead of passing it off as exact. */
  estimated: boolean;
  /** `[2026-10-07]` The way the check uses now (`walk` · `subway` · `bus` · `taxi` · `transit` · `estimate`), the way the calculator chose, and what became of the customer's choice (`kept` · `dropped` + why). */
  modeKey?: string | null;
  recommendedMode?: string | null;
  modeChoice?: { mode: string | null; state: "kept" | "dropped" | null; why: string | null } | null;
  /** `[2026-10-23 사용자 지시]` The first route candidates of the leg (the one it uses first), whether more can be asked for, the route it uses and what became of the customer's route. */
  routes?: MoveRoute[];
  routesMore?: boolean;
  routeKey?: string | null;
  routeChoice?: RouteChoice | null;
  /** `[2026-10-13]` A morning move 「숙소 → 그날 첫 일정」 — it opens its day (`day` is the day of `toId`), it does not follow `fromId` on the check-in day. */
  fromStay?: boolean;
  checks: CheckRow[];
  verdict: Verdict | null;
}

/** What a line of the uploaded plan turned into: the trip's date, a stop, or nothing. A stop's day or time is null when
 *  the server has not settled it — never filled in here. */
export type LineFinding = { kind: "date"; date: string } | { kind: "item"; id?: string; sourceKey?: string; date?: string | null; day: number | null; startsAt: string | null; title: string };
export interface PlanLine { no: number; text: string; read: boolean; found: LineFinding | null }

export interface PlanDay { day: number; /** "YYYY-MM-DD" */ date: string }

/** received → reading (lines) → checking (places, hours, moves) → done. */
export type PlanStage = "received" | "reading" | "checking" | "done";
export const STAGES: readonly PlanStage[] = ["received", "reading", "checking", "done"];

export interface PlanCheckView {
  risksAvailable?: boolean;
  riskMode?: string | null;
  riskCheckedAt?: string | null;
  /** 이동 후보의 이전 판 상태를 폐기할 때 쓰는 실제 접수 revision. */
  revision?: number;
  /** 이번 접수의 응답에 있는 호출 상품만 표시합니다. */
  taxiPricing?: WebTaxiPricing | null;
  stage: PlanStage;
  /** The trip's title once the check is done. */
  title: string | null;
  days: PlanDay[];
  lines: PlanLine[];
  /** In itinerary order within each day. */
  items: PlanItem[];
  moves: PlanMove[];
  /**
   * Changed since the whole plan was last checked: 「재검증」 comes before 「여행 등록」 (mockup scenario 7). A server that
   * checks the plan on every save leaves it false.
   */
  dirty: boolean;
  /** The whole plan is being checked again: the stop at it now, in order (mockup 「재검증 중 · 2/4」). Null otherwise. */
  rechecking: string | null;
  /**
   * `[2026-10-03 사용자 지시]` How far the server says it is (its `progress` packet: phase, done of total, what it is at). When it is
   * there the bar and the words come from it alone; when the server sends none (an older server) they come from the rows drawn, as before.
   */
  serverProgress?: ServerProgress | null;
  /**
   * `[2026-10-16 D-025]` What the server filled in first and what it understood beyond the stops — drawn as a short note above the list.
   * `questions`: what only the traveller knows. `understood`: the traveller's own words the server read as a move, a condition or a preference.
   */
  prefill?: PrefillNotes | null;
  /** `[2026-10-21 P6]` The interpretation questions not answered yet (`PlanAsk`). Absent on an older server and in the preview. */
  asks?: PlanAsk[];
}

export interface PrefillNotes { filledCount: number; questions: string[]; understood: string[]; handoff: PrefillHandoff[] }

/** `[2026-10-16 D-025 후속]` A read preference handed to an owner — `mine` true = 「우리가 채움」, false = the traveller's own answer wins. */
export interface PrefillHandoff { label: string; text: string; owner: string; mine: boolean }

/** What the server's `progress` packet says, with the stop's title to show. */
export interface ServerProgress { phase: "places" | "hours" | "moves"; done: number; total: number; title: string | null }

const stageIndex = (stage: PlanStage) => STAGES.indexOf(stage);

/** Items and moves of one day in the order they are lived: item, move, item … */
export function timeline(view: Pick<PlanCheckView, "items" | "moves">, day: number): ({ type: "item"; item: PlanItem } | { type: "move"; move: PlanMove })[] {
  const out: ({ type: "item"; item: PlanItem } | { type: "move"; move: PlanMove })[] = [];
  // `[2026-10-13]` A day of a stay opens with the move from the hotel to its first stop — before the stops, so checks, reveal and insertion points follow it in that order.
  for (const move of view.moves.filter((entry) => entry.fromStay && entry.day === day)) out.push({ type: "move", move });
  for (const item of view.items.filter((entry) => entry.day === day)) {
    out.push({ type: "item", item });
    const move = view.moves.find((entry) => entry.fromId === item.id && !entry.fromStay);
    if (move) out.push({ type: "move", move });
  }
  return out;
}

type OrderEntry = { type: "item"; id: string } | { type: "move"; id: string; to: string } | { type: "ask"; id: string };

/**
 * Every item and move in check order: day by day, along each day's timeline. `[2026-10-21 P6]` A question not answered yet (`asks`) stands at its line's time: after the stops that start
 * by then, before the leg into the next one.
 */
function checkOrder(view: PlanCheckView): OrderEntry[] {
  const asks = view.asks ?? [];
  const days = [...new Set([...view.items.map((item) => item.day), ...asks.map((ask) => ask.day)])].sort((a, b) => a - b);
  return days.flatMap((day) => {
    const out: OrderEntry[] = timeline(view, day).map((entry) => entry.type === "item" ? { type: "item" as const, id: entry.item.id } : { type: "move" as const, id: entry.move.id, to: entry.move.toId });
    for (const ask of asks.filter((entry) => entry.day === day).sort((a, b) => a.startsAt.localeCompare(b.startsAt))) {
      const later = out.findIndex((entry) => entry.type === "item" && (view.items.find((item) => item.id === entry.id)?.startsAt ?? "") > ask.startsAt);
      const before = later > 0 && out[later - 1].type === "move" && (out[later - 1] as { to: string }).to === out[later].id ? later - 1 : later;
      out.splice(later < 0 ? out.length : before, 0, { type: "ask", id: ask.id });
    }
    return out;
  });
}

/** `[2026-10-21 P6]` The stop of the check at an interpretation question — told apart from a stop's id. */
export const askStopId = (id: string) => `ask:${id}`;
export const askOfStop = (view: Pick<PlanCheckView, "asks">, stopId: string | null | undefined): PlanAsk | null =>
  stopId?.startsWith("ask:") ? (view.asks ?? []).find((ask) => askStopId(ask.id) === stopId) ?? null : null;

/**
 * `[2026-10-21 P6]` The list with the question's place in it: a card-less entry (`PlanItem.ask`) at the line's time, after the stops of that day that start by then (the waiting ones too).
 */
export function withAskSlot(view: PlanCheckView, ask: PlanAsk): PlanCheckView {
  const slot: PlanItem = { id: askStopId(ask.id), day: ask.day, date: ask.date, startsAt: ask.startsAt, endsAt: "", title: ask.quote, place: "", noPlace: true, coordinates: null,
    checks: [], verdict: null, locked: false, booked: null, info: null, suggestion: null, ask };
  const at = view.items.findIndex((item) => item.day > ask.day || (item.day === ask.day && item.startsAt > ask.startsAt));
  return { ...view, items: at < 0 ? [...view.items, slot] : [...view.items.slice(0, at), slot, ...view.items.slice(at)] };
}

/**
 * ★`[2026-10-04 사용자 지시]` 빨강(못 찾음·고쳐야 함)과 회색(–, 아직 모름)은 어차피 확인이 안 된 것이라 「확인 중」 애니메이션 없이 처음부터 그 모양으로 나온다.
 * 천천히 켜지는 것은 통과(✓)·채움(✎)·주의(!)뿐이다 — 사용자가 「이건 확인됐구나」를 알아볼 수 있는 속도로.
 * `[2026-10-20 사용자 결정 — 계획 확인 C안]` 처음 검사를 그릴 때는 빨강·회색 줄도 「확인 중」으로 나와 한 줄씩 켜진다(`pendingCopy`). 이 규칙은 「다시 제출」 뒤 다시 켜는 표시(`plan-check.tsx` `rowsFor`)에만 남는다.
 */
export const isInstantRow = (row: CheckRow) => row.result === "bad" || row.result === "unknown";

/**
 * `[2026-10-20 사용자 결정 — 계획 확인 C안]` A card comes with every check waiting, the red and grey ones too: its height is the finished card's, so nothing below it moves while its checks tick in.
 * `[2026-10-22 사용자 결정 — 한 줄씩]` The screen now draws only the checks ticked in and the one being checked (`revealedRows`): the card grows a row at a time.
 */
const pendingCopy = <T extends { checks: CheckRow[]; verdict: Verdict | null }>(entity: T): T =>
  ({ ...entity, checks: entity.checks.map((row) => ({ ...row, result: "pending" as const, text: "" })), verdict: null });

/**
 * One visible change from `shown` toward `target`, or null when they already match.
 *
 * ★The server says what happened and in which order; the screen decides the pace. However many changes arrive at once
 *   (a stream burst, or a re-read after a poll), they are drawn one at a time in this order: reading starts → each line
 *   read → the days → checking starts → each place along the day (appear with its checks waiting → each check → its
 *   verdict, a step of its own) → done → title. `[2026-10-20 사용자 결정 — 계획 확인 C안]` The leg to a place comes with that place, in one step
 *   (a leg the server sends after its place is drawn comes alone, where it stands).
 *   Anything the screen cannot step toward (something removed, a line changed) jumps straight to `target`.
 * `cutRows`: ★`[2026-10-22 사용자 결정 — 문제 줄에서 멈추기]` where the check stops at cards (`useReveal` `stops`), a card that stops ticks its checks in only down to the row its question
 *   is about (`stopRowOf`); its verdict then comes with the rest of its checks as the server has them, which the screen does not draw while it is stopped there (`revealedRows`).
 */
export function nextStep(shown: PlanCheckView, target: PlanCheckView, cutRows = false): PlanCheckView | null {
  if (JSON.stringify(shown) === JSON.stringify(target)) return null;
  const jump = () => target;
  if (stageIndex(target.stage) < stageIndex(shown.stage)) return jump();
  if (shown.lines.length > target.lines.length || shown.items.some((item) => !target.items.some((other) => other.id === item.id))
    || shown.moves.some((move) => !target.moves.some((other) => other.id === move.id))) return jump();

  // Reading starts before the first line is read, so the bar moves with the lines.
  if (shown.stage === "received" && target.stage !== "received") return { ...shown, stage: "reading" };
  // Lines: a line appears or is read, one at a time.
  for (let index = 0; index < target.lines.length; index += 1) {
    const want = target.lines[index], have = shown.lines[index];
    if (!have) return { ...shown, lines: [...shown.lines, { ...want, read: false, found: null }] };
    if (have.no !== want.no || have.text !== want.text || (have.read && !want.read)) return jump();
    if (!have.read && want.read) return { ...shown, lines: shown.lines.map((line, at) => at === index ? want : line) };
    if (JSON.stringify(have.found) !== JSON.stringify(want.found)) return { ...shown, lines: shown.lines.map((line, at) => at === index ? want : line) };
  }
  // The trip's days come with the reading; checking starts once every line is read.
  if (JSON.stringify(shown.days) !== JSON.stringify(target.days)) return { ...shown, days: target.days };
  if (shown.stage === "reading" && stageIndex(target.stage) > stageIndex("reading")) return { ...shown, stage: "checking" };

  // Places and moves along each day: appear (checks waiting) → each check → verdict.
  const order = checkOrder(target);
  for (const [at, entry] of order.entries()) {
    // `[2026-10-21 P6]` A question not answered yet: nothing past it is drawn (the check stops there to ask once it is final — `stopAt`).
    if (entry.type === "ask") return null;
    if (entry.type === "item") {
      const want = target.items.find((item) => item.id === entry.id)!;
      const have = shown.items.find((item) => item.id === entry.id);
      const step = advance(have, want, "rows", cutRows && have && stopsHere(want, shown) ? stopRowOf(want) : undefined);
      if (step === undefined) continue;
      // `[2026-10-20 사용자 결정 — 계획 확인 C안]` A card that needs a look shows that only once the check is final: the screen stops there to ask (`stopAt`), so it waits rather than
      //   draw past a verdict the server may still change.
      if (have && step.verdict !== null && have.verdict !== step.verdict && target.stage !== "done" && stopsHere(step, shown)) return null;
      const items = have ? shown.items.map((item) => item.id === want.id ? step : item) : insertInOrder(shown.items, step, target.items);
      return { ...shown, items };
    }
    const want = target.moves.find((move) => move.id === entry.id)!;
    const have = shown.moves.find((move) => move.id === entry.id);
    // A move is one line whose only visible part is its mark: its own checks (shown only when opened) are not ticked in one by one.
    const step = advance(have, want, "whole");
    if (step === undefined) continue;
    const moves = have ? shown.moves.map((move) => move.id === want.id ? step : move) : [...shown.moves, step];
    const next = order[at + 1];
    const card = !have && next?.type === "item" && next.id === want.toId && !shown.items.some((item) => item.id === next.id)
      ? target.items.find((item) => item.id === next.id) : undefined;
    return card ? { ...shown, moves, items: insertInOrder(shown.items, pendingCopy(card), target.items) } : { ...shown, moves };
  }
  // Done only once every check is in, then the title.
  if (stageIndex(shown.stage) < stageIndex(target.stage)) return { ...shown, stage: STAGES[stageIndex(shown.stage) + 1] };
  if (shown.title !== target.title) return { ...shown, title: target.title };
  return jump();
}

/**
 * The next state of one place or move toward `want`, or undefined when it already matches.
 * `rows`: a place appears with its checks waiting, then one check at a time, then — once every check is in — its verdict, a step of its own
 * (`[2026-10-20 사용자 결정 — 계획 확인 C안]` the red and grey checks are ticked in like the others; the verdict used to land with the last check).
 * `whole`: it appears finished — a move (its only visible part is its mark: no pretended search is replayed after the server has answered).
 * `until`: `[2026-10-22 사용자 결정 — 문제 줄에서 멈추기]` the checks are ticked in one at a time only down to this row; the rest come with the verdict, as the server has them.
 */
function advance<T extends { checks: CheckRow[]; verdict: Verdict | null }>(have: T | undefined, want: T, grain: "rows" | "whole", until?: number): T | undefined {
  if (!have) return grain === "whole" ? want : pendingCopy(want);
  if (JSON.stringify(have) === JSON.stringify(want)) return undefined;
  if (have.checks.length !== want.checks.length || have.checks.some((row, at) => row.kind !== want.checks[at].kind)) return want;
  if (grain === "whole") return { ...have, ...want };
  const at = have.checks.findIndex((row, index) => JSON.stringify(row) !== JSON.stringify(want.checks[index]));
  return at < 0 || (until !== undefined && at > until) ? { ...have, ...want } : { ...have, checks: have.checks.map((row, index) => index === at ? want.checks[at] : row) };
}

/** Put `item` where it stands in `order` (the server's order), among the items already shown. */
function insertInOrder(items: PlanItem[], item: PlanItem, order: PlanItem[]): PlanItem[] {
  const rank = (id: string) => order.findIndex((entry) => entry.id === id);
  return [...items, item].sort((a, b) => rank(a.id) - rank(b.id));
}

/** `[2026-10-20 C안]` The leg into a stop (from the stop before it, or from the stay in the morning) — none for the first stop of a day without a stay. */
export const incomingMove = (view: Pick<PlanCheckView, "moves">, id: string): PlanMove | null => view.moves.find((move) => move.toId === id) ?? null;

/** `[2026-10-20 C안]` The way there arrives after the stop starts. */
export const lateInto = (view: Pick<PlanCheckView, "moves">, id: string): boolean => {
  const slack = incomingMove(view, id)?.slackMin;
  return slack !== null && slack !== undefined && slack < 0;
};

/** `[2026-10-20 C안]` A card whose verdict is in stops the check: it needs a look, or the way to it arrives late (a place problem is asked first, then the arrival). */
export const stopsHere = (item: PlanItem, view: Pick<PlanCheckView, "moves">, acknowledged?: (item: PlanItem) => boolean) =>
  (item.verdict === "review" && !acknowledged?.(item)) || (item.verdict !== null && lateInto(view, item.id));

/**
 * `[2026-10-21 사용자 지적]` The card the check is held at while the server still checks the rest: its verdict needs a look (or its way in is late) and is drawn only once the
 * check is final (`nextStep`). To the customer the check has stopped there — the screen waits for the server only to ask.
 */
export function heldAt(shown: PlanCheckView, target: PlanCheckView, cutRows = false): string | null {
  if (target.stage === "done" || shown.stage !== "checking") return null;
  for (const entry of checkOrder(target)) {
    if (entry.type === "ask") return null;
    if (entry.type === "move") {
      if (advance(shown.moves.find((move) => move.id === entry.id), target.moves.find((move) => move.id === entry.id)!, "whole") === undefined) continue;
      return null;
    }
    const have = shown.items.find((item) => item.id === entry.id);
    const want = target.items.find((item) => item.id === entry.id)!;
    const step = advance(have, want, "rows", cutRows && have && stopsHere(want, shown) ? stopRowOf(want) : undefined);
    if (step === undefined) continue;
    return have && step.verdict !== null && have.verdict !== step.verdict && stopsHere(step, shown) ? entry.id : null;
  }
  return null;
}

/** `[2026-10-20 C안]` What the stopped card asks about: its place (or what else needs a look) first, then the way to it. */
export const stopKind = (view: PlanCheckView, id: string, acknowledged?: (item: PlanItem) => boolean): "place" | "arrival" => {
  const item = view.items.find((item) => item.id === id);
  return item?.verdict === "review" && !acknowledged?.(item) ? "place" : "arrival";
};

/**
 * ★`[2026-10-22 사용자 결정 — 문제 줄에서 멈추기]` (목업 `mockups/tripilot-plan-check-row-stop.html`) The check row a stopped card's question is about: the check stops there, the
 * question opens right under it and the rows below are not drawn until the card passes. Its place question (`stopKind` 「place」) is told in the order `stopKindOf`
 * (`stop-questions.ts`) asks it — a place not found, a closed day, a place taken for now, else the row the question quotes (the first red, else the first amber) —; a late arrival is its
 * 「도착」 row. The last row when none applies (nothing is hidden then).
 */
export function stopRowOf(item: PlanItem): number {
  const find = (test: (row: CheckRow) => boolean) => item.checks.findIndex(test);
  const last = item.checks.length - 1;
  if (item.verdict !== "review") { const arrival = find((row) => row.kind === "arrival"); return arrival < 0 ? last : arrival; }
  const place = find((row) => row.kind === "place");
  const closed = find((row) => row.kind === "closed" && row.result === "bad");
  const bad = find((row) => row.result === "bad");
  const at = item.unfound && place >= 0 ? place : closed >= 0 ? closed : item.placeState === "picked_nearest" && place >= 0 ? place
    : bad >= 0 ? bad : find((row) => row.result === "warn");
  return at < 0 ? last : at;
}

/**
 * ★`[2026-10-22 사용자 결정 — 문제 줄에서 멈추기]` The card being drawn in the first check — `id` (the card the check stopped at), else the first one along the days not drawn as the
 * server has it — when it stops the check and its checks down to its stop row are in: that row. Nothing below it is drawn from then on (`revealedRows`), so no row comes and goes
 * in the pause before its verdict.
 */
export function rowStop(shown: PlanCheckView, target: PlanCheckView, id: string | null = null): { id: string; row: number } | null {
  let at = id;
  if (!at) for (const entry of checkOrder(target)) {
    if (entry.type === "ask") return null;
    if (entry.type === "move") {
      if (advance(shown.moves.find((move) => move.id === entry.id), target.moves.find((move) => move.id === entry.id)!, "whole") === undefined) continue;
      return null;
    }
    if (advance(shown.items.find((item) => item.id === entry.id), target.items.find((item) => item.id === entry.id)!, "rows") === undefined) continue;
    at = entry.id;
    break;
  }
  const have = at ? shown.items.find((item) => item.id === at) : undefined;
  const want = at ? target.items.find((item) => item.id === at) : undefined;
  if (!have || !want || !stopsHere(want, shown)) return null;
  const row = stopRowOf(want);
  const inAlready = have.checks.length === want.checks.length && want.checks.slice(0, row + 1).every((check, n) => JSON.stringify(check) === JSON.stringify(have.checks[n]));
  return inAlready ? { id: want.id, row } : null;
}

/**
 * ★`[2026-10-22 사용자 결정 — 한 줄씩 · 문제 줄에서 멈추기]` The checks of a card being drawn in the first check, as the screen shows them: the ones ticked in and the one being checked
 * (「확인하는 중…」) — not the ones still to come. `cut` is the card's stop row (`useReveal`): `hide` — stopped there (or held there while the server still checks): nothing below it;
 * otherwise (checked again after a pick) the rows down to it stay while they wait again and a row below it comes as a new one (its old words are not shown).
 * The values are the card's own: only which rows are drawn changes.
 */
export function revealedRows(rows: CheckRow[], cut: { row: number; hide: boolean } | null): CheckRow[] {
  if (cut?.hide) return rows.slice(0, cut.row + 1);
  const next = rows.findIndex((row) => row.result === "pending");
  if (next < 0) return rows;
  const kept = cut?.row ?? -1;
  return rows.slice(0, Math.max(next, kept) + 1).map((row, at) => at > kept && row.result === "pending" && row.text ? { ...row, text: "" } : row);
}

/**
 * ★`[2026-10-20 사용자 결정 — 계획 확인 C안]` Where the first check stops to ask: the first card along the days whose drawn verdict is 「확인 필요」 or whose way in arrives late, once the
 * server's check is final. Nothing past it is drawn until the customer picks and the card passes (flow mockup `mockups/tripilot-plan-flow-register.html` 4단계).
 */
export function stopAt(shown: PlanCheckView, target: PlanCheckView, acknowledged?: (item: PlanItem) => boolean): string | null {
  if (target.stage !== "done") return null;
  // `[2026-10-21 P6]` Along the plan as the server has it: a question not answered yet stops it once every stop before it is drawn with its verdict (`askStopId`).
  for (const entry of checkOrder(target)) {
    if (entry.type === "move") continue;
    if (entry.type === "ask") return askStopId(entry.id);
    const item = shown.items.find((candidate) => candidate.id === entry.id);
    // Not drawn yet, or its verdict still to come: the check goes on toward it first.
    if (!item || (item.verdict === null && target.items.find((candidate) => candidate.id === entry.id)?.verdict != null)) return null;
    if (stopsHere(item, shown, acknowledged)) return entry.id;
  }
  return null;
}

/**
 * `[2026-10-20 C안]` The finished check cut where it stops: every card and leg up to the first card that needs a look (or arrives late), the rest not drawn yet — what a page shows at
 * once that opens a checked plan with something to fix, or that skips the animation. The whole check when nothing stops it.
 */
export function cutAtStop(view: PlanCheckView, acknowledged?: (item: PlanItem) => boolean): PlanCheckView {
  if (view.stage !== "done") return view;
  const order = checkOrder(view);
  const at = order.findIndex((entry) => entry.type === "ask" || (entry.type === "item" && stopsHere(view.items.find((item) => item.id === entry.id)!, view, acknowledged)));
  if (at < 0) return view;
  // `[2026-10-21 P6]` At a question, up to the stop before it (the question has no card).
  const drawn = new Set(order.slice(0, order[at].type === "ask" ? at : at + 1).map((entry) => entry.id));
  return { ...view, stage: "checking", title: null, items: view.items.filter((item) => drawn.has(item.id)), moves: view.moves.filter((move) => drawn.has(move.id)) };
}

/**
 * `[2026-10-20 사용자 결정 — 계획 확인 C안 · 이동 확인 C안]` Each stop's card carries the 「도착」 line of the way into it (the server's own line of that leg), so the stop is checked with
 * how it is reached — and a late arrival is asked in the stop's own card. Only for the first check: the result shows the legs as before.
 */
export function withArrivalRows(view: PlanCheckView): PlanCheckView {
  let added = false;
  const items = view.items.map((item) => {
    const row = incomingMove(view, item.id)?.checks.find((check) => check.kind === "arrival");
    if (!row) return item;
    added = true;
    return { ...item, checks: [...item.checks, row] };
  });
  return added ? { ...view, items } : view;
}

/** `[2026-10-20 C안]` Whether `next` changes nothing on screen but the card `id` (while the screen is stopped at it, nothing else is drawn). */
export function onlyCard(shown: PlanCheckView, next: PlanCheckView, id: string): boolean {
  const rest = (view: PlanCheckView) => JSON.stringify([view.stage, view.title, view.days, view.moves, view.items.filter((item) => item.id !== id)]);
  return rest(shown) === rest(next);
}

/** `[2026-10-20 C안 — 고른 뒤 다시 확인]` The card picked for is checked again where it stands: every check waits again, its words kept until the new ones come. */
export function beginRecheck(shown: PlanCheckView, id: string): PlanCheckView {
  return { ...shown, items: shown.items.map((item) => item.id !== id ? item : { ...item, checks: item.checks.map((row) => ({ ...row, result: "pending" as const })) }) };
}

/**
 * `[2026-10-20 C안 — 고른 뒤 다시 확인]` The server answered the pick with the new plan: what is drawn takes it at once (a stop or leg gone is dropped, a leg is kept where both its
 * ends are drawn), except the card `id`, which takes the new place and times with its new checks still waiting (the words it had kept where the check is the same kind) —
 * they are then ticked in one by one, and its verdict last.
 */
export function rebase(shown: PlanCheckView, target: PlanCheckView, id: string): PlanCheckView {
  const drawn = new Set(shown.items.map((item) => item.id));
  const items = target.items.filter((item) => drawn.has(item.id)).map((item) => {
    if (item.id !== id) return item;
    const was = shown.items.find((entry) => entry.id === id)!;
    return { ...item, verdict: was.verdict, checks: item.checks.map((row, at) => ({ ...row, result: "pending" as const, text: was.checks[at]?.kind === row.kind ? was.checks[at].text : "" })) };
  });
  const kept = new Set(items.map((item) => item.id));
  return { ...shown, items, moves: target.moves.filter((move) => kept.has(move.fromId) && kept.has(move.toId)) };
}

/**
 * ★`[2026-10-21 결함 — ST4F-703]` While the check stands stopped at a card (nothing picked), a new read of the server (the 3-minute re-read, which stamps every stop's risk check
 * anew; the card's place info when its alternatives arrive; another tab's change) is taken into what is drawn at once: the cards and legs on screen take the server's values, one
 * the server took out goes, a leg between two drawn cards comes, nothing past the stop is drawn. The stop could only draw its own card, so a change to an earlier card used to hold
 * the replay for good — the card looked 「다시 확인하는 중」 with its question gone. `keep` (the card whose checks are ticked in again after a pick) is left as drawn: it steps on.
 */
export function syncDrawn(shown: PlanCheckView, target: PlanCheckView, keep: string | null = null): PlanCheckView {
  const drawn = new Set(shown.items.map((item) => item.id));
  const items = target.items.filter((item) => drawn.has(item.id)).map((item) => item.id === keep ? shown.items.find((entry) => entry.id === keep)! : item);
  const kept = new Set(items.map((item) => item.id));
  const legs = new Set(shown.moves.map((move) => move.id));
  const moves = target.moves.filter((move) => legs.has(move.id) || (kept.has(move.fromId) && kept.has(move.toId)));
  const next = { ...shown, lines: target.lines, days: target.days, items, moves };
  return JSON.stringify(next) === JSON.stringify(shown) ? shown : next;
}

/**
 * How many places and moves there will be. Places come from the lines read (a line that turned into a stop), moves from
 * the stops of each day (one between two stops) — so the counts and the bar know the whole before every card is shown.
 * What the screen already shows counts when it is more.
 */
export function expected(view: Pick<PlanCheckView, "lines" | "items" | "moves">): { places: number; moves: number } {
  const stops = view.lines.flatMap((line) => line.read && line.found?.kind === "item" ? [line.found.day ?? 0] : []);
  const perDay = [...new Set(stops)].map((day) => stops.filter((value) => value === day).length);
  return { places: Math.max(view.items.length, stops.length), moves: Math.max(view.moves.length, perDay.reduce((sum, count) => sum + Math.max(0, count - 1), 0)) };
}

/** 0–100 along the four steps. Within reading it follows the lines read; within checking, the places and moves done. */
export function progress(view: PlanCheckView): number {
  const third = 100 / 3;
  if (view.stage === "received") return 0;
  if (view.stage === "done") return 100;
  // The server's own count, when it sends one: the whole line is split in three phases (places · hours · moves), each as far as `done / total`.
  //   ★The bar never goes back: the rows drawn so far (lines read; places and legs checked) still count, and the larger of the two is shown.
  const served = view.serverProgress ? (["places", "hours", "moves"].indexOf(view.serverProgress.phase) + Math.min(1, view.serverProgress.done / Math.max(1, view.serverProgress.total))) * third : 0;
  if (view.stage === "reading") return Math.max(served, view.lines.length ? third * view.lines.filter((line) => line.read).length / view.lines.length : 0);
  const total = expected(view);
  const all = total.places + total.moves;
  const done = [...view.items, ...view.moves].filter((entity) => entity.verdict !== null).length;
  // 100 is for the finished check only: the last leg counted is "almost", not "done".
  return Math.min(99, Math.max(served, third + (all ? third * Math.min(done, all) / all : 0)));
}

export interface Tally { places: number; placesDone: number; moves: number; movesDone: number; placesReview: number; movesReview: number }

export function tally(view: Pick<PlanCheckView, "lines" | "items" | "moves">): Tally {
  const total = expected(view);
  return {
    places: total.places,
    placesDone: view.items.filter((item) => item.verdict !== null).length,
    moves: total.moves,
    movesDone: view.moves.filter((move) => move.verdict !== null).length,
    placesReview: view.items.filter((item) => item.verdict === "review").length,
    movesReview: view.moves.filter((move) => move.verdict === "review").length,
  };
}

/** What the customer still has to look at before 「재검증」 or 「여행 등록」: places and moves that need a check. */
export function needs(view: Pick<PlanCheckView, "items" | "moves">): { places: number; moves: number; total: number } {
  const places = view.items.filter((item) => item.verdict === "review").length;
  const moves = view.moves.filter((move) => move.verdict === "review").length;
  return { places, moves, total: places + moves };
}

/** Lines that turned into a stop, among those read so far. */
export const foundCount = (view: Pick<PlanCheckView, "lines">) => view.lines.filter((line) => line.read && line.found?.kind === "item").length;

/** What the stop editor sends: the stop as the customer wants it. Same fields as the intake review's draft. */
export interface ItemDraft { title: string; date: string; start: string; end: string; place: string; noPlace: boolean }

export const draftOfItem = (item: PlanItem): ItemDraft =>
  ({ title: item.written ?? item.title, date: item.date, start: item.startsAt, end: item.endsAt, place: item.place, noPlace: item.noPlace });

/**
 * What stops the editor from saving, checked on the screen before anything is sent: no name, an end before the start,
 * no place name (unless 「장소 없음」). Everything else — whether the place exists, the date's range — is the server's to say.
 */
export function draftProblem(draft: ItemDraft): "title" | "time" | "place" | null {
  if (!draft.title.trim()) return "title";
  if (draft.start && draft.end && draft.end <= draft.start) return "time";
  if (!draft.noPlace && !draft.place.trim()) return "place";
  return null;
}

/** A trip-wide detail the server asks for before it can register (its problem codes `no_date` · `party_size_out_of_range`). */
export interface TripIssue { field: "first_day" | "party_size" | null; message: string }
