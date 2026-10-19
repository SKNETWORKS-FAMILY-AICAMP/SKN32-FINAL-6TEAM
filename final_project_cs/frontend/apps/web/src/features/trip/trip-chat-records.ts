import type { Notice, Proposal } from "@/lib/live/extras";
import type { TripMessage } from "./model";

export type ChatRecord = { kind: "message"; id: string; at: string; message: TripMessage; index: number }
  | { kind: "notice"; id: string; at: string; notice: Notice };

/** The original message index keeps old chat choices closed when notices arrive. */
export function chatRecords(messages: readonly TripMessage[], notices: readonly Notice[]): ChatRecord[] {
  const records: ChatRecord[] = messages.map((message, index) => ({ kind: "message", id: `message:${message.id}`, at: message.createdAt, message, index }));
  const seen = new Set<string>();
  for (const notice of notices) {
    if (seen.has(notice.key)) continue;
    seen.add(notice.key);
    records.push({ kind: "notice", id: `notice:${notice.key}`, at: notice.at, notice });
  }
  return records.sort((left, right) => {
    const a = Date.parse(left.at), b = Date.parse(right.at);
    return Number.isFinite(a) && Number.isFinite(b) ? a - b : 0;
  });
}

/** A visible proposal still needs the API's ownership, stale-version and expiry checks. */
export function proposalAvailable(proposal: Proposal, version: number | undefined, now = Date.now()): boolean {
  if (proposal.status !== "open" || version === undefined || proposal.baseVersion !== version) return false;
  if (!proposal.expiresAt) return true;
  const expiry = Date.parse(proposal.expiresAt);
  return Number.isFinite(expiry) && expiry > now;
}
