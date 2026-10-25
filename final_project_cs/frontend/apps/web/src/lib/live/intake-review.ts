import type { Language } from "../i18n";
import { api } from "./client";
import { STREAM_TIMING, streamApi } from "./stream";
import type { IntakeEdit, IntakeView } from "./intake";
import type { WebTaxiPricing } from "./taxi-pricing";

/**
 * The plan-check screen's server data (`wiki/external/rest-endpoints.md` 「확인 화면 검사 · 대체 후보 …」).
 *
 * ★The server computes the check once per revision and the screen only shows it. Nothing here decides whether a place
 *   is open or a leg is reachable — an unknown value stays `unknown` and is never drawn as "fine".
 */

/** ✓ ok · ✎ filled (a rule filled it in) · ! warn · ✕ bad (must be fixed) · – unknown (not known yet). */
export type CheckResult = "ok" | "filled" | "warn" | "bad" | "unknown";
/** `booking` (2026-10-03, server 8b0d4c88): shown only for a booking word or a meal line with no name — 예약 있음 · 예약 없이 간다 · 예약 있다는데 장소 모름 · 예약 여부 모름. */
/** `[2026-10-26]` `date` (server d2ab93a65): a new plan whose every stop is before today — on each stop, `bad`, with the server's sentence. */
export type ItemRow = "place" | "time" | "hours" | "closed" | "booking" | "risk" | "date" | "dining_check" | "dietary" | "kids" | "payment" | "business";
export type MoveRow = "route" | "mode" | "arrival";
export interface CheckLine<Row extends string = string> {
  row: Row; result: CheckResult; text: string; can_acknowledge?: boolean;
  requirement?: "required" | "preference";
  blocks_registration?: boolean;
}

export interface IntakeDiningJudge {
  status: "disabled" | "pending" | "running" | "completed" | "failed";
  revision: number;
  run_id: string | null;
  started_at?: string | null;
  deadline_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  blocks_registration?: boolean;
}

export interface DiningQuestion {
  id: string;
  quote: string;
  attribute: "halal" | "vegetarian" | "kids" | "card";
  required: boolean;
  choices: { item_id: string; date: string | null; starts_at: string | null; title: string | null }[];
  answer: { item_ids: string[]; excluded: boolean } | null;
}

export interface DiningAnswer {
  revision: number; run_id: string; question_id: string; item_ids: string[]; excluded: boolean;
}

export function answerDiningQuestion(intakeId: string, answer: DiningAnswer, language: Language): Promise<ReviewedIntakeView> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/dining-answers`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(answer),
  });
}

/** keep · adjusted (a rule filled it, or the customer changed it) · review (needs the customer). */
export type ItemStatus = "keep" | "adjusted" | "review";
/** `picked_nearest` — several shops share the name, the closest one was picked for now (change it from the candidates). */
/**
 * `needs_choice` · `needs_name` (server 8b0d4c88, 2026-10-03): a line with no shop name, only a kind and an area ("성수 식당"). The place is
 * not looked up by name: `needs_choice` — pick one of the candidates around the area; `needs_name` — the same line with a booking, so
 * no candidates are offered and the booked place's name is asked.
 */
export type PlaceState = "found" | "picked_nearest" | "customer" | "none" | "unresolved" | "searching" | "needs_choice" | "needs_name";

export interface ReviewPlace {
  name: string;
  latitude: number | null;
  longitude: number | null;
  source: string | null;
  kind: string | null;
  /** Korea Tourism Organization numbers — present only for places that came from it. */
  content_id?: string | null;
  content_type_id?: string | null;
  category?: string | null;
}

export interface ReviewItem {
  /** The same six-source risk result used by the watcher. Missing on an older deployment. */
  risk?: unknown;
  /** `<source position>-<index>` — the key that events, moves and candidates use to point at each other. */
  id: string;
  source_id: string;
  index: number;
  title: string;
  kind: string | null;
  day: number | null;
  date: string | null;
  starts_at: string | null;
  ends_at: string | null;
  /** `[2026-10-13]` The day it ends when that is another day — a stay (kind lodging) ends on its check-out day. Missing or null otherwise. */
  end_date?: string | null;
  locked: boolean;
  edited?: boolean;
  /** null while the check is still running (stream events before the check finished). */
  status: ItemStatus | null;
  can_lock: boolean;
  place_state: PlaceState;
  place: ReviewPlace | null;
  /** The plan says it is booked (`true`), says it is not (`false`), or says nothing (`null`; also an older server). */
  booked?: boolean | null;
  /** `[2026-10-15 ST4F-490]` An edit's stop tied to a vendor's booking: unlocking it does not change that booking (the customer changes it with the vendor). Absent on an older server. */
  vendor_booking?: boolean;
  candidates_hint: number | null;
  parts?: { content_type?: string | null; lodging_meal?: boolean } | null;
  lodging_group?: { id: string; members: string[]; place: Pick<ReviewPlace, "name" | "latitude" | "longitude"> | null };
  rows?: CheckLine<ItemRow>[];
  /**
   * `[2026-10-07 cs 개발 세션 제안 계약]` A value read off a photo or scan that the server read two ways (the whole page and a half of it read the same line differently). `current` is the value it kept,
   * `other` what the other reading gave (null when it could not tell - then only the row's note is shown). The customer picks one; it is sent as `items[i].<field>`. Absent on an older server.
   */
  rereads?: ReviewReread[];
}

export interface ReviewReread { field: "title" | "booking_no"; current: string; other: string | null }

export type MoveStatus = "keep" | "review" | "waiting";
export type MoveMode = "walk" | "subway" | "bus" | "taxi" | "transit" | "estimate" | null;  // `taxi`: after the customer picks it (2026-10-07 이동수단 고르기)

export interface ReviewMove {
  from: string;
  to: string;
  day: number | null;
  date: string | null;
  status: MoveStatus;
  mode: MoveMode;
  mode_label: string | null;
  minutes: number | null;
  km: number | null;
  depart: string | null;
  arrive: string | null;
  /** Negative = arrives after the next stop starts. */
  slack_min: number | null;
  /** `estimate` = a straight-line guess because the transit engine was off or could not fill the leg. */
  basis: "timetable" | "estimate" | null;
  summary: string;
  fare_krw?: number | null;
  /** `[2026-10-07]` The way the calculator chose (it stays when the customer picks another), and what became of the customer's choice after the stops around the leg changed. */
  recommended_mode?: string | null;
  mode_choice?: { mode?: string | null; state?: string | null; why?: string | null } | null;
  /** `[2026-10-23]` The leg's first route candidates (the one it uses first; the rest via `GET …/routes`), how many the calculation found, whether 「more」 is worth asking, the route it uses, and what became of the customer's route. */
  routes?: unknown[];
  routes_total?: number | null;
  routes_more?: boolean;
  route_key?: string | null;
  route_choice?: { key?: string | null; state?: string | null; why?: string | null } | null;
  /** `[2026-10-13]` A morning move 「숙소 → 그날 첫 일정」: it leaves from the stay, on the day of `to` (`day` · `date`), not right after `from`. */
  from_stay?: boolean;
  rows: CheckLine<MoveRow>[];
}

export interface ReviewNeeds { items: number; moves: number; total: number }

export interface Review {
  risk_mode?: "fresh" | "cached";
  risk_checked_at?: string | null;
  risk_schema_version?: number;
  dining_judge?: IntakeDiningJudge | null;
  dining_questions?: DiningQuestion[];
  taxi_pricing?: WebTaxiPricing;
  revision: number;
  built_at: string;
  engine: "timetable" | "estimate" | "mixed" | null;
  items: ReviewItem[];
  moves: ReviewMove[];
  needs: ReviewNeeds;
  /** No read problem and nothing to check — the 「여행 등록」 button turns on. */
  ready: boolean;
  /**
   * `[2026-10-20 사용자 지시]` false = the revision was only SAVED (`editIntake(..., { check: false })`): moves are not measured yet and `ready` is false
   * until 「다시 제출」 (`revalidate`) checks it. Absent on older servers and older revisions — read as checked.
   */
  checked?: boolean;
}

/** `GET /v1/web/trip-intakes/{id}` — the read view plus the check. */
export interface ReviewedIntakeView extends IntakeView {
  review?: Review | null;
  /** `review_failed` — the check could not be built; the read values are still shown, never an empty "all fine". */
  review_error?: string | null;
  /** `true` on the view `POST …/autofix {dry_run: true}` returns when something would change: the plan as it WOULD be (its `revision` is the one applying it makes) — nothing is saved. */
  preview?: boolean;
}

/** One place, in the shape `POST …/edits` takes for `items[n].place` when the customer picked it from a list. */
export interface PickedPlace {
  provider_ref?: string | null;
  name: string;
  latitude: number;
  longitude: number;
  source: "customer_pick" | "kakao" | "tour_api" | "places" | "search" | "map";
  kind?: string | null;
  content_id?: string | null;
}

export interface CandidatePlace extends ReviewPlace {
  address: string | null;
  category: string | null;
  /** `tour:<number>` — the key of the photo call. */
  ref: string | null;
}

export interface Candidate {
  risk?: unknown;
  date?: string | null;
  starts_at?: string | null;
  ends_at?: string | null;
  end_date?: string | null;
  rank: number;
  place: CandidatePlace;
  distance_m: number | null;
  /** The nearby stop the distance is measured from. */
  reference: string | null;
  /** `[2026-10-22]` Place search only: which list the result belongs to — nearest first, best name match first, or `[2026-10-23]` least out of the way between two stops (add search). */
  order?: "distance" | "relevance" | "route";
  rows: CheckLine<ItemRow>[];
  fits: boolean;
  status: "ok" | "warn" | "bad";
  slack: { before: number | null; after: number | null };
  /** One of the legs in or out is a straight-line guess. */
  estimated: boolean;
  /**
   * `[2026-10-07 서버 c0ca7054 — 대체 후보 세 단]` Which step of the ladder it came from: `same_kind` (the same kind, tourism classes) · `similar_experience` · `meal_inferred` (a meal place where a market stands
   * at a meal time — picking it makes the stop a meal: send `items[i].kind = "dining"` with the place) · null (a map search …). `reason`: the server's one sentence, only what it knows.
   */
  basis?: "same_kind" | "similar_experience" | "meal_inferred" | "lodging" | "lodging_meal" | "taste" | null;   // lodging · lodging_meal [2026-10-07 서버 90d9e403]: 이름 없는 「호텔」 줄의 숙소 / 그 숙소 안 식사
  reason?: string | null;
  similarity?: number | null;
  experience?: string | null;
  /** `[2026-10-19]` Whether the reason was written by the model or is the plain template. */
  reason_by?: "model" | "template";
  /** `[2026-10-19]` The way in from the stop before and out to the stop after: whose stop, minutes, the way (`mode_label`), and whether it is a straight-line guess. */
  legs?: { before: CandidateLeg | null; after: CandidateLeg | null };
  /** `[2026-10-19]` Only in the live answer (`streamCandidates`): what is still being worked out — the way in, the way out, the model's reason. */
  pending?: CandidatePending;
}

export interface CandidateLeg { with: string; minutes: number; mode: string; mode_label: string; estimated: boolean; slack_min: number }
export interface CandidatePending { before: boolean; after: boolean; reason: boolean }

export interface CandidateList {
  revision: number;
  item: string;
  current: ReviewPlace | null;
  reference: { before: string | null; after: string | null };
  candidates: Candidate[];
  /** Why the list is short or approximate (`engine_budget_exhausted` · `no_same_kind` · `no_other_branches` · `kakao:<reason>`). */
  notes: string[];
  /** `[2026-10-19]` The alternatives were made ready when the plan was read (no wait): when, for which revision, and which legs were measured again (`before` · `after`). Null when worked out now. */
  prepared?: { revision: number; computed_at: string; stale: string[] } | null;
}

/** `[2026-10-19]` One change to a card while the live answer works it out: the measured legs (`rows` … `legs`), or the model's reason. `rank` is the card's place in the first list. */
export interface CandidateUpdate {
  rank: number;
  rows?: Candidate["rows"]; fits?: boolean; status?: Candidate["status"]; slack?: Candidate["slack"]; estimated?: boolean; legs?: Candidate["legs"];
  reason?: string; reason_by?: "model" | "template";
  pending?: Partial<CandidatePending>;
}

export interface PlaceSearchResult {
  revision: number;
  item: string;
  query: string;
  /** `[2026-10-22]` Nearest first, measured from `center` (the stop being changed when it has a place) — each `order: "distance"`. */
  results: Candidate[];
  /** `[2026-10-22]` Best name match first, wherever it is in Seoul — each `order: "relevance"`. Absent from an older server. */
  relevance?: Candidate[];
  /** `[2026-10-22]` Where the distances are measured from: the stop's own place (`selected`), the area its line names (`area`), or the stops around it (`neighbours`). */
  center?: { name: string | null; basis: "selected" | "area" | "neighbours" } | null;
  notes: string[];
}

export interface PlacePhotos {
  ref: string;
  photos: { url: string; thumb: string | null; name: string | null }[];
  /** 「ⓒ한국관광공사」 — shown next to the photos. Photos are never stored here. */
  source_note: string | null;
  reason: string | null;
}

/** A place in an auto-fix answer: what it was, and what it became. */
export interface AutofixPlace { name: string; latitude: number | null; longitude: number | null; source: string | null; kind?: string | null; content_id?: string | null }

export interface AutofixChange {
  id: string;
  source_id: string;
  index: number;
  title: string;
  from: { place: AutofixPlace | null; starts_at: string | null; ends_at: string | null };
  to: { place: AutofixPlace | null; starts_at: string | null; ends_at: string | null };
  reason: "place" | "time" | "place_and_time";
  /** `[2026-10-25 사용자 결정 — 뒤 일정까지 함께 미루기]` (`push`) A stop after the asked one, made later so it is still reached. */
  pushed?: boolean;
}

/**
 * `booked` (server 8b0d4c88): a stop the plan says is booked is changed in neither place nor time.
 * `push_refused` `[2026-10-25]` (`push`): the stops after it could not be made later (a closing time · the day's end · a fixed or booked stop) — the server's sentence in `message`.
 */
export type AutofixKeptReason = "locked" | "booked" | "no_time" | "no_candidates" | "no_fitting_place" | "no_fitting_time" | "nothing_to_change" | "push_refused";

export interface AutofixResult {
  applied: boolean;
  revision: number;
  changed: AutofixChange[];
  /** `push_refused` also says the times it tried (`starts_at` · `ends_at`) and why (`message`). */
  kept: { id: string; title: string; reason: AutofixKeptReason; starts_at?: string; ends_at?: string; message?: string }[];
  view: ReviewedIntakeView;
  /** `[2026-10-25]` (`push`, something changed) The edits that make that plan — sent as they are (`keep_times`) they save what was shown. */
  edits?: IntakeEdit[];
}

const base = (intakeId: string) => `/v1/web/trip-intakes/${encodeURIComponent(intakeId)}`;
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function getCandidates(intakeId: string, item: Pick<ReviewItem, "source_id" | "index">, revision: number, language: Language): Promise<CandidateList> {
  const query = new URLSearchParams({ source_id: item.source_id, index: String(item.index), revision: String(revision) });
  return api(`${base(intakeId)}/candidates?${query}`, language);
}

/**
 * `[2026-10-19 사용자 지시]` The alternatives as a live answer: prepared ones come at once (only the result); otherwise the cards come first with
 * straight-line guesses (`onFirst`), each measured leg and each model reason as it lands (`onUpdate`), then the final list (resolved — the server picks
 * the three again by the full check). A server without streams answers once in JSON — then only the result comes.
 */
export function streamCandidates(intakeId: string, item: Pick<ReviewItem, "source_id" | "index">, revision: number, language: Language,
  onFirst: (list: CandidateList) => void, onUpdate: (update: CandidateUpdate) => void): Promise<CandidateList> {
  const query = new URLSearchParams({ source_id: item.source_id, index: String(item.index), revision: String(revision) });
  return streamApi<CandidateList>(`${base(intakeId)}/candidates?${query}`, language, { method: "GET" }, undefined, STREAM_TIMING, (name, body) => {
    if (name === "candidates") onFirst(body as unknown as CandidateList);
    else if (name === "candidate" && typeof body.rank === "number") onUpdate(body as unknown as CandidateUpdate);
  });
}

/** `relevance: false` — `[2026-10-22]` only the nearest list (the add-stop search draws no other), so the server makes no second map call for it. */
export function searchPlaces(intakeId: string, item: Pick<ReviewItem, "source_id" | "index">, revision: number, q: string, language: Language, signal?: AbortSignal,
  { relevance = true }: { relevance?: boolean } = {}): Promise<PlaceSearchResult> {
  const query = new URLSearchParams({ q, source_id: item.source_id, index: String(item.index), revision: String(revision), ...(relevance ? {} : { relevance: "false" }) });
  return api(`${base(intakeId)}/place-search?${query}`, language, { signal });
}

/** `[2026-10-23 사용자 지시 — Codex 합의]` The add-stop form's place search: the stops either side of the gap and the new stop's own values (judged as the new stop). */
export interface AddSearchQuery { q: string; previous: string | null; next: string | null; date?: string; start?: string; end?: string; kind?: string }

export function addSearch(intakeId: string, revision: number, query: AddSearchQuery, language: Language, signal?: AbortSignal): Promise<PlaceSearchResult> {
  const params = new URLSearchParams({ q: query.q, revision: String(revision) });
  for (const key of ["previous", "next", "date", "start", "end", "kind"] as const) { const value = query[key]; if (value) params.set(key, value); }
  return api(`${base(intakeId)}/add-search?${params}`, language, { signal });
}

export function getPlacePhotos(ref: string, language: Language): Promise<PlacePhotos> {
  return api(`/v1/web/places/photos?${new URLSearchParams({ ref })}`, language);
}

/** `dryRun`: only show how the plan would look (server 224e7a1b, 2026-10-03) — the server saves nothing and the answer's `view.preview` is true. */
export function autofixIntake(intakeId: string, revision: number, language: Language, dryRun = false, itemId?: string, push = false): Promise<AutofixResult> {
  return api(`${base(intakeId)}/autofix`, language, json({ revision, ...(dryRun ? { dry_run: true } : {}), ...(itemId ? { item_id: itemId } : {}), ...(itemId && push ? { push: true } : {}) }));
}

export function revalidateIntake(intakeId: string, revision: number, language: Language): Promise<ReviewedIntakeView> {
  return api(`${base(intakeId)}/revalidate`, language, json({ revision }));
}

const PICK_SOURCES: readonly string[] = ["customer_pick", "kakao", "tour_api", "places", "search", "map"];

/**
 * A candidate or search result as the `place` value of an edit — what the customer picked, sent back as it came.
 * ★null when the result has no coordinates: the server takes a picked place by its coordinates and does not look it up
 *   again, so a place without them cannot be picked (the screen leaves its 「이 장소로 바꾸기」 off).
 */
export function pickedPlace(place: CandidatePlace): PickedPlace | null {
  if (typeof place.latitude !== "number" || typeof place.longitude !== "number") return null;
  return {
    name: place.name,
    latitude: place.latitude,
    longitude: place.longitude,
    source: place.source && PICK_SOURCES.includes(place.source) ? place.source as PickedPlace["source"] : "search",
    ...(place.kind ? { kind: place.kind } : {}),
    ...(place.content_id ? { content_id: place.content_id } : {}),
    ...(place.ref && /^(?:kakao|tour):[0-9]{1,30}$/.test(place.ref) ? { provider_ref: place.ref } : {}),
  };
}
