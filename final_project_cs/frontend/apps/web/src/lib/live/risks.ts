import type { Language } from "../i18n";
import { api, LiveError } from "./client";

export type RiskStatus = "problem" | "clear" | "unknown";
export interface RiskProblem {
  category: string; label: string; summary: string | null; message: string | null; source: string | null;
  confirmedAt: string | null; startsAt: string | null; endsAt: string | null; incidentId: string | null;
  asOfNow: boolean;
}
export interface RiskCategory { category: string; label: string; status: string; source: string | null; confirmedAt: string | null }
export interface ItemRisk {
  itemId: string; title: string; status: RiskStatus; problems: RiskProblem[];
  categories: RiskCategory[]; unknownCategories: string[]; reason: string | null;
  checkedAt: string | null; checkedFor: string | null; mode: "fresh" | "cached" | null;
  dataConfirmedAt: string | null; stale: boolean;
}
export interface TripRisks {
  tripId: string; version: number | null; at: string | null; mode: string | null; items: ItemRisk[];
  horizonHours?: number | null;
  skipped?: { title: string; reason: string; note: string | null }[];
}

const object = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
const text = (value: unknown): string | null => typeof value === "string" && value.trim() ? value : null;
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : [];

/** Keep the provider facts; absent or unrecognised results are never marked clear. */
export function itemRiskOf(value: unknown): ItemRisk | null {
  const row = object(value);
  if (!row) return null;
  const status = row.status === "problem" || row.status === "clear" ? row.status : "unknown";
  return {
    itemId: text(row.item_id) ?? "", title: text(row.title) ?? "", status,
    problems: list(row.problems).flatMap((entry): RiskProblem[] => {
      const problem = object(entry);
      return problem ? [{ category: text(problem.category) ?? "", label: text(problem.label) ?? "",
        summary: text(problem.summary), message: text(problem.message) ?? text(problem.text) ?? text(problem.kind),
        source: text(problem.source), confirmedAt: text(problem.confirmed_at), startsAt: text(problem.starts_at),
        endsAt: text(problem.ends_at), incidentId: text(problem.incident_id), asOfNow: problem.as_of_now === true }] : [];
    }),
    categories: list(row.categories).flatMap((entry): RiskCategory[] => {
      const category = object(entry);
      return category ? [{ category: text(category.category) ?? "", label: text(category.label) ?? "",
        status: text(category.status) ?? "unknown", source: text(category.source), confirmedAt: text(category.confirmed_at) }] : [];
    }),
    unknownCategories: list(row.unknown_categories).flatMap((entry) => {
      const category = object(entry);
      const label = category && (text(category.label) ?? text(category.category));
      return label ? [label] : [];
    }),
    reason: text(row.reason), checkedAt: text(row.checked_at), checkedFor: text(row.checked_for),
    dataConfirmedAt: text(row.data_confirmed_at) ?? text(row.oldest_confirmed_at), stale: row.stale === true,
    mode: row.mode === "fresh" || row.mode === "cached" ? row.mode : null,
  };
}

export function tripRisksOf(value: unknown): TripRisks {
  const body = object(value);
  if (!body || !Array.isArray(body.items)) throw new LiveError("risk_result_unavailable", "위험 확인 결과를 읽지 못했어요. 다시 확인해 주세요.");
  const items = body.items.map(itemRiskOf);
  if (items.some((item) => !item?.itemId)) throw new LiveError("risk_result_unavailable", "위험 확인 결과 일부를 읽지 못했어요. 다시 확인해 주세요.");
  return { tripId: text(body.trip_id) ?? "", version: typeof body.version === "number" ? body.version : null,
    at: text(body.at), mode: text(body.mode), items: items as ItemRisk[],
    horizonHours: typeof body.horizon_hours === "number" ? body.horizon_hours : null,
    skipped: list(body.skipped).flatMap((entry) => {
      const skipped = object(entry);
      return skipped ? [{ title: text(skipped.title) ?? "", reason: text(skipped.reason) ?? "unknown", note: text(skipped.note) }] : [];
    }) };
}

export async function getTripRisks(tripId: string, language: Language, fresh = false): Promise<TripRisks> {
  return tripRisksOf(await api<unknown>(`/v1/web/trips/${encodeURIComponent(tripId)}/risks?fresh=${fresh ? "true" : "false"}`, language));
}

export interface RiskAlternatives {
  status: "offered" | "already" | "no_alternate" | "unavailable" | "no_risk" | "stale" | "ended";
  proposalId: string | null;
  reason: string | null;
  message: string | null;
  failedCategories: string[];
}

/** A proposal is created only by this explicit, CSRF-protected action; this never applies it. */
export async function requestRiskAlternatives(tripId: string, itemId: string, language: Language): Promise<RiskAlternatives> {
  const body = object(await api<unknown>(`/v1/web/trips/${encodeURIComponent(tripId)}/risks/${encodeURIComponent(itemId)}/alternatives`, language,
    { method: "POST", body: JSON.stringify({}) }));
  const status = body?.status;
  const proposalId = text(body?.proposal_id);
  const details = { reason: text(body?.reason), message: text(body?.message),
    failedCategories: list(body?.failed_categories).filter((value): value is string => typeof value === "string" && Boolean(value.trim())) };
  if ((status === "offered" || status === "already") && proposalId) return { status, proposalId, ...details };
  return { status: status === "no_alternate" || status === "no_risk" || status === "stale" || status === "ended" ? status : "unavailable",
    proposalId: null, ...details };
}

export const problemText = (problem: RiskProblem): string => problem.message ?? problem.summary ?? problem.label;

/** Observation timestamps never turn an unchanged incident into another alert. */
export function riskSignature(items: readonly ItemRisk[]): string {
  return items.filter((item) => item.status === "problem").flatMap((item) => item.problems.map((problem) =>
    `${item.itemId}:${problem.category}:${problem.incidentId ?? problemText(problem)}`)).sort().join("\n");
}
