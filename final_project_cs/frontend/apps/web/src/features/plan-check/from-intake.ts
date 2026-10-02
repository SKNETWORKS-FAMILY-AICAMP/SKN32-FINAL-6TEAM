import type { IntakeView } from "@/lib/live/intake";
import type { PlanCheckView, PlanLine } from "./model";

/**
 * The reading part of the plan check, from the intake the server returns (`GET /v1/web/trip-intakes/{id}`).
 *
 * ★Only what the server says: the stage (received → reading), each line of every uploaded source and whether it was
 *   read, and the stop a read line turned into. The places-and-hours check and its result are not mapped: the server has
 *   no such stage, no per-place checks and no moves yet (PLAN_CHECK_SCREEN.md §4). Once reading ends the intake review
 *   screen takes over, so a finished intake still maps to the reading stage here.
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
  return { stage: intake.stage === "received" ? "received" : "reading", title: null, days: [], lines, items: [], moves: [] };
}
