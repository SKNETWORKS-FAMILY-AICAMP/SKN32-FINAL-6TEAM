import type { TripSurvey } from "@/features/onboarding/payload";
import type { Language } from "../i18n";
import { api } from "./client";
import { streamApi, type OpProgress } from "./stream";

/** One value the server read, with how it was read and the evidence behind it (server `intake_claims`). */
export interface IntakeField {
  value: unknown;
  /** rule · llm_span (the model pointed at a span of the original) · lookup (place search) · customer */
  method: "rule" | "llm_span" | "lookup" | "customer";
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
}

export interface IntakeView {
  intake_id: string;
  status: "reading" | "review" | "confirmed" | "fatal";
  stage: string;
  stage_label: string;
  revision: number;
  fatal: { code: string; detail: string } | null;
  trip_id: string | null;
  sources: IntakeSource[];
  check: { ready: boolean; problems: IntakeProblem[]; filled: IntakeFilled[]; items: number; title: string; plan: IntakePlanBasis } | null;
  needs_review: { field: string; note: string | null }[];
}

/** 「일정 짜 줘」 기본값 — 읽은 값에서만 나온다. 모르면 null(화면이 묻는다). */
export interface IntakePlanBasis { requested: boolean; start_date: string | null; days: number | null; party_size: number | null; preferences: string }
/** `survey` rides along only when the customer finished the onboarding questions (server `TripSurvey`, optional). */
export interface IntakePlanInput { start_date: string; days: number; party_size: number; keep_read_items: boolean; survey?: TripSurvey }

export interface IntakeEdit { source_id?: string | null; field: string; value: unknown }

/** `humanToken` — the Turnstile token when the human check is on; the server checks it with Cloudflare. */
export async function submitIntake(text: string, files: File[], language: Language, humanToken?: string | null): Promise<{ intake_id: string }> {
  const form = new FormData();
  form.append("text", text);
  for (const file of files) form.append("files", file, file.name);
  if (humanToken) form.append("turnstile_token", humanToken);
  return api("/v1/web/trip-intakes", language, { method: "POST", body: form });
}

export function getIntake(intakeId: string, language: Language): Promise<IntakeView> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}`, language);
}

export function editIntake(intakeId: string, revision: number, edits: IntakeEdit[], language: Language): Promise<IntakeView> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/edits`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, edits }),
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

export function confirmIntake(intakeId: string, revision: number, language: Language, survey?: TripSurvey): Promise<{ status: "confirmed"; trip: { trip_id: string } }> {
  return api(`/v1/web/trip-intakes/${encodeURIComponent(intakeId)}/confirm`, language, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision, ...(survey && { survey }) }),
  });
}
