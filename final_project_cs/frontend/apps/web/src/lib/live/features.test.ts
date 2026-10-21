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
    expect(knownFeatures()).toEqual({ guardian: true });
    expect(guardianSwitchedOff()).toBe(false);
  });

  it("a plain false switches the Course Keeper off", async () => {
    reply = async () => json({ guardian: false });
    await expect(loadFeatures("ko")).resolves.toEqual({ guardian: false });
    expect(guardianSwitchedOff()).toBe(true);
  });

  it.each([
    ["an older server without the read (404)", async () => json({ detail: "Not Found" }, 404)],
    ["no connection", async () => { throw new TypeError("Failed to fetch"); }],
    ["an answer that is not true or false", async () => json({ guardian: "off" })],
  ])("%s: as before (on)", async (_case, answer) => {
    reply = answer;
    await expect(loadFeatures("ko")).resolves.toEqual({ guardian: true });
    expect(guardianSwitchedOff()).toBe(false);
  });

  it("nothing is held back before the answer", () => {
    expect(knownFeatures()).toBeNull();
    expect(guardianSwitchedOff()).toBe(false);
  });
});
