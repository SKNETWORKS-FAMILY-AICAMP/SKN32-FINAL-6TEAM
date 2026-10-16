import type { TripSurvey } from "@/features/onboarding/payload";
import type { Language } from "../i18n";
import { api } from "./client";
import type { ReviewedIntakeView } from "./intake-review";
import { streamApi, type OpProgress } from "./stream";

/** One value the server read, with how it was read and the evidence behind it (server `intake_claims`). */
export interface IntakeField {
  value: unknown;
  /** rule · llm_span (the model pointed at a span of the original) · lookup (place search) · customer · trip (`[2026-10-13]` taken from the registered trip an edit reopened) */
  method: "rule" | "llm_span" | "lookup" | "customer" | "trip" | "llm_agent";
  evidence: { line?: number; text?: string; source?: string; how?: string; blocked?: string[] } & Record<string, unknown>;
  needs_review: boolean;
  note: string | null;
}

export interface IntakeItem {
  index: number;
  line: number;
  day: number | null;
  date: string | null;
  fields: Partial<Record<"title" | "starts_at" | "ends_at" | "date" | "kind" | "place" | "booking_no" | "booked" | "removed", IntakeField>>;
}

export interface IntakeProblem { code: string; field: string; message: string; source_id: string | null }
export interface IntakeFilled { source_id: string; field: string; value: string; method: "rule"; note: string }

export interface IntakeSource {
  source_id: string;
  kind: string;
  filename: string | null;
  transcribed: boolean;
  lines: { no: number; text: string; read: boolean }[];
  items: IntakeItem[];
  trip: Record<string, { value: unknown }>;
  reading: { asked_lines?: number; accepted?: number; rejected?: { quote?: string; why: string }[]; error?: string } | null;
  /**
   * `[2026-10-16 D-025]` What the reading agent understood that is not a stop: moves, conditions (「비 오면 실내」), how the traveller likes to travel,
   * and the guard's view — each with the exact words it came from. Null (or absent, an older server) when the agent was not used.
   */
  understanding?: IntakeUnderstanding | null;
}

export interface IntakeUnderstanding {
  moves: { mode: string; scope: string; from: string | null; to: string | null; quote: string }[];
  conditions: { code: string; quote: string }[];
  preferences: { code: string; quote: string }[];
  pieces?: { kind: string; quote: string }[];
  gaps?: { kind: string; quote: string }[];
  missing?: string[];
  guard?: { travel: boolean; instruction_change: boolean; out_of_scope: boolean; quote: string | null } | null;
}

/**
 * `[2026-10-16 D-025]` What the server filled in first, like a secretary would: `filled[].item` is the check's stop id, with who proposed it and why;
 * `questions` are what only the traveller knows (asked, never refused). The page shows these words as they are.
 */
export interface IntakePrefill {
  filled: { item: string | null; title: string | null; owner: string; owner_label: string; reason: string; gap: string; new: boolean }[];
  questions: { kind: string; question: string; quote: string | null }[];
  kept: { kind: string; item: string | null; owner: string; reason: string }[];
}

export interface IntakeView {
  intake_id: string;
  test_scenario?: { code: string; name: string; description: string; mode: "prepared_text"; catalog_version: string } | null;
  status: "reading" | "review" | "confirmed" | "fatal";
  /** received · transcribing · reading · checking (places and hours) · review · … — shown through `stage_label`. */
  stage: string;
  stage_label: string;
  revision: number;
  fatal: { code: string; detail: string } | null;
  trip_id: string | null;
  sources: IntakeSource[];
  check: { ready: boolean; problems: IntakeProblem[]; filled: IntakeFilled[]; items: number; title: string; plan: IntakePlanBasis } | null;
  needs_review: { field: string; note: string | null }[];
  /**
   * `[2026-10-06]` Questions to ask while the server reads (`wiki/external/rest-endpoints.md` 「설문 질문」). The page DRAWS what is here and nothing else: a `kind` it does not know is skipped,
   * and no wording or option meaning is built into the page (an older server sends none). `answer` = the option id already saved, `null` when there is none.
   */
  questions?: IntakeQuestion[];
  /** The question set these come from; a change in meaning of an option raises it. Kept for the record - the page does not branch on it. */
  questions_version?: string;
  /**
   * `[2026-10-13]` An edit of a registered trip (`reopenTrip`): the trip and the version it reopened, and the trip's stops left out of the intake — they stay as they are when the edit is done.
   * Null (or absent, an older server) on an intake read from a plan.
   * `[2026-10-15 ST4F-490]` `frozen` says why each is left out (`reason` null on an edit opened before the server said so; absent on an older server). Stays, flights and vendor bookings
   * are no longer left out: they come into the edit locked.
   */
  reopen?: { trip_id: string; version: number; frozen_item_ids: string[]; frozen?: { item_id: string; reason: FrozenReason | null }[] } | null;
  /** `[2026-10-16 D-025]` See `IntakePrefill`. Null (or absent) when nothing was filled first. */
  prefill?: IntakePrefill | null;
}

/** `[2026-10-15 ST4F-490]` Why a stop of the trip is left out of an edit: over · runs past midnight · its place has no position · a kind the edit does not take. */
export type FrozenReason = "past" | "overnight" | "no_place" | "kind";

/** One question of `questions[]`. Only `kind: "single"` (pick one option) is drawn today; the fields are read as data and checked again before drawing (`features/survey-questions/model.ts`). */
export interface IntakeQuestion {
  id: string;
  kind: string;
  title?: string;
  why?: string;
  options?: { id: string; label: string }[];
  answer?: string | null;
  allow_custom?: boolean;
  custom_max_length?: number;
  custom_answer?: string | null;
}

/** 「일정 짜 줘」 기본값 — 읽은 값에서만 나온다. 모르면 null(화면이 묻는다). */
export interface IntakePlanBasis { requested: boolean; start_date: string | null; days: number | null; party_size: number | null; preferences: string }
/** `survey` rides along only when the customer finished the onboarding questions (server `TripSurvey`, optional). */
export interface IntakePlanInput { start_date: string; days: number; party_size: number; keep_read_items: boolean; survey?: TripSurvey }

export interface IntakeEdit { source_id?: string | null; field: string; value: unknown }

/** `humanToken` — the Turnstile token when the human check is on; the server checks it with Cloudflare. */
export async function submitIntake(text: string, files: File[], language: Language, humanToken?: string | null, signal?: AbortSignal): Promise<{ intake_id: string }> {
  const form = new FormData();
  form.append("text", text);
  for (const file of files) form.append("files", file, file.name);
  if (humanToken) form.append("turnstile_token", humanToken);
  return api("/v1/web/trip-intakes", language, { method: "POST", body: form, ...(signal && { signal }) });
}

/** The read values plus — once the plan is on the check screen — the server's check of every place and leg (`review`). */
export function getIntake(intakeId: string, language: Language): Promise<ReviewedIntakeView> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}`, language);
}

export function editIntake(intakeId: string, revision: number, edits: IntakeEdit[], language: Language): Promise<ReviewedIntakeView> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/edits`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, edits }),
  });
}

/** Restore a completed historical revision atomically; protected stops or a stale revision reject the whole request. */
export function restoreIntake(intakeId: string, revision: number, restoreRevision: number, language: Language, item?: { source_id: string; index: number }): Promise<ReviewedIntakeView> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/restore`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, restore_revision: restoreRevision, ...(item && { item }) }),
  });
}

/**
 * 「Plan it for me」 — streamed (`stream.ts`): the server says when it plans, checks and registers. A lost line sends the
 * same revision again; the server derives the request from it (`intake:{id}:plan:r{revision}`) and returns the trip it
 * already registered instead of planning twice.
 */
export function planIntake(intakeId: string, revision: number, input: IntakePlanInput, language: Language,
  onProgress?: (progress: OpProgress) => void): Promise<{ status: "confirmed"; trip: { trip_id: string } }> {
  return streamApi(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/plan`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, ...input }),
  }, onProgress);
}

/**
 * `[2026-10-06]` Save the answers to the questions asked while the server reads: `{question id: option id}`, one question at a time as the customer answers. The server keeps the LAST value of a
 * question (answering again corrects it) and refuses a whole request with `422 invalid_answers` when one id or option is unknown. A registered intake answers `409 intake_confirmed`.
 */
export function submitSurveyAnswers(intakeId: string, answers: Record<string, string | { custom: string } | null>, language: Language): Promise<{ ok: true; answered: string[]; questions_version: string }> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/survey`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }),
  });
}

/**
 * `[2026-10-13 사용자 결정]` 「일정 수정」: the registered trip as a plan-check intake (`POST /v1/web/trips/{id}/reopen`, `wiki/external/rest-endpoints.md` 「등록한 여행 고치기」). Its changes go
 * through the intake's own calls; `confirmIntake` on it writes the trip's next version. `version` is the trip version on screen — another one is refused (409 `stale_itinerary`).
 * The same trip and version opened again answer the same intake, with what was changed in it.
 */
export function reopenTrip(tripId: string, version: number, language: Language): Promise<ReviewedIntakeView> {
  return api(`/v1/web/trips/${encodeURIComponent(tripId)}/reopen`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ version }),
  });
}

/** `[2026-10-13 사용자 지시]` 「취소」 of an edit (`reopenTrip`): the intake is closed — nothing is written to the trip, and the next 「일정 수정」 starts afresh. */
export function cancelTripEdit(intakeId: string, language: Language): Promise<{ intake_id: string; status: "closed" }> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/cancel`, language, { method: "POST" });
}

/** On an edit of a registered trip (`reopen`) it answers the trip's `version` after it and whether a new one was written (`changed: false` = nothing was different). */
export function confirmIntake(intakeId: string, revision: number, language: Language, survey?: TripSurvey): Promise<{ status: "confirmed"; trip: { trip_id: string }; version?: number; changed?: boolean }> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/confirm`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, ...(survey && { survey }) }),
  });
}
