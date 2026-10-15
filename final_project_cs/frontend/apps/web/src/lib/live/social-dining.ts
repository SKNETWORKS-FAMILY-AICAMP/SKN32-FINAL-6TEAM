import type { Language } from "../i18n";
import type { ReviewedIntakeView } from "./intake-review";
import type { OpProgress } from "./stream";
import { streamApi } from "./stream";
import { api } from "./client";
import type { IntakePlanInput } from "./intake";

export type DiningPriority = "must" | "if_fits";
export interface DiningLinkEntry { url: string; note?: string; priority?: DiningPriority }
/** A quote the server verified against the text it actually read (post metadata or the customer's note). */
export interface DiningEvidence { source: string; quote: string; source_url?: string | null; checked_at?: string | null }
/** The model may return one menu as text or several as a list; the server keeps its shape. */
export interface DiningRestaurant { name: string; area?: string | null; branch?: string | null; menu?: string | string[] | null; evidence?: DiningEvidence[] }
export interface DiningChoice { ref: string; name: string; address?: string | null; latitude?: number | null; longitude?: number | null; source?: string; kind?: string; status?: string; reason?: string; checks?: { text?: string; result?: string }[] }
export interface DiningLink { key: string; source_urls: string[]; platform: string; status: string; reason: string | null; restaurants: DiningRestaurant[]; priority: DiningPriority; checked_at: string | null; choices?: DiningChoice[]; restaurant_index?: number; selected_ref?: string | null; placement_status?: "waiting" | "applied" | "unplaced"; placement_reason?: string | null }
export interface DiningLinksView { revision: number; links: DiningLink[] }
export interface DiningLinkPatch { priority?: DiningPriority; restaurant_index?: number; selected_ref?: string; name?: string; area?: string }
export interface DiningPreview extends DiningLinksView {
  proposal_id: string;
  changes: { key: string; item_id: string; from: { name?: string | null } | null; to: { name: string; ref?: string; address?: string | null }; reason: string }[];
  unplaced: { key: string; name?: string; priority?: DiningPriority; reason: string; message?: string }[];
  planning?: {
    mode: "model" | "rules" | "partial"; reason?: string | null; messages: string[];
    omissions: { key: string; reason: "missing_ranking" | "missing_slots"; slot_ids?: string[] }[];
    prompt_version?: string | null; prompt_hash?: string | null;
  };
}
export interface SocialDiningApi {
  list(intakeId: string, language: Language): Promise<DiningLinksView>;
  resolve(intakeId: string, entries: DiningLinkEntry[], language: Language, progress?: (next: OpProgress) => void): Promise<DiningLinksView>;
  update(intakeId: string, key: string, patch: DiningLinkPatch, language: Language): Promise<DiningLinksView>;
  preview(intakeId: string, revision: number, language: Language, targetItemId?: string, progress?: (next: OpProgress) => void): Promise<DiningPreview>;
  apply(intakeId: string, revision: number, proposalId: string, language: Language, progress?: (next: OpProgress) => void): Promise<ReviewedIntakeView>;
}
const base = (id: string) => `/v1/web/trip-intakes/${encodeURIComponent(id)}/dining-links`;
const json = (body: unknown, method = "POST"): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const listDiningLinks: SocialDiningApi["list"] = (id, language) => api(base(id), language);
export const resolveDiningLinks: SocialDiningApi["resolve"] = (id, links, language, progress) => streamApi(base(id), language, json({ links }), progress);
// The method is written out (not passed to `json`) so the web ↔ server contract check reads it as PATCH.
export const updateDiningLink: SocialDiningApi["update"] = (id, key, patch, language) => api(`${base(id)}/${encodeURIComponent(key)}`, language,
  { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
export const previewDiningLinks: SocialDiningApi["preview"] = (id, revision, language, targetItemId, progress) => streamApi(`${base(id)}/preview`, language,
  json({ revision, ...(targetItemId ? { target_item_id: targetItemId } : {}) }), progress);
/** `[2026-10-15]` Applying re-checks the whole itinerary and can pass a minute — streamed like the preview so the usual answer limit does not cut it off after the server saved. */
export const applyDiningLinks: SocialDiningApi["apply"] = (id, revision, proposalId, language, progress) => streamApi(`${base(id)}/apply`, language, json({ revision, proposal_id: proposalId }), progress);
/** Generate into the wishlist's existing intake; registering still requires the normal explicit confirmation. */
export function createDiningDraft(id: string, revision: number, input: Omit<IntakePlanInput, "keep_read_items">, language: Language, progress?: (next: OpProgress) => void): Promise<ReviewedIntakeView> {
  return streamApi(`/v1/web/trip-intakes/${encodeURIComponent(id)}/plan`, language, json({ revision, ...input, keep_read_items: true, review_only: true }), progress);
}
export const socialDiningApi: SocialDiningApi = { list: listDiningLinks, resolve: resolveDiningLinks, update: updateDiningLink, preview: previewDiningLinks, apply: applyDiningLinks };
