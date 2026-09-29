import type { Notice, Proposal } from "@/lib/live/extras";
import type { TripStop } from "./model";

/** A choice the server is waiting for, with the server's own sentence about it when a notice carries one. */
export interface OpenChoice {
  proposal: Proposal;
  /** The stop this is about, when it is still on the trip. */
  stop: TripStop | null;
  /** The notice text the server sent for this proposal. `null` when none was found — the screen then says so, it does not write one. */
  text: string | null;
}

/** How many notices the panel lists before it says how many it left out. */
export const NOTICE_LIMIT = 10;

export function openChoices(proposals: Proposal[], notices: Notice[], stops: TripStop[]): OpenChoice[] {
  return proposals
    .filter((proposal) => proposal.status === "open")
    .map((proposal) => ({
      proposal,
      stop: stops.find((stop) => stop.id === proposal.itemId) ?? null,
      text: notices.find((notice) => notice.proposalId === proposal.id && notice.text)?.text ?? null,
    }));
}

/** Newest first, cut at the limit — and how many were left out, so the cut is never silent. */
export function recentNotices(notices: Notice[], limit = NOTICE_LIMIT): { shown: Notice[]; total: number; hidden: number } {
  const shown = [...notices].sort((a, b) => Date.parse(b.at) - Date.parse(a.at)).slice(0, limit);
  return { shown, total: notices.length, hidden: notices.length - shown.length };
}

/**
 * The automatic change the customer can undo right now: the newest change notice that carries an undo and made the
 * version the trip is on. An older one would be refused (409) — the plan has moved on — so it is not offered.
 */
export function undoableChange(notices: Notice[], version: number | undefined): Notice | null {
  if (version === undefined) return null;
  return [...notices].filter((notice) => notice.rollback && notice.rollback.baseVersion === version)
    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0] ?? null;
}
