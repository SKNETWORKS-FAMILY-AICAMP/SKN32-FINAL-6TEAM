import { draftOf, placeOf, rows, statusOf, type ReviewRow } from "@/features/intake-review/model";
import type { IntakeItem, IntakeView } from "@/lib/live/intake";
import type { CheckRow, PlanCandidate, PlanCheckView, PlanItem, PlanLine, TripIssue, Verdict } from "./model";

/**
 * The reading part of the plan check, from the intake the server returns (`GET /v1/web/trip-intakes/{id}`).
 *
 * ★Only what the server says: the stage (received → reading), each line of every uploaded source and whether it was
 *   read, and the stop a read line turned into. There is no places-and-hours check stage on the server (PLAN_CHECK_SCREEN.md
 *   §4), so a finished intake still maps to the reading stage here; its result comes from `resultOf`.
 */
export function readingOf(intake: IntakeView): PlanCheckView {
  const lines: PlanLine[] = [];
  for (const source of intake.sources) {
    for (const line of source.lines) {
      const item = source.items.find((entry) => entry.line === line.no && entry.fields.removed?.value !== true);
      const title = item?.fields.title?.value;
      const startsAt = item?.fields.starts_at?.value;
      lines.push({
        // Numbered across sources: a photo's lines follow the typed text's.
        no: lines.length + 1, text: line.text, read: line.read,
        found: item && typeof title === "string" && title
          ? { kind: "item", day: item.day, startsAt: typeof startsAt === "string" && startsAt ? startsAt : null, title }
          : null,
      });
    }
  }
  return { stage: intake.stage === "received" ? "received" : "reading", title: null, days: [], lines, items: [], moves: [], dirty: false, rechecking: null };
}

/** A field the server flagged for a look — not one the customer set, nor a year or day it only assumed. */
const flagged = (row: ReviewRow, names: readonly string[]) => names.map((name) => row.item.fields[name as keyof IntakeItem["fields"]])
  .filter((field) => field?.needs_review && field.method !== "customer" && !["year_filled", "day_offset"].includes(String(field.evidence.how)));

/** What the server said about one stop's place and time. Nothing it did not say is added. */
function checksOf(row: ReviewRow, intake: IntakeView): CheckRow[] {
  const out: CheckRow[] = [];
  const problems = (names: readonly string[]) => row.problems.filter((problem) => names.some((name) => problem.field.endsWith(`.${name}`)));
  const place = placeOf(row);
  const placeProblems = problems(PLACE_FIELDS);
  const placeFlags = flagged(row, ["place"]);
  if (placeProblems.length) out.push({ kind: "place", result: "bad", text: placeProblems.map((problem) => problem.message).join(" · ") });
  else if (placeFlags.length) out.push({ kind: "place", result: "warn", text: placeFlags[0]?.note ?? "장소를 확인해 주세요" });
  else if (draftOf(row).noPlace) out.push({ kind: "place", result: "unknown", text: "장소 없이 두었어요" });
  else if (place?.name) out.push({ kind: "place", result: "ok", text: place.name });
  const timeProblems = problems(TIME_FIELDS);
  const timeFlags = flagged(row, TIME_FIELDS);
  const filled = intake.check?.filled.filter((entry) => entry.source_id === row.source.source_id && TIME_FIELDS.some((name) => entry.field === `items[${row.item.index}].${name}`)) ?? [];
  if (timeProblems.length) out.push({ kind: "time", result: "bad", text: timeProblems.map((problem) => problem.message).join(" · ") });
  else if (timeFlags.length) out.push({ kind: "time", result: "warn", text: timeFlags[0]?.note ?? "시각을 확인해 주세요" });
  else if (filled.length) out.push({ kind: "time", result: "filled", text: filled.map((entry) => entry.note).join(" · ") });
  return out;
}

const PLACE_FIELDS = ["place", "title", "kind"] as const;
const TIME_FIELDS = ["date", "starts_at", "ends_at"] as const;

/**
 * The plan check's result, from an intake the server has finished reading (`status` review or confirmed).
 *
 * ★Only what the server says. A card shows the place the server found (or why it could not), and what it flagged about
 *   the place or the time — `check.problems`, a field's `needs_review` note, a time it filled in (`check.filled`). Its
 *   verdict: something flagged → 확인 필요, a time filled in or a change of the customer's → 조정, otherwise 유지.
 *   Opening hours, closed days and the moves between places are not in the response, so none are shown
 *   (PLAN_CHECK_SCREEN.md §4). Nothing is locked (no such field yet), no place details or photos, no first alternative;
 *   the server checks the plan on every save, so it is never 「changed since the last check」.
 */
export function resultOf(intake: IntakeView): PlanCheckView {
  const list = rows(intake);
  // Days: the server's day number; a stop without one counts by its date's order.
  const dates = [...new Set(list.map((row) => draftOf(row).date))];
  const dayOf = (row: ReviewRow) => row.item.day ?? dates.indexOf(draftOf(row).date) + 1;
  const days = [...new Map(list.map((row) => [dayOf(row), draftOf(row).date])).entries()]
    .map(([day, date]) => ({ day, date })).sort((a, b) => a.day - b.day);
  const items: PlanItem[] = list.map((row) => {
    const draft = draftOf(row);
    const place = placeOf(row);
    const checks = checksOf(row, intake);
    // A stop the customer changed counts as adjusted, like one the server filled in; the server has checked it again.
    const status = statusOf(row);
    const verdict: Verdict = status === "review" ? "review" : status === "edited" || checks.some((check) => check.result === "filled") ? "adjusted" : "keep";
    return { id: row.key, day: dayOf(row), date: draft.date, startsAt: draft.start, endsAt: draft.end, title: draft.title || place?.name || "",
      place: draft.place, noPlace: draft.noPlace, coordinates: place?.coordinates ?? null, checks, verdict, locked: false, info: null, suggestion: null };
  });
  return { stage: "done", title: intake.check?.title ?? null, days, lines: readingOf(intake).lines.map((line) => ({ ...line })), items, moves: [], dirty: false, rechecking: null };
}

/**
 * The other places the server weighed for one stop — when a name fitted several (「올리브영」), it picks the one nearest
 * the stops around it and keeps the names it chose among (`evidence.chosen_from`). Names only: no distance, details or
 * checks yet; choosing one sends its name and the server looks it up again.
 */
export function candidatesOf(intake: IntakeView, id: string): PlanCandidate[] {
  const row = rows(intake).find((entry) => entry.key === id);
  if (!row) return [];
  const current = placeOf(row)?.name;
  const names = row.item.fields.place?.evidence.chosen_from;
  return (Array.isArray(names) ? names : []).filter((name): name is string => typeof name === "string" && name !== current)
    .map((name, index) => ({ id: `${id}:${name}`, name, source: "candidate", rank: index + 1, distance: null, coordinates: null, info: null, checks: [] }));
}

/** The trip-wide problems (not one stop's): the first day and the party size can be answered on the screen. */
export function tripIssuesOf(intake: IntakeView): TripIssue[] {
  return (intake.check?.problems ?? []).filter((problem) => !problem.field.startsWith("items[")).map((problem) => ({
    field: problem.code === "no_date" ? "first_day" : problem.code === "party_size_out_of_range" ? "party_size" : null,
    message: problem.message,
  }));
}
