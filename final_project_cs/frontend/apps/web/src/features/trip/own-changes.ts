import type { Notice } from "@/lib/live/extras";
import { ownNotice } from "./stop-progress";

/**
 * `[2026-10-22 사용자 결정 — ST4F-716 A · ST4F-723 g]` What this device did by itself: a 「끝났어요」 report, an option picked or an undo in the notice center, on a stop's detail or in the
 * chat. The notice it brings is not barred again — the place where the customer acted already said what came of it. Kept per trip for this page's life (another device, and the notice
 * center's lists, still show it):
 * - the version it wrote: the server writes the base version + 1 and its change notice can come in before the answer, so that version is held from the press and put right (or dropped)
 *   when the answer comes;
 * - 「예보에 맞게 일정 변경」 · 「다른 곳 찾아보기」: the proposal's options notice that answer brings (once) — the options stand where it was pressed.
 */
const held = new Map<string, Set<number>>();
const asked = new Map<string, Set<string>>();
const NONE: ReadonlySet<number> = new Set();

export const ownVersions = (tripId: string): ReadonlySet<number> => held.get(tripId) ?? NONE;

export function holdOwnVersion(tripId: string, version: number) {
  held.set(tripId, new Set([...(held.get(tripId) ?? []), version]));
}

export function dropOwnVersion(tripId: string, version: number) {
  const versions = new Set(held.get(tripId) ?? []);
  versions.delete(version);
  held.set(tripId, versions);
}

/** Runs a write that makes the next version (`base + 1`) and keeps that version as this device's — the one the server answers with, if it differs. */
export async function ownChange<T extends { version?: number }>(tripId: string, base: number | undefined, write: () => Promise<T>): Promise<T> {
  if (base === undefined) return write();
  const expected = base + 1;
  holdOwnVersion(tripId, expected);
  try {
    const result = await write();
    if (result.version !== expected) dropOwnVersion(tripId, expected);
    if (typeof result.version === "number") holdOwnVersion(tripId, result.version);
    return result;
  } catch (error) {
    dropOwnVersion(tripId, expected);
    throw error;
  }
}

/** An answer to a proposal: asking for its options (`consent`) holds that proposal's next notice; picking or keeping holds the version it writes. */
export async function ownAnswer<T extends { version?: number }>(tripId: string, base: number | undefined, answer: { proposalId: string; consent: boolean },
  write: () => Promise<T>): Promise<T> {
  if (!answer.consent) return ownChange(tripId, base, write);
  asked.set(tripId, new Set([...(asked.get(tripId) ?? []), answer.proposalId]));
  try {
    return await write();
  } catch (error) {
    asked.get(tripId)?.delete(answer.proposalId);
    throw error;
  }
}

/** Whether a notice that just came in is what this device's own press brought (its options notice is taken off the hold: a later one is barred as usual). */
export function ownTripNotice(tripId: string, notice: Pick<Notice, "type" | "version" | "proposalId">): boolean {
  if (ownNotice(notice, ownVersions(tripId))) return true;
  const proposals = asked.get(tripId);
  if (notice.type !== "proposal_request" || !notice.proposalId || !proposals?.has(notice.proposalId)) return false;
  proposals.delete(notice.proposalId);
  return true;
}
