import { describe, expect, it } from "vitest";
import {
  ASSUMED_MINUTES, DAY_END, GAP_BASE_PX, GAP_MAX_PX, SNAP,
  formatHm, gapPx, legMinutes, moveStop, occupancy, ownRange, parseHm, pushRange, settledAfter, slackAfter, snap,
  type TimedLeg, type TimedStop,
} from "./time-plan";

/** Times in these days are written as minutes since midnight: 540 = 09:00, 600 = 10:00, 660 = 11:00, 720 = 12:00. */
const stop = (id: string, start: number, end: number | null, fixed = false): TimedStop => ({ id, start, end, fixed });
const leg = (fromId: string, toId: string, minutes: number): TimedLeg => ({ fromId, toId, minutes });
const ids = (changes: { id: string }[]) => changes.map((change) => change.id);

/** Three stops with free time between them: a 09:00-10:00, b 11:00-12:00, c 14:00-15:00. a-b takes 30 minutes, b-c 20. */
const DAY = [stop("a", 540, 600), stop("b", 660, 720), stop("c", 840, 900)];
const DAY_LEGS = [leg("a", "b", 30), leg("b", "c", 20)];
/** The same day with the middle stop booked: a wall that nothing may push. */
const DAY_BOOKED = [stop("a", 540, 600), stop("b", 660, 720, true), stop("c", 840, 900)];

/** Six stops, two of them booked (s2, s5). */
const BUSY = [
  stop("s1", 480, 540), stop("s2", 600, 660, true), stop("s3", 720, 780),
  stop("s4", 840, 900), stop("s5", 1020, 1080, true), stop("s6", 1200, 1260),
];
const BUSY_LEGS = [leg("s1", "s2", 30), leg("s2", "s3", 15), leg("s3", "s4", 20), leg("s4", "s5", 25), leg("s5", "s6", 10)];

/** p (09:00-10:30) and q (10:00-11:00) overlap before anything is moved; r is far behind them. */
const OVERLAPPING = [stop("p", 540, 630), stop("q", 600, 660), stop("r", 780, 840)];

/** Like BUSY but with trouble already in it: e1/e2 overlap, e4 starts 5 minutes before it can be reached from the booked e3. */
const TROUBLED = [stop("e1", 540, 630), stop("e2", 600, 660), stop("e3", 720, 780, true), stop("e4", 790, 840), stop("e5", 960, 1020)];
const TROUBLED_LEGS = [leg("e3", "e4", 15), leg("e4", "e5", 30)];

describe("reading and writing a time of day", () => {
  it("reads hours and minutes into minutes since midnight and shows them back", () => {
    expect(parseHm("09:30")).toBe(570);
    expect(parseHm("9:30")).toBe(570);
    expect(parseHm(" 00:00 ")).toBe(0);
    expect(parseHm("23:59")).toBe(1439);
    expect(formatHm(570)).toBe("09:30");
    expect(formatHm(0)).toBe("00:00");
  });

  it("gives back every minute of the day it was given (parse and format round trip)", () => {
    const broken: number[] = [];
    for (let minutes = 0; minutes < DAY_END; minutes++) if (parseHm(formatHm(minutes)) !== minutes) broken.push(minutes);
    expect(broken).toEqual([]);
  });

  it("answers null for text that is not a time of day, including 24:00", () => {
    for (const text of ["", "  ", "abc", "9", "9:5", "09:60", "24:00", "-1:30", "09:30pm", "09.30", "123:00"]) expect(parseHm(text)).toBeNull();
  });

  it("clamps what it shows to 00:00..23:59 and shows an unknown time as dashes instead of midnight", () => {
    expect(formatHm(DAY_END)).toBe("23:59");
    expect(formatHm(-20)).toBe("00:00");
    expect(formatHm(569.6)).toBe("09:30");
    expect(formatHm(Number.NaN)).toBe("--:--");
  });
});

describe("snapping a time to the step", () => {
  it("rounds to the nearest multiple of the step, a half going up", () => {
    expect(SNAP).toBe(5);
    expect(snap(572)).toBe(570);
    expect(snap(573)).toBe(575);
    expect(snap(570)).toBe(570);
    expect(snap(572.5)).toBe(575);
    expect(snap(7, 10)).toBe(10);
  });

  it("never answers minus zero and leaves a value alone when the step is not a positive number", () => {
    expect(snap(-2)).toBe(0);
    expect(snap(5, 0)).toBe(5);
    expect(snap(5, -5)).toBe(5);
  });
});

describe("how long a stop takes and how much free time follows it", () => {
  it("takes end minus start, assumes an hour when the end is unknown, and is never below zero", () => {
    expect(occupancy(stop("a", 540, 600))).toBe(60);
    expect(occupancy(stop("a", 540, null))).toBe(ASSUMED_MINUTES);
    expect(occupancy(stop("a", 540, 540))).toBe(0);
    expect(occupancy(stop("a", 540, 500))).toBe(0);
  });

  it("is the time between the traveller getting there and the next stop starting", () => {
    expect(slackAfter(DAY, DAY_LEGS, 0)).toBe(30);                // 660 - (540 + 60 + 30)
    expect(slackAfter(DAY, DAY_LEGS, 1)).toBe(100);               // 840 - (660 + 60 + 20)
    expect(slackAfter([stop("a", 540, 600), stop("b", 690, 750)], [leg("a", "b", 30)], 0)).toBe(60);
    expect(slackAfter([stop("a", 540, 600), stop("b", 630, 690)], [leg("a", "b", 30)], 0)).toBe(0);
  });

  it("is negative when the next stop cannot be reached in time, and null where nothing follows", () => {
    expect(slackAfter([stop("a", 540, 600), stop("b", 610, 670)], [leg("a", "b", 30)], 0)).toBe(-20);
    expect(slackAfter(DAY, DAY_LEGS, 2)).toBeNull();
    expect(slackAfter(DAY, DAY_LEGS, 9)).toBeNull();
  });

  it("counts a pair with no leg as no travel, takes the first leg listed twice, and ignores a negative one", () => {
    expect(slackAfter(DAY, [], 0)).toBe(60);                      // 660 - (540 + 60)
    expect(legMinutes([leg("a", "b", 30), leg("a", "b", 99)], "a", "b")).toBe(30);
    expect(legMinutes([leg("a", "b", -5)], "a", "b")).toBe(0);
    expect(legMinutes(DAY_LEGS, "b", "a")).toBe(0);               // legs have a direction
  });
});

describe("the space drawn for free time", () => {
  it("grows with the free minutes from a base and stops growing at the cap", () => {
    expect(gapPx(0)).toBe(GAP_BASE_PX);
    expect(gapPx(30)).toBe(40);                                   // 14 + 66 * (1 - e^-0.5)
    expect(gapPx(60)).toBe(56);
    expect(gapPx(120)).toBe(71);
    expect(gapPx(193)).toBe(77);
    expect(gapPx(5000)).toBe(GAP_MAX_PX);                         // flattens out at 80 and never passes it
    expect(GAP_MAX_PX).toBe(80);
    expect([0, 15, 30, 60, 120, 240, 600].map(gapPx)).toEqual([...[0, 15, 30, 60, 120, 240, 600].map(gapPx)].sort((a, b) => a - b));   // more free time never gets less space
  });

  it("gives only the base space to a stop that is already late or has nothing after it", () => {
    expect(gapPx(-45)).toBe(GAP_BASE_PX);
    expect(gapPx(null)).toBe(GAP_BASE_PX);
  });
});

describe("the times a stop can have without moving anyone", () => {
  it("runs from the previous stop's arrival to the next stop's start minus the stop's own length", () => {
    expect(ownRange(DAY, DAY_LEGS, 0)).toEqual({ min: 0, max: 570 });          // first stop: from midnight; 660 - 30 - 60
    expect(ownRange(DAY, DAY_LEGS, 1)).toEqual({ min: 630, max: 760 });        // 540 + 60 + 30; 840 - 20 - 60
    expect(ownRange(DAY, DAY_LEGS, 2)).toEqual({ min: 740, max: 1380 });       // last stop: to the day's end minus 60
  });

  it("rounds the first time up and the last time down to the step so that nobody is touched", () => {
    const day = [stop("u", 540, 600), stop("v", 720, 780), stop("x", 900, 960)];
    const legs = [leg("u", "v", 33), leg("v", "x", 33)];
    expect(ownRange(day, legs, 0).max).toBe(625);                              // 720 - 33 - 60 = 627
    expect(ownRange(day, legs, 2).min).toBe(815);                              // 780 + 33 = 813
  });

  it("is only the place the stop stands in when there is no room, and for a stop that cannot move", () => {
    const tight = [stop("p", 540, 600), stop("q", 630, 690), stop("r", 710, 770)];
    expect(ownRange(tight, [leg("p", "q", 30), leg("q", "r", 30)], 1)).toEqual({ min: 630, max: 630 });
    expect(ownRange(DAY_BOOKED, DAY_LEGS, 1)).toEqual({ min: 660, max: 660 });
  });

  it("keeps the stop's own place in the range when it already stands outside it", () => {
    expect(ownRange(TROUBLED, TROUBLED_LEGS, 3).min).toBe(790);                // e3 is booked until 780, +15 would be 795
    expect(ownRange(OVERLAPPING, [], 1).min).toBe(600);                        // p runs until 630
  });
});

describe("the times a stop can be dragged to", () => {
  it("is as far as the whole day packs when nothing is booked, from the start of the day to its end", () => {
    expect(pushRange(DAY, DAY_LEGS, 0)).toEqual({ min: 0, max: 1210 });        // 1440 - (60 + 30 + 60 + 20 + 60)
    expect(pushRange(DAY, DAY_LEGS, 1)).toEqual({ min: 90, max: 1300 });
    expect(pushRange(DAY, DAY_LEGS, 2)).toEqual({ min: 170, max: 1380 });
  });

  it("is stopped by a booked stop before it and by a booked stop after it", () => {
    expect(pushRange(DAY_BOOKED, DAY_LEGS, 0)).toEqual({ min: 0, max: 570 });  // b starts 660: 660 - 30 - 60
    expect(pushRange(DAY_BOOKED, DAY_LEGS, 2)).toEqual({ min: 740, max: 1380 });
    expect(pushRange(BUSY, BUSY_LEGS, 2)).toEqual({ min: 675, max: 855 });     // between s2 and s5, with s4 packed behind it
    expect(pushRange(BUSY, BUSY_LEGS, 3)).toEqual({ min: 755, max: 935 });
    expect(pushRange(BUSY, BUSY_LEGS, 5)).toEqual({ min: 1090, max: 1380 });   // after the last booked stop, up to the day's end
  });

  it("leaves a booked stop where it is and a squeezed stop where it stands", () => {
    expect(pushRange(BUSY, BUSY_LEGS, 1)).toEqual({ min: 600, max: 600 });
    const squeezed = [stop("t1", 540, 600, true), stop("t2", 630, 690), stop("t3", 710, 770, true)];
    expect(pushRange(squeezed, [leg("t1", "t2", 30), leg("t2", "t3", 30)], 1)).toEqual({ min: 630, max: 630 });
  });

  it("rounds inwards to the step and widens to reach a stop that already stands outside it", () => {
    const day = [stop("u", 540, 600), stop("v", 720, 780, true), stop("x", 900, 960)];
    const legs = [leg("u", "v", 33), leg("v", "x", 33)];
    expect(pushRange(day, legs, 0)).toEqual({ min: 0, max: 625 });
    expect(pushRange(day, legs, 2)).toEqual({ min: 815, max: 1380 });
    expect(pushRange(TROUBLED, TROUBLED_LEGS, 3)).toEqual({ min: 790, max: 1300 });
  });

  it("asks for a stop the day does not have with a RangeError rather than an invented time", () => {
    expect(() => ownRange(DAY, DAY_LEGS, -1)).toThrow(RangeError);
    expect(() => pushRange(DAY, DAY_LEGS, 3)).toThrow(RangeError);
    expect(() => moveStop(DAY, DAY_LEGS, 1.5, 600)).toThrow(RangeError);
  });
});

describe("moving a stop later", () => {
  it("moves only that stop while it stays inside its own free time", () => {
    const result = moveStop(DAY, DAY_LEGS, 0, 570);                            // exactly as late as it can be without touching b
    expect(result).toEqual({ start: 570, changes: [{ id: "a", start: 570, end: 630 }], clamped: false, min: 0, max: 1210 });
  });

  it("pushes the next stop to the moment it can be reached when the free time runs out", () => {
    const result = moveStop(DAY, DAY_LEGS, 0, 600);
    expect(result.changes).toEqual([
      { id: "a", start: 600, end: 660 },
      { id: "b", start: 690, end: 750 },                                       // 600 + 60 + 30; the hour it lasts is kept
    ]);                                                                        // c (840) is far enough away and stays
  });

  it("goes on down the day for as long as each stop is hit, keeping every length", () => {
    const result = moveStop(DAY, DAY_LEGS, 0, 700);
    expect(result.changes).toEqual([
      { id: "a", start: 700, end: 760 },
      { id: "b", start: 790, end: 850 },
      { id: "c", start: 870, end: 930 },                                       // 790 + 60 + 20
    ]);
    expect(result.changes.every((change) => change.end! - change.start === 60)).toBe(true);
  });

  it("keeps an unknown end unknown on the stop that is moved and on a stop that is pushed", () => {
    const first = [stop("d", 540, null), stop("e", 660, 720)];
    expect(moveStop(first, [leg("d", "e", 15)], 0, 630).changes).toEqual([
      { id: "d", start: 630, end: null },
      { id: "e", start: 705, end: 765 },                                       // d is assumed to take 60 minutes
    ]);
    const second = [stop("g", 540, 600), stop("h", 630, null)];
    expect(moveStop(second, [leg("g", "h", 30)], 0, 570).changes).toEqual([
      { id: "g", start: 570, end: 630 },
      { id: "h", start: 660, end: null },
    ]);
  });
});

describe("moving a stop earlier", () => {
  it("moves only that stop while it stays inside its own free time", () => {
    const result = moveStop(DAY, DAY_LEGS, 2, 760);
    expect(result.changes).toEqual([{ id: "c", start: 760, end: 820 }]);
    expect(result.clamped).toBe(false);
  });

  it("pushes the previous stop earlier, to the last moment that still gets it there", () => {
    const result = moveStop(DAY, DAY_LEGS, 2, 730);
    expect(result.changes).toEqual([
      { id: "b", start: 650, end: 710 },                                       // 730 - 20 - 60
      { id: "c", start: 730, end: 790 },
    ]);                                                                        // a still has room (650 - 30 - 60 = 560)
  });

  it("goes on up the day and lists the changes in day order, not in the order they were found", () => {
    const result = moveStop(DAY, DAY_LEGS, 2, 700);
    expect(ids(result.changes)).toEqual(["a", "b", "c"]);
    expect(result.changes).toEqual([
      { id: "a", start: 530, end: 590 },
      { id: "b", start: 620, end: 680 },
      { id: "c", start: 700, end: 760 },
    ]);
  });
});

describe("a move that runs into a wall", () => {
  it("stops a booked stop from being pushed: the moved time is held where the booked stop would be hit", () => {
    const later = moveStop(BUSY, BUSY_LEGS, 0, 540);                           // s2 is booked at 600 and s1 needs 60 + 30 before it
    expect(later).toMatchObject({ start: 510, clamped: true, max: 510 });
    expect(later.changes).toEqual([{ id: "s1", start: 510, end: 570 }]);

    const earlier = moveStop(BUSY, BUSY_LEGS, 2, 0);                           // s2 ends 660, +15 to s3
    expect(earlier).toMatchObject({ start: 675, clamped: true, min: 675 });
    expect(earlier.changes).toEqual([{ id: "s3", start: 675, end: 735 }]);
  });

  it("pushes up to a booked stop but not into it", () => {
    const result = moveStop(BUSY, BUSY_LEGS, 2, 900);                          // held at 855: s4 pushed to 935, s5 (1020) is just reached
    expect(result.start).toBe(855);
    expect(result.clamped).toBe(true);
    expect(result.changes).toEqual([{ id: "s3", start: 855, end: 915 }, { id: "s4", start: 935, end: 995 }]);
  });

  it("does not move a booked stop at all, whatever is asked, and says the request was not followed", () => {
    for (const push of [true, false]) {
      const result = moveStop(BUSY, BUSY_LEGS, 1, 700, { push });
      expect(result).toEqual({ start: 600, changes: [], clamped: true, min: 600, max: 600 });
    }
  });

  it("never moves a booked stop, whichever stop is dragged to whichever time, and never breaks a connection that held", () => {
    const problems: string[] = [];
    for (const [name, day, legs] of [["busy", BUSY, BUSY_LEGS], ["troubled", TROUBLED, TROUBLED_LEGS], ["overlapping", OVERLAPPING, []], ["booked", DAY_BOOKED, DAY_LEGS]] as const) {
      for (let index = 0; index < day.length; index++) {
        for (const push of [true, false]) {
          for (let wanted = -60; wanted <= 1500; wanted += 5) {
            const result = moveStop(day, legs, index, wanted, { push });
            const after = settledAfter(day, result.changes);
            const label = `${name}[${index}] -> ${wanted} push=${push}`;
            if (result.changes.some((change) => day.find((s) => s.id === change.id)?.fixed)) problems.push(`${label}: a booked stop moved`);
            if (!push && result.changes.length > 1) problems.push(`${label}: a neighbour moved without push`);
            if (result.start < result.min || result.start > result.max) problems.push(`${label}: start outside its range`);
            if (after[index].start !== result.start) problems.push(`${label}: result.start is not the stop's new start`);
            for (const change of result.changes) {
              const before = day.find((s) => s.id === change.id)!;
              if ((change.end === null) !== (before.end === null)) problems.push(`${label}: ${change.id} lost or gained an end`);
              if (change.end !== null && change.end - change.start !== before.end! - before.start) problems.push(`${label}: ${change.id} changed length`);
              if (change.start < 0 || (change.end ?? change.start + ASSUMED_MINUTES) > DAY_END) problems.push(`${label}: ${change.id} left the day`);
            }
            for (let k = 0; k + 1 < day.length; k++) {
              const was = slackAfter(day, legs, k)!;
              const now = slackAfter(after, legs, k)!;
              if (now < Math.min(was, 0)) problems.push(`${label}: pair ${k} got worse (${was} -> ${now})`);
            }
          }
        }
      }
    }
    expect(problems).toEqual([]);
  });
});

describe("a move that runs into the ends of the day", () => {
  it("holds the first stop at midnight and the last stop to the end of the day", () => {
    expect(moveStop(DAY, DAY_LEGS, 0, -30)).toMatchObject({ start: 0, clamped: true, changes: [{ id: "a", start: 0, end: 60 }] });
    const last = moveStop(DAY, DAY_LEGS, 2, 1439);                             // snaps to 1440, but an hour has to fit
    expect(last).toMatchObject({ start: 1380, clamped: true });
    expect(last.changes).toEqual([{ id: "c", start: 1380, end: DAY_END }]);
  });

  it("packs the whole day against its end when the first stop is dragged as late as it goes", () => {
    const result = moveStop(DAY, DAY_LEGS, 0, 1300);
    expect(result.clamped).toBe(true);
    expect(result.changes).toEqual([
      { id: "a", start: 1210, end: 1270 },
      { id: "b", start: 1300, end: 1360 },
      { id: "c", start: 1380, end: DAY_END },
    ]);
  });
});

describe("typing a time that must not move the neighbours", () => {
  it("holds the stop inside its own free time where a drag would have pushed the next stops", () => {
    const typed = moveStop(DAY, DAY_LEGS, 0, 700, { push: false });
    expect(typed).toEqual({ start: 570, changes: [{ id: "a", start: 570, end: 630 }], clamped: true, min: 0, max: 570 });
    const dragged = moveStop(DAY, DAY_LEGS, 0, 700);
    expect(ids(dragged.changes)).toEqual(["a", "b", "c"]);
    expect(dragged.clamped).toBe(false);
  });

  it("lets a stop go anywhere in its own free time", () => {
    expect(moveStop(DAY, DAY_LEGS, 1, 640, { push: false }).changes).toEqual([{ id: "b", start: 640, end: 700 }]);
    expect(moveStop(DAY, DAY_LEGS, 1, 600, { push: false })).toMatchObject({ start: 630, clamped: true, min: 630, max: 760 });
  });
});

describe("what a move does and does not change", () => {
  it("snaps the time asked for to the step before it is used", () => {
    expect(moveStop(DAY, DAY_LEGS, 0, 553)).toMatchObject({ start: 555, clamped: false, changes: [{ id: "a", start: 555, end: 615 }] });
    expect(moveStop(DAY, DAY_LEGS, 0, 543).start).toBe(545);
  });

  it("changes nothing when the snapped time is the one the stop has", () => {
    expect(moveStop(DAY, DAY_LEGS, 1, 660)).toEqual({ start: 660, changes: [], clamped: false, min: 90, max: 1300 });
    expect(moveStop(DAY, DAY_LEGS, 0, 542).changes).toEqual([]);              // 542 snaps to 540, where a already is
  });

  it("changes nothing for a time that is not a number", () => {
    expect(moveStop(DAY, DAY_LEGS, 0, Number.NaN)).toMatchObject({ start: 540, changes: [], clamped: false });
    expect(moveStop(DAY, DAY_LEGS, 0, Number.POSITIVE_INFINITY).changes).toEqual([]);
  });

  it("leaves stops that overlap before the move as they are and pushes only what the move itself causes", () => {
    expect(slackAfter(OVERLAPPING, [], 0)).toBe(-30);
    expect(moveStop(OVERLAPPING, [], 2, 900).changes).toEqual([{ id: "r", start: 900, end: 960 }]);
    expect(moveStop(OVERLAPPING, [], 2, 700).changes).toEqual([{ id: "r", start: 700, end: 760 }]);
    const later = moveStop(OVERLAPPING, [], 1, 620);                          // q moves away from p: p is not "repaired" or touched
    expect(later.changes).toEqual([{ id: "q", start: 620, end: 680 }]);
    expect(slackAfter(settledAfter(OVERLAPPING, later.changes), [], 0)).toBe(-10);
    const earlier = moveStop(OVERLAPPING, [], 1, 590);                        // q moves into p: now p has to give way
    expect(earlier.changes).toEqual([{ id: "p", start: 500, end: 590 }, { id: "q", start: 590, end: 650 }]);
  });

  it("does not throw a stop that already stands outside its range the other way", () => {
    // e4 starts at 790, five minutes before it can be reached from the booked e3 (780 + 15 = 795): asking for earlier must not send it later.
    expect(moveStop(TROUBLED, TROUBLED_LEGS, 3, 600)).toEqual({ start: 790, changes: [], clamped: true, min: 790, max: 1300 });
    expect(moveStop(TROUBLED, TROUBLED_LEGS, 3, 800).changes).toEqual([{ id: "e4", start: 800, end: 850 }]);
  });

  it("gives the same answer for the same day and leaves the day it was given as it was", () => {
    const before = JSON.stringify([DAY, DAY_LEGS]);
    const first = moveStop(DAY, DAY_LEGS, 0, 700);
    const second = moveStop(DAY, DAY_LEGS, 0, 700);
    expect(second).toEqual(first);
    expect(JSON.stringify([DAY, DAY_LEGS])).toBe(before);
  });
});

describe("the day after a move", () => {
  it("applies the changes in place of the old times, keeps the order and every other field, and shares the stops it did not touch", () => {
    const labelled = DAY.map((s) => ({ ...s, label: s.id.toUpperCase() }));
    const result = moveStop(labelled, DAY_LEGS, 0, 600);
    const after = settledAfter(labelled, result.changes);
    expect(after.map((s) => [s.id, s.start, s.end, s.label])).toEqual([["a", 600, 660, "A"], ["b", 690, 750, "B"], ["c", 840, 900, "C"]]);
    expect(after[2]).toBe(labelled[2]);
    expect(labelled[0].start).toBe(540);                                       // the day it was given is not changed
  });

  it("keeps an unknown end unknown and ignores a change for a stop the day does not have", () => {
    const day = [stop("d", 540, null), stop("e", 660, 720)];
    const after = settledAfter(day, [{ id: "d", start: 570, end: null }, { id: "zz", start: 1, end: 2 }]);
    expect(after).toEqual([stop("d", 570, null), stop("e", 660, 720)]);
    expect(settledAfter(day, [])).toEqual(day);
  });
});

describe("a time typed in by hand is taken to the minute", () => {
  const day = [
    { id: "a", start: 540, end: 630, fixed: false },
    { id: "b", start: 700, end: 760, fixed: false },
  ];
  const legs = [{ fromId: "a", toId: "b", minutes: 12 }];

  it("keeps a typed minute that a drag would round to the grid, and holds it to the minute-exact range", () => {
    expect(moveStop(day, legs, 1, 703, { push: false, step: 1 }).start).toBe(703);
    expect(moveStop(day, legs, 1, 703, { push: false }).start).toBe(705);                       // the drag's own grid
    expect(ownRange(day, legs, 1, 1)).toEqual({ min: 642, max: 1380 });                         // 630 + 12 ... 24:00 - 60
    expect(ownRange(day, legs, 1)).toEqual({ min: 645, max: 1380 });
    expect(moveStop(day, legs, 1, 641, { push: false, step: 1 })).toMatchObject({ start: 642, clamped: true });
  });

  it("moves the neighbours by the minute too, when pushing", () => {
    const result = moveStop(day, legs, 0, 655, { step: 1 });                                      // a would end at 745 + 12 > 700: b is pushed to 757
    expect(result.changes.map((change) => [change.id, change.start])).toEqual([["a", 655], ["b", 757]]);
  });
});
