import type { ReviewedIntakeView } from "@/lib/live/intake-review";

function itemValues(view: ReviewedIntakeView, sourceId: string, index: number, detailsOnly = false): string {
  const fields = view.sources.find(source => source.source_id === sourceId)?.items.find(item => item.index === index)?.fields;
  return JSON.stringify(Object.entries(fields ?? {}).filter(([key]) => !detailsOnly || !["starts_at", "ends_at"].includes(key))
    .map(([key, field]) => [key, field?.value]).sort(([a], [b]) => String(a).localeCompare(String(b))));
}

/** Values only: provenance and check results may change without changing the customer's plan. */
function valuesOf(view: ReviewedIntakeView): string {
  const sources = view.sources.map((source) => ({
    id: source.source_id,
    trip: Object.entries(source.trip).map(([key, field]) => [key, field.value]).sort(([a], [b]) => String(a).localeCompare(String(b))),
    items: source.items.filter((item) => item.fields.removed?.value !== true).map((item) => ({
      index: item.index,
      fields: Object.entries(item.fields).filter(([key]) => key !== "removed").map(([key, field]) => [key, field?.value])
        .sort(([a], [b]) => String(a).localeCompare(String(b))),
    })).sort((a, b) => a.index - b.index),
  })).sort((a, b) => a.id.localeCompare(b.id));
  return JSON.stringify(sources);
}

/** One intake's first successfully edited, completed revision. Never uses an animation or dry-run view as its original. */
export class ReviewUndo {
  private original: { revision: number; values: string } | null = null;
  private revision: number | null = null;
  private unavailable = false;
  private items = new Map<string, { revision: number; source_id: string; index: number; details: string }>();
  active = true;

  constructor(readonly intakeId: string) {}

  activate(): void { this.active = true; }
  deactivate(): void { this.active = false; }

  remember(before: ReviewedIntakeView, next: ReviewedIntakeView): void {
    if (!this.active || before.intake_id !== this.intakeId || next.intake_id !== this.intakeId || next.preview) return;
    if (!this.original && !this.unavailable) {
      if (before.status === "review" && !before.preview && before.review?.revision === before.revision) {
        this.original = { revision: before.revision, values: valuesOf(before) };
      } else this.unavailable = true;
    }
    if (before.status === "review" && !before.preview && before.review?.revision === before.revision) {
      for (const item of before.review.items ?? []) {
        if (!this.items.has(item.id) && itemValues(before, item.source_id, item.index) !== itemValues(next, item.source_id, item.index)) {
          this.items.set(item.id, { revision: before.revision, source_id: item.source_id, index: item.index, details: itemValues(before, item.source_id, item.index, true) });
        }
      }
    }
    this.advance(next);
  }

  advance(next: ReviewedIntakeView): void {
    if (this.active && next.intake_id === this.intakeId && !next.preview) this.revision = next.revision;
  }

  canRestore(view: ReviewedIntakeView | undefined): boolean {
    return !!(this.active && this.original && view && !view.preview && view.status === "review"
      && view.intake_id === this.intakeId && view.revision === this.revision && valuesOf(view) !== this.original.values);
  }

  target(view: ReviewedIntakeView): number | null {
    return this.canRestore(view) ? this.original!.revision : null;
  }

  itemTarget(view: ReviewedIntakeView | undefined, id: string): { revision: number; source_id: string; index: number } | null {
    const original = this.items.get(id);
    if (!this.active || !original || !view || view.intake_id !== this.intakeId || view.preview || view.status !== "review" || view.revision !== this.revision) return null;
    if (itemValues(view, original.source_id, original.index, true) === original.details) return null;
    return { revision: original.revision, source_id: original.source_id, index: original.index };
  }

  /** Called only after an atomic restore succeeded. A failed attempt leaves the original available. */
  restored(next: ReviewedIntakeView): void {
    this.advance(next);
  }
}
