import type { Language } from "../i18n";
import { api } from "./client";
import type { IntakeView } from "./intake";

/**
 * The plan-check screen's server data (`wiki/external/rest-endpoints.md` 「확인 화면 검사 · 대체 후보 …」).
 *
 * ★The server computes the check once per revision and the screen only shows it. Nothing here decides whether a place
 *   is open or a leg is reachable — an unknown value stays `unknown` and is never drawn as "fine".
 */

/** ✓ ok · ✎ filled (a rule filled it in) · ! warn · ✕ bad (must be fixed) · – unknown (not known yet). */
export type CheckResult = "ok" | "filled" | "warn" | "bad" | "unknown";
/** `booking` (2026-10-03, server 8b0d4c88): shown only for a booking word or a meal line with no name — 예약 있음 · 예약 없이 간다 · 예약 있다는데 장소 모름 · 예약 여부 모름. */
export type ItemRow = "place" | "time" | "hours" | "closed" | "booking";
export type MoveRow = "route" | "mode" | "arrival";
export interface CheckLine<Row extends string = string> { row: Row; result: CheckResult; text: string }

/** keep · adjusted (a rule filled it, or the customer changed it) · review (needs the customer). */
export type ItemStatus = "keep" | "adjusted" | "review";
/** `picked_nearest` — several shops share the name, the closest one was picked for now (change it from the candidates). */
export type PlaceState = "found" | "picked_nearest" | "customer" | "none" | "unresolved" | "searching";

export interface ReviewPlace {
  name: string;
  latitude: number | null;
  longitude: number | null;
  source: string | null;
  kind: string | null;
  /** Korea Tourism Organization numbers — present only for places that came from it. */
  content_id?: string | null;
  content_type_id?: string | null;
}

export interface ReviewItem {
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
  locked: boolean;
  edited?: boolean;
  /** null while the check is still running (stream events before the check finished). */
  status: ItemStatus | null;
  can_lock: boolean;
  place_state: PlaceState;
  place: ReviewPlace | null;
  candidates_hint: number | null;
  rows?: CheckLine<ItemRow>[];
}

export type MoveStatus = "keep" | "review" | "waiting";
export type MoveMode = "walk" | "subway" | "bus" | "transit" | "estimate" | null;

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
  rows: CheckLine<MoveRow>[];
}

export interface ReviewNeeds { items: number; moves: number; total: number }

export interface Review {
  revision: number;
  built_at: string;
  engine: "timetable" | "estimate" | "mixed" | null;
  items: ReviewItem[];
  moves: ReviewMove[];
  needs: ReviewNeeds;
  /** No read problem and nothing to check — the 「여행 등록」 button turns on. */
  ready: boolean;
}

/** `GET /v1/web/trip-intakes/{id}` — the read view plus the check. */
export interface ReviewedIntakeView extends IntakeView {
  review?: Review | null;
  /** `review_failed` — the check could not be built; the read values are still shown, never an empty "all fine". */
  review_error?: string | null;
}

/** One place, in the shape `POST …/edits` takes for `items[n].place` when the customer picked it from a list. */
export interface PickedPlace {
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
  rank: number;
  place: CandidatePlace;
  distance_m: number | null;
  /** The nearby stop the distance is measured from. */
  reference: string | null;
  rows: CheckLine<ItemRow>[];
  fits: boolean;
  status: "ok" | "warn" | "bad";
  slack: { before: number | null; after: number | null };
  /** One of the legs in or out is a straight-line guess. */
  estimated: boolean;
}

export interface CandidateList {
  revision: number;
  item: string;
  current: ReviewPlace | null;
  reference: { before: string | null; after: string | null };
  candidates: Candidate[];
  /** Why the list is short or approximate (`engine_budget_exhausted` · `no_same_kind` · `no_other_branches` · `kakao:<reason>`). */
  notes: string[];
}

export interface PlaceSearchResult {
  revision: number;
  item: string;
  query: string;
  results: Candidate[];
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
}

export type AutofixKeptReason = "locked" | "no_time" | "no_candidates" | "no_fitting_place" | "no_fitting_time" | "nothing_to_change";

export interface AutofixResult {
  applied: boolean;
  revision: number;
  changed: AutofixChange[];
  kept: { id: string; title: string; reason: AutofixKeptReason }[];
  view: ReviewedIntakeView;
}

const base = (intakeId: string) => `/v1/web/trip-intakes/${encodeURIComponent(intakeId)}`;
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export function getCandidates(intakeId: string, item: Pick<ReviewItem, "source_id" | "index">, revision: number, language: Language): Promise<CandidateList> {
  const query = new URLSearchParams({ source_id: item.source_id, index: String(item.index), revision: String(revision) });
  return api(`${base(intakeId)}/candidates?${query}`, language);
}

export function searchPlaces(intakeId: string, item: Pick<ReviewItem, "source_id" | "index">, revision: number, q: string, language: Language, signal?: AbortSignal): Promise<PlaceSearchResult> {
  const query = new URLSearchParams({ q, source_id: item.source_id, index: String(item.index), revision: String(revision) });
  return api(`${base(intakeId)}/place-search?${query}`, language, { signal });
}

export function getPlacePhotos(ref: string, language: Language): Promise<PlacePhotos> {
  return api(`/v1/web/places/photos?${new URLSearchParams({ ref })}`, language);
}

export function autofixIntake(intakeId: string, revision: number, language: Language): Promise<AutofixResult> {
  return api(`${base(intakeId)}/autofix`, language, json({ revision }));
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
  };
}
