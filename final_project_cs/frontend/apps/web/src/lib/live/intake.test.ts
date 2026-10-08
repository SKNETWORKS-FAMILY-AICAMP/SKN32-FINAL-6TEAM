import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SURVEY_VERSION } from "@/features/onboarding/payload";
import { resetSessionState } from "./client";
import { confirmIntake, planIntake, submitIntake } from "./intake";
import { answeringSession } from "./session-kit";

function memory() {
  const items = new Map<string, string>();
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}

const CONFIRMED = { status: "confirmed", trip: { trip_id: "c287a5e9-7707-408c-9ea9-456cde20cbec" } };
const SURVEY = { version: SURVEY_VERSION, pace: "relaxed" } as const;

describe("live intake requests carry the onboarding survey", () => {
  let bodies: Record<string, unknown>[];

  beforeEach(() => {
    bodies = [];
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
    vi.stubGlobal("fetch", answeringSession(async (_url, init) => {
      bodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return new Response(JSON.stringify(CONFIRMED), { status: 200 });
    }, { has: false }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("sends the survey with /confirm when the customer finished the questions", async () => {
    await confirmIntake("i1", 3, "ko", SURVEY);
    expect(bodies).toEqual([{ revision: 3, survey: SURVEY }]);
  });

  it("sends no survey field at all when there is none — the server only accepts a whole, valid one", async () => {
    await confirmIntake("i1", 3, "ko");
    expect(bodies).toEqual([{ revision: 3 }]);
    expect(bodies[0]).not.toHaveProperty("survey");
  });

  it("sends the survey with /plan next to the plan conditions", async () => {
    await planIntake("i1", 2, { start_date: "2026-10-01", days: 2, party_size: 1, keep_read_items: true, survey: SURVEY }, "ko");
    expect(bodies).toEqual([{ revision: 2, start_date: "2026-10-01", days: 2, party_size: 1, keep_read_items: true, survey: SURVEY }]);
  });
});

describe("plan submission carries the human-check token", () => {
  let forms: FormData[];

  beforeEach(() => {
    forms = [];
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
    vi.stubGlobal("fetch", answeringSession(async (_url, init) => {
      forms.push(init.body as FormData);
      return new Response(JSON.stringify({ intake_id: "i1" }), { status: 202 });
    }, { has: false }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("adds turnstile_token next to the plan text when the check gave one", async () => {
    await submitIntake("09:00 경복궁", [], "ko", "tok-123");
    expect(forms[0].get("text")).toBe("09:00 경복궁");
    expect(forms[0].get("turnstile_token")).toBe("tok-123");
  });

  it("sends no token field at all when the check is off", async () => {
    await submitIntake("09:00 경복궁", [], "ko");
    await submitIntake("09:00 경복궁", [], "ko", null);
    expect(forms.map((form) => form.has("turnstile_token"))).toEqual([false, false]);
  });
});
