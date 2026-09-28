import { describe, expect, it } from "vitest";
import { defaultRequest } from "./model";
import { testRequestSchema } from "./validation";

describe("test request contract", () => {
  it.each([
    { target: "booking" },
    { version: "production" },
    { fixtureMode: "live" },
    { input: { ...defaultRequest("activity").input, transport: "flight" } },
    { input: { ...defaultRequest("activity").input, durationMinutes: "60" } },
    { unexpected: "unvalidated field" },
  ])("rejects unknown or incorrectly typed contract values", (override) => {
    expect(testRequestSchema.safeParse({ ...defaultRequest("activity"), ...override }).success).toBe(false);
  });

  it("accepts time boundaries and returns a frozen detached input snapshot", () => {
    const request = defaultRequest("activity");
    request.input.time = "00:00";
    const parsed = testRequestSchema.parse(request);
    request.input.time = "23:59";
    expect(testRequestSchema.safeParse(request).success).toBe(true);
    expect(parsed.input.time).toBe("00:00");
    expect(Object.isFrozen(parsed)).toBe(true);
    expect(Object.isFrozen(parsed.input)).toBe(true);
  });
});
