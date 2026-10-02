import type { IntakeEdit, IntakeItem, IntakeProblem, IntakeSource, IntakeView } from "@/lib/live/intake";
import { hasValidCoordinates } from "@/features/map/map-points";
import type { Coordinates, MapPoint } from "@/features/map/model";

export interface ReviewRow {
  source: IntakeSource;
  item: IntakeItem;
  key: string;
  problems: IntakeProblem[];
  filledStart?: string;
  filledEnd?: string;
}
export interface Draft { title: string; date: string; start: string; end: string; place: string; noPlace: boolean }
export type ReviewStatus = "ready" | "edited" | "review";

export function rows(view: IntakeView): ReviewRow[] {
  return view.sources.flatMap((source) => source.items.filter((item) => item.fields.removed?.value !== true).map((item) => {
    const prefix = `items[${item.index}].`;
    const filled = (name: string) => view.check?.filled.find((entry) => entry.source_id === source.source_id && entry.field === prefix + name)?.value;
    return { source, item, key: `${source.source_id}:${item.index}`,
      problems: view.check?.problems.filter((problem) => problem.source_id === source.source_id && problem.field.startsWith(prefix)) ?? [],
      filledStart: filled("starts_at"), filledEnd: filled("ends_at") };
  })).sort((a, b) => (draftOf(a).date || "9999").localeCompare(draftOf(b).date || "9999") || draftOf(a).start.localeCompare(draftOf(b).start));
}

/** Only fields actually supplied by the intake API. Missing metadata stays missing. */
export function placeOf(row: ReviewRow): { name: string; coordinates?: Coordinates } | null {
  const value = row.item.fields.place?.value;
  if (!value || typeof value !== "object") return null;
  const place = value as Record<string, unknown>;
  const point = { lat: place.latitude as number, lng: place.longitude as number };
  return { name: typeof place.name === "string" ? place.name : "", ...(hasValidCoordinates(point) && { coordinates: point }) };
}

export function draftOf(row: ReviewRow): Draft {
  const fields = row.item.fields;
  return { title: String(fields.title?.value ?? ""), date: String(fields.date?.value ?? row.item.date ?? ""),
    start: String(fields.starts_at?.value ?? row.filledStart ?? ""), end: String(fields.ends_at?.value ?? row.filledEnd ?? ""),
    place: placeOf(row)?.name ?? "", noPlace: fields.place?.method === "customer" && fields.place.value === null };
}

/** These are registration/readback states, not invented feasibility or optimization verdicts. */
export function statusOf(row: ReviewRow): ReviewStatus {
  if (row.problems.length) return "review";
  if (Object.values(row.item.fields).some((field) => field?.needs_review && field.method !== "customer"
    && !["year_filled", "day_offset"].includes(String(field.evidence.how)))) return "review";
  return Object.values(row.item.fields).some((field) => field?.method === "customer") ? "edited" : "ready";
}

export function editsFor(row: ReviewRow, draft: Draft): IntakeEdit[] {
  const base = draftOf(row);
  const edits: IntakeEdit[] = [];
  const add = (name: string, value: unknown) => edits.push({ source_id: row.source.source_id, field: `items[${row.item.index}].${name}`, value });
  for (const [key, name] of [["title", "title"], ["date", "date"], ["start", "starts_at"], ["end", "ends_at"]] as const) {
    if (draft[key].trim() !== base[key]) add(name, draft[key].trim());
  }
  if (draft.noPlace !== base.noPlace || (!draft.noPlace && draft.place.trim() !== base.place)) add("place", draft.noPlace ? { none: true } : { name: draft.place.trim() });
  return edits;
}

export function invalidDraft(draft: Draft): "title" | "date" | "time" | "order" | "place" | null {
  if (!draft.title.trim() || draft.title.trim().length > 80) return "title";
  // Leave existing missing values to the server's check, but reject invalid entered values.
  if (draft.date && (!/^\d{4}-\d{2}-\d{2}$/.test(draft.date) || !Number.isFinite(Date.parse(draft.date)))) return "date";
  if ([draft.start, draft.end].some((time) => time && !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) return "time";
  if (draft.start && draft.end && draft.end <= draft.start) return "order";
  if (!draft.noPlace && draft.place.trim().length > 80) return "place";
  return null;
}

export function overlaps(row: ReviewRow, draft: Draft, all: ReviewRow[]): ReviewRow[] {
  if (!draft.date || !draft.start || !draft.end || draft.end <= draft.start) return [];
  return all.filter((other) => {
    const value = draftOf(other);
    return other.key !== row.key && value.date === draft.date && value.start && value.end
      && value.start < draft.end && value.end > draft.start;
  });
}

export function mapPoints(all: ReviewRow[]): MapPoint[] {
  return all.flatMap((row, index) => {
    const place = placeOf(row), draft = draftOf(row);
    return place?.coordinates ? [{ id: row.key, title: place.name || draft.title, date: draft.date, time: draft.start,
      endTime: draft.end, order: index + 1, coordinates: place.coordinates }] : [];
  });
}
