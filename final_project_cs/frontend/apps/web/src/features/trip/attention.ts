import type { Notice, Proposal, ProposalOption } from "@/lib/live/extras";
import type { TripChange, TripStop } from "./model";

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

const newestFirst = (a: { at: string }, b: { at: string }) => Date.parse(b.at) - Date.parse(a.at);

/**
 * `[2026-10-22 ST4F-723 · 실서버 확인]` The sentence is the proposal's NEWEST notice with text: a forecast question is first sent as 「바꿀까요?」 and, once the customer asks for
 * options, again with the options — the first sentence (「…을 누르면 다른 곳을 찾아 보여 드려요」) stood over the options on the list card, the detail and the notice center.
 */
export function openChoices(proposals: Proposal[], notices: Notice[], stops: TripStop[]): OpenChoice[] {
  return proposals
    .filter((proposal) => proposal.status === "open")
    .map((proposal) => ({
      proposal,
      stop: stops.find((stop) => stop.id === proposal.itemId) ?? null,
      text: [...notices].sort(newestFirst).find((notice) => notice.proposalId === proposal.id && notice.text)?.text ?? null,
    }));
}

/** Newest first, cut at the limit — and how many were left out, so the cut is never silent. */
export function recentNotices(notices: Notice[], limit = NOTICE_LIMIT): { shown: Notice[]; total: number; hidden: number } {
  const shown = [...notices].sort(newestFirst).slice(0, limit);
  return { shown, total: notices.length, hidden: notices.length - shown.length };
}

/**
 * The automatic change the customer can undo right now: the newest change notice that carries an undo and made the
 * version the trip is on. An older one would be refused (409) — the plan has moved on — so it is not offered.
 */
export function undoableChange(notices: Notice[], version: number | undefined): Notice | null {
  if (version === undefined) return null;
  return [...notices].filter((notice) => notice.rollback && notice.rollback.baseVersion === version)
    .sort(newestFirst)[0] ?? null;
}

/**
 * `[2026-10-22 사용자 결정 — ST4F-723 구성 Ⓑ · 카드 ⓑ]` One entry of 「소식」: a notice on its own, or every notice of one proposal (asked · options · the change it made) as one card.
 * `at` is its newest notice.
 */
export type FeedEntry =
  | { kind: "notice"; notice: Notice; at: string }
  | { kind: "proposal"; proposalId: string; proposal: Proposal | null; notices: Notice[]; at: string }
  | { kind: "version"; change: TripChange; at: string };

/**
 * 「소식」, newest first. What waits for the customer stays in 「할 일」 until answered (`held` — the open choices and the undoable change), and a service notice sent to
 * the customer too (`kind: service_notice`) is shown under 「공지」 only, where the service's notices are. A version of the trip that no notice carries (the old 「변경 이력」 tab's
 * rows) is an entry of its own — the others are named on their notice's card.
 */
export function noticeFeed(notices: readonly Notice[], proposals: readonly Proposal[], held: { proposals: ReadonlySet<string>; notices: ReadonlySet<string> },
  history: readonly TripChange[] = []): FeedEntry[] {
  const groups = new Map<string, Notice[]>();
  const entries: FeedEntry[] = [];
  for (const notice of notices) {
    if (notice.kind === "service_notice" || held.notices.has(notice.key)) continue;
    if (notice.proposalId) {
      if (held.proposals.has(notice.proposalId)) continue;
      groups.set(notice.proposalId, [...(groups.get(notice.proposalId) ?? []), notice]);
      continue;
    }
    entries.push({ kind: "notice", notice, at: notice.at });
  }
  for (const [proposalId, list] of groups) {
    const ordered = [...list].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
    entries.push({ kind: "proposal", proposalId, proposal: proposals.find((proposal) => proposal.id === proposalId) ?? null, notices: ordered, at: ordered[ordered.length - 1].at });
  }
  const told = new Set(notices.map((notice) => notice.version));
  // A version's time is Seoul's wall clock (「2026-09-28 12:23」, gateway `history`) — made an instant to sort with the notices.
  for (const change of history) if (!told.has(change.version)) entries.push({ kind: "version", change, at: `${change.at.replace(" ", "T")}:00+09:00` });
  return entries.sort(newestFirst);
}

/** Which version's reason names a change notice (「처음 등록」 · 「자동으로 바꿈」 …): the trip's history row of the version it made. */
export const changeOf = (notice: Pick<Notice, "type" | "version">, history: readonly TripChange[]) =>
  notice.type === "change_notice" && notice.version !== null ? history.find((change) => change.version === notice.version) ?? null : null;

/**
 * `[2026-10-22 ST4F-723]` The registration notice (`trip_api` 「여행 일정이 준비되었습니다 — {제목}. 계획서: {url}」) without the plan's address, which the card shows as 「여행계획서 열기」 —
 * only when it is this trip's own plan address in that frame to the letter. `null`: leave the sentence as the server wrote it (its address stays a link).
 */
export function withoutPlanLink(text: string, planUrl: string | null | undefined): string | null {
  if (!planUrl) return null;
  const tail = ` 계획서: ${planUrl}`;
  return text.endsWith(tail) ? text.slice(0, -tail.length) : null;
}

/** A cause the server sent as its own code only (gateway `causeText` falls back to the code: 「closed」 · 「customer_request · alternate」) tells the customer nothing — left out. */
export const causeLines = (causes: readonly string[]) => causes.filter((cause) => !/^[a-z_]+( · [a-z_]+)*$/.test(cause));

/** The day before a Seoul date (「2026-10-22」 → 「2026-10-21」) — 「어제」 of 「소식」's date heads. */
export function dayBefore(date: string): string {
  const noon = new Date(`${date}T12:00:00+09:00`);
  noon.setUTCDate(noon.getUTCDate() - 1);
  return new Date(noon.getTime() + 9 * 3_600_000).toISOString().slice(0, 10);
}

/**
 * `[2026-10-22 사용자 결정 — 채팅 ⓑ 「겹친 줄 빼기」를 알림 문장에도]` The server's proposal sentence (`pending.proposal_notice`: 「{일정} — {이유}. 어떻게 할까요? 1) A · 2) B {A}: {경고} 답이 없으면 …」)
 * without what the drawn card already shows: the stop's name in front when the card names the stop, the numbered options and their warnings when the card draws those options.
 * A piece is taken out only when it is the server's frame to the letter (rebuilt from the same values) — anything else stays as the server wrote it.
 */
export function proposalText(text: string, cover: { stopTitle?: string | null; options?: readonly ProposalOption[] }): string {
  let out = text;
  const head = "⚠️ 안전 알림 — ";
  if (cover.stopTitle) {
    const lead = `${cover.stopTitle} — `;
    if (out.startsWith(lead)) out = out.slice(lead.length);
    else if (out.startsWith(head + lead)) out = head + out.slice(head.length + lead.length);
  }
  const options = cover.options ?? [];
  if (options.length && options.every((option) => option.rank !== null)) {
    const listed = options.map((option) => `${option.rank}) ${option.name}${option.note ? ` (${option.note})` : ""}`).join(" · ");
    if (out.includes(` 다른 안: ${listed} `)) out = out.replace(` 다른 안: ${listed}`, "");
    else if (out.includes(`어떻게 할까요? ${listed} `)) out = out.replace(`어떻게 할까요? ${listed} `, "어떻게 할까요? ");
    const warned = options.flatMap((option) => option.warnings.map((warning) => `${option.name}: ${warning}`)).join(" ");
    if (warned && out.includes(` ${warned} 답이 없으면`)) out = out.replace(` ${warned} 답이 없으면`, " 답이 없으면");
    else if (warned && out.includes(`${warned} 답이 없으면`)) out = out.replace(`${warned} 답이 없으면`, "답이 없으면");
  }
  return out;
}
