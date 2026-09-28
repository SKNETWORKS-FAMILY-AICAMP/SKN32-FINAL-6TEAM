// A stand-in for the triPilot server's web API (`/v1/web/*`), for testing the live screens end to end.
//
// ★Why a stand-in: registering on the real server sends a notice to the team's chat channel and leaves data behind.
//   This server answers with the same shapes (read from `final_project_cs/app/modules/travel_ops/trip_api.py`) and
//   keeps every request it received, so a test can check what the screen actually sent.
//
// Test control (never part of the real API):
//   POST /__test/reset               back to the default scenario, clears the request log
//   POST /__test/scenario {…}        change the scenario (see DEFAULTS)
//   GET  /__test/log                 every request received since the last reset
import { createServer } from "node:http";

const PORT = Number(process.env.STUB_PORT ?? 8043);
const TRIP_ID = "11111111-2222-3333-4444-555555555555";
const INTAKE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const DEFAULTS = {
  // "one" = the customer already has a trip, "none" = first visit
  trips: "one",
  // proposals the server is waiting on: "open" | "none"
  proposals: "none",
  // answer to choosing a proposal: "ok" | "conflict"
  choose: "ok",
  // chat: "answered" (server gives an answer) | "escalated_bare" (an old server: escalated with no answer)
  chat: "answered",
  // intake once read: "items" (has stops, ready) | "empty_plan" (nothing read, the customer asks us to plan)
  intake: "items",
  // how many polls answer "reading" before the review is ready
  readingPolls: 1,
  // trip warnings / notices to show
  warnings: "some",
  notices: "some",
  // make one call fail with a 500: "trips" | "proposals" | "notices" | "confirm" | "" (none)
  fail: "",
  // "stale": the server refuses an edit because the plan moved on (409 stale_revision)
  edits: "ok",
  // "limited": too many new keys from this address (429 too_many_sessions)
  session: "ok",
  // "missing": there is no such trip
  trip: "ok",
  // how long planning takes to answer, in ms (the real server reads opening hours: up to about a minute)
  planDelay: 0,
};

let scenario;
let log;
let sessions;
let polls;
let confirmed;
let keys;

function reset() {
  scenario = { ...DEFAULTS };
  log = [];
  sessions = 0;
  polls = 0;
  confirmed = false;
  keys = new Set(["acop_u_known"]);
}
reset();

const at = (hour, minute = 0, day = 1) => `2026-10-0${day}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00+09:00`;

function tripView() {
  return {
    trip_id: TRIP_ID, customer_id: "cust-1", title: "내 여행", locale: "ko", party_size: 2, version: scenario.proposals === "open" ? 2 : 1,
    items: [
      { item_id: "i-a", seq: 1, kind: "dining", title: "아침 식당", place: "아침 식당", starts_at: at(8), ends_at: at(9), changed: false, other_options: [], customer_pinned: false, lat: 37.575, lon: 126.98, booked: false },
      { item_id: "i-b", seq: 2, kind: "activity", title: "경복궁 관람", place: "경복궁", starts_at: at(9, 30), ends_at: at(11), changed: false, other_options: [{ key: "alt-1", name: "창덕궁" }], customer_pinned: true, lat: 37.5796, lon: 126.977, booked: true },
      { item_id: "i-m", seq: 3, kind: "mobility", title: "경복궁 관람 → 점심 식당", place: null, starts_at: at(11, 10), ends_at: at(11, 30), changed: false, other_options: [], customer_pinned: false, lat: null, lon: null, booked: false },
      { item_id: "i-c", seq: 4, kind: "dining", title: "점심 식당", place: "점심 식당", starts_at: at(12), ends_at: at(13), changed: false, other_options: [], customer_pinned: false, lat: 37.57, lon: 126.99, booked: false },
      { item_id: "i-d", seq: 5, kind: "activity", title: "둘째 날 박물관", place: "박물관", starts_at: at(10, 0, 2), ends_at: at(11, 30, 2), changed: false, other_options: [], customer_pinned: false, lat: 37.52, lon: 126.98, booked: false },
    ],
    history: [
      { version: 1, reason: "created", causes: [], at: at(7) },
      ...(scenario.proposals === "open" ? [{ version: 2, reason: "closed", causes: [{ category: "place", summary: "점심 식당이 문을 닫았어요." }], at: at(11, 40) }] : []),
    ],
    plan_url: `http://127.0.0.1:${PORT}/plan/${TRIP_ID}?t=stub`,
    density: [],
    warnings: scenario.warnings === "some" ? [{ code: "density_exceeded", date: "2026-10-01", reason: "하루가 빡빡해요", remedy: "일정을 줄이세요" }] : [],
  };
}

function proposals() {
  if (scenario.proposals !== "open") return { trip_id: TRIP_ID, proposals: [] };
  return {
    trip_id: TRIP_ID,
    proposals: [{
      proposal_id: "p-1", item_id: "i-c", base_version: 2, reason: "closed", protected_by: null, safety: false, status: "open",
      expires_at: at(23), chosen_key: null, causes: [],
      options: [{ key: "o-1", rank: 1, name: "대체 식당 A", starts_at: at(12, 30) }, { key: "o-2", rank: 2, name: "대체 식당 B", starts_at: at(12, 40) }],
    }],
  };
}

function notices() {
  if (scenario.notices !== "some") return { notices: [] };
  const out = [{ key: "n-1", type: "change_notice", kind: null, text: "여행 일정이 준비되었습니다 — 내 여행.", version: 1, proposal_id: null, options: null, delivery: "sent", at: at(7) },
    { key: "n-2", type: "guidance", kind: "day_start", text: "오늘 첫 일정은 08:00 아침 식당이에요.", version: 1, proposal_id: null, options: null, delivery: "sent", at: at(7, 30) }];
  if (scenario.proposals === "open") out.push({ key: "n-3", type: "proposal_request", kind: null, text: "점심 식당이 문을 닫았어요. 대체 식당을 골라 주세요.", version: 2, proposal_id: "p-1", options: [], delivery: "sent", at: at(11, 41) });
  return { notices: out };
}

function intakeView(revision) {
  const base = { intake_id: INTAKE_ID, revision, fatal: null, trip_id: confirmed ? TRIP_ID : null, needs_review: [] };
  if (polls <= scenario.readingPolls) return { ...base, status: "reading", stage: "reading", stage_label: "계획을 읽는 중이에요", sources: [], check: null };
  if (scenario.intake === "fatal") return { ...base, status: "fatal", stage: "fatal", stage_label: "읽지 못했어요", fatal: { code: "unreadable", detail: "사진에서 글자를 찾지 못했어요" }, sources: [], check: null };
  const item = {
    index: 0, line: 1, day: 1, date: "2026-10-01",
    fields: {
      title: { value: "경복궁 관람", method: "rule", evidence: { line: 1, text: "10/1 09:00 경복궁 관람" }, needs_review: false, note: null },
      starts_at: { value: "09:00", method: "rule", evidence: { line: 1 }, needs_review: false, note: null },
      date: { value: "2026-10-01", method: "rule", evidence: { line: 1 }, needs_review: false, note: null },
      place: { value: { name: "경복궁" }, method: "lookup", evidence: { line: 1 }, needs_review: false, note: null },
    },
  };
  const source = { source_id: "s1", kind: "text", filename: null, transcribed: false, lines: [{ no: 1, text: "10/1 09:00 경복궁 관람", read: true }], items: scenario.intake === "items" ? [item] : [], trip: {}, reading: null };
  return {
    ...base, status: confirmed ? "confirmed" : "review", stage: "review", stage_label: "확인해 주세요", sources: [source],
    check: { ready: scenario.intake === "items", problems: [], filled: [], items: scenario.intake === "items" ? 1 : 0, title: "내 여행",
      plan: scenario.intake === "items" ? { requested: false, start_date: null, days: null, party_size: null, preferences: "" }
        : { requested: true, start_date: "2026-10-01", days: 2, party_size: 2, preferences: "조용한 곳" } },
  };
}

function json(response, status, body, origin) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": origin ?? "*", Vary: "Origin" });
  response.end(JSON.stringify(body));
}

const readBody = (request) => new Promise((resolve) => { const chunks = []; request.on("data", (chunk) => chunks.push(chunk)); request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8"))); });

createServer(async (request, response) => {
 try {
  const origin = request.headers.origin;
  const url = new URL(request.url, `http://127.0.0.1:${PORT}`);
  const path = url.pathname;

  if (request.method === "OPTIONS") {
    response.writeHead(200, {
      "Access-Control-Allow-Origin": origin ?? "*", "Access-Control-Allow-Methods": "GET, POST", Vary: "Origin",
      "Access-Control-Allow-Headers": "Accept, Accept-Language, Content-Language, Content-Type, X-User-Key", "Access-Control-Max-Age": "600",
    });
    response.end();
    return;
  }

  const raw = request.method === "POST" ? await readBody(request) : "";

  // ── test control ─────────────────────────────────────────────────
  if (path === "/__test/reset") { reset(); return json(response, 200, { ok: true }, origin); }
  if (path === "/__test/scenario") { scenario = { ...scenario, ...JSON.parse(raw || "{}") }; return json(response, 200, scenario, origin); }
  if (path === "/__test/log") return json(response, 200, log, origin);
  if (path.startsWith("/plan/")) { response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }); response.end("<h1>여행계획서(스텁)</h1>"); return; }

  const key = request.headers["x-user-key"];
  const isJson = (request.headers["content-type"] ?? "").includes("json");
  log.push({ method: request.method, path, key: key ?? null, body: isJson && raw ? JSON.parse(raw) : raw ? { multipart: raw } : null });

  // ── session (the only route that needs no key) ───────────────────
  if (request.method === "POST" && path === "/v1/web/session") {
    if (scenario.session === "limited") return json(response, 429, { error: { code: "too_many_sessions", message: "새 키를 너무 많이 받았다 — 잠시 뒤에 다시 하거나 가진 키를 넣는다", retry_after_seconds: 60 } }, origin);
    sessions += 1;
    const issued = `acop_u_stub_${sessions}`;
    keys.add(issued);
    return json(response, 201, { customer_id: "cust-1", user_key: issued, notice: "이 키를 따로 잘 보관해 주세요. 다시 보여 드리지 않아요 — 다른 기기에서 이어 쓸 때 필요합니다." }, origin);
  }
  if (!key || !keys.has(key)) return json(response, 401, { error: { code: "unauthenticated", message: "사용자 키가 없거나 맞지 않는다" } }, origin);

  if (request.method === "POST" && path === "/v1/web/session/rotate") {
    keys.delete(key);
    const rotated = `acop_u_rotated_${Date.now()}`;
    keys.add(rotated);
    return json(response, 200, { customer_id: "cust-1", user_key: rotated, notice: "새 키예요. 옛 키는 더 이상 쓸 수 없어요 — 따로 잘 보관해 주세요." }, origin);
  }
  // ★true once it has answered with the failure — the caller must stop there, or it would answer twice and crash this server
  const broken = (name) => {
    if (scenario.fail !== name) return false;
    json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin);
    return true;
  };
  if (request.method === "GET" && path === "/v1/web/trips") {
    if (broken("trips")) return;
    return json(response, 200, { trips: scenario.trips === "one" ? [{ trip_id: TRIP_ID, title: "내 여행", version: 1, created_at: at(7) }] : [] }, origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}` && request.method === "GET") {
    if (scenario.trip === "missing") return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
    return json(response, 200, tripView(), origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/proposals` && request.method === "GET") return broken("proposals") || json(response, 200, proposals(), origin);
  if (path === `/v1/web/trips/${TRIP_ID}/notices` && request.method === "GET") return broken("notices") || json(response, 200, notices(), origin);
  if (path === `/v1/web/trips/${TRIP_ID}/proposals/p-1/choose` && request.method === "POST") {
    if (scenario.choose === "conflict") return json(response, 409, { error: { code: "already_decided", message: "안을 고르지 못했다 — 아무것도 바뀌지 않았다", detail: { status: "kept" } } }, origin);
    const body = JSON.parse(raw || "{}");
    scenario = { ...scenario, proposals: "none" };
    return json(response, 200, body.key === null ? { status: "kept" } : { status: "adjusted" }, origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/messages` && request.method === "POST") {
    const body = JSON.parse(raw || "{}");
    if (scenario.chat === "escalated_bare") return json(response, 200, { case_id: "c-1", case_status: "escalated", status: "escalated", reason: "not_understood", report: null }, origin);
    return json(response, 200, { case_id: "c-1", case_status: "resolved", status: "answered", reason: "trip_fact_answered", report: { type: "question", fact: "detail" }, answer: `서버 답: ${body.message}` }, origin);
  }

  // ── plan intake ──────────────────────────────────────────────────
  // 모델 예열 — 여행 화면이 열릴 때 부른다. 늘 「이미 올라가 있다」로 답한다
  if (request.method === "POST" && path === "/v1/web/warmup") return json(response, 200, { status: "warm", model: "stub-model", last_attempt: null }, origin);
  if (request.method === "POST" && path === "/v1/web/trip-intakes") { polls = 0; confirmed = false; return json(response, 202, { intake_id: INTAKE_ID, status: "reading", stage: "received" }, origin); }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}` && request.method === "GET") { polls += 1; return json(response, 200, intakeView(1), origin); }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/edits` && request.method === "POST") {
    if (scenario.edits === "stale") return json(response, 409, { error: { code: "stale_revision", message: "그 사이 바뀌었어요", current_revision: 2 } }, origin);
    return json(response, 200, intakeView(2), origin);
  }
  if ((path === `/v1/web/trip-intakes/${INTAKE_ID}/confirm` || path === `/v1/web/trip-intakes/${INTAKE_ID}/plan`) && request.method === "POST") {
    if (path.endsWith("/plan") && scenario.planDelay) await new Promise((resolve) => setTimeout(resolve, scenario.planDelay));
    if (path.endsWith("/confirm") && broken("confirm")) return;
    confirmed = true;
    scenario = { ...scenario, trips: "one" };
    return json(response, 200, { status: "confirmed", trip: { trip_id: TRIP_ID } }, origin);
  }

  return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
 } catch (error) {
  // a bug in this stand-in must show up as a failing request, not as a dead server that fails every later test
  if (!response.headersSent) json(response, 500, { error: { code: "stub_error", message: String(error) } }, "*");
  console.error(error);
 }
}).listen(PORT, "127.0.0.1", () => console.log(`stub server on http://127.0.0.1:${PORT}`));
