import { describe, expect, it } from "vitest";
import { diningEntry, generateWithDiningLinks, openDiningIntake } from "./start";
import type { submitIntake } from "@/lib/live/intake";
import type { createDiningDraft } from "@/lib/live/social-dining";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";

describe("explicit restaurant link entry keeps existing input separate", () => {
  it("opts into the empty intake only from the restaurant entry URL", () => {
    expect(diningEntry("https://tripilot.test/intakes/i1?dining=1")).toBe(true);
    expect(diningEntry("https://tripilot.test/intakes/i1")).toBe(false);
    expect(diningEntry("https://tripilot.test/intakes/i1?dining=0")).toBe(false);
  });
  it("creates an empty intake with the human-check token, leaving other input out of the request", async () => {
    const sent: unknown[] = [];
    const submit: typeof submitIntake = async (...args) => { sent.push(args); return { intake_id: "i /1" }; };
    expect(await openDiningIntake("ko", "human-token", submit)).toBe("/intakes/i%20%2F1?dining=1");
    expect(sent).toEqual([["", [], "ko", "human-token"]]);
  });
  it("initial generation stays on the same intake for review before restaurant changes or registration", async () => {
    const sent: unknown[] = [];
    const draft = { intake_id: "same-intake", revision: 9, status: "review", trip_id: null } as ReviewedIntakeView;
    const plan: typeof createDiningDraft = async (...args) => { sent.push(args); return draft; };
    expect(await generateWithDiningLinks("same-intake", 8, { start_date: "2026-10-20", days: 3, party_size: 2 }, "en", undefined, plan)).toEqual(draft);
    expect(sent).toEqual([["same-intake", 8, { start_date: "2026-10-20", days: 3, party_size: 2 }, "en", undefined]]);
  });
});
