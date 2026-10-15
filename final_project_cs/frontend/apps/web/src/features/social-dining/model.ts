import { translator, type Language } from "@/lib/i18n";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import type { DiningLinkEntry, DiningLinkPatch, DiningLinksView, DiningPreview, SocialDiningApi } from "@/lib/live/social-dining";
import { socialDiningApi } from "@/lib/live/social-dining";
import type { OpProgress } from "@/lib/live/stream";
import type { PlanItem } from "@/features/plan-check/model";

export function diningMeals(items: PlanItem[]): { id: string; label: string }[] {
  return items.filter((item) => item.kind === "dining" && !item.locked && !item.past && !item.booked)
    .map((item) => ({ id: item.id, label: [item.date, item.startsAt, item.title].filter(Boolean).join(" · ") }));
}

export function safeSourceUrl(raw: string): string | null {
  try { const url = new URL(raw); return url.protocol === "https:" && !url.username && !url.password ? url.href : null; }
  catch { return null; }
}
/** One URL per line; preserve input order and let the server report unsupported links individually. */
export function linkEntries(text: string, note = ""): DiningLinkEntry[] {
  const urls = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!urls.length || urls.some((url) => !safeSourceUrl(url))) throw new Error("invalid_links");
  return urls.map((url) => ({ url, ...(note.trim() ? { note: note.trim() } : {}), priority: "if_fits" }));
}

export interface DiningState {
  links: DiningLinksView["links"]; proposal: DiningPreview | null; error: string | null;
  pending: "load" | "resolve" | "update" | "preview" | "apply" | null; progress: OpProgress | null; applied: boolean;
}
export interface DiningContext { intakeId: string; revision: number; onApplied: (view: ReviewedIntakeView) => void; onRefresh: () => void }

/** A link intake and an itinerary proposal are separate; only explicit apply publishes a new intake view. */
export class SocialDiningController {
  private state: DiningState = { links: [], proposal: null, error: null, pending: null, progress: null, applied: false };
  private listeners = new Set<() => void>();
  private active = true;
  constructor(private intakeId: string, private revision: number, private language: Language,
    private hooks: { applied: (view: ReviewedIntakeView) => void; refresh: () => void }, private api: SocialDiningApi = socialDiningApi) {}
  snapshot = (): DiningState => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  activate() { this.active = true; }
  dispose() { this.active = false; }
  setHooks(hooks: { applied: (view: ReviewedIntakeView) => void; refresh: () => void }) { this.hooks = hooks; }
  private patch(next: Partial<DiningState>) { if (!this.active) return; this.state = { ...this.state, ...next }; this.listeners.forEach((listener) => listener()); }
  setRevision(revision: number) {
    if (this.revision === revision) return;
    this.revision = revision;
    const t = translator(this.language);
    this.patch({ proposal: null, ...(this.state.proposal || this.state.pending === "preview" ? { error: t("일정이 바뀌었어요. 반영안을 다시 확인해 주세요.", "The itinerary changed. Preview the meal changes again.") } : {}) });
  }
  clearProposal() { this.patch({ proposal: null }); }
  private progress = (progress: OpProgress) => this.patch({ progress });
  private async run(kind: NonNullable<DiningState["pending"]>, work: () => Promise<boolean>): Promise<boolean> {
    if (!this.active || this.state.pending) return false;
    this.patch({ pending: kind, error: null, progress: null, applied: false });
    try { return await work(); }
    catch (error) {
      if (!this.active) return false;
      const code = (error as { code?: string } | null)?.code;
      if (["stale_revision", "stale_itinerary", "stale_proposal", "proposal_stale"].includes(code ?? "")) { this.patch({ proposal: null }); this.hooks.refresh(); }
      const t = translator(this.language);
      this.patch({ error: error instanceof Error ? error.message : t("요청을 처리하지 못했어요. 다시 시도해 주세요.", "The request failed. Please try again.") });
      return false;
    } finally { this.patch({ pending: null, progress: null }); }
  }
  load() { return this.run("load", async () => { const view = await this.api.list(this.intakeId, this.language); this.patch({ links: view.links }); return true; }); }
  resolve(entries: DiningLinkEntry[]) { return this.run("resolve", async () => {
    this.patch({ proposal: null });
    const view = await this.api.resolve(this.intakeId, entries, this.language, this.progress);
    this.patch({ links: view.links }); return this.active;
  }); }
  update(key: string, patch: DiningLinkPatch) { return this.run("update", async () => {
    this.patch({ proposal: null });
    const view = await this.api.update(this.intakeId, key, patch, this.language);
    this.patch({ links: view.links }); return this.active;
  }); }
  preview(target?: string) { return this.run("preview", async () => {
    const revision = this.revision;
    this.patch({ proposal: null });
    const view = await this.api.preview(this.intakeId, revision, this.language, target, this.progress);
    if (!this.active) return false;
    if (revision !== this.revision || view.revision !== revision) {
      const t = translator(this.language);
      this.patch({ error: t("일정이 바뀌었어요. 반영안을 다시 확인해 주세요.", "The itinerary changed. Preview the meal changes again.") });
      if (view.revision !== this.revision) this.hooks.refresh();
      return false;
    }
    this.patch({ links: view.links, proposal: view }); return true;
  }); }
  async apply(): Promise<boolean> {
    const proposal = this.state.proposal;
    if (!proposal || proposal.revision !== this.revision || !proposal.changes.length) return false;
    return this.run("apply", async () => {
      const next = await this.api.apply(this.intakeId, proposal.revision, proposal.proposal_id, this.language, this.progress);
      if (!this.active) return false;
      if (next.intake_id !== this.intakeId || next.revision < this.revision) { this.patch({ proposal: null }); this.hooks.refresh(); return false; }
      this.revision = next.revision;
      this.patch({ proposal: null, applied: true, links: this.state.links.map((link) => proposal.changes.some((change) => change.key === link.key) ? { ...link, placement_status: "applied", placement_reason: null } : link) });
      this.hooks.applied(next); return true;
    });
  }
}
