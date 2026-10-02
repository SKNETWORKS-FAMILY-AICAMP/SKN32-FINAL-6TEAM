import type { Translate } from "@/lib/i18n";
import { lineKey, type StreamState } from "@/lib/live/intake-events";

/**
 * The reading phase of the check screen (2026-10-02 mockup, screens ①②): four steps on one line and the original, line by line,
 * turning from grey to checked as the server reads it. This file decides *what* the screen shows; the components only draw it.
 *
 * ★Nothing here is invented progress. A step is current when the server says it is in that stage, and the bar moves only
 *   with lines the server really read (and, later, places it really checked).
 */

export type StepState = "todo" | "cur" | "done";

/** The four steps on the progress line, in order. `labels` are shown under the nodes. */
export const STEPS: readonly { labels: readonly [ko: string, en: string] }[] = [
  { labels: ["받았어요", "Received"] },
  { labels: ["일정 읽기", "Reading"] },
  { labels: ["장소·운영시간", "Places & hours"] },
  { labels: ["정리 완료", "Done"] },
];

/** Where each fourth of the line ends, in percent (nodes sit at 0, ⅓, ⅔ and 100). */
const SEGMENT = 100 / 3;

/**
 * Which of the four steps the server is on: 0 received (and photo transcribing) · 1 reading · 2 checking places and hours ·
 * 3 tidying up. A stage this screen does not know yet counts as reading, so the line never jumps back or goes blank.
 * Anything past reading (`review`, `confirmed`) is every step done.
 */
export function currentStep(stage: string, status: "reading" | "review" | "confirmed" | "fatal"): number {
  if (status !== "reading") return STEPS.length;
  switch (stage) {
    case "received":
    case "transcribing": return 0;
    case "reading": return 1;
    case "checking": return 2;
    case "review": return 3;
    default: return 1;
  }
}

export function stepStates(current: number): StepState[] {
  return STEPS.map((_, index) => index < current ? "done" : index === current ? "cur" : "todo");
}

export interface ProgressInput {
  /** `currentStep()` */
  step: number;
  readLines: number;
  totalLines: number;
  /** Places and legs checked so far / all of them — only known while the check streams in. */
  checked?: number;
  totalChecks?: number;
}

/**
 * How far the line is filled, 0–100. Received → 0; the reading step fills the first third by the share of lines read; the
 * checking step fills the second third by the share of places and legs checked; tidying up and done are the end.
 */
export function progressPercent({ step, readLines, totalLines, checked = 0, totalChecks = 0 }: ProgressInput): number {
  const share = (done: number, all: number) => all > 0 ? Math.min(1, Math.max(0, done / all)) : 0;
  if (step <= 0) return 0;
  if (step === 1) return SEGMENT * share(readLines, totalLines);
  if (step === 2) return SEGMENT + SEGMENT * share(checked, totalChecks);
  return 100;
}

export interface ReadingLine {
  /** `<source_id>:<no>` — the key the server uses for a read line. */
  key: string;
  no: number;
  text: string;
  /** todo = not read yet · cur = the one being read now · read = the server read it. */
  state: "todo" | "cur" | "read";
  /** What was found on a read line, e.g. 「1일차 11:00 · 올리브영」 — null for a line that gave no stop (a date, a heading). */
  tag: string | null;
}

export interface SourceLines { source_id: string; lines: { no: number; text: string; read: boolean }[] }

/** 「1일차 11:00 · 올리브영」 */
export function foundTag(found: NonNullable<StreamState["lines"][string]["found"]>, t: Translate): string {
  const when = [found.day ? t(`${found.day}일차`, `Day ${found.day}`) : "", found.starts_at ?? ""].filter(Boolean).join(" ");
  return [when, found.title].filter(Boolean).join(" · ");
}

/**
 * The original, line by line. A line is read when the GET said so or the stream told us; the first line not read yet is the
 * one being read (while the server is reading). Lines of several uploads come one after the other, each keeping its own numbers.
 */
export function readingLines(sources: readonly SourceLines[], stream: StreamState, reading: boolean, t: Translate): ReadingLine[] {
  const out: ReadingLine[] = [];
  let cursorTaken = false;
  for (const source of sources) {
    for (const line of source.lines) {
      const key = lineKey({ source_id: source.source_id, no: line.no });
      const heard = stream.lines[key];
      const read = line.read || Boolean(heard);
      let state: ReadingLine["state"] = "read";
      if (!read) {
        state = reading && !cursorTaken ? "cur" : "todo";
        cursorTaken = true;
      }
      out.push({ key, no: line.no, text: line.text, state, tag: read && heard?.found ? foundTag(heard.found, t) : null });
    }
  }
  // A line the stream read aloud but the plan read does not list (yet) — the plan read may be late, or empty while the original is
  // still being turned into text — is shown too, in the order the server read it. The stream carries the text of what it read.
  const listed = new Set(out.map((line) => line.key));
  for (const entry of stream.order) {
    if (!entry.startsWith("line:")) continue;
    const key = entry.slice("line:".length);
    const heard = stream.lines[key];
    if (!heard || listed.has(key)) continue;
    out.push({ key, no: heard.no, text: heard.text, state: "read", tag: heard.found ? foundTag(heard.found, t) : null });
  }
  return out;
}

/** How many stops the reading has found so far: the stops named by the read lines, or the stops the stream listed. */
export function foundCount(lines: readonly ReadingLine[], stream: StreamState): number {
  return Math.max(lines.filter((line) => line.tag !== null).length, Object.keys(stream.items).length);
}
