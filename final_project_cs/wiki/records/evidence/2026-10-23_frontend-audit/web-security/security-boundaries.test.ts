/** Audit probes: passing means the described unsafe current behavior was reproduced, not that it is fixed. */
import { afterEach, expect, it, vi } from "vitest";
import { api, currentSession, resetSessionState, sessionOf, takeSession } from "../../../../../frontend/apps/web/src/lib/live/client";
import { readRouteShapes } from "../../../../../frontend/apps/web/src/lib/live/route-shapes";
import { toMapLines } from "../../../../../frontend/apps/web/src/features/map/route-lines";
import { readFileSync } from "node:fs";

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const account = (csrf: string) => sessionOf({ kind: "member", csrf_token: csrf })!;
function browser() {
  vi.stubGlobal("window", { localStorage: { getItem: () => null, removeItem: () => undefined }, dispatchEvent: () => true });
}
afterEach(() => { resetSessionState(); vi.unstubAllGlobals(); });

it("reproduces: a write started in account A is replayed with account B's CSRF token", async () => {
  browser(); takeSession(account("csrf-account-a"));
  const writes: RequestInit[] = [];
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    if (url.endsWith("/auth/me")) return response({ kind: "member", csrf_token: "csrf-account-b" });
    writes.push(init);
    return writes.length === 1 ? response({ error: { code: "csrf_failed" } }, 403) : response({ updated: true });
  });
  await api("/v1/web/profile", "ko", { method: "PUT", body: JSON.stringify({ discord_webhook_url: "A's channel" }) });
  expect(writes).toHaveLength(2);
  expect(writes[0].headers).toMatchObject({ "X-CSRF-Token": "csrf-account-a" });
  expect(writes[1].headers).toMatchObject({ "X-CSRF-Token": "csrf-account-b" });
  expect(writes[1].body).toEqual(writes[0].body);
});

it("reproduces: an old request's 401 clears a newer signed-in session", async () => {
  browser(); takeSession(account("csrf-old"));
  let reply!: (value: Response) => void;
  vi.stubGlobal("fetch", () => new Promise<Response>(resolve => { reply = resolve; }));
  const request = api("/v1/web/profile", "ko").catch(error => error);
  await vi.waitFor(() => expect(reply).toBeTypeOf("function"));
  takeSession(account("csrf-new"));
  reply(response({ error: { code: "unauthenticated" } }, 401));
  expect((await request).code).toBe("session_expired");
  expect(currentSession()).toBeNull();
});

it("reproduces: server route text reaches Leaflet's actual HTML assignment without escaping", () => {
  const title = '<img src="x" onerror="document.body.dataset.audit=1">';
  const routes = readRouteShapes({ shapes: [{ from_item_id: "a", to_item_id: "b", item_id: "move", from: title, to: "도착", mode: "walk", source: "straight_line", line: { type: "LineString", coordinates: [[126.97, 37.56], [126.98, 37.57]] } }] });
  const line = toMapLines(routes.shapes)[0];
  expect(line.title).toContain(title);
  const adapter = readFileSync(new URL("../../../../../frontend/apps/web/src/features/map/providers/osm.ts", import.meta.url), "utf8");
  expect(adapter).toContain(".bindTooltip(line.title, { sticky: true })");
  const leaflet = readFileSync(new URL("../../../../../frontend/apps/web/node_modules/leaflet/src/layer/DivOverlay.js", import.meta.url), "utf8");
  const source = leaflet.match(/_updateContent: function \(\) \{([\s\S]*?)\n\t\},/)?.[1];
  expect(source).toBeTruthy();
  const target = { innerHTML: "" };
  new Function(source!).call({ _content: line.title, _contentNode: target, fire: () => undefined });
  expect(target.innerHTML).toContain(title);
});
