import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "@/lib/live/client";
import { answeringSession } from "@/lib/live/session-kit";
import { noConsents, requiredAgreed } from "./consent-model";
import { consentsSynced, forgetConsents, readConsents, replaceConsents } from "./consent-store";
import { adoptServer, reconcileConsents, saveConsents, sendConsents } from "./consent-sync";
import { TERMS_VERSION } from "./terms-content";
import { resetLiveTerms, termsVersion } from "./terms-live";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const row = (code: string, agreed: boolean, version = TERMS_VERSION) => ({ code, agreed, version, agreed_at: "2026-10-05T09:00:00+09:00" });
const requiredOn = [row("service_terms", true), row("privacy", true)];
const RETENTION_PATH = "/v1/web/legal/retention";
/** The public retention read (`terms-live.ts`) answered apart from the consent calls: an older server without it (404) unless a test sets `retention`. */
let retention: (() => Response) | null = null;
const legal = (inner: (url: string, init: RequestInit) => Promise<Response>) => async (url: string, init: RequestInit) =>
  new URL(url).pathname === RETENTION_PATH ? (retention ? retention() : json({ error: { code: "not_found", message: "no" } }, 404)) : inner(url, init);

describe("the browser's copy of the consents and the server's record", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: Response[];

  beforeEach(() => {
    const storage = new Map<string, string>();
    vi.stubGlobal("window", {
      localStorage: { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => { storage.set(key, value); }, removeItem: (key: string) => { storage.delete(key); } },
      dispatchEvent: () => true, addEventListener: () => {}, removeEventListener: () => {},
    });
    calls = [];
    replies = [];
    retention = null;
    resetLiveTerms();
    vi.stubGlobal("fetch", answeringSession(legal(async (url, init) => { calls.push({ url, init }); return replies.shift() ?? json({}); }), { kind: "guest" }));
    forgetConsents();
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  const consentCalls = () => calls.filter((call) => new URL(call.url).pathname === "/v1/web/consents");

  it("saves what the customer chose at once in the browser, and records it on the server with the fingerprint of every text shown", async () => {
    replies.push(json({ current_version: TERMS_VERSION, required: ["service_terms", "privacy"], ok: true, items: [...requiredOn, row("location", true)] }));
    const next = { ...noConsents(), service_terms: true, privacy: true, location: true };
    const result = saveConsents(next, "ko");
    expect(readConsents().location).toBe(true);                                     // the screen follows at once, before the server answers
    expect(await result).toBe("recorded");
    const [post] = consentCalls();
    expect(post.init.method).toBe("POST");
    const body = JSON.parse(String(post.init.body)) as { version: string; items: { code: string; agreed: boolean; text_sha256: string }[] };
    expect(body.version).toBe(TERMS_VERSION);
    expect(body.items.map((item) => [item.code, item.agreed])).toEqual([["service_terms", true], ["privacy", true], ["sensitive", false], ["location", true], ["alert_channel", false]]);
    for (const item of body.items) expect(item.text_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(consentsSynced()).toBe(true);
  });

  it("keeps the copy and says it is not recorded when the server cannot be reached - it is sent again later", async () => {
    replies.push(new Response("boom", { status: 500 }));
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true }, "2026-10-05T09:00:00Z", false);
    expect(await sendConsents("ko")).toBe("failed");
    expect(requiredAgreed(readConsents())).toBe(true);
    expect(consentsSynced()).toBe(false);
  });

  it("works with an older server that has no consent record (404): the copy is all there is, and it counts as sent", async () => {
    replies.push(json({ detail: "Not Found" }, 404));
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true });
    expect(await sendConsents("ko")).toBe("local_only");
    expect(consentsSynced()).toBe(true);
  });

  it("says the page is out of date when the server's terms are a newer version (409)", async () => {
    replies.push(json({ error: { code: "terms_version_changed", message: "약관 버전이 바뀌었어요" } }, 409));
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true });
    expect(await sendConsents("ko")).toBe("outdated");
  });

  it("lets the server's record win: a withdrawal made on another device closes this one", async () => {
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true }, "2026-10-05T09:00:00Z", true);
    replies.push(json({ current_version: TERMS_VERSION, required: ["service_terms", "privacy"], ok: false, items: [row("service_terms", true), row("privacy", false)] }));
    expect(await reconcileConsents("ko")).toBe("needs");
    expect(readConsents().privacy).toBe(false);
    expect(requiredAgreed(readConsents())).toBe(false);
  });

  it("takes the server's record in as it is - items it does not mention, or from an older version, are not agreed", () => {
    adoptServer({ currentVersion: TERMS_VERSION, required: ["service_terms", "privacy"], ok: true, items: [
      { code: "service_terms", agreed: true, version: TERMS_VERSION, agreedAt: "2026-10-05T09:00:00+09:00" },
      { code: "privacy", agreed: true, version: TERMS_VERSION, agreedAt: null },
      { code: "location", agreed: true, version: "2025-01-01", agreedAt: null },
    ] });
    expect(readConsents()).toEqual({ ...noConsents(), service_terms: true, privacy: true });
    expect(consentsSynced()).toBe(true);
  });

  it("sends the copy when the server has no record of this terms version yet (the customer chose offline)", async () => {
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true }, "2026-10-05T09:00:00Z", false);
    replies.push(json({ current_version: TERMS_VERSION, required: ["service_terms", "privacy"], ok: false, items: [row("service_terms", true, "2025-01-01")] }));   // GET: only an older version
    replies.push(json({ current_version: TERMS_VERSION, required: ["service_terms", "privacy"], ok: true, items: requiredOn }));                                    // POST
    expect(await reconcileConsents("ko")).toBe("ok");
    expect(consentCalls().map((call) => call.init.method ?? "GET")).toEqual(["GET", "POST"]);
  });

  it("asks for the terms when nothing is agreed and the server has nothing - and does not ask a visitor with no session (that would make a user)", async () => {
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return json({}); }, { has: false }));
    expect(await reconcileConsents("ko")).toBe("needs");
    expect(consentCalls()).toHaveLength(0);
  });

  it("does not mistake a server on another terms version for a record: the page is out of date", async () => {
    replies.push(json({ current_version: "2099-01-01", required: ["service_terms", "privacy"], ok: false, items: [] }));
    expect(await reconcileConsents("ko")).toBe("outdated");
  });

  it("puts the customer's latest choice after a running read of the server, never under it", async () => {
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true }, "2026-10-05T09:00:00Z", true);
    let release: (response: Response) => void = () => {};
    const slowGet = new Promise<Response>((resolve) => { release = resolve; });
    vi.stubGlobal("fetch", answeringSession(legal(async (url, init) => {
      calls.push({ url, init });
      return init.method === "POST" ? json({ current_version: TERMS_VERSION, required: ["service_terms", "privacy"], ok: true, items: [...requiredOn, row("location", true)] }) : slowGet;
    }), { kind: "guest" }));
    const reading = reconcileConsents("ko");                                            // the read of the server is under way (and slow)
    const saving = saveConsents({ ...noConsents(), service_terms: true, privacy: true, location: true }, "ko");
    release(json({ current_version: TERMS_VERSION, required: ["service_terms", "privacy"], ok: true, items: requiredOn }));   // it brings the OLD record
    await Promise.all([reading, saving]);
    expect(readConsents().location).toBe(true);                                         // the choice made while it was reading survives
  });

  // `[2026-10-07]` An operator can change a retention period on the admin screen; the server's terms version then becomes `<base>+ret<N>`.
  const SERVER_VERSION = `${TERMS_VERSION}+ret2`;
  const retentionBody = { revision: 2, terms_version: SERVER_VERSION, cells: [
    { key: "member_idle_days", text_ko: "회원이 지우거나 탈퇴를 요청할 때까지, 마지막 이용 후 2년이 지나면 파기", text_en: "Kept until you delete it or ask to withdraw, and destroyed once 2 years have passed since your last use" },
    { key: "a_cell_this_page_does_not_know", text_ko: "모름", text_en: "unknown" },
  ] };

  it("sends the consents with the server's terms version and the fingerprint of the text with the server's retention wording", async () => {
    retention = () => json(retentionBody);
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true }, "2026-10-07T09:00:00Z", false);
    const fingerprintsBefore = await import("./consent-sync").then((sync) => sync.choicesOf(readConsents()));
    replies.push(json({ current_version: SERVER_VERSION, required: ["service_terms", "privacy"], ok: true, items: [row("service_terms", true, SERVER_VERSION), row("privacy", true, SERVER_VERSION)] }));
    expect(await sendConsents("ko")).toBe("recorded");
    expect(termsVersion()).toBe(SERVER_VERSION);
    const body = JSON.parse(String(consentCalls()[0].init.body)) as { version: string; items: { code: string; text_sha256: string }[] };
    expect(body.version).toBe(SERVER_VERSION);
    const privacyBefore = fingerprintsBefore.find((choice) => choice.code === "privacy")!.textSha256;
    expect(body.items.find((item) => item.code === "privacy")!.text_sha256).not.toBe(privacyBefore);   // the privacy text carries the member period: it changed
    expect(consentsSynced()).toBe(true);
  });

  it("keeps the agreed copy while the server version is not read yet, but asks again once the server says the terms moved on", async () => {
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true }, "2026-10-07T09:00:00Z", true);
    expect(requiredAgreed(readConsents())).toBe(true);
    retention = () => json(retentionBody);
    replies.push(json({ current_version: SERVER_VERSION, required: ["service_terms", "privacy"], ok: false, items: [row("service_terms", true), row("privacy", true)] }));
    expect(await reconcileConsents("ko")).toBe("needs");                                // the old agreement was for the old wording
    expect(requiredAgreed(readConsents())).toBe(false);
  });

  it("reads the terms again when the server refuses the version (409), so the next screen shows the new wording", async () => {
    replaceConsents({ ...noConsents(), service_terms: true, privacy: true }, "2026-10-07T09:00:00Z", false);
    await sendConsents("ko").catch(() => undefined);                                    // first read: an older server answers 404, the page keeps its own version
    retention = () => json(retentionBody);
    replies.push(json({ error: { code: "terms_version_changed", message: "new terms" } }, 409));
    expect(await sendConsents("ko")).toBe("outdated");
    expect(termsVersion()).toBe(SERVER_VERSION);
  });
});
