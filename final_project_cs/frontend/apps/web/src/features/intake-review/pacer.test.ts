import { describe, expect, it } from "vitest";
import { toIntakeEvent, type IntakeStreamEvent } from "@/lib/live/intake-events";
import { createPacer, GAP_MS, MAX_BACKLOG_MS, newnessKey, SETTLE_MS } from "./pacer";

/** A clock the test turns by hand — no real waiting. */
function clock() {
  let time = 0;
  const timers: { at: number; run: () => void; live: boolean }[] = [];
  return {
    now: () => time,
    setTimer: (run: () => void, ms: number) => { const entry = { at: time + ms, run, live: true }; timers.push(entry); return () => { entry.live = false; }; },
    advance(ms: number) {
      const end = time + ms;
      for (;;) {
        const due = timers.filter((entry) => entry.live && entry.at <= end).sort((a, b) => a.at - b.at)[0];
        if (!due) break;
        due.live = false; time = due.at; due.run();
      }
      time = end;
    },
  };
}

const ev = (name: string, body: object): IntakeStreamEvent => toIntakeEvent(name, JSON.stringify(body)) as IntakeStreamEvent;
const line = (no: number) => ev("line", { source_id: "s1", no, text: `줄 ${no}`, read: true, found: null });
const item = (id: string, patch: object = {}) => ev("item", { id, source_id: "s1", index: Number(id.split("-")[1]), title: id, place_state: "searching", ...patch });
const check = (itemId: string, row: string) => ev("check", { item: itemId, row, result: "ok", text: `${itemId} ${row}` });
const move = (from: string, to: string) => ev("move", { from, to, status: "keep", summary: "도보", rows: [] });

function setup(options: { instant?: boolean } = {}) {
  const c = clock();
  const shown: string[] = [];
  const busy: boolean[] = [];
  const label = (e: IntakeStreamEvent) => e.type === "check" ? `check:${e.item}:${e.line.row}` : e.type === "item" ? `item:${e.item.id}` : e.type === "move" ? `move:${e.move.from}>${e.move.to}` : e.type === "line" ? `line:${e.line.no}` : e.type;
  const pacer = createPacer({ show: (e) => shown.push(label(e)), onBusy: (b) => busy.push(b), setTimer: c.setTimer, now: c.now, ...options });
  return { c, shown, busy, pacer };
}

describe("the pace of the check screen", () => {
  it("shows the first thing after a moment (so what arrived together is lined up) and each new thing its gap after the one before", () => {
    const { c, shown, pacer } = setup();
    pacer.push(line(1)); pacer.push(line(2)); pacer.push(line(3));
    expect(shown).toEqual([]);
    c.advance(SETTLE_MS);
    expect(shown).toEqual(["line:1"]);
    c.advance(GAP_MS.line - 1);
    expect(shown).toEqual(["line:1"]);
    c.advance(1);
    expect(shown).toEqual(["line:1", "line:2"]);
    c.advance(GAP_MS.line);
    expect(shown).toEqual(["line:1", "line:2", "line:3"]);
  });

  it("applies a repeat at once — a stop whose place was just found, a line a reconnect replayed", () => {
    const { c, shown, pacer } = setup();
    pacer.push(item("0-0")); pacer.push(item("0-1"));
    c.advance(SETTLE_MS + GAP_MS.item);
    expect(shown).toEqual(["item:0-0", "item:0-1"]);
    pacer.push(item("0-0", { place_state: "found" }));
    c.advance(SETTLE_MS);                                           // no gap — only the moment to line up with what arrives with it
    expect(shown).toEqual(["item:0-0", "item:0-1", "item:0-0"]);
    pacer.push(line(1)); pacer.push(line(1));
    c.advance(SETTLE_MS + GAP_MS.line);
    expect(shown.filter((entry) => entry === "line:1")).toHaveLength(2);
  });

  it("keeps the order events arrived in when nothing says otherwise", () => {
    const { c, shown, pacer } = setup();
    pacer.push(ev("stage", { stage: "checking", label: "x" })); pacer.push(line(1)); pacer.push(ev("stage", { stage: "review", label: "y" }));
    c.advance(5_000);
    expect(shown).toEqual(["stage", "line:1", "stage"]);
  });

  it("puts a stop's check lines behind that stop and a leg behind the stop it leads to", () => {
    // what the server sends: every stop first, then every check line, then every leg
    const { c, shown, pacer } = setup();
    for (const e of [item("0-0"), item("0-1"), item("0-2"), check("0-0", "place"), check("0-0", "hours"), check("0-1", "place"), check("0-2", "place"), move("0-0", "0-1"), move("0-1", "0-2")]) pacer.push(e);
    c.advance(60_000);
    expect(shown).toEqual(["item:0-0", "check:0-0:place", "check:0-0:hours", "item:0-1", "check:0-1:place", "move:0-0>0-1", "item:0-2", "check:0-2:place", "move:0-1>0-2"]);
  });

  it("does not move a check line behind a stop that was already shown", () => {
    const { c, shown, pacer } = setup();
    pacer.push(item("0-0"));
    c.advance(SETTLE_MS);
    pacer.push(item("0-1")); pacer.push(check("0-0", "place"));
    c.advance(60_000);
    expect(shown).toEqual(["item:0-0", "item:0-1", "check:0-0:place"]);
  });

  it("shortens a long backlog so the customer is not kept waiting after the server has finished", () => {
    const { c, shown, pacer } = setup();
    for (let no = 1; no <= 60; no += 1) pacer.push(line(no));        // 60 lines × 450 ms = 27 s if shown at full pace
    c.advance(MAX_BACKLOG_MS + 500);
    expect(shown.filter((entry) => entry.startsWith("line:"))).toHaveLength(60);
  });

  it("says when it is busy and when the last waiting event has been shown", () => {
    const { c, busy, pacer } = setup();
    pacer.push(line(1)); pacer.push(line(2));
    expect(busy).toEqual([true]);
    c.advance(SETTLE_MS + GAP_MS.line);
    expect(busy).toEqual([true, false]);
    expect(pacer.pending).toBe(0);
  });

  it("shows everything waiting at once on flush, and drops it on stop", () => {
    const first = setup();
    first.pacer.push(line(1)); first.pacer.push(line(2)); first.pacer.push(line(3));
    first.pacer.flush();
    expect(first.shown).toEqual(["line:1", "line:2", "line:3"]);
    expect(first.busy.at(-1)).toBe(false);
    const second = setup();
    second.pacer.push(line(1)); second.pacer.push(line(2));
    second.c.advance(SETTLE_MS);
    second.pacer.stop();
    second.c.advance(5_000);
    expect(second.shown).toEqual(["line:1"]);
  });

  it("shows every event as it arrives when the customer asked for less motion", () => {
    const { shown, pacer } = setup({ instant: true });
    pacer.push(line(1)); pacer.push(item("0-0")); pacer.push(check("0-0", "place"));
    expect(shown).toEqual(["line:1", "item:0-0", "check:0-0:place"]);
  });

  it("knows what each event adds, and that heartbeats and ends add nothing", () => {
    expect(newnessKey(line(2))).toBe("line:s1:2");
    expect(newnessKey(check("0-1", "hours"))).toBe("check:0-1:hours");
    expect(newnessKey(move("0-0", "0-1"))).toBe("move:0-0:0-1");
    expect(newnessKey(ev("beat", { stage: "reading" }))).toBeNull();
  });
});
