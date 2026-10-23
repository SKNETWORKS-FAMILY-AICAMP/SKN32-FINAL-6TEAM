import type { PlanItem } from "./model";

/** Only the server can distinguish an uncertain last order from a known hours violation. */
export function canAcknowledgeHours(item: PlanItem): boolean {
  return Boolean(item.place && item.coordinates && !item.unfound && !item.rereads?.length && (item.placeState === "found" || item.placeState === "customer"))
    && item.checks.some((row) => row.kind === "place" && row.result === "ok")
    && item.checks.some((row) => row.kind === "hours" && row.result === "warn" && row.canAcknowledge === true)
    && !item.checks.some((row) => row.kind !== "arrival" && (row.result === "bad"
      || (row.result === "warn" && !(row.kind === "hours" && row.canAcknowledge === true))));
}

/** Local acknowledgement follows the actual inputs, never just an item id or a refreshed risk timestamp. */
export function hoursWarningKey(item: PlanItem): string {
  return JSON.stringify([item.id, item.title, item.place, item.placeState, item.date, item.startsAt, item.endsAt, item.coordinates,
    item.checks.filter((row) => row.kind !== "arrival")]);
}
