import type { Candidate, ReviewItem } from "@/lib/live/intake-review";
import type { IntakeEdit } from "@/lib/live/intake";
import { itemEdit } from "@/lib/live/intake-edits";
import type { PlanCandidate } from "./model";

type TimeProposal = NonNullable<PlanCandidate["proposedTime"]>;

function clock(value: string | null | undefined): string | null {
  if (!value) return null;
  if (/^([01]\d|2[0-3]):[0-5]\d$/.test(value)) return value;
  if (!/^\d{4}-\d{2}-\d{2}T/.test(value) || !/(Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  const at = new Date(value);
  return Number.isNaN(at.getTime()) ? null : new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hour12: false }).format(at);
}

/** Times are taken only from a server proposal; the client never invents a new start. */
export function proposedTimeOf(candidate: Pick<Candidate, "date" | "starts_at" | "ends_at">): TimeProposal | undefined {
  const date = candidate.date && /^\d{4}-\d{2}-\d{2}$/.test(candidate.date) ? candidate.date : null;
  const startsAt = clock(candidate.starts_at), endsAt = clock(candidate.ends_at);
  return startsAt ? { date, startsAt, endsAt } : undefined;
}

export function candidateTimeEdits(item: ReviewItem, proposal: TimeProposal | undefined): { edits: IntakeEdit[]; undo: IntakeEdit[] | null } {
  const edits: IntakeEdit[] = [], undo: IntakeEdit[] = [];
  let restorable = true;
  if (proposal) {
    if (proposal.date && proposal.date !== item.date) {
      edits.push(itemEdit.date(item, proposal.date));
      if (item.date) undo.push(itemEdit.date(item, item.date)); else restorable = false;
    }
    if (proposal.startsAt && proposal.startsAt !== item.starts_at) {
      edits.push(itemEdit.starts(item, proposal.startsAt));
      if (item.starts_at) undo.push(itemEdit.starts(item, item.starts_at)); else restorable = false;
    }
    if (proposal.endsAt && proposal.endsAt !== item.ends_at) {
      edits.push(itemEdit.ends(item, proposal.endsAt));
      if (item.ends_at) undo.push(itemEdit.ends(item, item.ends_at)); else restorable = false;
    }
  }
  return { edits, undo: restorable ? undo : null };
}
