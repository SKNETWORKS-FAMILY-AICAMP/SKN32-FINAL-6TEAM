import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { emptyStream, reduceStream, toIntakeEvent, watchIntake, type IntakeStreamEvent } from "./intake-events";
import { answeringSession } from "./session-kit";

function memory(initial: Record<string, string> = {}) {
  const items = new Map<string, string>(Object.entries(initial));
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({ start(controller) { chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk))); controller.close(); } });
}

const STATE = { status: "reading", stage: "checking", stage_label: "장소·운영시간 확인", revision: 1, fatal_code: null, quiet_seconds: 0.4 };
const ITEM = { id: "0-1", source_id: "s1", index: 1, title: "올리브영", kind: "shopping", day: 1, date: "2026-10-01", starts_at: "11:00", ends_at: "12:30", locked: false, status: null, can_lock: false, place_state: "searching", place: null, candidates_hint: null };

describe("reading the server's progress events", () => {
  it("reads a stage with the state the server attached", () => {
    expect(toIntakeEvent("stage", JSON.stringify({ stage: "checking", label: "장소·운영시간 확인", elapsed: 1.2, state: STATE })))
      .toEqual({ type: "stage", stage: "checking", label: "장소·운영시간 확인", state: { status: "reading", stage: "checking", stage_label: "장소·운영시간 확인", revision: 1, fatal_code: null, quiet_seconds: 0.4 } });
  });

  it("reads the heartbeat, and whether the server says it is slow", () => {
    expect(toIntakeEvent("beat", JSON.stringify({ elapsed: 12, stage: "reading", label: "일정 읽기", slow: true, stage_elapsed: 9 })))
      .toEqual({ type: "beat", stage: "reading", label: "일정 읽기", slow: true, elapsed: 12 });
    expect(toIntakeEvent("beat", JSON.stringify({ stage: "reading" }))).toMatchObject({ slow: false });
  });

  it("reads a line that was read, with the stop found on it", () => {
    const body = { source_id: "s1", no: 3, text: "11시 올리브영", read: true, found: { id: "0-1", index: 1, day: 1, date: "2026-10-01", starts_at: "11:00", title: "올리브영" } };
    expect(toIntakeEvent("line", JSON.stringify(body))).toEqual({
      type: "line", line: { source_id: "s1", no: 3, text: "11시 올리브영", found: { id: "0-1", index: 1, day: 1, date: "2026-10-01", starts_at: "11:00", title: "올리브영" } },
    });
    expect(toIntakeEvent("line", JSON.stringify({ ...body, found: null }))).toMatchObject({ line: { found: null } });
  });

  it("reads a stop that is still being looked up — no status, no place yet", () => {
    expect(toIntakeEvent("item", JSON.stringify(ITEM))).toMatchObject({ type: "item", item: { id: "0-1", status: null, place: null, place_state: "searching", locked: false } });
  });

  it("reads a stop with its place once the lookup finished", () => {
    const place = { name: "올리브영 인사동점", latitude: 37.5741, longitude: 126.9857, source: "kakao", kind: "shopping" };
    const event = toIntakeEvent("item", JSON.stringify({ ...ITEM, status: "review", can_lock: false, place_state: "picked_nearest", place, candidates_hint: 5 }));
    expect(event).toMatchObject({ item: { status: "review", place_state: "picked_nearest", candidates_hint: 5, place: { name: "올리브영 인사동점", latitude: 37.5741, source: "kakao" } } });
  });

  it("reads the booking row the server added (2026-10-03) like any other check line", () => {
    expect(toIntakeEvent("check", JSON.stringify({ item: "0-1", row: "booking", result: "warn", text: "예약했다고 했는데 장소를 모르겠어요" })))
      .toEqual({ type: "check", item: "0-1", line: { row: "booking", result: "warn", text: "예약했다고 했는데 장소를 모르겠어요" } });
  });

  it("reads the booked flag of a stop and the two new place states as they come (server 8b0d4c88)", () => {
    const withBooked = (booked: unknown, state: string) => toIntakeEvent("item", JSON.stringify({ ...ITEM, booked, place_state: state }));
    expect(withBooked(true, "needs_name")).toMatchObject({ item: { booked: true, place_state: "needs_name" } });
    expect(withBooked(false, "needs_choice")).toMatchObject({ item: { booked: false, place_state: "needs_choice" } });
    expect(withBooked(undefined, "found")).toMatchObject({ item: { booked: null } });          // an older server says nothing: not "not booked"
  });

  it("reads a check line, and reads a result word it does not know as 'unknown' — never as fine", () => {
    expect(toIntakeEvent("check", JSON.stringify({ item: "0-1", row: "hours", result: "warn", text: "영업 시간 밖이에요" })))
      .toEqual({ type: "check", item: "0-1", line: { row: "hours", result: "warn", text: "영업 시간 밖이에요" } });
    expect(toIntakeEvent("check", JSON.stringify({ item: "0-1", row: "hours", result: "great", text: "?" }))).toMatchObject({ line: { result: "unknown" } });
  });

  it("drops a check line for a row it does not know, or without the stop it belongs to", () => {
    expect(toIntakeEvent("check", JSON.stringify({ item: "0-1", row: "parking", result: "ok", text: "" }))).toBeNull();
    expect(toIntakeEvent("check", JSON.stringify({ row: "place", result: "ok", text: "" }))).toBeNull();
  });

  it("reads a leg between two stops, keeping a waiting leg waiting", () => {
    const body = { from: "0-0", to: "0-1", day: 1, date: "2026-10-01", status: "review", mode: "subway", mode_label: "지하철 3호선", minutes: 9, km: 0.6, depart: "11:30", arrive: "11:39", slack_min: -39, basis: "timetable",
      summary: "지하철 3호선 9분 · 0.6km", rows: [{ row: "arrival", result: "warn", text: "일정보다 39분 늦어요" }, { row: "weird", result: "ok", text: "x" }] };
    expect(toIntakeEvent("move", JSON.stringify(body))).toMatchObject({ type: "move", move: { from: "0-0", to: "0-1", status: "review", mode: "subway", slack_min: -39, basis: "timetable", rows: [{ row: "arrival", result: "warn" }] } });
    expect(toIntakeEvent("move", JSON.stringify({ from: "0-1", to: "0-2", status: "waiting", mode: null, summary: "장소가 정해지면 경로를 찾아요", rows: [] })))
      .toMatchObject({ move: { status: "waiting", mode: null, minutes: null, depart: null } });
  });

  it("reads the end of the check and the end of the reading", () => {
    expect(toIntakeEvent("done", JSON.stringify({ stage: "review", revision: 1, needs: { items: 1, moves: 1, total: 2 }, ready: false })))
      .toEqual({ type: "done", revision: 1, needs: { items: 1, moves: 1, total: 2 }, ready: false });
    expect(toIntakeEvent("result", JSON.stringify({ state: { ...STATE, status: "review", stage: "review" } }))).toMatchObject({ type: "result", state: { status: "review" } });
    expect(toIntakeEvent("error", JSON.stringify({ code: "stalled", retryable: true, message: "멈춘 것 같아요" }))).toEqual({ type: "error", code: "stalled", message: "멈춘 것 같아요", retryable: true });
  });

  it("reads the server's progress packet — which step, how many done of how many, and what it is at", () => {
    expect(toIntakeEvent("progress", JSON.stringify({ phase: "hours", done: 3, total: 14, current: { id: "0-3", title: "광장시장" } })))
      .toEqual({ type: "progress", progress: { phase: "hours", done: 3, total: 14, current: { id: "0-3", title: "광장시장" } } });
    expect(toIntakeEvent("progress", JSON.stringify({ phase: "moves", done: 0, total: 12 }))).toMatchObject({ progress: { phase: "moves", current: null } });
  });

  it("drops a progress packet that does not make sense instead of guessing", () => {
    for (const body of [{ phase: "weird", done: 1, total: 2 }, { phase: "places", done: 3, total: 2 }, { phase: "places", done: -1, total: 2 },
      { phase: "places", done: 1, total: 0 }, { phase: "places", done: "1", total: 2 }, { phase: "places" }]) {
      expect(toIntakeEvent("progress", JSON.stringify(body)), JSON.stringify(body)).toBeNull();
    }
  });

  it("ignores what it does not use, and a body it cannot read", () => {
    expect(toIntakeEvent("message", "{}")).toBeNull();
    expect(toIntakeEvent("item", "not json")).toBeNull();
    expect(toIntakeEvent("item", JSON.stringify({ title: "id 가 없어요" }))).toBeNull();
    expect(toIntakeEvent("line", JSON.stringify({ source_id: "s1", no: 0, text: "x" }))).toBeNull();
    expect(toIntakeEvent("accepted", JSON.stringify({ op: "intake", state: { status: "weird" } }))).toEqual({ type: "accepted", state: null });
  });
});

describe("building the screen from events", () => {
  const item = (patch: object = {}): IntakeStreamEvent => toIntakeEvent("item", JSON.stringify({ ...ITEM, ...patch })) as IntakeStreamEvent;
  const check = (row: string, result: string, text = ""): IntakeStreamEvent => toIntakeEvent("check", JSON.stringify({ item: "0-1", row, result, text })) as IntakeStreamEvent;

  it("keeps the order things first appeared in, and overwrites a repeat without moving it", () => {
    let state = emptyStream();
    state = reduceStream(state, item({ id: "0-0", title: "경복궁" }));
    state = reduceStream(state, item());
    state = reduceStream(state, check("place", "ok", "찾았어요"));
    state = reduceStream(state, item({ place_state: "found", status: "keep" }));
    expect(state.order).toEqual(["item:0-0", "item:0-1", "check:0-1:place"]);
    expect(state.items["0-1"]).toMatchObject({ place_state: "found", status: "keep" });
  });

  it("gives the same result when everything arrives twice — a reconnect replays the whole state", () => {
    const events = [item({ id: "0-0" }), item(), check("place", "bad", "정하지 못했어요"), check("time", "warn", "30분 겹쳐요")];
    const once = events.reduce(reduceStream, emptyStream());
    const twice = [...events, ...events].reduce(reduceStream, emptyStream());
    expect(twice).toEqual(once);
  });

  it("does not build anything from heartbeats, results and errors — it hands back the same state", () => {
    const state = reduceStream(emptyStream(), item());
    for (const name of ["beat", "result", "error"]) {
      const event = toIntakeEvent(name, JSON.stringify({ stage: "x", state: STATE, code: "e", retryable: true })) as IntakeStreamEvent;
      expect(reduceStream(state, event)).toBe(state);
    }
  });

  it("does not change the state it was given", () => {
    const before = reduceStream(emptyStream(), item());
    const snapshot = JSON.stringify(before);
    reduceStream(before, check("place", "ok"));
    expect(JSON.stringify(before)).toBe(snapshot);
  });

  it("shows the furthest phase's latest packet, whatever order a reconnect replays them in", () => {
    const packet = (phase: string, done: number, total = 14) => toIntakeEvent("progress", JSON.stringify({ phase, done, total })) as IntakeStreamEvent;
    let state = emptyStream();
    expect(state.progress).toBeNull();
    state = reduceStream(state, packet("places", 5));
    state = reduceStream(state, packet("hours", 2));
    expect(state.progress).toMatchObject({ phase: "hours", done: 2 });
    state = reduceStream(state, packet("places", 14));            // the places count finishing late: hours is still the furthest
    expect(state.progress).toMatchObject({ phase: "hours", done: 2 });
    state = reduceStream(state, packet("hours", 2));              // the same packet twice changes nothing
    expect(state.progress).toMatchObject({ phase: "hours", done: 2 });
    state = reduceStream(state, packet("moves", 0, 12));
    expect(state.progress).toMatchObject({ phase: "moves", done: 0, total: 12 });
    const replay = [packet("moves", 4, 12), packet("places", 14), packet("hours", 14)].reduce(reduceStream, emptyStream());
    expect(replay.progress).toMatchObject({ phase: "moves", done: 4 });          // the replay brings them in any order
  });

  it("never counts back inside a phase, but takes a new count (another source's places) as it comes", () => {
    const packet = (done: number, total: number) => toIntakeEvent("progress", JSON.stringify({ phase: "places", done, total })) as IntakeStreamEvent;
    let state = [packet(5, 14), packet(3, 14)].reduce(reduceStream, emptyStream());
    expect(state.progress).toMatchObject({ done: 5, total: 14 });                // an older packet of the same count
    state = reduceStream(state, packet(1, 6));                                   // the second source starts its own count
    expect(state.progress).toMatchObject({ done: 1, total: 6 });
  });

  it("notes the end of the check with how many things need the customer", () => {
    const state = reduceStream(emptyStream(), { type: "done", revision: 1, needs: { items: 1, moves: 1, total: 2 }, ready: false });
    expect(state.done).toEqual({ revision: 1, needs: { items: 1, moves: 1, total: 2 }, ready: false });
  });
});

describe("watching a plan being read", () => {
  let calls: { url: string; init: RequestInit }[];
  let reply: () => Response;

  beforeEach(() => {
    calls = [];
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
    vi.stubGlobal("fetch", answeringSession(async (url, init) => { calls.push({ url, init }); return reply(); }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("asks for an event stream with the session cookie — no key header, nothing secret in the address", async () => {
    reply = () => new Response(streamOf([": ping\n\n"]), { status: 200, headers: { "Content-Type": "text/event-stream" } });
    await watchIntake("i 1", "ko", () => undefined, new AbortController().signal);
    expect(calls[0].url).toMatch(/\/v1\/web\/trip-intakes\/i%201\/events$/);
    expect(calls[0].init.credentials).toBe("include");
    expect(calls[0].init.headers).toMatchObject({ Accept: "text/event-stream" });
    expect(calls[0].init.headers).not.toHaveProperty("X-User-Key");
  });

  it("hands over the events as they come, across chunk boundaries, and ends when the stream ends", async () => {
    reply = () => new Response(streamOf([
      "event: accepted\ndata: {\"op\":\"intake\",\"state\":" + JSON.stringify(STATE) + "}\n\n: ping\n\nevent: li",
      "ne\ndata: {\"source_id\":\"s1\",\"no\":1,\"text\":\"10시 경복궁\",\"read\":true,\"found\":null}\n\n",
      "event: done\ndata: {\"revision\":1,\"needs\":{\"items\":0,\"moves\":0},\"ready\":true}\n\nevent: result\ndata: {\"state\":" + JSON.stringify({ ...STATE, status: "review" }) + "}\n\n",
    ]), { status: 200 });
    const seen: string[] = [];
    const end = await watchIntake("i1", "ko", (event) => seen.push(event.type), new AbortController().signal);
    expect(seen).toEqual(["accepted", "line", "done", "result"]);
    expect(end).toBe("closed");
  });

  it("says 'unsupported' when this server has no stream, so the screen polls instead", async () => {
    for (const status of [404, 405]) {
      reply = () => new Response("", { status });
      expect(await watchIntake("i1", "ko", () => undefined, new AbortController().signal)).toBe("unsupported");
    }
  });

  it("says 'failed' for a refusal before the stream opened and for a dropped connection — never throws", async () => {
    reply = () => new Response(JSON.stringify({ error: { code: "too_many_streams" } }), { status: 429 });
    expect(await watchIntake("i1", "ko", () => undefined, new AbortController().signal)).toBe("failed");
    vi.stubGlobal("fetch", async () => { throw new TypeError("network"); });
    expect(await watchIntake("i1", "ko", () => undefined, new AbortController().signal)).toBe("failed");
  });

  it("says 'closed' when the screen itself stopped watching", async () => {
    const stop = new AbortController();
    stop.abort();
    vi.stubGlobal("fetch", async () => { throw new DOMException("aborted", "AbortError"); });
    expect(await watchIntake("i1", "ko", () => undefined, stop.signal)).toBe("closed");
  });
});
