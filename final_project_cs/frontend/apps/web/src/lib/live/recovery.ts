import type { Language } from "../i18n";
import { api, LiveError } from "./client";

/**
 * `[2026-10-06 사용자 결정 — 재난 뒤 다시 시작]` After the customer lifts a disaster pause (「일정 다시 시작」) the server builds a situation brief of that disaster: what is known (with its source), what it does NOT know,
 * what each remaining stop's status is (affected · unknown · unaffected - 「모르면 불명」), three ways to go on, and two questions. The screen only shows it and sends the customer's choice. ★Every sentence is the
 * server's, and an unknown is never drawn as 「no effect」; nothing here changes the plan (a choice only records, and 「영향받은 것만 바꾸기」 makes proposals the customer may take or leave).
 * Contract: `wiki/external/rest-endpoints.md` 「재난 뒤 다시 시작」.
 */
export type RecoveryChoice = "keep" | "replace_affected" | "replan_all";
export type ItemStatus = "affected" | "unknown" | "unaffected";
export type RecoveryAnswer = "yes" | "no" | "unknown";
export type RecoveryQuestionKey = "lodging" | "companions";

const CHOICES: readonly RecoveryChoice[] = ["keep", "replace_affected", "replan_all"];
const STATUSES: readonly ItemStatus[] = ["affected", "unknown", "unaffected"];
const ANSWERS: readonly RecoveryAnswer[] = ["yes", "no", "unknown"];
const QUESTION_KEYS: readonly RecoveryQuestionKey[] = ["lodging", "companions"];

export interface RecoveryItem {
  id: string;
  title: string;
  kind: string | null;
  startsAt: string | null;
  placeName: string | null;
  district: string | null;
  /** ★Anything but the three words the server uses reads as 「unknown」 - never as 「unaffected」. */
  status: ItemStatus;
  /** The server's one-line reason for the status. */
  reason: string | null;
}

export interface RecoveryOption { key: RecoveryChoice; label: string; detail: string | null; recommended: boolean }
export interface RecoveryQuestion { key: RecoveryQuestionKey; text: string; answers: RecoveryAnswer[] }
export interface RecoveryExtra { key: string; label: string; detail: string | null; byDefault: boolean }
export interface RecoveryChosen { choice: RecoveryChoice | null; lighterDay: boolean; answers: Partial<Record<RecoveryQuestionKey, RecoveryAnswer>> }

export interface Recovery {
  pauseId: string;
  /** `in_progress` (the trip has started) or `upcoming` (it has not): the server words the scope note differently. */
  phase: "in_progress" | "upcoming" | null;
  event: { label: string | null; category: string | null; at: string | null; officialText: string | null };
  /** What is known, each with its source. */
  facts: string[];
  /** What the server does not know. Shown beside the facts, never folded into them. */
  unknowns: string[];
  districts: string[];
  items: RecoveryItem[];
  counts: { affected: number; unknown: number; unaffected: number };
  options: RecoveryOption[];
  lighterDay: RecoveryExtra | null;
  questions: RecoveryQuestion[];
  /** What we do and do not do (a timetable only: no booking, postponing or cancelling) - shown as the server wrote it. */
  scopeNote: string | null;
  chosen: RecoveryChosen | null;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const str = (value: unknown): string | null => (typeof value === "string" && value.trim() ? value.trim() : null);
const strings = (value: unknown): string[] => (Array.isArray(value) ? value.flatMap((entry) => { const text = str(entry); return text ? [text] : []; }) : []);
const count = (value: unknown): number => (typeof value === "number" && Number.isFinite(value) && value > 0 ? Math.floor(value) : 0);

function answersOf(raw: unknown): RecoveryChosen["answers"] {
  const out: RecoveryChosen["answers"] = {};
  if (!isRecord(raw)) return out;
  for (const key of QUESTION_KEYS) { const value = raw[key]; if (typeof value === "string" && (ANSWERS as readonly string[]).includes(value)) out[key] = value as RecoveryAnswer; }
  return out;
}

/** A brief from the server (`GET …/safety/recovery`, or `recovery` of the resume answer); anything that is not one reads as none. */
export function recoveryOf(raw: unknown): Recovery | null {
  if (!isRecord(raw)) return null;
  const pauseId = str(raw.pause_id);
  if (!pauseId) return null;
  const event = isRecord(raw.event) ? raw.event : {};
  const counts = isRecord(raw.counts) ? raw.counts : {};
  const extras = Array.isArray(raw.extras) ? raw.extras : [];
  const lighter = extras.find((entry): entry is Record<string, unknown> => isRecord(entry) && entry.key === "lighter_day");
  const chosen = isRecord(raw.chosen) ? raw.chosen : null;
  return {
    pauseId,
    phase: raw.phase === "upcoming" || raw.phase === "in_progress" ? raw.phase : null,
    event: { label: str(event.label), category: str(event.category), at: str(event.at), officialText: str(event.official_text) },
    facts: strings(raw.facts),
    unknowns: strings(raw.unknowns),
    districts: strings(raw.affected_districts),
    items: (Array.isArray(raw.items) ? raw.items : []).flatMap((entry): RecoveryItem[] => {
      if (!isRecord(entry)) return [];
      const id = str(entry.item_id);
      const title = str(entry.title);
      if (!id || !title) return [];                                  // nothing true to show for a stop without a name
      const status = (STATUSES as readonly string[]).includes(String(entry.status)) ? entry.status as ItemStatus : "unknown";
      return [{ id, title, kind: str(entry.kind), startsAt: str(entry.starts_at), placeName: str(entry.place_name), district: str(entry.district), status, reason: str(entry.reason) }];
    }),
    counts: { affected: count(counts.affected), unknown: count(counts.unknown), unaffected: count(counts.unaffected) },
    options: (Array.isArray(raw.options) ? raw.options : []).flatMap((entry): RecoveryOption[] => {
      if (!isRecord(entry)) return [];
      const key = entry.key;
      const label = str(entry.label);
      // A way we do not know cannot be sent back, so it is not offered.
      return (CHOICES as readonly unknown[]).includes(key) && label ? [{ key: key as RecoveryChoice, label, detail: str(entry.detail), recommended: entry.recommended === true }] : [];
    }),
    lighterDay: lighter ? { key: "lighter_day", label: str(lighter.label) ?? "", detail: str(lighter.detail), byDefault: lighter.default === true } : null,
    questions: (Array.isArray(raw.questions) ? raw.questions : []).flatMap((entry): RecoveryQuestion[] => {
      if (!isRecord(entry)) return [];
      const key = entry.key;
      const text = str(entry.text);
      const answers = (Array.isArray(entry.answers) ? entry.answers : []).filter((answer): answer is RecoveryAnswer => typeof answer === "string" && (ANSWERS as readonly string[]).includes(answer));
      return (QUESTION_KEYS as readonly unknown[]).includes(key) && text && answers.length ? [{ key: key as RecoveryQuestionKey, text, answers }] : [];
    }),
    scopeNote: str(raw.scope_note),
    chosen: chosen ? { choice: (CHOICES as readonly unknown[]).includes(chosen.choice) ? chosen.choice as RecoveryChoice : null, lighterDay: chosen.lighter_day === true, answers: answersOf(chosen.answers) } : null,
  };
}

/** `GET /v1/web/trips/{id}/safety/recovery` → the brief, or null (no pause was lifted, or it was more than 72 hours ago). A server that does not have it yet (404) reads as none. */
export async function getRecovery(tripId: string, language: Language): Promise<Recovery | null> {
  try {
    const body = await api<{ recovery?: unknown }>(`/v1/web/trips/${encodeURIComponent(tripId)}/safety/recovery`, language);
    return recoveryOf(body.recovery);
  } catch (error) {
    if (error instanceof LiveError && (error.status === 404 || error.status === 405)) return null;
    throw error;
  }
}

/** What 「영향받은 것만 바꾸기」 made for one stop: a proposal the customer may take or leave (the plan is not changed), or nothing when no place fits. */
export interface RecoveryProposal { itemId: string; title: string; status: string | null; proposalId: string | null; options: string[] }
export interface RecoveryResult { recorded: boolean; choice: RecoveryChoice | null; lighterDay: boolean; proposals: RecoveryProposal[] }

/** The statuses of a proposal that has no place to offer (the stop stays as it is). */
export const NO_CANDIDATE_STATUSES: readonly string[] = ["no_alternate", "no_option_outside_area"];

/**
 * `POST /v1/web/trips/{id}/safety/recovery` → what was recorded. ★`recorded: false` means the choice could not be written down - the plan was not touched either way, and the screen says so
 * instead of going on quietly. A refusal (404 not resumed · 422 unknown choice) is a `LiveError`.
 */
export async function chooseRecovery(
  tripId: string, body: { pauseId: string; choice: RecoveryChoice; lighterDay: boolean; answers: Partial<Record<RecoveryQuestionKey, RecoveryAnswer>> }, language: Language,
): Promise<RecoveryResult> {
  const raw = await api<Record<string, unknown>>(`/v1/web/trips/${encodeURIComponent(tripId)}/safety/recovery`, language, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pause_id: body.pauseId, choice: body.choice, lighter_day: body.lighterDay, ...(Object.keys(body.answers).length ? { answers: body.answers } : {}) }),
  });
  return {
    recorded: raw.recorded === true,
    choice: (CHOICES as readonly unknown[]).includes(raw.choice) ? raw.choice as RecoveryChoice : null,
    lighterDay: raw.lighter_day === true,
    proposals: (Array.isArray(raw.proposals) ? raw.proposals : []).flatMap((entry): RecoveryProposal[] => {
      if (!isRecord(entry)) return [];
      const itemId = str(entry.item_id);
      return itemId ? [{ itemId, title: str(entry.title) ?? "", status: str(entry.status), proposalId: str(entry.proposal_id), options: strings(entry.options) }] : [];
    }),
  };
}
