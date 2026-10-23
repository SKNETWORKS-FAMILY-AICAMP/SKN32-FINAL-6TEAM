import type { ChatDiff } from "./chat-diff";
import type { Trip, TripMessage, TripStop } from "./model";

/**
 * `[2026-10-22 사용자 결정 — ST4F-719 · 목업 ⓑ]` An answer drawn as a card: a heading badge from what the server did (`status` and the answer's own flags), a small card of what it is about
 * (the stop, the day, or what the change changed), and the server's text without the lines the card already shows.
 */
export type AnswerTone = "primary" | "success" | "warning" | "adjusted" | "muted";
export type AnswerLook = { tone: AnswerTone; kind: "pick" | "location" | "waiting" | "undone" | "changed" | "kept" | "answer" };

/**
 * The heading badge. Null for an answer this tab did not receive (read back from the server's record on another tab or device): it has no status, so it shows the text only — as its undo,
 * which also lives in this tab only.
 */
export function answerLook(message: TripMessage, undone: boolean): AnswerLook | null {
  if (message.pick) return { tone: "warning", kind: "pick" };
  if (message.needsLocation) return { tone: "adjusted", kind: "location" };
  if (message.awaitingReply) return { tone: "warning", kind: "waiting" };
  if (message.changedTo !== undefined) return undone ? { tone: "muted", kind: "undone" } : { tone: "success", kind: "changed" };
  if (message.status === "still_fits") return { tone: "success", kind: "kept" };
  return message.status ? { tone: "primary", kind: "answer" } : null;
}

export type AnswerCard = { kind: "diff"; diff: ChatDiff } | { kind: "day"; date: string; stops: TripStop[] } | { kind: "place"; stop: TripStop } | null;

/** The card under an answer: what a change changed (this tab only), the day a summary was asked for, or the stop the answer is about (the chip pressed, else the server's `focus`). */
export function answerCard(message: TripMessage, trip: Pick<Trip, "stops">, diffs: Record<string, ChatDiff>): AnswerCard {
  if (message.changedTo !== undefined) {
    const diff = diffs[String(message.changedTo)];
    return diff ? { kind: "diff", diff } : null;
  }
  if (message.summaryDay) {
    const stops = dayStops(trip.stops, message.summaryDay);
    return stops.length ? { kind: "day", date: message.summaryDay, stops } : null;
  }
  const stop = message.focusId ? trip.stops.find((entry) => entry.id === message.focusId) : undefined;
  return stop ? { kind: "place", stop } : null;
}

/** A day's stops as the server lists them in a summary (`trip_facts._stops`: by start). */
export const dayStops = (stops: readonly TripStop[], date: string) => stops.filter((stop) => stop.date === date).sort((a, b) => a.time.localeCompare(b.time));

// ── The server's sentence frames (app/domains/travel_ops/components/conversation/trip_facts.py · chat_edit.py, 2026-10-22) ──
const WEEKDAY = "일월화수목금토";
/** `trip_facts._day_label`: 「10월 4일(토)」 — no zero padding. */
export function serverDayLabel(date: string): string {
  const [, month, day] = date.split("-").map(Number);
  return `${month}월 ${day}일(${WEEKDAY[new Date(`${date}T12:00:00+09:00`).getUTCDay()]})`;
}
const KIND_LABEL: Record<string, string> = { activity: "활동", dining: "식사", lodging: "숙소", mobility: "이동" };
const span = (stop: TripStop) => `${stop.time}${stop.endTime ? `~${stop.endTime}` : ""}`;
/** `trip_facts._stop_line`: 「09:00~11:00 경복궁 관람(활동)」 — an unknown kind keeps the server's own word ("flight"). */
const stopLine = (stop: TripStop) => stop.kind ? `${span(stop)} ${stop.title}(${KIND_LABEL[stop.kind] ?? stop.kind})` : null;
/** `chat_edit.done_text`'s trailing sentence: the undo button says the same while it is drawn. */
export const UNDO_SENTENCE = "마음에 안 드시면 「되돌려 줘」라고 말씀해 주세요.";

/**
 * `[2026-10-22 사용자 결정 — 겹친 줄 빼기]` The server lines the drawn card already shows, rebuilt from the card's own values in the server's frames. A line is left out only when it is the same to the
 * letter: a frame the server changes or a value that differs leaves the line in. What the web cannot rebuild stays (the address from the server's own lookup, the day's stored hours, the move
 * lines — their values are not in the trip view) — until the server sends these as fields of their own.
 */
export function coveredLines(card: AnswerCard): Set<string> {
  const lines = new Set<string>();
  if (card?.kind === "place") {
    const { stop } = card;
    const address = stop.placeInfo?.address;
    if (stop.place && address) lines.add(`· 어디: ${stop.place} · ${address}`);
    if (stop.mapUrl) { lines.add(`· 지도: ${stop.mapUrl}`); lines.add(`지도에서 보기: ${stop.mapUrl}`); }
  } else if (card?.kind === "day") {
    for (const stop of card.stops) { const line = stopLine(stop); if (line) lines.add(`· ${line}`); }
  } else if (card?.kind === "diff") {
    // `chat_edit.done_text`: 「· 10월 24일(금) 12:00~13:00 광장시장 점심」 — the card's after values
    for (const row of card.diff.rows) if (row.line) lines.add(row.line);
  }
  return lines;
}

/** The answer's text without the covered lines, and without the undo sentence while the undo button is drawn. */
export function shownText(text: string, covered: ReadonlySet<string>, undoShown: boolean): string {
  return text.split("\n").filter((line) => !covered.has(line))
    .map((line) => (undoShown && line.includes(UNDO_SENTENCE) ? line.replace(` ${UNDO_SENTENCE}`, "").replace(UNDO_SENTENCE, "") : line))
    .filter((line, index, all) => line !== "" || (index > 0 && index < all.length - 1)).join("\n");
}

/** The line `chat_edit.done_text` writes for a stop after the change. */
export const doneLine = (stop: TripStop) => `· ${serverDayLabel(stop.date)} ${span(stop)} ${stop.title}`;
