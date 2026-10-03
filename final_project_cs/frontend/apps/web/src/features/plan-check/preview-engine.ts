import type { Coordinates } from "@/features/map/model";
import { gwa } from "@/lib/josa";
import { EXAMPLE_GROUP_OF, EXAMPLE_PLACE_OF, EXAMPLE_PLACES, exampleDone, placeInfo, type ExamplePlace } from "./fixtures";
import type { CheckRow, PlanCandidate, PlanCheckView, PlanItem, PlanMove } from "./model";

/**
 * ★The preview's stand-in for the server — example rules only, ported from the mockup's script
 *   (`mockups/tripilot-plan-check-streaming.html`, 개정 4·5). Never used by the real route: there the server picks the
 *   alternatives, checks hours and closing days, works out moves and re-checks the plan (PLAN_CHECK_SCREEN.md §4).
 */

export interface PreviewState {
  view: PlanCheckView;
  /** Which example place each stop is (null: not settled). */
  placeOf: Record<string, string | null>;
}

const row = (kind: CheckRow["kind"], result: CheckRow["result"], text: string): CheckRow => ({ kind, result, text });
const placeByKey = (key: string) => EXAMPLE_PLACES.find((entry) => entry.key === key)!;

const KM_PER_LAT = 111.32, KM_PER_LNG = 88.22;
const km = (p: Coordinates, q: Coordinates) => Math.hypot((p.lat - q.lat) * KM_PER_LAT, (p.lng - q.lng) * KM_PER_LNG);
const toMinutes = (time: string) => { const [hours, minutes] = time.split(":").map(Number); return hours * 60 + minutes; };
const hhmm = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
const weekday = (date: string) => "일월화수목금토"[new Date(`${date}T00:00:00Z`).getUTCDay()];
const normalized = (text: string) => text.replace(/\s+/g, "").toLowerCase();

const dayItems = (view: PlanCheckView, day: number) => view.items.filter((item) => item.day === day);
const itemOf = (view: PlanCheckView, id: string) => view.items.find((item) => item.id === id)!;

/** The example as the preview starts: the mockup's result, each stop's first alternative named on its card. */
export function exampleState(): PreviewState {
  const state: PreviewState = { view: exampleDone, placeOf: { ...EXAMPLE_PLACE_OF } };
  return withSuggestions(state);
}

function withSuggestions(state: PreviewState): PreviewState {
  return { ...state, view: { ...state.view, items: state.view.items.map((item) => ({ ...item, suggestion: candidatesFor(state, item.id)[0]?.name ?? null })) } };
}

// ── checks of one place at one stop (mockup hoursRow · offRow · overlapRow · placeRows) ───────────────────────
function hoursRow(place: ExamplePlace, item: PlanItem): CheckRow {
  if (!place.hours) return row("hours", "ok", `${place.hoursText} 열려 있어요`);
  const inside = toMinutes(item.startsAt) >= toMinutes(place.hours[0]) && toMinutes(item.endsAt || item.startsAt) <= toMinutes(place.hours[1]);
  return inside ? row("hours", "ok", `${place.hours[0]}–${place.hours[1]} 안에 머물러요`) : row("hours", "warn", `영업 시간(${place.hours[0]}–${place.hours[1]}) 밖이에요`);
}

function closedRow(place: ExamplePlace, item: PlanItem): CheckRow {
  const day = weekday(item.date);
  if (!place.closed) return row("closed", "unknown", "휴무 정보가 없어요");
  if (place.closed === "연중무휴") return row("closed", "ok", "연중무휴");
  if (place.closed === "점포마다 다름") return row("closed", "unknown", "점포마다 달라요");
  return place.closed.startsWith(day) ? row("closed", "bad", `${place.closed} · 방문일이 휴무예요`) : row("closed", "ok", `${place.closed} · 방문은 ${day}요일`);
}

function overlapRow(view: PlanCheckView, id: string): CheckRow | null {
  const item = itemOf(view, id), stops = dayItems(view, item.day), previous = stops[stops.indexOf(item) - 1];
  if (!previous?.endsAt) return null;
  const overlap = toMinutes(previous.endsAt) - toMinutes(item.startsAt);
  return overlap > 0 ? row("time", "warn", `${gwa(previous.title)} ${overlap}분 겹쳐요 · 등록 때 막힐 수 있어요`) : null;
}

function placeChecks(state: PreviewState, id: string, key: string, first: string): CheckRow[] {
  const place = placeByKey(key), item = itemOf(state.view, id), overlap = overlapRow(state.view, id);
  const filled = item.checks.filter((check) => check.kind === "time" && check.result === "filled");
  return [row("place", "ok", first), ...(overlap ? [overlap] : []), ...filled, hoursRow(place, item), closedRow(place, item)];
}

/** A stop's verdict from its checks (mockup applyPlace): something to fix needs a look, else it was adjusted. A warning stays a warning. */
const verdictOf = (checks: CheckRow[]) => checks.some((check) => check.result === "bad") ? "review" as const : "adjusted" as const;

/** The time-overlap warnings follow the day's order and times. */
function refreshTimeRows(view: PlanCheckView, day: number): PlanCheckView {
  let next = view;
  for (const item of dayItems(view, day)) {
    const overlap = overlapRow(next, item.id);
    const checks = item.checks.filter((check) => !(check.kind === "time" && check.result === "warn"));
    if (overlap) checks.splice(1, 0, overlap);
    next = { ...next, items: next.items.map((entry) => entry.id === item.id ? { ...entry, checks } : entry) };
  }
  return next;
}

// ── moves (mockup travel · calcMove): 1.2 km or less is a walk at 70 m/min, else the subway at 8 min + 2.6 min/km ──
function travel(from: Coordinates, to: Coordinates) {
  const distance = km(from, to), walk = distance <= 1.2;
  return { distance, walk, minutes: walk ? Math.max(3, Math.round(distance * 1000 / 70)) : Math.round(8 + distance * 2.6), mode: walk ? "도보" : "지하철" };
}

function moveBetween(from: PlanItem, to: PlanItem): PlanMove {
  const base = { id: `${from.id}-${to.id}`, fromId: from.id, toId: to.id, day: from.day, departAt: from.endsAt };
  if (!from.coordinates || !to.coordinates) {
    return { ...base, mode: "이동", summary: "장소가 정해지면 경로를 찾아요", verdict: "review",
      checks: [row("route", "unknown", "한쪽 장소가 정해지지 않았어요"), row("mode", "unknown", "장소를 정하면 찾아요"), row("arrival", "unknown", "장소를 정하면 확인해요")] };
  }
  const { distance, walk, minutes, mode } = travel(from.coordinates, to.coordinates);
  const arrive = toMinutes(from.endsAt) + minutes, slack = toMinutes(to.startsAt) - arrive;
  return { ...base, mode, summary: `${walk ? "" : "약 "}${minutes}분 · ${distance.toFixed(1)}km`, verdict: slack >= 0 ? "keep" : "review",
    checks: [row("route", "ok", `${from.title} → ${to.title}`), row("mode", "ok", `${mode} ${minutes}분 · 거리로 낸 예시 계산`),
      row("arrival", slack >= 0 ? "ok" : "warn", slack >= 0 ? `${from.endsAt}에 나서면 ${hhmm(arrive)} 도착 · ${slack}분 여유` : `${from.endsAt}에 나서면 ${hhmm(arrive)} 도착 · 일정보다 ${-slack}분 늦어요`)] };
}

/** Moves between each day's stops: kept where the two stops did not change, worked out again where they did. */
function rebuildMoves(view: PlanCheckView, changed: Set<string>): PlanCheckView {
  const moves: PlanMove[] = [];
  for (const day of view.days) {
    const stops = dayItems(view, day.day);
    stops.slice(1).forEach((to, index) => {
      const from = stops[index], id = `${from.id}-${to.id}`;
      const kept = !changed.has(from.id) && !changed.has(to.id) && view.moves.find((move) => move.id === id);
      moves.push(kept || moveBetween(from, to));
    });
  }
  return { ...view, moves };
}

// ── alternatives and search (mockup refsOf · nearest · cands · onSearch) ─────────────────────────────────────
function referencesOf(state: PreviewState, id: string): { name: string; coordinates: Coordinates }[] {
  const item = itemOf(state.view, id), stops = dayItems(state.view, item.day), at = stops.indexOf(item);
  const around = [stops[at - 1], stops[at + 1]].filter((stop): stop is PlanItem => Boolean(stop?.coordinates)).map((stop) => ({ name: stop.title, coordinates: stop.coordinates! }));
  const current = state.placeOf[id];
  return around.length ? around : current ? [{ name: "지금 장소", coordinates: placeByKey(current).coordinates }] : [];
}

function nearest(place: ExamplePlace, references: { name: string; coordinates: Coordinates }[]): { km: number; from: string } | null {
  return references.reduce<{ km: number; from: string } | null>((best, reference) => {
    const distance = km(place.coordinates, reference.coordinates);
    return !best || distance < best.km ? { km: distance, from: reference.name } : best;
  }, null);
}

function candidate(state: PreviewState, id: string, place: ExamplePlace, source: PlanCandidate["source"], rank: number | null, references = referencesOf(state, id)): PlanCandidate {
  return { id: place.key, name: place.name, source, rank, distance: nearest(place, references), coordinates: place.coordinates, info: placeInfo(place),
    checks: placeChecks(state, id, place.key, `${place.source} 정보로 찾았어요`) };
}

/** Three places of the same kind, nearest to the stops before and after it (or to where it is now). */
export function candidatesFor(state: PreviewState, id: string): PlanCandidate[] {
  const references = referencesOf(state, id), current = state.placeOf[id], group = EXAMPLE_GROUP_OF[id];
  return EXAMPLE_PLACES.filter((place) => place.group === group && place.key !== current)
    .map((place) => ({ place, distance: nearest(place, references)?.km ?? 0 }))
    .sort((a, b) => a.distance - b.distance).slice(0, 3)
    .map(({ place }, index) => candidate(state, id, place, "candidate", index + 1, references));
}

/** Example places whose name or kind holds the words, nearest first. */
export function searchPlaces(state: PreviewState, id: string, query: string): PlanCandidate[] {
  const words = normalized(query);
  if (!words) return [];
  const references = referencesOf(state, id);
  return EXAMPLE_PLACES.filter((place) => normalized(place.name).includes(words) || normalized(place.category).includes(words))
    .map((place) => candidate(state, id, place, "search", null, references))
    .sort((a, b) => (a.distance?.km ?? 0) - (b.distance?.km ?? 0)).slice(0, 8);
}

export const findPlaceByName = (name: string) => EXAMPLE_PLACES.find((place) => normalized(place.name) === normalized(name))
  ?? EXAMPLE_PLACES.find((place) => normalized(place.name).includes(normalized(name)));

// ── changes ──────────────────────────────────────────────────────────────────────────────────────────────────
export type ApplyHow = "auto" | "pick" | "search";
const FIRST_LINE: Record<ApplyHow, string> = { auto: "대체 후보 1순위", pick: "대체 후보에서 고른 곳", search: "검색으로 고른 곳" };

/** Put an example place in a stop: its checks, its moves before and after, the day's overlaps. */
export function applyPlace(state: PreviewState, id: string, key: string, how: ApplyHow): PreviewState {
  const place = placeByKey(key);
  const placeOf = { ...state.placeOf, [id]: key };
  const moved: PreviewState = { placeOf, view: { ...state.view, items: state.view.items.map((item) => item.id === id
    ? { ...item, title: place.name, place: place.name, noPlace: false, coordinates: place.coordinates, info: placeInfo(place) } : item) } };
  const checks = placeChecks(moved, id, key, `${FIRST_LINE[how]} · ${place.source} 정보로 찾았어요`);
  let view: PlanCheckView = { ...moved.view, dirty: true, items: moved.view.items.map((item) => item.id === id ? { ...item, checks, verdict: verdictOf(checks) } : item) };
  view = rebuildMoves(refreshTimeRows(view, itemOf(view, id).day), new Set([id]));
  return withSuggestions({ placeOf, view });
}

export function removeStop(state: PreviewState, id: string): PreviewState {
  const item = itemOf(state.view, id);
  // The stops either side now meet: their move is worked out anew (it has no id yet), the others are kept.
  let view: PlanCheckView = { ...state.view, dirty: true, items: state.view.items.filter((entry) => entry.id !== id) };
  view = rebuildMoves(refreshTimeRows(view, item.day), new Set());
  const placeOf = { ...state.placeOf };
  delete placeOf[id];
  return { placeOf, view };
}

export function setLocked(state: PreviewState, id: string, locked: boolean): PreviewState {
  return { ...state, view: { ...state.view, items: state.view.items.map((item) => item.id === id ? { ...item, locked } : item) } };
}

/** A stop's time fitted between its neighbours at a place (mockup fitWindow): null when it cannot fit or the place is shut. */
function fitWindow(state: PreviewState, id: string, key: string): { start: string; end: string; changed: boolean } | null {
  const item = itemOf(state.view, id), stops = dayItems(state.view, item.day), at = stops.indexOf(item), place = placeByKey(key);
  const previous = stops[at - 1], next = stops[at + 1];
  let start = toMinutes(item.startsAt);
  const duration = toMinutes(item.endsAt || item.startsAt) - start;
  if (previous?.coordinates) { const arrive = toMinutes(previous.endsAt) + travel(previous.coordinates, place.coordinates).minutes; if (arrive > start) start = Math.ceil(arrive / 5) * 5; }
  let end = start + duration;
  if (next?.coordinates) { const latest = toMinutes(next.startsAt) - travel(place.coordinates, next.coordinates).minutes; if (end > latest) end = Math.floor(latest / 5) * 5; }
  if (end - start < 30) return null;
  if (place.hours && (start < toMinutes(place.hours[0]) || end > toMinutes(place.hours[1]))) return null;
  if (place.closed?.startsWith(weekday(item.date))) return null;
  return { start: hhmm(start), end: hhmm(end), changed: hhmm(start) !== item.startsAt || hhmm(end) !== item.endsAt };
}

/**
 * 「전체 자동 추천」(mockup autoAll): every stop that needs a look, or that the move before it reaches late, gets the first
 * alternative (or keeps its place) that fits the hours, the closing day and the moves either side — its time shortened to
 * fit when needed (at least 30 minutes). Locked stops stay as they are.
 */
export function recommendAll(state: PreviewState): { state: PreviewState; changes: string[]; kept: number } {
  let current = state;
  const changes: string[] = [];
  let kept = 0;
  for (const day of state.view.days) {
    for (const stop of dayItems(current.view, day.day)) {
      const item = itemOf(current.view, stop.id), stops = dayItems(current.view, day.day), previous = stops[stops.indexOf(item) - 1];
      const placeBad = item.verdict === "review";
      const late = Boolean(previous) && current.view.moves.find((move) => move.id === `${previous.id}-${item.id}`)?.verdict === "review";
      if (!placeBad && !late) continue;
      if (item.locked) { kept += 1; continue; }
      const keys = placeBad ? candidatesFor(current, item.id).map((entry) => entry.id) : [current.placeOf[item.id]].filter((key): key is string => Boolean(key));
      const fit = keys.map((key) => ({ key, window: fitWindow(current, item.id, key) })).find((entry) => entry.window);
      if (!fit?.window) { kept += 1; continue; }
      const old = item.title, place = placeByKey(fit.key);
      const timed: PreviewState = { ...current, view: { ...current.view, items: current.view.items.map((entry) => entry.id === item.id ? { ...entry, startsAt: fit.window!.start, endsAt: fit.window!.end } : entry) } };
      const applied = placeBad ? applyPlace(timed, item.id, fit.key, "auto") : timed;
      const after = itemOf(applied.view, item.id);
      const checks = [row("place", "ok", placeBad ? `서버가 검증한 대체 후보 · ${place.source} 정보로 찾았어요` : item.checks.find((check) => check.kind === "place")?.text ?? `${place.source} 정보로 찾았어요`),
        ...(fit.window.changed ? [row("time", "filled", `앞뒤 이동에 맞춰 ${fit.window.start}–${fit.window.end}(${toMinutes(fit.window.end) - toMinutes(fit.window.start)}분)으로 맞췄어요`)] : []),
        hoursRow(place, after), closedRow(place, after)];
      current = { ...applied, view: rebuildMoves({ ...applied.view, dirty: true, items: applied.view.items.map((entry) => entry.id === item.id ? { ...entry, checks, verdict: verdictOf(checks) } : entry) }, new Set([item.id])) };
      changes.push(`${old} → ${place.name} ${fit.window.start}–${fit.window.end}`);
    }
    current = { ...current, view: refreshTimeRows(current.view, day.day) };
  }
  return { state: withSuggestions(current), changes, kept };
}

/** While one or more stops are checked again: their checks and verdicts wait, and so do the moves either side (and `moveIds`). */
export function waitingFor(view: PlanCheckView, ids: string[], moveIds: string[] = []): PlanCheckView {
  const wait = new Set(ids), waitMoves = new Set(moveIds);
  const pending = <T extends { checks: CheckRow[]; verdict: PlanItem["verdict"] }>(entity: T): T =>
    ({ ...entity, verdict: null, checks: entity.checks.map((check) => ({ ...check, result: "pending" as const, text: "" })) });
  return { ...view, items: view.items.map((item) => wait.has(item.id) ? pending(item) : item),
    moves: view.moves.map((move) => wait.has(move.fromId) || wait.has(move.toId) || waitMoves.has(move.id) ? pending(move) : move) };
}

/** The stops in the order a full re-check goes through them. */
export const recheckOrder = (view: PlanCheckView) => view.days.flatMap((day) => dayItems(view, day.day).map((item) => item.id));
