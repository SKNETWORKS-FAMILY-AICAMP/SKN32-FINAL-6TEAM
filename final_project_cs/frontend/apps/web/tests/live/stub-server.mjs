// 테스트용 모방 서버 — ★실제 서버가 아니다. triPilot 서버의 웹 API(`/v1/web/*`) 모양만 흉내 내어 화면 자동 시험에만 쓴다.
// 실제 앱(개발 서버 3100 · 배포)은 이 파일을 쓰지 않는다. 실제 서버 확인은 `tests/real/` 이 한다.
//
// ★Why a test mock server: registering on the real server sends a notice to the team's chat channel and leaves data behind.
//   This server answers with the same shapes (read from `final_project_cs/app/modules/travel_ops/trip_api.py`) and
//   keeps every request it received, so a test can check what the screen actually sent.
//
// Test control (never part of the real API):
//   POST /__test/reset               back to the default scenario, clears the request log
//   POST /__test/scenario {…}        change the scenario (see DEFAULTS)
//   GET  /__test/log                 every request received since the last reset
//   POST /__test/ring {kinds}        ring the "this trip changed" bell on every open stream (scenario bell: "on")
//   POST /__test/hangup              close every open bell stream (the screen must reconnect and re-read)
import { createServer } from "node:http";

const PORT = Number(process.env.STUB_PORT ?? 8043);
const TRIP_ID = "11111111-2222-3333-4444-555555555555";
const INTAKE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const DEFAULTS = {
  // "one" = the customer already has a trip, "none" = first visit
  trips: "one",
  // proposals the server is waiting on: "open" | "consent" (indoor unknown — asks "change it?" with no options yet)
  //   | "consent_options" (after "change": the same proposal now holds options) | "none"
  proposals: "none",
  // answer to choosing a proposal: "ok" | "conflict"
  choose: "ok",
  // chat: "answered" (server gives an answer) | "escalated_bare" (an old server: escalated with no answer)
  chat: "answered",
  // intake once read: "items" (has stops, ready) | "empty_plan" (nothing read, the customer asks us to plan)
  intake: "items",
  // how many polls answer "reading" before the review is ready
  readingPolls: 1,
  // the check of the read plan (`review` in the intake view): "on" | "off" = a server that could not build it (review: null + review_error)
  review: "on",
  // the reading progress stream (`GET …/trip-intakes/{id}/events`): "off" = an older server without it (404) | "on" (sends what was read, then ends)
  //   | "silent" (opens, says "accepted" and then nothing at all — a dead line)
  intakeEvents: "off",
  // an edit the server refuses: "" | "locked" (409 item_locked)
  editRefusal: "",
  // the plan on the check screen: "simple" (one stop that is fine — nothing to fix, 「여행 등록」 is open) | "rich" (three stops, one needs review, two legs)
  board: "simple",
  // trip warnings / notices to show
  warnings: "some",
  notices: "some",
  // make one call fail with a 500: "trips" | "proposals" | "notices" | "confirm" | "messages" | "" (none)
  fail: "",
  // "stale": the server refuses an edit because the plan moved on (409 stale_revision)
  edits: "ok",
  // "limited": too many new keys from this address (429 too_many_sessions)
  session: "ok",
  // an automatic change the customer can undo: "none" | "open" (latest change notice carries an undo) | "stale" (undo is refused: 409)
  undo: "none",
  // "missing": there is no such trip
  trip: "ok",
  // how long planning takes to answer, in ms (the real server reads opening hours: up to about a minute)
  planDelay: 0,
  // the "this trip changed" bell (`GET /v1/web/trips/{id}/events`): "off" = an older server without it (404) | "on"
  bell: "off",
  // the customer's contact details (`GET/PUT /v1/web/profile`): "on" | "off" = an older server without it (404) | "reject" = refuses a save (422)
  profile: "on",
  // how many times the trip itself fails to load (500) right after the server answered a chat message
  rereadFails: 0,
};

/** Trip loads still to fail after a chat answer (see `rereadFails`). */
let tripFailures = 0;

/** Open bell streams. The real server keeps no record of who received a bell — neither does this one. */
const bells = new Set();

let scenario;
/** The check of the plan the customer is working on (items, legs), changed by edits. */
let board;
let log;
let sessions;
let polls;
let confirmed;
let keys;
/** The recovery email the server holds (`PUT /v1/web/profile`). */
let recoveryEmail = null;

/** The conversation record the server keeps (`GET /v1/web/trips/{id}/chat`), oldest first. */
let turns = [];

function reset() {
  scenario = { ...DEFAULTS };
  tripFailures = 0;
  turns = [];
  log = [];
  sessions = 0;
  polls = 0;
  confirmed = false;
  board = freshBoard(scenario.board);
  keys = new Set(["acop_u_known"]);
  recoveryEmail = null;
}

const at = (hour, minute = 0, day = 1) => `2026-10-0${day}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00+09:00`;

function tripView() {
  return {
    trip_id: TRIP_ID, customer_id: "cust-1", title: "내 여행", locale: "ko", party_size: 2, version: scenario.proposals === "open" ? 2 : 1,
    items: [
      { item_id: "i-a", seq: 1, kind: "dining", title: "아침 식당", place: "아침 식당", starts_at: at(8), ends_at: at(9), changed: false, other_options: [], customer_pinned: false, lat: 37.575, lon: 126.98, booked: false,
        map_url: "https://www.google.com/maps/search/?api=1&query=%EC%95%84%EC%B9%A8",
        place_info: { address: "서울특별시 종로구 율곡로1길 7", phone: "02-000-0000", category: "한식", hours: [{ day: "월", open: "08:00", close: "21:00" }], tags: ["michelin_selected", "card_payment"], michelin: { level: "셀렉티드", year: 2026 } } },
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
    map: { days: [{ date: "2026-10-15", legs: [{ from_item_id: "i-a", to_item_id: "i-b", url: "https://www.google.com/maps/dir/?api=1&origin=a&destination=b&travelmode=transit" }] }] },
    density: [],
    warnings: scenario.warnings === "some" ? [{ code: "density_exceeded", date: "2026-10-01", reason: "하루가 빡빡해요", remedy: "일정을 줄이세요" }] : [],
  };
}

function proposals() {
  if (scenario.proposals === "consent" || scenario.proposals === "consent_options") {
    const filled = scenario.proposals === "consent_options";
    return { trip_id: TRIP_ID, proposals: [{
      proposal_id: "p-1", item_id: "i-b", base_version: 1, reason: filled ? "indoor_unknown_options" : "indoor_unknown", protected_by: null,
      safety: false, status: "open", expires_at: at(23), chosen_key: null, causes: [],
      options: filled ? [{ key: "o-9", rank: 1, name: "실내 박물관", starts_at: at(9, 30) }] : [],
    }] };
  }
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
  if (scenario.undo !== "none") out.push({ key: "n-4", type: "change_notice", kind: null, text: "비 소식이 있어 09:30 경복궁 관람을 실내 박물관으로 바꿨어요.", version: 1, proposal_id: null, options: null, delivery: "sent", at: at(9),
    rollback: { base_version: 1, to_version: 0, request_id: "rollback:v1->v0", label: "되돌리기", path: "/rollback" } });
  if (scenario.proposals === "open") out.push({ key: "n-3", type: "proposal_request", kind: null, text: "점심 식당이 문을 닫았어요. 대체 식당을 골라 주세요.", version: 2, proposal_id: "p-1", options: [], delivery: "sent", at: at(11, 41) });
  return { notices: out };
}


const row = (name, result, text) => ({ row: name, result, text });
const place = (name, latitude, longitude, extra = {}) => ({ name, latitude, longitude, source: "tour_api", kind: null, content_id: null, content_type_id: null, ...extra });

/** The check of a plan — the shape of `review` in the real server's answer. "rich": three stops (one needs review) and two legs. */
function freshBoard(kind = "simple") {
  const rich = freshRichBoard();
  if (kind === "rich") return rich;
  return { revision: 1, items: [rich.items[0]], moves: [] };
}

function freshRichBoard() {
  return {
    revision: 1,
    items: [
      { id: "0-0", source_id: "s1", index: 0, title: "경복궁 관람", kind: "activity", day: 1, date: "2026-10-01", starts_at: "09:00", ends_at: "10:30", locked: false, status: "keep", can_lock: true, place_state: "found",
        place: place("경복궁", 37.5796, 126.977, { content_id: "126508" }), candidates_hint: null,
        rows: [row("place", "ok", "관광공사 정보로 찾았어요"), row("hours", "ok", "09:00–17:00 안에 머물러요"), row("closed", "ok", "화요일 휴무 · 방문은 목요일")] },
      { id: "0-1", source_id: "s1", index: 1, title: "올리브영", kind: "shopping", day: 1, date: "2026-10-01", starts_at: "11:00", ends_at: "12:00", locked: false, status: "review", can_lock: false, place_state: "picked_nearest",
        place: place("올리브영 인사동점", 37.5741, 126.9857, { source: "kakao" }), candidates_hint: 3,
        rows: [row("place", "warn", "이름이 여러 곳이라 가까운 「올리브영 인사동점」으로 임시로 골랐어요"), row("time", "warn", "경복궁 관람과 30분 겹쳐요")] },
      { id: "0-2", source_id: "s1", index: 2, title: "광장시장", kind: "dining", day: 1, date: "2026-10-01", starts_at: "12:30", ends_at: "13:30", locked: false, status: "adjusted", can_lock: true, place_state: "found",
        place: place("광장시장", 37.57, 126.9996, { content_id: "132183" }), candidates_hint: null,
        rows: [row("place", "ok", "가게 이름이 없어 광장시장으로 잡았어요"), row("time", "filled", "끝 시각이 없어 60분으로 두었어요")] },
    ],
    moves: [
      { from: "0-0", to: "0-1", day: 1, date: "2026-10-01", status: "review", mode: "subway", mode_label: "지하철 3호선", minutes: 9, km: 0.6, depart: "10:30", arrive: "10:39", slack_min: -39, basis: "timetable",
        summary: "지하철 3호선 9분 · 0.6km", rows: [row("route", "warn", "올리브영 인사동점을 임시로 골라서 계산했어요"), row("mode", "ok", "지하철 3호선 9분 · 0.6km"), row("arrival", "warn", "일정보다 39분 늦어요")] },
      { from: "0-1", to: "0-2", day: 1, date: "2026-10-01", status: "keep", mode: "subway", mode_label: "지하철 1호선", minutes: 16, km: 1.5, depart: "12:00", arrive: "12:16", slack_min: 14, basis: "timetable",
        summary: "지하철 1호선 16분 · 1.5km", rows: [row("route", "ok", "종로3가 → 종로5가"), row("mode", "ok", "지하철 1호선 16분 · 1.5km"), row("arrival", "ok", "14분 여유")] },
    ],
  };
}

/** Every stop and leg re-measured: stops that were `review` and legs that were late become fine (what 「전체 자동 추천」 and 「재검증」 end with). */
function settle(items) {
  return items.map((item) => item.status === "review"
    ? { ...item, status: "adjusted", place_state: "customer", rows: [row("place", "ok", "서버가 검증한 대체 후보"), row("hours", "ok", "10:00–22:00 안에 머물러요")] } : item);
}

function reviewOf(b) {
  const needsItems = b.items.filter((item) => item.status === "review").length;
  const needsMoves = b.moves.filter((move) => move.status === "review").length;
  const needs = { items: needsItems, moves: needsMoves, total: needsItems + needsMoves };
  const ids = new Set(b.items.map((item) => item.id));
  return { revision: b.revision, built_at: "2026-10-03T09:00:00+09:00", engine: "timetable", items: b.items, moves: b.moves.filter((move) => ids.has(move.from) && ids.has(move.to)), needs, ready: needs.total === 0 };
}

const CANDIDATES = [
  { rank: 1, place: { ...place("올리브영 광화문점", 37.5717, 126.9791, { source: "kakao" }), address: "서울 종로구 종로1길 50", category: "화장품", ref: null }, distance_m: 450, reference: "경복궁",
    rows: [row("place", "ok", "카카오 지도 정보로 찾았어요"), row("hours", "unknown", "카카오 지도 정보에는 운영시간이 없어요")], fits: true, status: "ok", slack: { before: 5, after: 8 }, estimated: false },
  { rank: 2, place: { ...place("올리브영 종각점", 37.5702, 126.9838, { source: "kakao" }), address: "서울 종로구 종로 51", category: "화장품", ref: null }, distance_m: 910, reference: "경복궁",
    rows: [row("place", "ok", "카카오 지도 정보로 찾았어요")], fits: false, status: "warn", slack: { before: -4, after: 8 }, estimated: false },
];

const SEARCH_RESULTS = [
  { rank: 1, place: { ...place("올리브영 명동 플래그십", 37.5637, 126.9851, { source: "kakao" }), address: "서울 중구 명동길 53", category: "화장품", ref: null }, distance_m: 2300, reference: "경복궁",
    rows: [row("place", "ok", "카카오 지도 정보로 찾았어요")], fits: false, status: "warn", slack: { before: null, after: null }, estimated: false },
];

/** What the screen sees while the plan is being read — one line, one stop, its check lines. Ends with `done` and `result`. */
function intakeStream() {
  const state = (status, stage = status === "reading" ? "checking" : "review") => ({ status, stage, stage_label: stage === "reading" ? "일정 읽기" : status === "reading" ? "장소·운영시간 확인" : "확인해 주세요", revision: 1, fatal_code: null, quiet_seconds: 0 });
  const rev = reviewOf(board);
  const events = [["accepted", { op: "intake", state: state("reading", "reading"), at: "2026-10-03T09:00:00+09:00" }]];
  [["10월 1일 서울 여행", null], ["09:00 경복궁 관람", board.items[0]], ["11:00 올리브영", board.items[1]], ["12:30 광장시장", board.items[2]]].forEach(([text, found], i) => {
    events.push(["line", { source_id: "s1", no: i + 1, text, read: true, found: found && { id: found.id, index: found.index, day: 1, date: "2026-10-01", starts_at: found.starts_at, title: found.title } }]);
  });
  events.push(["stage", { stage: "checking", label: "장소·운영시간 확인", elapsed: 1, state: state("reading") }]);
  for (const item of rev.items) events.push(["item", item]);
  for (const item of rev.items) for (const line of item.rows) events.push(["check", { item: item.id, ...line }]);
  for (const move of rev.moves) events.push(["move", move]);
  events.push(["done", { stage: "review", revision: 1, needs: rev.needs, ready: rev.ready }]);
  events.push(["result", { state: state("review") }]);
  return events.map(([name, body]) => `event: ${name}\ndata: ${JSON.stringify(body)}\n\n`);
}

reset();                                   // after the board's helpers above are declared

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
  const withReview = scenario.review === "on" && scenario.intake === "items"
    ? { review: reviewOf(board) } : scenario.review === "off" ? { review: null, review_error: "review_failed" } : {};
  return {
    ...base, ...withReview, status: confirmed ? "confirmed" : "review", stage: "review", stage_label: "확인해 주세요", sources: [source],
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
      "Access-Control-Allow-Origin": origin ?? "*", "Access-Control-Allow-Methods": "GET, POST, PUT", Vary: "Origin",
      "Access-Control-Allow-Headers": "Accept, Accept-Language, Content-Language, Content-Type, X-User-Key", "Access-Control-Max-Age": "600",
    });
    response.end();
    return;
  }

  const raw = request.method === "POST" || request.method === "PUT" ? await readBody(request) : "";

  // ── test control ─────────────────────────────────────────────────
  if (path === "/__test/reset") { reset(); return json(response, 200, { ok: true }, origin); }
  if (path === "/__test/scenario") {
    const change = JSON.parse(raw || "{}");
    scenario = { ...scenario, ...change };
    if ("board" in change) board = freshBoard(scenario.board);
    return json(response, 200, scenario, origin);
  }
  if (path === "/__test/log") return json(response, 200, log, origin);
  if (path === "/__test/ring") {
    const { kinds } = JSON.parse(raw || "{}");
    const line = `event: trip.changed
data: ${JSON.stringify({ trip_id: TRIP_ID, kinds: kinds ?? ["itinerary", "notice", "proposal"], version: 1 })}

`;
    bells.forEach((stream) => stream.write(line));
    return json(response, 200, { rang: bells.size }, origin);
  }
  if (path === "/__test/hangup") { const closed = bells.size; bells.forEach((stream) => stream.end()); bells.clear(); return json(response, 200, { closed }, origin); }
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

  // ── the customer's contact details ───────────────────────────────
  if (path === "/v1/web/profile" && scenario.profile !== "off") {
    const view = () => ({ recovery_email: recoveryEmail, discord_webhook: { set: false, masked: null, status: null, checked_at: null }, updated_at: null });
    if (request.method === "GET") return json(response, 200, view(), origin);
    if (request.method === "PUT") {
      if (scenario.profile === "reject") return json(response, 422, { error: { code: "invalid_email", message: "이메일 형식이 맞지 않아요." } }, origin);
      const body = JSON.parse(raw || "{}");
      const unknown = Object.keys(body).find((name) => !["recovery_email", "discord_webhook_url"].includes(name));
      if (unknown) return json(response, 422, { error: { code: "unknown_field", message: unknown } }, origin);
      if ("recovery_email" in body) recoveryEmail = String(body.recovery_email ?? "").trim() || null;
      return json(response, 200, view(), origin);
    }
  }

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
    if (tripFailures > 0) { tripFailures -= 1; return json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin); }
    return json(response, 200, tripView(), origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/proposals` && request.method === "GET") return broken("proposals") || json(response, 200, proposals(), origin);
  if (path === `/v1/web/trips/${TRIP_ID}/events` && request.method === "GET" && scenario.bell === "on") {
    response.writeHead(200, { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", "Access-Control-Allow-Origin": origin ?? "*", Vary: "Origin" });
    response.write(`: connected

event: ready
data: ${JSON.stringify({ trip_id: TRIP_ID, version: 1 })}

`);
    bells.add(response);
    request.on("close", () => bells.delete(response));
    return;
  }
  if (path === `/v1/web/trips/${TRIP_ID}/notices` && request.method === "GET") return broken("notices") || json(response, 200, notices(), origin);
  if (path === `/v1/web/trips/${TRIP_ID}/rollback` && request.method === "POST") {
    if (scenario.undo === "stale") return json(response, 409, { error: { code: "stale_itinerary", message: "일정이 그 사이 바뀌었다" } }, origin);
    scenario = { ...scenario, undo: "none" };
    return json(response, 200, { status: "rolled_back", answer: "09:30 일정을 원래대로(경복궁 관람) 되돌렸어요." }, origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/proposals/p-1/choose` && request.method === "POST") {
    if (scenario.choose === "conflict") return json(response, 409, { error: { code: "already_decided", message: "안을 고르지 못했다 — 아무것도 바뀌지 않았다", detail: { status: "kept" } } }, origin);
    const body = JSON.parse(raw || "{}");
    if (scenario.proposals === "consent" && body.key === "change") {
      // the server computes other places only now, into the same proposal — or finds none and keeps the plan
      if (scenario.choose === "no_alternate") { scenario = { ...scenario, proposals: "none" }; return json(response, 200, { status: "no_alternate" }, origin); }
      scenario = { ...scenario, proposals: "consent_options" };
      return json(response, 200, { status: "options" }, origin);
    }
    scenario = { ...scenario, proposals: "none" };
    return json(response, 200, body.key === null ? { status: "kept" } : { status: "adjusted" }, origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/messages` && request.method === "POST") {
    if (broken("messages")) return;
    const body = JSON.parse(raw || "{}");
    if (scenario.chat === "escalated_bare") return json(response, 200, { case_id: "c-1", case_status: "escalated", status: "escalated", reason: "not_understood", report: null }, origin);
    // a question about where the customer is now: the real server's decision unit says so with `needs_location`
    //   (this test mock server only looks for 「여기서」). With a position it answers from there.
    const here = String(body.message).includes("여기서");
    const answer = here && body.location ? `지금 계신 곳(${body.location.lat}, ${body.location.lng})에서 도보 12분이에요.`
      : here ? "현재 위치를 알려 주시면 지금 계신 곳에서 가는 길을 알려 드릴게요." : `서버 답: ${body.message}`;
    tripFailures = scenario.rereadFails;
    // the server records both sides; the answer's time can be a moment before the screen receives it (real server)
    turns.push({ role: "customer", text: body.message, case_id: "c-1", at: new Date(Date.now() - 50).toISOString() },
      { role: "assistant", text: answer, case_id: "c-1", at: new Date(Date.now() - 40).toISOString() });
    return json(response, 200, { case_id: "c-1", case_status: "resolved", status: "answered", reason: "trip_fact_answered", report: { type: "question", fact: "detail" }, answer, ...(here && !body.location ? { needs_location: true } : {}) }, origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/chat` && request.method === "GET") return json(response, 200, { trip_id: TRIP_ID, turns: turns.slice(-40) }, origin);

  // ── plan intake ──────────────────────────────────────────────────
  // 모델 예열 — 여행 화면이 열릴 때 부른다. 늘 「이미 올라가 있다」로 답한다
  if (request.method === "POST" && path === "/v1/web/warmup") return json(response, 200, { status: "warm", model: "stub-model", last_attempt: null }, origin);
  if (request.method === "POST" && path === "/v1/web/trip-intakes") { polls = 0; confirmed = false; board = freshBoard(scenario.board); return json(response, 202, { intake_id: INTAKE_ID, status: "reading", stage: "received" }, origin); }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}` && request.method === "GET") { polls += 1; return json(response, 200, intakeView(board.revision), origin); }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/events` && request.method === "GET") {
    if (scenario.intakeEvents === "off") return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
    response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Access-Control-Allow-Origin": origin ?? "*", Vary: "Origin" });
    const chunks = scenario.intakeEvents === "silent" ? intakeStream().slice(0, 1) : intakeStream();
    chunks.forEach((chunk) => response.write(chunk));
    if (scenario.intakeEvents !== "silent") response.end();                  // "silent" leaves the line open and says nothing more
    return;
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/edits` && request.method === "POST") {
    if (scenario.edits === "stale") return json(response, 409, { error: { code: "stale_revision", message: "그 사이 바뀌었어요", current_revision: 2 } }, origin);
    const { edits = [] } = JSON.parse(raw || "{}");
    if (scenario.editRefusal === "locked" && edits.some((edit) => !edit.field.endsWith(".locked"))) return json(response, 409, { error: { code: "item_locked", message: "고정한 일정이라 바꿀 수 없어요" } }, origin);
    for (const edit of edits) {
      const m = /^items\[(\d+)\]\.(\w+)$/.exec(edit.field);
      if (!m) continue;
      const item = board.items.find((entry) => entry.index === Number(m[1]));
      if (!item) continue;
      if (m[2] === "locked") item.locked = edit.value === true;
      else if (m[2] === "removed") { if (edit.value === true) board.removed = [...(board.removed ?? []), item]; board.items = edit.value === true ? board.items.filter((entry) => entry !== item) : board.items; }
      else if (m[2] === "place" && edit.value?.name) { item.place = place(edit.value.name, edit.value.latitude ?? 37.57, edit.value.longitude ?? 126.98, { source: edit.value.source ?? "kakao" }); item.status = "adjusted"; item.place_state = "customer"; item.rows = [row("place", "ok", "직접 고른 곳이에요")]; }
      else if (m[2] === "starts_at") item.starts_at = edit.value;
      else if (m[2] === "ends_at") item.ends_at = edit.value;
    }
    // a removed stop comes back when the edit says `removed: false`
    for (const edit of edits) {
      const m = /^items\[(\d+)\]\.removed$/.exec(edit.field);
      if (m && edit.value === false) {
        const back = (board.removed ?? []).find((entry) => entry.index === Number(m[1]));
        if (back) { board.items = [...board.items, back].sort((a, b) => a.index - b.index); board.removed = board.removed.filter((entry) => entry !== back); }
      }
    }
    board.revision += 1;
    return json(response, 200, intakeView(board.revision), origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/candidates` && request.method === "GET") {
    const index = Number(url.searchParams.get("index"));
    const item = board.items.find((entry) => entry.index === index) ?? board.items[0];
    return json(response, 200, { revision: board.revision, item: item.id, current: item.place, reference: { before: "경복궁", after: "광장시장" }, candidates: CANDIDATES, notes: [] }, origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/place-search` && request.method === "GET") {
    const q = (url.searchParams.get("q") ?? "").replace(/\s/g, "");
    if (q.length < 2) return json(response, 422, { error: { code: "query_too_short", message: "두 글자 이상 적어 주세요" } }, origin);
    return json(response, 200, { revision: board.revision, item: "0-1", query: url.searchParams.get("q"), results: SEARCH_RESULTS.filter((entry) => entry.place.name.includes(url.searchParams.get("q") ?? "") || q.length >= 2), notes: [] }, origin);
  }
  if (path === "/v1/web/places/photos" && request.method === "GET") {
    const ref = url.searchParams.get("ref") ?? "";
    if (!ref.startsWith("tour:")) return json(response, 200, { ref, photos: [], source_note: null, reason: "no_photo_source" }, origin);
    return json(response, 200, { ref, photos: [{ url: `http://127.0.0.1:${PORT}/__test/photo.svg`, thumb: `http://127.0.0.1:${PORT}/__test/photo.svg`, name: "경복궁_1" }], source_note: "ⓒ한국관광공사", reason: null }, origin);
  }
  if (path === "/__test/photo.svg") { response.writeHead(200, { "Content-Type": "image/svg+xml", "Access-Control-Allow-Origin": "*" }); response.end('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120"><rect width="160" height="120" fill="#cfd8dc"/></svg>'); return; }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/autofix` && request.method === "POST") {
    const before = reviewOf(board).needs.total;
    if (!before) return json(response, 200, { applied: false, revision: board.revision, changed: [], kept: [{ id: "0-0", title: "경복궁 관람", reason: "nothing_to_change" }], view: intakeView(board.revision) }, origin);
    const old = board.items.find((item) => item.status === "review");
    board.items = settle(board.items);
    board.moves = board.moves.map((move) => ({ ...move, status: "keep", slack_min: 5, rows: move.rows.map((r) => r.row === "arrival" ? row("arrival", "ok", "5분 여유") : r) }));
    board.revision += 1;
    return json(response, 200, { applied: true, revision: board.revision, changed: [{ id: old.id, source_id: "s1", index: old.index, title: old.title,
      from: { place: place("올리브영 인사동점", 37.5741, 126.9857, { source: "kakao" }), starts_at: "11:00", ends_at: "12:00" }, to: { place: place("올리브영 광화문점", 37.5717, 126.9791, { source: "kakao" }), starts_at: "11:45", ends_at: "12:15" }, reason: "place_and_time" }],
      kept: [], view: intakeView(board.revision) }, origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/revalidate` && request.method === "POST") return json(response, 200, intakeView(board.revision), origin);
  if ((path === `/v1/web/trip-intakes/${INTAKE_ID}/confirm` || path === `/v1/web/trip-intakes/${INTAKE_ID}/plan`) && request.method === "POST") {
    if (path.endsWith("/plan") && scenario.planDelay) await new Promise((resolve) => setTimeout(resolve, scenario.planDelay));
    if (path.endsWith("/confirm") && broken("confirm")) return;
    confirmed = true;
    scenario = { ...scenario, trips: "one" };
    return json(response, 200, { status: "confirmed", trip: { trip_id: TRIP_ID } }, origin);
  }

  return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
 } catch (error) {
  // a bug in this test mock server must show up as a failing request, not as a dead server that fails every later test
  if (!response.headersSent) json(response, 500, { error: { code: "stub_error", message: String(error) } }, "*");
  console.error(error);
 }
}).listen(PORT, "127.0.0.1", () => console.log(`stub server on http://127.0.0.1:${PORT}`));
