import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { guardianSwitchedOff, knownFeatures, loadFeatures, resetFeatures } from "./features";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe("the operator's switches, read without a session (`GET /v1/web/features`)", () => {
  let urls: string[];
  let reply: () => Promise<Response>;

  beforeEach(() => {
    urls = [];
    reply = async () => json({ guardian: true });
    vi.stubGlobal("fetch", async (url: string) => { urls.push(String(url)); return reply(); });
  });
  afterEach(() => { vi.unstubAllGlobals(); resetFeatures(); resetSessionState(); });

  it("asks once per page and only that — asking makes no session", async () => {
    await Promise.all([loadFeatures("ko"), loadFeatures("ko")]);
    await loadFeatures("en");
    expect(urls).toHaveLength(1);
    expect(urls[0]).toMatch(/\/v1\/web\/features$/);
    expect(knownFeatures()).toEqual({ guardian: true, riskPanel: true, planInputExtras: true });
    expect(guardianSwitchedOff()).toBe(false);
  });

  it("a plain false switches the Course Keeper off", async () => {
    reply = async () => json({ guardian: false });
    await expect(loadFeatures("ko")).resolves.toEqual({ guardian: false, riskPanel: true, planInputExtras: true });
    expect(guardianSwitchedOff()).toBe(true);
  });

  // `[2026-10-22 사용자 지시]` The plan check's risk panel follows its own switch, apart from the Course Keeper.
  it("a plain false of risk_panel hides only the plan check's risk panel", async () => {
    reply = async () => json({ guardian: true, risk_panel: false });
    await expect(loadFeatures("ko")).resolves.toEqual({ guardian: true, riskPanel: false, planInputExtras: true });
    expect(guardianSwitchedOff()).toBe(false);
  });

  // `[2026-10-25 사용자 지시 — ST4F-739]` The plan screen's extra panels follow their own switch.
  it("a plain false of plan_input_extras hides only the plan screen's extra panels", async () => {
    reply = async () => json({ guardian: true, risk_panel: true, plan_input_extras: false });
    await expect(loadFeatures("ko")).resolves.toEqual({ guardian: true, riskPanel: true, planInputExtras: false });
    expect(guardianSwitchedOff()).toBe(false);
  });

  it.each([
    ["an older server without the read (404)", async () => json({ detail: "Not Found" }, 404)],
    ["no connection", async () => { throw new TypeError("Failed to fetch"); }],
    ["an answer that is not true or false", async () => json({ guardian: "off" })],
  ])("%s: as before (on)", async (_case, answer) => {
    reply = answer;
    await expect(loadFeatures("ko")).resolves.toEqual({ guardian: true, riskPanel: true, planInputExtras: true });
    expect(guardianSwitchedOff()).toBe(false);
  });

  it("nothing is held back before the answer", () => {
    expect(knownFeatures()).toBeNull();
    expect(guardianSwitchedOff()).toBe(false);
  });
});
