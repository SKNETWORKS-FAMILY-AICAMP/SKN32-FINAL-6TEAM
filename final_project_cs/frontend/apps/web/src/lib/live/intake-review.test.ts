import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { itemEdit } from "./intake-edits";
import { autofixIntake, getCandidates, getPlacePhotos, pickedPlace, revalidateIntake, searchPlaces, type CandidatePlace } from "./intake-review";
import { answeringSession } from "./session-kit";

function memory(initial: Record<string, string> = {}) {
  const items = new Map<string, string>(Object.entries(initial));
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}

const ITEM = { source_id: "s1", index: 2 };

describe("the edits the check screen sends", () => {
  it("points at the stop by its source and its place in the read values", () => {
    expect(itemEdit.lock(ITEM, true)).toEqual({ source_id: "s1", field: "items[2].locked", value: true });
    expect(itemEdit.remove(ITEM, true)).toEqual({ source_id: "s1", field: "items[2].removed", value: true });
    expect(itemEdit.remove(ITEM, false)).toEqual({ source_id: "s1", field: "items[2].removed", value: false });
    expect(itemEdit.starts(ITEM, "11:45")).toEqual({ source_id: "s1", field: "items[2].starts_at", value: "11:45" });
    expect(itemEdit.ends(ITEM, "12:15")).toEqual({ source_id: "s1", field: "items[2].ends_at", value: "12:15" });
  });

  it("sends a place in the three shapes the server takes", () => {
    expect(itemEdit.placeByName(ITEM, "경복궁").value).toEqual({ name: "경복궁" });
    expect(itemEdit.placeNone(ITEM).value).toEqual({ none: true });
    const picked = { name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791, source: "kakao" as const };
    expect(itemEdit.placePicked(ITEM, picked)).toEqual({ source_id: "s1", field: "items[2].place", value: picked });
  });
});

describe("picking a candidate", () => {
  const place = (patch: Partial<CandidatePlace> = {}): CandidatePlace => ({
    name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791, source: "kakao", kind: "shopping",
    content_id: null, content_type_id: null, address: "서울 종로구 종로1길 50", category: "화장품", ref: null, ...patch,
  });

  it("sends back what the server gave: name, coordinates, where it came from", () => {
    expect(pickedPlace(place())).toEqual({ name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791, source: "kakao", kind: "shopping" });
  });

  it("carries the tourism-organization number only when there is one", () => {
    expect(pickedPlace(place({ source: "tour_api", content_id: "126508" }))).toMatchObject({ source: "tour_api", content_id: "126508" });
    expect(pickedPlace(place())).not.toHaveProperty("content_id");
  });

  it("reads a source it does not know as a search result", () => {
    expect(pickedPlace(place({ source: "something_new" }))).toMatchObject({ source: "search" });
    expect(pickedPlace(place({ source: null }))).toMatchObject({ source: "search" });
  });

  it("cannot be picked without coordinates — the server takes a picked place by its coordinates", () => {
    expect(pickedPlace(place({ latitude: null }))).toBeNull();
    expect(pickedPlace(place({ longitude: null }))).toBeNull();
  });
});

describe("the calls of the check screen", () => {
  let calls: { url: string; init: RequestInit }[];

  beforeEach(() => {
    calls = [];
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return new Response("{}", { status: 200 }); }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  const path = () => new URL(calls[0].url);

  it("asks for the other places of one stop at one revision", async () => {
    await getCandidates("i1", ITEM, 3, "ko");
    expect(path().pathname).toBe("/v1/web/trip-intakes/i1/candidates");
    expect(Object.fromEntries(path().searchParams)).toEqual({ source_id: "s1", index: "2", revision: "3" });
    expect(calls[0].init.credentials).toBe("include");
    expect(calls[0].init.headers).not.toHaveProperty("X-User-Key");
  });

  it("searches places by name for one stop, encoding what was typed", async () => {
    await searchPlaces("i1", ITEM, 3, "올리브영 & 명동", "ko");
    expect(path().pathname).toBe("/v1/web/trip-intakes/i1/place-search");
    expect(path().searchParams.get("q")).toBe("올리브영 & 명동");
    expect(path().searchParams.get("revision")).toBe("3");
  });

  it("can drop a search that the customer typed past", async () => {
    const stop = new AbortController();
    stop.abort();
    vi.stubGlobal("fetch", answeringSession(async (_url, init) => { if (init.signal?.aborted) throw new DOMException("aborted", "AbortError"); return new Response("{}"); }));
    await expect(searchPlaces("i1", ITEM, 3, "올", "ko", stop.signal)).rejects.toMatchObject({ code: "network" });
  });

  it("asks for a place's registered photos by its reference", async () => {
    await getPlacePhotos("tour:132183", "ko");
    expect(path().pathname).toBe("/v1/web/places/photos");
    expect(path().searchParams.get("ref")).toBe("tour:132183");
  });

  it("sends the revision with the whole-plan actions", async () => {
    await autofixIntake("i1", 4, "ko");
    await revalidateIntake("i1", 5, "ko");
    expect(calls.map((call) => [new URL(call.url).pathname, call.init.method, call.init.body])).toEqual([
      ["/v1/web/trip-intakes/i1/autofix", "POST", JSON.stringify({ revision: 4 })],
      ["/v1/web/trip-intakes/i1/revalidate", "POST", JSON.stringify({ revision: 5 })],
    ]);
  });
});
