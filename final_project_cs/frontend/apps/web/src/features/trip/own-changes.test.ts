import { describe, expect, it } from "vitest";
import { ownAnswer, ownChange, ownTripNotice, ownVersions } from "./own-changes";

const change = (version: number) => ({ type: "change_notice", version, proposalId: null });
const options = (proposalId: string) => ({ type: "proposal_request", version: null, proposalId });

describe("what this device's own press brought — not barred again (ST4F-723 g)", () => {
  it("holds the version a pick writes from the press, and the one the server answers with", async () => {
    let during = false;
    await ownChange("trip-a", 4, async () => { during = ownTripNotice("trip-a", change(5)); return { version: 5 }; });
    expect(during).toBe(true);                                         // the notice can come in before the answer
    expect(ownTripNotice("trip-a", change(5))).toBe(true);
    expect(ownTripNotice("trip-a", change(6))).toBe(false);            // a change made elsewhere afterwards
    await ownChange("trip-a", 6, async () => ({ version: 8 }));        // the server wrote another version than base + 1
    expect([...ownVersions("trip-a")]).toEqual([5, 8]);
  });

  it("drops the held version when the write fails — that version is someone else's", async () => {
    await expect(ownChange("trip-b", 1, async () => { throw new Error("409"); })).rejects.toThrow("409");
    expect(ownTripNotice("trip-b", change(2))).toBe(false);
  });

  it("holds the options notice that 「예보에 맞게 일정 변경」 brings, once", async () => {
    await ownAnswer("trip-c", 3, { proposalId: "p1", consent: true }, async () => ({ status: "options", version: undefined }));
    expect(ownTripNotice("trip-c", options("p2"))).toBe(false);        // another proposal
    expect(ownTripNotice("trip-c", options("p1"))).toBe(true);
    expect(ownTripNotice("trip-c", options("p1"))).toBe(false);        // a later notice of it is barred as usual
    expect(ownTripNotice("trip-c", change(4))).toBe(false);            // asking for options writes no version
  });

  it("does not hold the options notice when asking for them failed", async () => {
    await expect(ownAnswer("trip-d", 3, { proposalId: "p1", consent: true }, async () => { throw new Error("expired"); })).rejects.toThrow();
    expect(ownTripNotice("trip-d", options("p1"))).toBe(false);
  });

  it("a pick or a keep is a version change of its own", async () => {
    await ownAnswer("trip-e", 2, { proposalId: "p1", consent: false }, async () => ({ status: "chosen", version: 3 }));
    expect(ownTripNotice("trip-e", change(3))).toBe(true);
    expect(ownTripNotice("trip-e", options("p1"))).toBe(false);
  });
});
