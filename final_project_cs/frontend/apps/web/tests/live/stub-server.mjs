// 테스트용 mock 서버 — ★실제 서버가 아니다. triPilot 서버의 웹 API(`/v1/web/*`) 모양만 흉내 내어 화면 자동 시험에만 쓴다.
// 실제 앱(개발 서버 3100 · 배포)은 이 파일을 쓰지 않는다. 실제 서버 확인은 `tests/real/` 이 한다.
//
// ★Why a test mock server: registering on the real server sends a notice to the team's chat channel and leaves data behind.
//   This server answers with the same shapes (read from `final_project_cs/app/domains/travel_ops/entry/trip_api.py`) and
//   keeps every request it received, so a test can check what the screen actually sent.
//
// Test control (never part of the real API):
//   POST /__test/reset               back to the default scenario, clears the request log
//   POST /__test/scenario {…}        change the scenario (see DEFAULTS; `trips: 5` = five trips in the list)
//   GET  /__test/log                 every request received since the last reset
//   POST /__test/ring {kinds}        ring the "this trip changed" bell on every open stream (scenario bell: "on")
//   POST /__test/hangup              close every open bell stream (the screen must reconnect and re-read)
//
// Live progress (SSE, server `op_stream.py`): `POST …/messages` and `POST …/plan` asked with `Accept: text/event-stream`
// answer `accepted` → `stage` … `beat` → `result` | `error`; `GET /v1/web/trip-intakes/{id}/events` follows the reading.
import { createServer } from "node:http";

const PORT = Number(process.env.STUB_PORT ?? 8043);
const TILE_PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");
const TRIP_ID = "11111111-2222-3333-4444-555555555555";
const INTAKE_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";

const DEFAULTS = {
  // the customer's trips (`GET /v1/web/trips`): "one" = already has a trip, "none" = first visit, or a number = that many (newest first; the first is TRIP_ID)
  trips: "one",
  // deleting a trip (`POST /v1/web/trips/{id}/delete` — the contract asked of the backend 2026-10-03, not on the real server yet):
  //   "ok" (deletes) | "unsupported" (the route is not there: 404 {"detail":"Not Found"}, as the real server answers today) | "fail" (500 for every trip)
  tripDelete: "ok",
  // trips whose delete fails with a 500 whatever `tripDelete` says (by trip id)
  deleteFails: [],
  // proposals the server is waiting on: "open" | "consent" (indoor unknown — asks "change it?" with no options yet)
  //   | "consent_options" (after "change": the same proposal now holds options) | "none"
  proposals: "none",
  // answer to choosing a proposal: "ok" | "conflict"
  choose: "ok",
  // chat: "answered" (server gives an answer) | "escalated_bare" (an old server: escalated with no answer)
  //   | "summary" (a 「요약」 question gets the day's stops as the real server writes them — for the pictures of `scripts/guide-shots.mjs`)
  chat: "answered",
  // intake once read: "items" (has stops, ready) | "empty_plan" (nothing read, the customer asks us to plan)
  //   | "blocked" (has a stop whose place the server could not settle: not ready, one problem)
  intake: "items",
  // how many polls answer "reading" before the review is ready
  readingPolls: 1,
  // the plan's upload (`POST /v1/web/trip-intakes`): how long the server takes to answer (ms), and a sentence when it refuses (422)
  intakeDelay: 0,
  intakeRefusal: "",
  // the check of the read plan (`review` in the intake view): "absent" = a server without it (the screen says only what was read) | "on"
  //   | "off" = a server that could not build it (review: null + review_error)
  review: "absent",
  // `[2026-10-06]` the questions asked while the server reads (`questions[]` of the intake view, `POST …/trip-intakes/{id}/survey`):
  //   "none" (an older server: no list — nothing is asked) | "two" (the server's two) | "unknown_kind" (the two and a third of a kind the page does not know)
  questions: "none",
  // the answer to `POST …/survey`: "ok" | "fail" (500: the answer is not saved) | "refuse" (422 invalid_answers) | "confirmed" (409 intake_confirmed)
  surveySave: "ok",
  // `[2026-10-06]` the Course Keeper of the trip (`guardian` of the trip view, `POST …/trips/{id}/guardian`): "absent" (an older server: no `guardian` — no icon) | "on" | "off"
  guardian: "absent",
  // the answer to `POST …/guardian`: "ok" | "fail" (500: nothing changes)
  guardianSave: "ok",
  // an edit the server refuses: "" | "locked" (409 item_locked)
  editRefusal: "",
  // the plan on the check screen: "simple" (one stop that is fine — nothing to fix, 「여행 등록」 is open) | "rich" (three stops, one needs review, two legs)
  board: "simple",
  // 받아쓰기 두 읽기 (2026-10-07): "on" = the first stop was read two ways off a photo (`rereads[]` + a warning row) — see `withReread`; "note_only" = the other value is unknown (`other: null`).
  reread: "off",
  // the trip screen's stops: "default" | "map" (three days for the map tests — see `mapItems`)
  tripItems: "default",
  // trip warnings / notices to show
  warnings: "some",
  notices: "some",
  // make one call fail with a 500: "trips" | "proposals" | "notices" | "confirm" | "messages" | "" (none)
  fail: "",
  // "stale": the server refuses an edit because the plan moved on (409 stale_revision)
  //   | "not_found": the server finds no place by the typed name (422 place_not_found)
  edits: "ok",
  // "limited": too many new sessions from this address (429 too_many_sessions)
  session: "ok",
  // `[2026-10-04]` the session this browser has (server D-CS-011): "guest" | "member" (a linked account makes any session a member's)
  sessionKind: "guest",
  // a guest's limits: "" | "trip_limit" | "too_far" | "too_long" — registering (`/confirm`) is refused with 403 guest_* and `login_required`
  guestLimit: "",
  // how many writes are refused once for their CSRF token (403 csrf_failed); the page reads the token again from `/auth/me` and sends it once more
  csrfRefuse: 0,
  // an automatic change the customer can undo: "none" | "open" (latest change notice carries an undo) | "stale" (undo is refused: 409)
  undo: "none",
  // "missing": there is no such trip
  trip: "ok",
  // how long planning takes to answer, in ms (the real server reads opening hours: up to about a minute)
  planDelay: 0,
  // a sentence when the server refuses to plan (422 `plan_refused`, before any stream opens); "" = it plans
  planRefusal: "",
  // `[2026-10-04]` the lines between stops (`GET /v1/web/trips/{id}/route-shapes`, mobility session): "off" = an older server (FastAPI 404 `{detail}`)
  //   | "on" (two shapes on day 1: a walk on a road graph, drawn solid; a bus joined by a straight line with no ground, drawn dashed) | "fail" (500) | "slow" ("on" after 3 s).
  routeShapes: "off",
  // `[2026-10-04]` the same for a plan not registered yet (`GET /v1/web/trip-intakes/{id}/route-shapes`, mobility session): "off" (404) | "on" (the board's first leg joined by a straight line with no ground, the second on a road) | "fail" (500)
  intakeRoutes: "off",
  // `[2026-10-07]` the ways to go for one leg of a checked plan (`GET …/moves/{from}~{to}/options?revision=`, `POST …/mode` - built by the mobility session 2026-10-07, `wiki/external/rest-endpoints.md` 「이동수단 고르기」):
  //   "off" (404 not_available - an older server: no box) | "on" | "none" (nothing reaches in time) | "partial" (the bus could not be finished: `fits: null`) | "fail" (500) | "slow" (4 s) | "unknown_mode" (also sends a way the screen does not know)
  moveOptions: "off",
  // `[2026-10-04]` agent keys (`/v1/web/agent-keys*`, server D-CS-012): "on" | "off" (an older server: FastAPI 404 `{detail}`) | "limit" (making one answers 409 agent_key_limit)
  agentKeys: "on",
  // the "this trip changed" bell (`GET /v1/web/trips/{id}/events`): "off" = an older server without it (404) | "on"
  bell: "off",
  // the customer's contact details (`GET/PUT /v1/web/profile`): "on" | "off" = an older server without it (404) | "reject" = refuses a save (422)
  profile: "on",
  // `[2026-10-05]` 「디스코드로 연결」 (`POST /v1/web/profile/discord/connect/start`, the profile's `discord_connect.available`): "off" = an older server (the profile does not say) | "on"
  //   | "cancelled" | "expired" | "failed" (the mock Discord window sends the browser back with that word) | "start_fails" (the start answers 500) | "bad_address" (the start hands out an address that is not Discord's)
  discordConnect: "off",
  // ── 텔레그램 연결 (2026-10-05) ── 시작
  // `[2026-10-05]` 「텔레그램으로 연결」 (`POST /v1/web/profile/telegram/connect/start`, the profile's `telegram_connect` · `telegram` · `notice_channel`;
  //   contract `wiki/records/plans/2026-10-05_텔레그램_연결_백엔드_요청.md`): "off" = an older server (the profile carries no telegram words; the start answers 404 `{detail}`) | "on"
  //   | "start_fails" (the start answers 500) | "bad_link" (the start hands out an address that is not Telegram's) | "short" (the code stops working 2 s after the start)
  //   | "blocked" (the test message finds the bot blocked) | "too_soon" (the test message is refused: 429 pressed again within 20 s).
  //   Tapping 「시작」 in Telegram is played by opening the link (`GET /__test/telegram-open?code=…`, no session - a browser move, as Telegram's webhook is the server's business).
  telegram: "off",
  // ── 텔레그램 연결 (2026-10-05) ── 끝
  // ── 동의 기록 (2026-10-05) ── 시작
  // `[2026-10-05]` The consent record (`GET/POST /v1/web/consents`, contract `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md`): "off" = an older server (404 `{detail}`)
  //   | "on" (records, nobody is turned away) | "gate" (records, and every other `/v1/web/*` call is refused with 403 `consent_required` until the REQUIRED items are on record for the current version).
  //   "server_ahead" = the server's terms are a NEWER version than the page carries (the GET says so, a POST answers 409 `terms_version_changed`).
  consents: "off",
  // ── 동의 기록 (2026-10-05) ── 끝
  // ── 약관 보관 기간 (2026-10-07) ── 시작
  // `[2026-10-07]` The public retention read (`GET /v1/web/legal/retention`, no session): "off" = an older server (404) | "on" = an operator changed a period on the
  //   admin screen (member data 2 years), so the server's terms version is `<TERMS_VERSION>+ret1` - the consent record then expects that version too.
  retention: "off",
  // ── 약관 보관 기간 (2026-10-07) ── 끝
  // how many times the trip itself fails to load (500) right after the server answered a chat message
  rereadFails: 0,
  // chat and planning asked as a stream: "on" | "off" (an older server: JSON once) | "slow" (a `slow` beat first)
  //   | "drop" (the first try goes silent after its first stage — the screen must reconnect with the same request)
  //   | "error" (an `error` event: timeout, retryable) | "busy" (429 too_many_streams before the stream opens)
  stream: "on",
  // the intake reading stream (`GET …/trip-intakes/{id}/events`): "on" | "off" (an older server: 404 — the screen re-reads every 1.5 s)
  //   | "stalled" (the server's reader died) | "silent" (opens, says "accepted" and then nothing at all — a dead line; with the check "on")
  //   With the check "on" the stream also carries what was checked (line · item · check · move · done); without it, only the stage.
  intakeEvents: "on",
  //   `[2026-10-03]` the "how far" packets (`progress {phase, done, total, current}`): "on" | "off" (a server without them — the bar is worked out from the rows)
  intakeProgress: "on",
  // the Discord test message: "ok" | "invalid" (Discord refused the webhook) | "too_soon" (429: pressed again within 20 s)
  webhookTest: "ok",
  // why the candidates list is short or empty (`notes` of `GET …/candidates`, server 8b0d4c88): [] | ["booked_needs_name"] (no candidates) | ["no_same_kind"] …
  candidateNotes: [],
  // `[2026-10-07]` "on": candidates carry `basis` (same_kind · similar_experience · meal_inferred) and `reason`, as the server does since c0ca7054
  candidateBasis: "off",
  // the whole-plan recommendation (`POST …/autofix`): "on" | "none" (it finds nothing to change although something needs a look) | "unknown_from" (what it changes had no known place before: it cannot be put back)
  autofix: "on",
  // social sign-in (`/v1/web/auth/*`, `wiki/records/plans/2026-10-03_1930_소셜_로그인_백엔드_요청.md`): "on" | "off" (an older server: 404) | "none" (no provider set up)
  social: "on",
  //   what the provider's page does when the customer is sent to it: "ok" | "cancelled" | "elsewhere" (the account belongs to another user)
  socialResult: "ok",
  //   "required" = a sign-in with no key is first refused with `human_check_required`
  socialHumanCheck: "off",
  // ── 위치 점 (2026-10-05) ── 시작
  // the customer's positions (`POST|DELETE /v1/web/trips/{id}/location`, `GET …/location/stops` — `wiki/records/plans/2026-10-05_동의기록_위치수집_백엔드_요청.md` §2·§3):
  //   "off" = an older server without the routes (FastAPI 404 `{detail}`) | "on" (keeps the points, finds no stay) | "no_consent" (403 consent_required)
  //   | "stops" (keeps the points, and says the customer stayed once — near 경복궁, on day 1 of the default trip)
  location: "off",
  // ── 위치 점 (2026-10-05) ── 끝
};

/** Trip loads still to fail after a chat answer (see `rereadFails`). */
let tripFailures = 0;

/** Open bell streams. The real server keeps no record of who received a bell — neither does this one. */
const bells = new Set();

let scenario;
/** The check of the plan the customer is working on (items, legs), changed by edits. */
let board;
let log;
let polls;
// the answers saved through `POST …/trip-intakes/{id}/survey`: question id → option id
let surveyAnswers = {};
// what `POST …/trips/{id}/guardian` last set: `{enabled, since, via}` (null: the scenario's own value stands)
let guardianState = null;
let confirmed;
let keys;
/** Session cookies this server made (`sid` → {sid, csrf, member}); `known-session` always exists (the browser of a returning visitor). */
let webSessions;
/** The agent keys this server made (`GET /v1/web/agent-keys` lists them without the key itself). */
let agentKeyRows;
/** Sessions that were signed out or ended by a sign-in. */
let ended;
/** The recovery email the server holds (`PUT /v1/web/profile`). */
let recoveryEmail = null;
/** The name the customer gave the plan (`trip.title` edit); the check says 「내 여행」 until then. */
let tripTitle = "내 여행";
/** Social sign-in: the providers linked to the browser's key, and the flows started (id → what the browser said at the start). */
let socialLinks = [];
let socialFlows = new Map();
/** The Discord webhook the server holds (never answered back — only a masked form) and what its last test said. */
let webhook = null;
let webhookStatus = null;
/** `[2026-10-05]` 「디스코드로 연결」: the flows started (id → the web origin to come back to). */
let discordFlows = new Map();
// ── 텔레그램 연결 (2026-10-05) ── 시작
/**
 * The Telegram chat the server holds (never answered back - only `connected`, a status and a time), the one-time code the last start made, and where alerts go now
 * (`notice_channel`: ONE place, the one connected last). Declared before `reset()` is first called (below), which sets it all up.
 */
let tg = { connected: false, status: null, at: null, code: null, codeUntil: 0, codes: 0, notice: null };
function telegramReset() { tg = { connected: false, status: null, at: null, code: null, codeUntil: 0, codes: 0, notice: null }; }
/** A Discord webhook was saved or connected: Discord is where alerts go now (the one connected last). Removing it hands alerts to Telegram when it is connected. */
function telegramAfterWebhook(saved) {
  if (saved === undefined) return;
  if (saved) tg.notice = "discord";
  else if (tg.notice === "discord") tg.notice = tg.connected ? "telegram" : null;
}
/** The words the profile carries about Telegram. An older server ("off") says none of them. */
function telegramProfile() {
  if (scenario.telegram === "off") return {};
  return { telegram_connect: { available: true }, telegram: { connected: tg.connected, status: tg.connected ? tg.status : null, connected_at: tg.connected ? tg.at : null }, notice_channel: tg.notice };
}
/** `PUT /v1/web/profile` `{notice_channel}`: a place that is not connected is refused (422 `channel_not_connected`); null = fine. */
function telegramChannelRefusal(body) {
  if (!("notice_channel" in body)) return null;
  const wanted = body.notice_channel;
  const there = wanted === "telegram" ? tg.connected : wanted === "discord" ? Boolean(webhook) : null;
  if (there === null) return { error: { code: "invalid_notice_channel", message: "알림을 받는 곳은 discord 또는 telegram 이에요" } };
  return there ? null : { error: { code: "channel_not_connected", message: "연결되지 않은 곳이에요 - 먼저 연결해 주세요" } };
}
// ── 텔레그램 연결 (2026-10-05) ── 끝
/** How many times each `request_id` came as a stream (the "drop" scenario answers only the second). */
let attempts = new Map();
// ── 동의 기록 (2026-10-05) ── 시작
/** The terms version the page under test carries (`src/features/consent/terms-content.ts` `TERMS_VERSION`) - keep the two the same; a different one is what "server_ahead" plays. */
const TERMS_VERSION = "2026-10-07.1";   // 웹 `terms-content.ts` 와 같은 값(2026-10-07 보관 기간 확정)
const CONSENT_CODES = ["service_terms", "privacy", "sensitive", "location", "alert_channel"];
const CONSENT_REQUIRED = ["service_terms", "privacy"];
/** code → { agreed, version, at } - the latest line of the append-only record (the stub keeps only that; the requests it received are the log). */
let consentRecords = new Map();
function consentReset() { consentRecords = new Map(); }
const consentVersion = () => scenario.consents === "server_ahead" ? "2099-01-01" : scenario.retention === "on" ? `${TERMS_VERSION}+ret1` : TERMS_VERSION;
// ── 약관 보관 기간 (2026-10-07) ── 시작
/** The shape of `GET /v1/web/legal/retention` (server `retention.public_view`): one cell per period with the Korean and English sentence the terms carry. */
function retentionView() {
  const cell = (key, value, unit, ko, en) => ({ key, label_ko: key, label_en: key, value, unit, default: value, editable: unit !== null, text_ko: ko, text_en: en });
  return { revision: 1, terms_version: `${TERMS_VERSION}+ret1`, cells: [
    cell("member_idle_days", 730, "days", "회원이 지우거나 탈퇴를 요청할 때까지, 마지막 이용 후 2년이 지나면 파기", "Kept until you delete it or ask to withdraw, and destroyed once 2 years have passed since your last use"),
    cell("case_follows_trip", null, null, "여행 · 게스트 자료가 지워질 때 함께 파기", "Destroyed together when the trip or guest data is deleted"),
    cell("consent_days", 1825, "days", "기록한 때부터 5년", "5 years from the time it was recorded"),
    cell("location_points_days", 7, "days", "여행 종료 후 7일", "7 days after the trip ends"),
    cell("location_proof_months", 6, "months", "기록한 때부터 6개월", "6 months from the time it was recorded"),
  ] };
}
// ── 약관 보관 기간 (2026-10-07) ── 끝
function consentView() {
  const items = CONSENT_CODES.map((code) => {
    const row = consentRecords.get(code);
    return { code, agreed: row?.agreed === true, version: row?.version ?? null, agreed_at: row?.at ?? null };
  });
  return { current_version: consentVersion(), required: CONSENT_REQUIRED, ok: CONSENT_REQUIRED.every((code) => items.find((item) => item.code === code)?.agreed === true && items.find((item) => item.code === code)?.version === consentVersion()), items };
}
/** What withdrawing an item takes with it. */
function consentWithdrawn(code) {
  if (code === "alert_channel") { webhook = null; webhookStatus = null; tg.connected = false; tg.status = null; tg.notice = null; }
  if (code === "location") locationPoints = new Map();
}
// ── 동의 기록 (2026-10-05) ── 끝
// ── 위치 점 (2026-10-05) ── 시작
/** The positions the server kept: `trip_id` → (`at` → point) — one per `(trip_id, at)`, as the contract says. */
let locationPoints = new Map();
// ── 위치 점 (2026-10-05) ── 끝

/** The conversation record the server keeps (`GET /v1/web/trips/{id}/chat`), oldest first. */
let turns = [];

/** The trips the list answers, newest first, and the ids deleted since the last reset (a deleted trip is gone for good). */
let rows = [];
let deleted = new Set();
const rowId = (index) => index === 0 ? TRIP_ID : `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`;
function freshRows(kind) {
  const count = kind === "one" ? 1 : kind === "none" ? 0 : Number(kind);
  return Array.from({ length: count }, (_, index) => ({ trip_id: rowId(index), title: "내 여행", version: 1, created_at: at(7, 59 - index) }));
}

function reset() {
  scenario = { ...DEFAULTS };
  rows = freshRows(scenario.trips);
  deleted = new Set();
  tripFailures = 0;
  turns = [];
  log = [];
  polls = 0;
  surveyAnswers = {};
  guardianState = null;
  confirmed = false;
  board = freshBoard(scenario.board);
  keys = new Set(["acop_u_known"]);
  webSessions = new Map();
  agentKeyRows = [];
  ended = new Set();
  recoveryEmail = null;
  tripTitle = "내 여행";
  socialLinks = [];
  socialFlows = new Map();
  webhook = null;
  webhookStatus = null;
  discordFlows = new Map();
  telegramReset();                                  // 텔레그램 연결 (2026-10-05)
  consentReset();                                   // 동의 기록 (2026-10-05)
  attempts = new Map();
  locationPoints = new Map();                       // 위치 점 (2026-10-05)
}

const at = (hour, minute = 0, day = 1) => `2026-10-0${day}T${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}:00+09:00`;

/** `tripItems: "map"` — a three-day trip for the map tests: stops with and without coordinates, one title that is HTML (it must show as text). */
function mapItems() {
  const stop = (n, title, hour, day, lat, lon) => ({ item_id: `m${n}`, seq: n, kind: "activity", title, place: title, starts_at: at(hour, 0, day), ends_at: at(hour + 1, 0, day), changed: false,
    other_options: [], customer_pinned: false, lat, lon, booked: false });
  return [
    stop(1, "첫 지도 장소", 9, 1, 37.58, 126.98),
    stop(2, "좌표가 없는 중간 일정", 10, 1, null, null),
    stop(3, '<img src=x onerror="window.__mapXss=1">', 12, 1, 37.57, 127.01),
    stop(4, "다음 날 첫 장소", 9, 2, 37.52, 126.97),
    stop(5, "다음 날 둘째 장소", 10, 2, 37.51, 127.02),
    stop(6, "좌표를 확인해야 하는 장소", 9, 3, null, null),
  ];
}

function tripView(id = TRIP_ID) {
  const view = {
    trip_id: id, customer_id: "cust-1", title: "내 여행", locale: "ko", party_size: 2, version: scenario.proposals === "open" ? 2 : 1,
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
  const withGuardian = scenario.guardian === "absent" ? view : { ...view, guardian: guardianState ?? { enabled: scenario.guardian === "on", since: null, via: null } };
  return scenario.tripItems === "map" ? { ...withGuardian, items: mapItems(), warnings: [], history: view.history.slice(0, 1) } : withGuardian;
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
  const board = kind === "rich" ? rich : { revision: 1, items: [rich.items[0]], moves: [] };
  return scenario.reread === "on" || scenario.reread === "note_only" ? withReread(board) : board;
}

// ── 받아쓰기 두 읽기 (2026-10-07) ── 시작
/**
 * `[2026-10-07 cs 개발 세션 제안 계약]` scenario `reread: "on"`: the first stop was read off a photo two ways — the server kept 「청경궁 관람」, the other half read 「창경궁 관람」 (`rereads[]`),
 * so the stop needs review with a warning row. Sending `items[0].title` (method customer) settles it.
 */
const REREAD_NOTE = "사진에서 이 줄을 두 가지로 읽었어요 — 「09:00 청경궁 관람」 / 「09:00 창경궁 관람」 · 원본과 맞는 쪽을 골라 주세요";
function withReread(board) {
  const [first, ...rest] = board.items;
  return { ...board, items: [{ ...first, title: "청경궁 관람", status: "review", can_lock: false, rereads: [{ field: "title", current: "청경궁 관람", other: scenario.reread === "note_only" ? null : "창경궁 관람" }],
    rows: [row("place", "warn", REREAD_NOTE), ...first.rows.filter((line) => line.row !== "place")] }, ...rest] };
}
// ── 받아쓰기 두 읽기 (2026-10-07) ── 끝

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

/**
 * `[2026-10-04]` After a stop's start or end changed, the legs follow it, like the server's timetable does: a leg leaves when the stop before it ends
 * (60 minutes after it starts when it has no end), arrives `minutes` later, and has `slack_min` = the next stop's start − that arrival.
 * Late (negative slack) = `review`, otherwise `keep`; the leg's arrival line says it in the server's words.
 */
function followTimes(b) {
  const toMin = (hhmm) => { const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm ?? ""); return m ? Number(m[1]) * 60 + Number(m[2]) : null; };
  const toText = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
  for (const move of b.moves) {
    const from = b.items.find((entry) => entry.id === move.from), to = b.items.find((entry) => entry.id === move.to);
    const start = toMin(from?.starts_at), next = toMin(to?.starts_at);
    if (start === null || next === null || typeof move.minutes !== "number") continue;
    const leave = toMin(from.ends_at) ?? start + 60;
    const arrive = leave + move.minutes;
    move.depart = toText(leave);
    move.arrive = toText(arrive);
    move.slack_min = next - arrive;
    move.status = move.slack_min < 0 ? "review" : "keep";
    const line = row("arrival", move.slack_min < 0 ? "warn" : "ok", move.slack_min < 0 ? `일정보다 ${-move.slack_min}분 늦어요` : `${move.slack_min}분 여유`);
    move.rows = move.rows.some((entry) => entry.row === "arrival") ? move.rows.map((entry) => entry.row === "arrival" ? line : entry) : [...move.rows, line];
  }
}

/**
 * `[2026-10-07]` The ways to go for a leg, worked out like the proposal says: a leg leaves when the stop before it ends, takes `minutes` by that way and has `slack_min` = the next stop's start - its arrival;
 * a way fits when nothing is late. The minutes are made up for this mock (walking is a third of the subway time again, the bus slower, the taxi faster) - only the shape of the answer is the contract's.
 */
const WAYS = {
  subway: { label: "지하철", minutes: (m) => m, fare: 1550, floor: false, grade: "확정" },
  bus: { label: "버스", minutes: (m) => m + 22, fare: 1500, floor: false, grade: "확정" },
  taxi: { label: "택시", minutes: (m) => Math.max(5, Math.round(m * 0.6)), fare: 9000, floor: false, grade: "추정" },
  walk: { label: "걸음", minutes: (m) => m * 3, fare: 0, floor: false, grade: "추정" },
};
function moveWays(b, move) {
  const toMin = (hhmm) => { const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm ?? ""); return m ? Number(m[1]) * 60 + Number(m[2]) : null; };
  const toText = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
  const from = b.items.find((entry) => entry.id === move.from), to = b.items.find((entry) => entry.id === move.to);
  const start = toMin(from?.starts_at), next = toMin(to?.starts_at);
  const base = move.base_minutes ?? move.minutes;
  if (start === null || next === null || typeof base !== "number") return null;
  const leave = toMin(from.ends_at) ?? start + 60;
  return Object.entries(WAYS).map(([mode, way], at) => {
    const minutes = way.minutes(base), arrive = leave + minutes;
    const slack = scenario.moveOptions === "none" ? -(at + 1) * 5 : next - arrive;           // "none": every way is late
    const fits = scenario.moveOptions === "none" ? false : slack >= 0;
    const unknown = scenario.moveOptions === "partial" && mode === "bus";
    return { mode, label: mode === "subway" && move.base_label ? move.base_label : way.label, minutes, km: mode === "walk" ? Math.round(minutes * 0.07 * 10) / 10 : move.km, fare_krw: way.fare, fare_is_floor: way.floor, fare_is_estimate: mode === "taxi",
      depart: toText(leave), arrive: toText(arrive), slack_min: slack, fits: unknown ? null : fits, basis: mode === "taxi" || mode === "walk" ? "estimate" : "timetable", grade: way.grade,
      ...(unknown ? { why_not: "계산이 오래 걸려 확인하지 못했어요" } : !fits ? { why_not: `${way.label}(으)로는 ${Math.abs(slack)}분 늦어요 · 다음 일정이 ${to.starts_at}에 시작해요` } : {}) };
  });
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
  // Like the server (`progress` — one value per phase): the places are counted while it reads, the hours and the legs while it checks.
  const packets = scenario.intakeProgress !== "off";
  const packet = (phase, done, total, current) => { if (packets) events.push(["progress", { phase, done, total, current: current && { id: current.id, title: current.title } }]); };
  rev.items.forEach((item, at) => packet("places", at + 1, rev.items.length, item));
  events.push(["stage", { stage: "checking", label: "장소·운영시간 확인", elapsed: 1, state: state("reading") }]);
  rev.items.forEach((item, at) => {
    events.push(["item", item]);
    for (const line of item.rows) events.push(["check", { item: item.id, ...line }]);
    packet("hours", at + 1, rev.items.length, item);
  });
  rev.moves.forEach((move, at) => {
    events.push(["move", move]);
    packet("moves", at + 1, rev.moves.length, { id: `${move.from}>${move.to}`, title: `${rev.items.find((entry) => entry.id === move.from)?.title ?? move.from} → ${rev.items.find((entry) => entry.id === move.to)?.title ?? move.to}` });
  });
  events.push(["done", { stage: "review", revision: 1, needs: rev.needs, ready: rev.ready }]);
  events.push(["result", { state: state("review") }]);
  return events.map(([name, body]) => `event: ${name}\ndata: ${JSON.stringify(body)}\n\n`);
}

reset();                                   // after the board's helpers above are declared

// The questions as the server sends them (`survey_answers.py`): the same list in the same order whatever was answered, `answer` = the saved option id or null.
const QUESTIONS = [
  { id: "preferred_mobility", kind: "single", title: "이동은 주로 어떻게 하세요?", why: "계획서만으로는 이동 방법을 알 수 없어서 여쭤요",
    options: [{ id: "public", label: "대중교통" }, { id: "taxi", label: "택시" }, { id: "walk", label: "걷기 위주" }] },
  { id: "priority", kind: "single", title: "일정이 바뀔 때 대체할 곳은 무엇을 먼저 볼까요?", why: "계획서만으로는 알 수 없어요",
    options: [{ id: "activity", label: "하고 싶은 활동이 비슷한 곳" }, { id: "mobility", label: "이동이 편한 곳" }] },
];
const QUESTION_IDS = new Set(QUESTIONS.map((question) => question.id));
function withQuestions(view) {
  if (scenario.questions === "none") return view;
  const list = QUESTIONS.map((question) => ({ ...question, answer: surveyAnswers[question.id] ?? null }));
  if (scenario.questions === "unknown_kind") list.push({ id: "future_pick", kind: "multi", title: "미래의 질문", why: "", options: [{ id: "a", label: "에이" }], answer: null });
  return { ...view, questions: list, questions_version: "1" };
}

function intakeView(revision) { return withQuestions(intakeBaseView(revision)); }

function intakeBaseView(revision) {
  const base = { intake_id: INTAKE_ID, revision, fatal: null, trip_id: confirmed ? TRIP_ID : null, needs_review: [] };
  const line = { no: 1, text: "10/1 09:00 경복궁 관람" };
  // Like the server: while reading, the source and its lines are there already, not yet read and without stops.
  if (polls <= scenario.readingPolls) return { ...base, status: "reading", stage: "reading", stage_label: "계획을 읽는 중이에요", check: null,
    sources: [{ source_id: "s1", kind: "text", filename: null, transcribed: false, lines: [{ ...line, read: false }], items: [], trip: {}, reading: null }] };
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
  const source = { source_id: "s1", kind: "text", filename: null, transcribed: false, lines: [{ ...line, read: true }], items: scenario.intake === "empty_plan" ? [] : [item], trip: {}, reading: null };
  const withReview = scenario.review === "on" && scenario.intake === "items"
    ? { review: reviewOf(board) } : scenario.review === "off" ? { review: null, review_error: "review_failed" } : {};
  return {
    ...base, ...withReview, status: confirmed ? "confirmed" : "review", stage: "review", stage_label: "확인해 주세요", sources: [source],
    check: { ready: scenario.intake === "items", items: scenario.intake === "empty_plan" ? 0 : 1, title: tripTitle, filled: [],
      problems: scenario.intake === "blocked" ? [{ code: "no_place", field: "items[0].place", message: "장소를 정하지 못했습니다", source_id: "s1" }] : [],
      plan: scenario.intake !== "empty_plan" ? { requested: false, start_date: null, days: null, party_size: null, preferences: "" }
        : { requested: true, start_date: "2026-10-01", days: 2, party_size: 2, preferences: "조용한 곳" } },
  };
}

/** CORS with credentials: the page sends its cookie, so the origin is named (never "*") and credentials are allowed. */
const cors = (origin) => ({ "Access-Control-Allow-Origin": origin ?? "*", "Access-Control-Allow-Credentials": "true", Vary: "Origin" });

function json(response, status, body, origin, extra = {}) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8", ...cors(origin), ...extra });
  response.end(JSON.stringify(body));
}

// ── the browser session (server D-CS-011) ───────────────────────────────────────────────────────
const COOKIE = "tripilot_sid_dev";
const cookieOf = (request) => { const found = new RegExp(`(?:^|; )${COOKIE}=([^;]*)`).exec(request.headers.cookie ?? ""); return found ? decodeURIComponent(found[1]) : null; };
const setCookie = (sid) => `${COOKIE}=${encodeURIComponent(sid)}; Path=/; HttpOnly; SameSite=Lax`;
const KNOWN_SESSION = { sid: "known-session", csrf: "csrf-known", member: false };
function lookupSession(sid) {
  if (ended.has(sid)) return null;
  return sid === KNOWN_SESSION.sid ? KNOWN_SESSION : webSessions.get(sid) ?? null;
}
function makeSession(kind) {
  const number = webSessions.size + 1;                                // starts again at 1 with every reset (`webSessions` is cleared there)
  const sid = kind === "member" ? `member-session-${number}` : `stub-session-${number}`;
  const made = { sid, csrf: `csrf-${sid}`, member: kind === "member" };
  webSessions.set(sid, made);
  return made;
}
/** A linked social account (or the scenario) makes a session a member's — the same session, from its next request on. */
const kindOf = (session) => session.member || scenario.sessionKind === "member" || socialLinks.length > 0 ? "member" : "guest";
const sessionBody = (session) => ({ kind: kindOf(session), csrf_token: session.csrf, ...(kindOf(session) === "guest" ? { guest_idle_hours: 168 } : {}),
  idle_expires_at: at(23), absolute_expires_at: at(23) });

/** The server's stage words (`op_stream.STAGES`) and what each waits on. */
const STAGES = {
  reading: ["여행 일정을 읽는 중이에요", null], understanding: ["요청을 이해하는 중이에요", "model"],
  planning: ["일정을 짜는 중이에요", "model"], checking: ["조건을 확인하는 중이에요", null], registering: ["여행으로 등록하는 중이에요", null],
};

function openStream(response, origin) {
  response.writeHead(200, { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", ...cors(origin) });
  return (event, data) => { if (!response.writableEnded) response.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`); };
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** A long task answered as a stream, like `op_stream.run`: `finish()` makes the result (the same body as the JSON answer). */
async function streamTask(request, response, origin, op, stages, requestId, finish, extraMs = 0) {
  const write = openStream(response, origin);
  let gone = false;
  request.on("close", () => { gone = true; });
  write("accepted", { op, at: new Date().toISOString() });
  const tries = (attempts.get(requestId) ?? 0) + 1;
  attempts.set(requestId, tries);
  const stageEvent = (stage, elapsed) => ({ stage, label: STAGES[stage]?.[0] ?? stage, waiting_on: STAGES[stage]?.[1] ?? null, elapsed });
  if (scenario.stream === "drop" && tries === 1) { write("stage", stageEvent(stages[0], 0.1)); return; }   // then silence: no beat
  if (scenario.stream === "error") {
    await wait(200);
    write("error", { code: "timeout", retryable: true, message: "시간이 오래 걸려 기다리기를 멈췄어요 — 같은 요청으로 다시 시도하면 이어서 확인해요", elapsed: 90 });
    return response.end();
  }
  let elapsed = 0;
  for (const stage of stages) {
    await wait(250);
    elapsed += 0.4;
    if (gone) return;
    write("stage", stageEvent(stage, Number(elapsed.toFixed(1))));
  }
  const last = stages.at(-1);
  const slow = scenario.stream === "slow";
  await wait(250);
  write("beat", { elapsed: slow ? 12.3 : elapsed + 0.4, stage: last, label: STAGES[last]?.[0] ?? last, waiting_on: STAGES[last]?.[1] ?? null,
    stage_elapsed: slow ? 9.1 : 0.6, slow, server_time: new Date().toISOString() });
  await wait((slow ? 1500 : 300) + extraMs);
  if (gone) return;
  write("result", finish());
  response.end();
}

const DISCORD = /^https:\/\/(?:(?:canary|ptb)\.)?discord(?:app)?\.com\/api\/webhooks\/(\d{15,25})\/[A-Za-z0-9_-]{20,120}$/;

const readBody = (request) => new Promise((resolve) => { const chunks = []; request.on("data", (chunk) => chunks.push(chunk)); request.on("end", () => resolve(Buffer.concat(chunks).toString("utf8"))); });

createServer(async (request, response) => {
 try {
  const origin = request.headers.origin;
  const url = new URL(request.url, `http://127.0.0.1:${PORT}`);
  const path = url.pathname;

  if (request.method === "OPTIONS") {
    response.writeHead(200, {
      ...cors(origin), "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE",
      "Access-Control-Allow-Headers": "Accept, Accept-Language, Content-Language, Content-Type, X-User-Key, X-CSRF-Token", "Access-Control-Max-Age": "600",
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
    if ("board" in change || "reread" in change) board = freshBoard(scenario.board);
    if ("trips" in change) rows = freshRows(scenario.trips);
    return json(response, 200, scenario, origin);
  }
  if (path === "/__test/log") return json(response, 200, log, origin);
  // 동의 기록 (2026-10-05): the test sets what the server's record says (another device agreed or withdrew) - `{ "items": { "privacy": false }, "version"?: "…" }`.
  if (path === "/__test/consents" && request.method === "POST") {
    const body = JSON.parse(raw || "{}");
    for (const [code, agreed] of Object.entries(body.items ?? {})) consentRecords.set(code, { agreed: agreed === true, version: body.version ?? consentVersion(), at: new Date().toISOString() });
    return json(response, 200, consentView(), origin);
  }
  if (path === "/__test/ring") {
    const { kinds } = JSON.parse(raw || "{}");
    const line = `event: trip.changed
data: ${JSON.stringify({ trip_id: TRIP_ID, kinds: kinds ?? ["itinerary", "notice", "proposal"], version: 1 })}

`;
    bells.forEach((stream) => stream.write(line));
    return json(response, 200, { rang: bells.size }, origin);
  }
  if (path === "/__test/hangup") { const closed = bells.size; bells.forEach((stream) => stream.end()); bells.clear(); return json(response, 200, { closed }, origin); }
  if (path.startsWith("/plan/")) {
    // `download=1` → the same page sent as a file (the server writes `Content-Disposition: attachment; filename*=UTF-8''triPilot-<제목>.html`)
    const file = url.searchParams.get("download") === "1" ? { "Content-Disposition": "attachment; filename*=UTF-8''triPilot-" + encodeURIComponent("내 여행") + ".html" } : {};
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8", ...file });
    response.end("<h1>여행계획서(스텁)</h1>");
    return;
  }
  // The free map's tiles in the test build (`serve.mjs` points `NEXT_PUBLIC_OSM_TILE_URL` here): a one-pixel image, so the real map code runs
  // without any test reaching OpenStreetMap. Not logged — a map draws dozens of them.
  if (path.startsWith("/__test/tile/")) { response.writeHead(200, { "Content-Type": "image/png", "Cache-Control": "max-age=3600" }); response.end(TILE_PNG); return; }

  const key = request.headers["x-user-key"] ?? null;                 // the legacy header (agents, an older page) — the page itself sends the cookie
  const sid = cookieOf(request);
  const isJson = (request.headers["content-type"] ?? "").includes("json");
  log.push({ method: request.method, path, query: url.search || null, key, session: sid, csrf: request.headers["x-csrf-token"] ?? null, accept: request.headers.accept ?? null, body: isJson && raw ? JSON.parse(raw) : raw ? { multipart: raw } : null });
  const write = ["POST", "PUT", "PATCH", "DELETE"].includes(request.method);

  // ── the browser session: a cookie the page cannot read, and a CSRF token it keeps in memory ────────
  const found = sid ? lookupSession(sid) : null;
  const clear = sid && !found ? { "Set-Cookie": `${COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0` } : {};
  const refuse = (status, code, message) => json(response, status, { error: { code, message } }, origin, clear);
  const ambiguous = () => refuse(400, "ambiguous_credentials", "쿠키와 사용자 키를 함께 보낼 수 없어요");
  /** Who is asking, or why not: a cookie (a write also needs the CSRF token), or — for an agent or an older page — the key; never both. */
  const authenticate = () => {
    if (key && sid) return { denied: ambiguous };
    if (sid) {
      if (!found) return { denied: () => refuse(401, "unauthenticated", "로그인 상태가 아니에요") };
      if (write) {
        if (scenario.csrfRefuse > 0) { scenario.csrfRefuse -= 1; return { denied: () => refuse(403, "csrf_failed", "보안 토큰이 맞지 않아요") }; }
        if (request.headers["x-csrf-token"] !== found.csrf) return { denied: () => refuse(403, "csrf_failed", "보안 토큰이 맞지 않아요") };
      }
      return { session: found };
    }
    if (key && keys.has(key)) return { legacy: true };
    return { denied: () => refuse(401, "unauthenticated", "로그인 상태가 아니에요") };
  };
  if (path === "/v1/web/auth/session" && request.method === "POST") {
    if (key && sid) return ambiguous();
    if (found) return json(response, 200, sessionBody(found), origin);
    if (scenario.session === "limited") return json(response, 429, { error: { code: "too_many_sessions", message: "새 세션을 너무 많이 받았다 — 잠시 뒤에 다시 해 주세요", retry_after_seconds: 60 } }, origin, clear);
    const made = makeSession("guest");
    return json(response, 201, sessionBody(made), origin, { "Set-Cookie": setCookie(made.sid) });
  }
  if (path === "/v1/web/auth/me" && request.method === "GET") {
    if (key && sid) return ambiguous();
    if (!found) return refuse(401, "unauthenticated", "로그인 상태가 아니에요");
    return json(response, 200, sessionBody(found), origin);
  }
  if (path === "/v1/web/auth/adopt" && request.method === "POST") {
    if (sid) return ambiguous();                                       // the key alone, no cookie
    if (!key || !keys.has(key)) return refuse(401, "unauthenticated", "사용자 키가 없거나 맞지 않는다");
    const made = makeSession("guest");
    return json(response, 201, sessionBody(made), origin, { "Set-Cookie": setCookie(made.sid) });
  }
  // ── 「디스코드로 연결」: Discord's own window (a browser move, no CORS). Choosing a channel there gives the SERVER a webhook; the browser goes back to My page. ──
  if (path === "/__test/discord-connect" && request.method === "GET") {
    const flow = discordFlows.get(url.searchParams.get("flow") ?? "");
    if (!flow) { response.writeHead(404); response.end(); return; }
    const goBack = (word) => { response.writeHead(302, { Location: `${flow.origin}/mypage?discord=${word}` }); response.end(); };
    if (["cancelled", "expired", "failed"].includes(scenario.discordConnect)) return goBack(scenario.discordConnect);
    webhook = "https://discord.com/api/web" + "hooks/123456789012345678/abcdefghijklmnopqrstuvwxyz0123456789ABCD";      // what Discord handed the server
    webhookStatus = "untested";
    telegramAfterWebhook(webhook);                  // 텔레그램 연결 (2026-10-05): the channel connected last gets the alerts
    return goBack("connected");
  }
  // ── 텔레그램 연결 (2026-10-05) ── 시작
  // The customer taps 「시작」 in Telegram (a browser move to the link the start handed out, no session, no CORS): Telegram would tell the server's webhook, here the page itself does.
  // A right code that has not run out connects the chat (`untested`, and alerts go to Telegram now); anything else is the bot's "link ran out / already used" answer.
  if (path === "/__test/telegram-open" && request.method === "GET") {
    const right = scenario.telegram !== "off" && tg.code !== null && url.searchParams.get("code") === tg.code && Date.now() < tg.codeUntil;
    if (right) { tg.connected = true; tg.status = "untested"; tg.at = new Date().toISOString(); tg.notice = "telegram"; tg.code = null; }
    response.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" });
    response.end(right ? "<h1>텔레그램 연결됨 (mock 서버)</h1>" : "<h1>연결 시간이 지났거나 이미 쓴 링크예요 (mock 서버)</h1>");
    return;
  }
  // ── 텔레그램 연결 (2026-10-05) ── 끝
  // ── social sign-in: the provider's page (a browser move, no CORS) and the calls that need no key ─────────
  const oauthPage = /^\/__test\/oauth\/(\w+)$/.exec(path);
  if (oauthPage && request.method === "GET") {
    const flow = socialFlows.get(url.searchParams.get("flow") ?? "");
    if (!flow) { response.writeHead(404); response.end(); return; }
    const goBack = (query) => { response.writeHead(302, { Location: `${flow.origin}/auth/done?${query}` }); response.end(); };
    if (scenario.socialResult === "cancelled") return goBack("error=cancelled");
    if (scenario.socialResult === "elsewhere" && flow.mode === "link") return goBack("error=already_linked_elsewhere");
    flow.ticket = `ticket-${flow.id}`;
    return goBack(`ticket=${flow.ticket}`);
  }
  if (path.startsWith("/v1/web/auth/") && scenario.social === "off") return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
  if (path === "/v1/web/auth/providers" && request.method === "GET") return json(response, 200, { providers: scenario.social === "none" ? [] : [{ id: "google" }, { id: "kakao" }] }, origin);
  const startMatch = /^\/v1\/web\/auth\/(\w+)\/start$/.exec(path);
  if (startMatch && request.method === "POST") {
    const { mode, client_nonce: nonce, turnstile_token: token } = JSON.parse(raw || "{}");
    if (mode === "link") { const who = authenticate(); if (who.denied) return who.denied(); }
    if (mode === "login" && scenario.socialHumanCheck === "required" && !token) return json(response, 422, { error: { code: "human_check_required", message: "사람인지 확인해 주세요" } }, origin);
    if (!["google", "kakao"].includes(startMatch[1])) return json(response, 404, { error: { code: "provider_not_enabled", message: "이 로그인 방법은 아직 쓸 수 없어요" } }, origin);
    const id = String(socialFlows.size + 1);
    socialFlows.set(id, { id, mode, nonce, provider: startMatch[1], origin: origin ?? "", used: false, ticket: null });
    return json(response, 200, { authorize_url: `http://127.0.0.1:${PORT}/__test/oauth/${startMatch[1]}?flow=${id}` }, origin);
  }
  if (path === "/v1/web/auth/exchange" && request.method === "POST") {
    const { ticket, client_nonce: nonce, session: wanted } = JSON.parse(raw || "{}");
    const flow = [...socialFlows.values()].find((entry) => entry.ticket && entry.ticket === ticket);
    // one use only, and only with the nonce the starting browser made
    if (!flow || flow.used || flow.nonce !== nonce) return json(response, 410, { error: { code: "ticket_invalid", message: "로그인 확인이 만료됐거나 맞지 않아요" } }, origin);
    flow.used = true;
    if (flow.mode === "link") {
      if (!socialLinks.includes(flow.provider)) socialLinks.push(flow.provider);
      return json(response, 200, { outcome: "linked", provider: flow.provider, trips: 1 }, origin);
    }
    if (wanted === "cookie") {
      if (sid) ended.add(sid);                                         // the guest session this browser had is ended by the server (session fixation)
      const member = makeSession("member");
      return json(response, 200, { outcome: "signed_in", provider: flow.provider, trips: 2, ...sessionBody(member) }, origin, { "Set-Cookie": setCookie(member.sid) });
    }
    keys.add("acop_u_social_account");
    return json(response, 200, { outcome: "signed_in", provider: flow.provider, user_key: "acop_u_social_account", notice: "이 계정의 키예요. 따로 보관해 주세요.", trips: 2 }, origin);
  }
  // ── 약관 보관 기간 (2026-10-07) ── 시작 (no session needed: asking must not make a user)
  if (path === "/v1/web/legal/retention" && request.method === "GET") {
    return scenario.retention === "on" ? json(response, 200, retentionView(), origin) : json(response, 404, { detail: "Not Found" }, origin);
  }
  // ── 약관 보관 기간 (2026-10-07) ── 끝
  const auth = authenticate();
  if (auth.denied) return auth.denied();
  // ── 동의 기록 (2026-10-05) ── 시작
  if (path === "/v1/web/consents") {
    if (scenario.consents === "off") return json(response, 404, { detail: "Not Found" }, origin);
    if (request.method === "GET") return json(response, 200, consentView(), origin);
    if (request.method === "POST") {
      const body = JSON.parse(raw || "{}");
      if (body.version !== consentVersion()) return json(response, 409, { error: { code: "terms_version_changed", message: "약관이 새 버전이에요", current_version: consentVersion() } }, origin);
      const items = Array.isArray(body.items) ? body.items : null;
      if (!items) return json(response, 422, { error: { code: "invalid_items", message: "items 가 필요해요" } }, origin);
      for (const item of items) {
        if (!CONSENT_CODES.includes(item?.code)) return json(response, 422, { error: { code: "unknown_code", message: String(item?.code) } }, origin);
        if (typeof item.agreed !== "boolean") return json(response, 422, { error: { code: "invalid_items", message: "agreed 는 true/false 예요" } }, origin);
        if (typeof item.text_sha256 !== "string" || !/^[0-9a-f]{64}$/.test(item.text_sha256)) return json(response, 422, { error: { code: "invalid_text_sha256", message: "소문자 16진수 64자예요" } }, origin);
      }
      for (const item of items) {
        const before = consentRecords.get(item.code);
        consentRecords.set(item.code, { agreed: item.agreed, version: body.version, at: new Date().toISOString() });
        if (before?.agreed === true && item.agreed === false) consentWithdrawn(item.code);       // a withdrawn item takes its data with it
      }
      return json(response, 200, consentView(), origin);
    }
  }
  // The gate: until the required items are on record, every other call is refused (the sign-in calls and the record itself stay open).
  if (scenario.consents === "gate" && path.startsWith("/v1/web/") && !path.startsWith("/v1/web/auth/") && !consentView().ok) {
    return json(response, 403, { error: { code: "consent_required", message: "약관에 동의해야 쓸 수 있어요", current_version: consentVersion(), required: CONSENT_REQUIRED } }, origin);
  }
  // ── 동의 기록 (2026-10-05) ── 끝
  if (path === "/v1/web/auth/logout" && request.method === "POST") {
    if (auth.session) ended.add(auth.session.sid);
    return json(response, 200, { status: "signed_out" }, origin, { "Set-Cookie": `${COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0` });
  }
  if (path === "/v1/web/agent-keys" || path.startsWith("/v1/web/agent-keys/")) {
    if (scenario.agentKeys === "off") return json(response, 404, { detail: "Not Found" }, origin);
    if (!auth.session) return refuse(403, "cookie_required", "에이전트 키는 브라우저(쿠키)로만 만들어요");
    if (kindOf(auth.session) !== "member") return json(response, 403, { error: { code: "member_only", message: "로그인한 사용자만 쓸 수 있어요", login_required: true } }, origin);
    const rowOf = (row) => ({ key_id: row.key_id, name: row.name, scope: row.scope, created_at: row.created_at, expires_at: row.expires_at, last_used_at: row.last_used_at, status: row.status });
    if (path === "/v1/web/agent-keys" && request.method === "GET") return json(response, 200, { keys: agentKeyRows.map(rowOf) }, origin);
    if (path === "/v1/web/agent-keys" && request.method === "POST") {
      const body = JSON.parse(raw || "{}");
      const days = body.expires_days ?? 90;
      if (scenario.agentKeys === "limit") return json(response, 409, { error: { code: "agent_key_limit", message: "사용 중인 에이전트 키가 10개예요 — 쓰지 않는 키를 폐기해 주세요" } }, origin);
      if (typeof body.name !== "string" || !body.name.trim() || body.name.trim().length > 60 || !["read", "write"].includes(body.scope) || !Number.isInteger(days) || days < 1 || days > 90) {
        return json(response, 422, { error: { code: "invalid_agent_key", message: "이름은 1~60자, 권한은 read|write, 유효 기간은 1~90일이에요" } }, origin);
      }
      const made = { key_id: `k-${agentKeyRows.length + 1}`, name: body.name.trim(), scope: body.scope, created_at: at(10), expires_at: at(10, 0, 2), last_used_at: null, status: "active" };
      agentKeyRows.push(made);
      return json(response, 201, { ...rowOf(made), key: `acop_a_stub_${agentKeyRows.length}_0123456789abcdef`, notice: "이 키는 지금 한 번만 보여요. 안전한 곳에 따로 보관해 주세요." }, origin);
    }
    const revokePath = /^\/v1\/web\/agent-keys\/([^/]+)$/.exec(path);
    if (revokePath && request.method === "DELETE") {
      const row = agentKeyRows.find((entry) => entry.key_id === revokePath[1]);
      if (!row) return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
      row.status = "revoked";
      return json(response, 200, { key_id: row.key_id, status: "revoked" }, origin);
    }
  }
  if (path === "/v1/web/auth/links" && request.method === "GET") return json(response, 200, { links: socialLinks.map((provider) => ({ provider, linked_at: "2026-10-03T10:00:00+09:00" })) }, origin);
  const unlinkMatch = /^\/v1\/web\/auth\/(\w+)$/.exec(path);
  if (unlinkMatch && request.method === "DELETE") {
    if (!socialLinks.includes(unlinkMatch[1])) return json(response, 404, { error: { code: "not_linked", message: "연결돼 있지 않아요" } }, origin);
    socialLinks = socialLinks.filter((provider) => provider !== unlinkMatch[1]);
    return json(response, 200, { links: socialLinks.map((provider) => ({ provider, linked_at: "2026-10-03T10:00:00+09:00" })) }, origin);
  }

  // ── the customer's contact details ───────────────────────────────
  if (path === "/v1/web/profile" && scenario.profile !== "off") {
    if (request.method === "GET") return json(response, 200, profileView(), origin);
    if (request.method === "PUT") {
      if (scenario.profile === "reject") return json(response, 422, { error: { code: "invalid_email", message: "이메일 형식이 맞지 않아요." } }, origin);
      const body = JSON.parse(raw || "{}");
      const unknown = Object.keys(body).find((name) => !["recovery_email", "discord_webhook_url", ...(scenario.telegram === "off" ? [] : ["notice_channel"])].includes(name));   // 텔레그램 연결 (2026-10-05): notice_channel
      if (unknown) return json(response, 422, { error: { code: "unknown_field", message: unknown } }, origin);
      const hook = "discord_webhook_url" in body ? String(body.discord_webhook_url ?? "").trim() : undefined;
      // like the server: one wrong value refuses the whole update, and the refused value is not sent back
      if (hook && !DISCORD.test(hook)) return json(response, 422, { error: { code: "invalid_webhook", message: "디스코드 웹훅 주소 모양이 아니에요" } }, origin);
      const channelRefusal = telegramChannelRefusal(body);                                    // 텔레그램 연결 (2026-10-05)
      if (channelRefusal) return json(response, 422, channelRefusal, origin);
      if ("recovery_email" in body) recoveryEmail = String(body.recovery_email ?? "").trim() || null;
      if (hook !== undefined) { webhook = hook || null; webhookStatus = hook ? "untested" : null; }
      telegramAfterWebhook(hook);                                                             // 텔레그램 연결 (2026-10-05): a saved webhook is where alerts go now
      if ("notice_channel" in body) tg.notice = body.notice_channel;                          // 텔레그램 연결 (2026-10-05): the customer chose
      return json(response, 200, profileView(), origin);
    }
  }
  if (path === "/v1/web/profile/discord/connect/start" && request.method === "POST") {
    if (scenario.discordConnect === "off") return json(response, 404, { detail: "Not Found" }, origin);
    if (scenario.discordConnect === "start_fails") return json(response, 500, { error: { code: "internal_error", message: "디스코드 연결을 시작하지 못했어요" } }, origin);
    if (scenario.discordConnect === "bad_address") return json(response, 200, { authorize_url: "https://evil.example/oauth2/authorize" }, origin);
    const id = String(discordFlows.size + 1);
    discordFlows.set(id, { id, origin: origin ?? "" });
    return json(response, 200, { authorize_url: `http://127.0.0.1:${PORT}/__test/discord-connect?flow=${id}` }, origin);
  }
  if (path === "/v1/web/profile/discord/test" && request.method === "POST" && scenario.profile !== "off") {
    if (!webhook) return json(response, 409, { error: { code: "no_webhook", message: "저장된 디스코드 웹훅이 없어요" } }, origin);
    if (scenario.webhookTest === "too_soon") return json(response, 429, { error: { code: "too_soon", message: "방금 보냈어요 — 20초 뒤에 다시 해 주세요" } }, origin);
    webhookStatus = scenario.webhookTest === "invalid" ? "invalid" : "ok";
    return json(response, 200, { result: webhookStatus, profile: profileView() }, origin);
  }
  // ── 텔레그램 연결 (2026-10-05) ── 시작
  if (path.startsWith("/v1/web/profile/telegram")) {
    if (scenario.telegram === "off") return json(response, 404, { detail: "Not Found" }, origin);        // an older server: FastAPI's own 404
    if (path === "/v1/web/profile/telegram/connect/start" && request.method === "POST") {
      if (scenario.telegram === "start_fails") return json(response, 500, { error: { code: "internal_error", message: "텔레그램 연결을 시작하지 못했어요" } }, origin);
      const until = Date.now() + (scenario.telegram === "short" ? 2000 : 10 * 60 * 1000);
      tg.codes += 1;
      tg.code = `tg-code-${tg.codes}-${Math.random().toString(36).slice(2, 10)}`;                      // one-time, and only the latest works
      tg.codeUntil = until;
      const link = scenario.telegram === "bad_link" ? `https://t.me.evil.example/tripilot_alert_bot?start=${tg.code}` : `http://127.0.0.1:${PORT}/__test/telegram-open?code=${tg.code}`;
      return json(response, 200, { link, expires_at: new Date(until).toISOString() }, origin);
    }
    if (path === "/v1/web/profile/telegram/test" && request.method === "POST") {
      if (!tg.connected) return json(response, 409, { error: { code: "no_telegram", message: "연결된 텔레그램이 없어요" } }, origin);
      if (scenario.telegram === "too_soon") return json(response, 429, { error: { code: "too_soon", message: "방금 보냈어요 — 20초 뒤에 다시 해 주세요" } }, origin);
      tg.status = scenario.telegram === "blocked" ? "blocked" : "ok";
      return json(response, 200, { result: tg.status, profile: profileView() }, origin);
    }
    if (path === "/v1/web/profile/telegram" && request.method === "DELETE") {
      tg.connected = false; tg.status = null; tg.at = null;
      if (tg.notice === "telegram") tg.notice = webhook ? "discord" : null;                           // alerts go to Discord when it is connected, else nowhere
      return json(response, 200, { profile: profileView() }, origin);
    }
  }
  // ── 텔레그램 연결 (2026-10-05) ── 끝

  // Google Maps only after the server allows this load (`POST /v1/web/map-load`); this mock always allows it (the `google` build of `maps.spec.ts`).
  if (request.method === "POST" && path === "/v1/web/map-load") return json(response, 200, { allowed: true, provider: "google", reason: null, used: { day: 1, month: 1 }, cap: { day: 312, month: 9688 } }, origin);
  // ★true once it has answered with the failure — the caller must stop there, or it would answer twice and crash this server
  const broken = (name) => {
    if (scenario.fail !== name) return false;
    json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin);
    return true;
  };
  if (request.method === "GET" && path === "/v1/web/trips") {
    if (broken("trips")) return;
    return json(response, 200, { trips: rows }, origin);
  }
  // `[2026-10-06]` Turn the Course Keeper on or off: `{enabled, via}` -> `{enabled, since, via}` (the same value again changes nothing).
  const guardianPath = /^\/v1\/web\/trips\/([^/]+)\/guardian$/.exec(path);
  if (guardianPath && request.method === "POST") {
    if (scenario.guardianSave === "fail") return json(response, 500, { error: { code: "internal_error", message: "저장하지 못했어요" } }, origin);
    const body = JSON.parse(raw || "{}");
    if (typeof body.enabled !== "boolean" || !["card", "header", "notice", "settings"].includes(body.via)) return json(response, 422, { error: { code: "validation_error", message: "enabled 와 via 가 필요해요" } }, origin);
    const now = guardianState ?? { enabled: scenario.guardian === "on", since: null, via: null };
    if (now.enabled !== body.enabled) guardianState = { enabled: body.enabled, since: new Date().toISOString(), via: body.via };
    return json(response, 200, guardianState ?? now, origin);
  }
  // A trip of this customer's list (and TRIP_ID, until it is deleted) opens; any other id is "not yours / not there" (404 not_found).
  const tripPath = /^\/v1\/web\/trips\/([^/]+)$/.exec(path);
  if (tripPath && request.method === "GET") {
    const id = tripPath[1];
    const known = (id === TRIP_ID || rows.some((entry) => entry.trip_id === id)) && !deleted.has(id);
    if (!known || scenario.trip === "missing") return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
    if (tripFailures > 0) { tripFailures -= 1; return json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin); }
    return json(response, 200, tripView(id), origin);
  }
  // ★Delete a trip — the contract asked for in `wiki/records/plans/2026-10-03_*_웹_실서버_전환_백엔드_요청.md`. With `tripDelete: "unsupported"` this
  //   route does not exist, which falls through to the 404 below exactly as the real server answers a route it does not have.
  const shapesPath = /^\/v1\/web\/trips\/([^/]+)\/route-shapes$/.exec(path);
  if (shapesPath && request.method === "GET" && scenario.routeShapes !== "off") {
    if (scenario.routeShapes === "fail") return json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin);
    if (scenario.routeShapes === "slow") await wait(3000);
    // `[2026-10-05]` `?detail=true` (mobility session): the same line with many more points (a zoomed-in map follows the streets); the answer says `detail`.
    const detailed = url.searchParams.get("detail") === "true";
    const dense = (coordinates) => detailed ? coordinates.flatMap((point, at) => {
      const next = coordinates[at + 1];
      return next ? [0, 1, 2, 3, 4].map((step) => [point[0] + (next[0] - point[0]) * step / 5 + (step % 2 ? 0.0002 : 0), point[1] + (next[1] - point[1]) * step / 5]) : [point];
    }) : coordinates;
    return json(response, 200, { trip_id: shapesPath[1], detail: detailed, attribution: "경로선: 지도 데이터 © OpenStreetMap contributors (ODbL)", shapes: [
      { item_id: "i-m", from_item_id: "i-b", to_item_id: "i-c", from: "경복궁", to: "점심 식당", mode: "walk",
        line: { type: "LineString", coordinates: dense([[126.977, 37.5796], [126.981, 37.5745], [126.99, 37.57]]) }, source: "local_road_graph", grade: "추정", distance_m: 1250, note: null },
      { item_id: "i-m0", from_item_id: "i-a", to_item_id: "i-b", from: "아침 식당", to: "경복궁", mode: "bus",
        line: { type: "LineString", coordinates: [[126.98, 37.575], [126.977, 37.5796]] }, source: "straight_line", grade: "근거없음", distance_m: 640, note: detailed ? "정류장 정보가 없어 직선으로 이었어요 (상세 선)" : "정류장 정보가 없어 직선으로 이었어요" },
    ] }, origin);
  }
  // ── 위치 점 (2026-10-05) ── 시작
  // The customer's positions and where they stayed (contract §2·§3). "off" falls through to the 404 below, as a server without the routes answers.
  // ★Like the real server, nothing here writes a position to the console; a test reads what came in through `/__test/log`.
  const locationPath = /^\/v1\/web\/trips\/([^/]+)\/location(\/stops)?$/.exec(path);
  if (locationPath && scenario.location !== "off") {
    const id = locationPath[1];
    const known = (id === TRIP_ID || rows.some((entry) => entry.trip_id === id)) && !deleted.has(id);
    if (!known) return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
    const noConsent = () => json(response, 403, { error: { code: "consent_required", message: "위치 정보 수집·이용에 동의해야 쓸 수 있어요", current_version: "2026-10-05", required: ["location"] } }, origin);
    const kept = locationPoints.get(id) ?? new Map();
    if (!locationPath[2] && request.method === "POST") {
      if (scenario.location === "no_consent") return noConsent();
      const { fixes } = JSON.parse(raw || "{}");
      const point = (fix) => fix && Number.isFinite(fix.lat) && Number.isFinite(fix.lng) && typeof fix.at === "string" && Number.isFinite(Date.parse(fix.at));
      if (!Array.isArray(fixes) || fixes.length < 1 || fixes.length > 20 || !fixes.every(point)) return json(response, 422, { error: { code: "invalid_fixes", message: "위치 점은 1~20개, 각 점에 lat·lng·at 이 있어야 해요" } }, origin);
      let saved = 0, skipped = 0;
      for (const fix of fixes) {
        const inKorea = fix.lat >= 33 && fix.lat <= 39 && fix.lng >= 124 && fix.lng <= 132;
        if (!inKorea || (Number.isFinite(fix.accuracy_m) && fix.accuracy_m > 500)) { skipped += 1; continue; }
        if (kept.has(fix.at)) continue;                                   // the same (trip_id, at) is kept once
        kept.set(fix.at, { lat: fix.lat, lng: fix.lng, accuracy_m: fix.accuracy_m ?? null, at: fix.at });
        saved += 1;
      }
      locationPoints.set(id, kept);
      return json(response, 200, { saved, skipped }, origin);
    }
    if (!locationPath[2] && request.method === "DELETE") {
      locationPoints.delete(id);
      return json(response, 200, { deleted: kept.size }, origin);
    }
    if (locationPath[2] && request.method === "GET") {
      if (scenario.location === "no_consent") return noConsent();
      const last = [...kept.values()].sort((a, b) => Date.parse(a.at) - Date.parse(b.at)).at(-1) ?? null;
      const stops = scenario.location === "stops"
        ? [{ stop_id: "stay-1", lat: 37.579, lng: 126.9772, started_at: at(9, 32), ended_at: at(10, 50), radius_m: 35, points: 12, matched_item_id: "i-b" }]
        : [];
      return json(response, 200, { stops, last_fix: last, computed_at: at(11) }, origin);
    }
  }
  // ── 위치 점 (2026-10-05) ── 끝
  const deletePath = /^\/v1\/web\/trips\/([^/]+)\/delete$/.exec(path);
  if (deletePath && request.method === "POST" && scenario.tripDelete !== "unsupported") {
    const id = deletePath[1];
    if (scenario.tripDelete === "fail" || scenario.deleteFails.includes(id)) return json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin);
    const known = (id === TRIP_ID || rows.some((entry) => entry.trip_id === id)) && !deleted.has(id);
    if (!known) return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
    deleted.add(id);
    rows = rows.filter((entry) => entry.trip_id !== id);
    return json(response, 200, { trip_id: id, status: "deleted" }, origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/proposals` && request.method === "GET") return broken("proposals") || json(response, 200, proposals(), origin);
  if (path === `/v1/web/trips/${TRIP_ID}/events` && request.method === "GET" && scenario.bell === "on") {
    response.writeHead(200, { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache", ...cors(origin) });
    response.write(`: connected

event: ready
data: ${JSON.stringify({ trip_id: TRIP_ID, version: 1 })}

`);
    bells.add(response);
    request.on("close", () => bells.delete(response));
    return;
  }
  if (path === `/v1/web/trips/${TRIP_ID}/notices` && request.method === "GET") return broken("notices") || json(response, 200, notices(), origin);
  // `[2026-10-06]` The situation brief after a disaster pause was lifted: this mock server has no disaster, so there is none (tests that need one put it in with `page.route`).
  if (path === `/v1/web/trips/${TRIP_ID}/safety/recovery` && request.method === "GET") return json(response, 200, { recovery: null }, origin);
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
    if (wantsStream(request) && scenario.stream === "busy") return tooManyStreams(response, origin);
    return wantsStream(request) ? streamTask(request, response, origin, "message", ["reading", "understanding"], body.request_id, () => chatReply(body))
      : json(response, 200, chatReply(body), origin);
  }
  if (path === `/v1/web/trips/${TRIP_ID}/chat` && request.method === "GET") return json(response, 200, { trip_id: TRIP_ID, turns: turns.slice(-40) }, origin);

  // ── plan intake ──────────────────────────────────────────────────
  // 모델 예열 — 여행 화면이 열릴 때 부른다. 늘 「이미 올라가 있다」로 답한다
  if (request.method === "POST" && path === "/v1/web/warmup") return json(response, 200, { status: "warm", model: "stub-model", last_attempt: null }, origin);
  if (request.method === "POST" && path === "/v1/web/trip-intakes") {
    if (scenario.intakeDelay) await new Promise((resolve) => setTimeout(resolve, scenario.intakeDelay));
    if (scenario.intakeRefusal) return json(response, 422, { error: { code: "intake_refused", message: scenario.intakeRefusal } }, origin);
    polls = 0; surveyAnswers = {}; confirmed = false; board = freshBoard(scenario.board);
    return json(response, 202, { intake_id: INTAKE_ID, status: "reading", stage: "received" }, origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/survey` && request.method === "POST") {
    if (scenario.surveySave === "fail") return json(response, 500, { error: { code: "internal_error", message: "저장하지 못했어요" } }, origin);
    if (scenario.surveySave === "confirmed" || confirmed) return json(response, 409, { error: { code: "intake_confirmed", message: "이미 등록한 접수예요" } }, origin);
    const answers = JSON.parse(raw || "{}").answers ?? {};
    const problems = Object.entries(answers).flatMap(([key, value]) => {
      const question = QUESTIONS.find((entry) => entry.id === key);
      return !question ? [{ key, reason: "모르는 문항이다" }] : !question.options.some((option) => option.id === value) ? [{ key, reason: "모르는 선택지다" }] : [];
    });
    if (scenario.surveySave === "refuse" || problems.length) return json(response, 422, { error: { code: "invalid_answers", message: "답을 받을 수 없어요", problems } }, origin);
    surveyAnswers = { ...surveyAnswers, ...answers };
    return json(response, 200, { ok: true, answered: Object.keys(surveyAnswers).filter((key) => QUESTION_IDS.has(key)).sort(), questions_version: "1" }, origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}` && request.method === "GET") { polls += 1; return json(response, 200, intakeView(board.revision), origin); }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/route-shapes` && request.method === "GET" && scenario.intakeRoutes !== "off") {
    if (scenario.intakeRoutes === "fail") return json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin);
    const byId = new Map(board.items.map((item) => [item.id, item]));
    const shapes = board.moves.flatMap((move, at) => {
      const a = byId.get(move.from), b = byId.get(move.to);
      if (typeof a?.place?.latitude !== "number" || typeof b?.place?.latitude !== "number") return [];
      const from = [a.place.longitude, a.place.latitude], to = [b.place.longitude, b.place.latitude];
      const straight = at === 0;
      return [{ from_item_id: move.from, to_item_id: move.to, from: a.title, to: b.title, mode: straight ? "subway" : "walk",
        line: { type: "LineString", coordinates: straight ? [from, to] : [from, [(from[0] + to[0]) / 2 + 0.002, (from[1] + to[1]) / 2 - 0.001], to] },
        source: straight ? "straight_line" : "local_road_graph", grade: straight ? "근거없음" : "추정", distance_m: 900 + at * 300, note: straight ? "탄 역 정보가 없어 직선으로 이었어요" : null }];
    });
    return json(response, 200, { intake_id: INTAKE_ID, revision: board.revision, shapes, attribution: "경로선: 지도 데이터 © OpenStreetMap contributors (ODbL)" }, origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/events` && request.method === "GET") {
    if (scenario.intakeEvents === "off") return json(response, 404, { error: { code: "not_found", message: "resource not found" } }, origin);
    // Without the server's own check there is no content to stream: only the stage (and "stalled"), as an older server did.
    if (scenario.review !== "on" || scenario.intakeEvents === "stalled") return intakeEvents(request, response, origin);
    response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", ...cors(origin) });
    const chunks = scenario.intakeEvents === "silent" ? intakeStream().slice(0, 1) : intakeStream();
    chunks.forEach((chunk) => response.write(chunk));
    if (scenario.intakeEvents !== "silent") response.end();                  // "silent" leaves the line open and says nothing more
    return;
  }
  // `[2026-10-07]` The ways to go for one leg, and picking one (see `moveOptions` in the scenario).
  const waysPath = new RegExp(`^/v1/web/trip-intakes/${INTAKE_ID}/moves/([^/]+)~([^/]+)/(options|mode)$`).exec(path);
  if (waysPath) {
    const [, fromId, toId, kind] = waysPath;
    const unavailable = () => json(response, 404, { error: { code: "not_available", message: "이 구간은 이동 수단을 고를 수 없어요" } }, origin);
    const move = board.moves.find((entry) => entry.from === fromId && entry.to === toId);
    if (scenario.moveOptions === "off" || !move) return unavailable();
    if (scenario.moveOptions === "fail") return json(response, 500, { error: { code: "internal_error", message: "서버 오류" } }, origin);
    if (kind === "options" && request.method === "GET") {
      // 서버 구현(2026-10-07): 보고 있는 판(`?revision=`)이 낡았으면 409 stale_revision
      const asked = url.searchParams.get("revision");
      if (asked !== null && Number(asked) !== board.revision) return json(response, 409, { error: { code: "stale_revision", message: "그 사이 바뀌었어요", current_revision: board.revision } }, origin);
      if (scenario.moveOptions === "slow") await new Promise((resolve) => setTimeout(resolve, 4000));
      const ways = moveWays(board, move);
      if (!ways) return unavailable();
      const options = scenario.moveOptions === "unknown_mode" ? [...ways, { mode: "rocket", minutes: 1, fits: true }] : ways;
      return json(response, 200, { intake_id: INTAKE_ID, revision: board.revision, from: fromId, to: toId, current_mode: move.mode, recommended_mode: move.recommended_mode ?? move.mode, options }, origin);
    }
    if (kind === "mode" && request.method === "POST") {
      const body = JSON.parse(raw || "{}");
      if (body.revision !== board.revision) return json(response, 409, { error: { code: "stale_revision", message: "그 사이 바뀌었어요", current_revision: board.revision } }, origin);
      const ways = moveWays(board, move) ?? [];
      const recommended = move.recommended_mode ?? move.mode;
      const mode = body.mode === "recommended" ? recommended : body.mode;
      const way = ways.find((entry) => entry.mode === mode);
      // "refuse": the list said it reaches, but counted again with that way it does not (the server checks again before it takes it)
      if (scenario.moveOptions === "refuse") return json(response, 422, { error: { code: "mode_not_fit", message: "그 수단은 고를 수 없어요", why: "다시 계산해 보니 택시로도 다음 일정에 늦어요" } }, origin);
      if (!way) return json(response, 422, { error: { code: "mode_not_fit", message: "그 수단은 이 구간에서 쓸 수 없어요" } }, origin);
      if (way.fits !== true) return json(response, 422, { error: { code: "mode_not_fit", message: "그 수단은 고를 수 없어요", why: way.why_not ?? "그 수단으로는 닿지 않아요" } }, origin);   // 이동 세션 구현: 이유는 `why`
      move.base_minutes ??= move.minutes;
      move.base_label ??= move.mode_label;
      move.recommended_mode ??= move.mode;
      move.mode = mode;
      move.mode_label = way.label;
      move.minutes = way.minutes;
      move.km = way.km;
      move.summary = `${way.label} ${way.minutes}분 · ${way.km}km`;
      move.rows = move.rows.map((entry) => entry.row === "mode" ? row("mode", "ok", move.summary) : entry);
      move.mode_choice = mode === recommended ? null : { mode, state: "kept" };
      followTimes(board);
      board.revision += 1;
      return json(response, 200, { revision: board.revision, review: reviewOf(board) }, origin);
    }
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/edits` && request.method === "POST") {
    if (scenario.edits === "stale") return json(response, 409, { error: { code: "stale_revision", message: "그 사이 바뀌었어요", current_revision: 2 } }, origin);
    if (scenario.edits === "not_found") return json(response, 422, { error: { code: "place_not_found", message: "「없는 곳」: 이 이름으로 장소를 찾지 못했어요" } }, origin);
    const { edits = [] } = JSON.parse(raw || "{}");
    if (scenario.editRefusal === "locked" && edits.some((edit) => !edit.field.endsWith(".locked"))) return json(response, 409, { error: { code: "item_locked", message: "고정한 일정이라 바꿀 수 없어요" } }, origin);
    let retimed = false;
    for (const edit of edits) {
      if (edit.field === "trip.title" && typeof edit.value === "string") tripTitle = edit.value.trim().slice(0, 80) || tripTitle;
      const m = /^items\[(\d+)\]\.(\w+)$/.exec(edit.field);
      if (!m) continue;
      const item = board.items.find((entry) => entry.index === Number(m[1]));
      if (!item) continue;
      if (m[2] === "locked") item.locked = edit.value === true;
      else if (m[2] === "removed") { if (edit.value === true) board.removed = [...(board.removed ?? []), item]; board.items = edit.value === true ? board.items.filter((entry) => entry !== item) : board.items; }
      else if (m[2] === "place" && edit.value?.name) { item.place = place(edit.value.name, edit.value.latitude ?? 37.57, edit.value.longitude ?? 126.98, { source: edit.value.source ?? "kakao" }); item.status = "adjusted"; item.place_state = "customer"; item.rows = [row("place", "ok", "직접 고른 곳이에요")]; }
      else if (m[2] === "place" && edit.value?.none === true) { item.place = null; item.place_state = "none"; item.status = "adjusted"; item.rows = [row("place", "ok", "장소 없이 자유 시간으로 두었어요")]; }
      else if ((m[2] === "title" || m[2] === "booking_no") && typeof edit.value === "string") {           // 받아쓰기 두 읽기: the customer's value settles the row
        if (m[2] === "title") item.title = edit.value;
        item.rereads = (item.rereads ?? []).filter((entry) => entry.field !== m[2]);
        if (!item.rereads.length) { item.rows = item.rows.filter((line) => line.text !== REREAD_NOTE); item.rows.unshift(row("place", "ok", "관광공사 정보로 찾았어요")); item.status = "adjusted"; item.can_lock = true; }
      }
      else if (m[2] === "starts_at") { item.starts_at = edit.value; retimed = true; }
      else if (m[2] === "ends_at") { item.ends_at = edit.value || null; retimed = true; }       // "" = no end time, as the stop editor sends it
    }
    // a removed stop comes back when the edit says `removed: false`
    for (const edit of edits) {
      const m = /^items\[(\d+)\]\.removed$/.exec(edit.field);
      if (m && edit.value === false) {
        const back = (board.removed ?? []).find((entry) => entry.index === Number(m[1]));
        if (back) { board.items = [...board.items, back].sort((a, b) => a.index - b.index); board.removed = board.removed.filter((entry) => entry !== back); }
      }
    }
    if (retimed) followTimes(board);                       // the legs follow the new times (other edits leave them as they are)
    board.revision += 1;
    return json(response, 200, intakeView(board.revision), origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/candidates` && request.method === "GET") {
    const index = Number(url.searchParams.get("index"));
    const item = board.items.find((entry) => entry.index === index) ?? board.items[0];
    // "on" (2026-10-07 서버 c0ca7054): each candidate says which step of the ladder it came from and why; a meal place where a market stands at a meal time is `meal_inferred`
    const laddered = scenario.candidateBasis === "on" ? [
      { ...CANDIDATES[0], basis: "same_kind", similarity: 2, reason: "올리브영 인사동점과 같은 중분류(관광공사 분류)의 곳이에요 · 경복궁에서 450m · 다음 일정까지 8분 여유가 있어요" },
      { ...CANDIDATES[1], basis: "similar_experience", experience: "indoor_exhibit", reason: null },
      { rank: 3, place: { ...place("광장시장 순희네 빈대떡", 37.5701, 126.9996, { source: "kakao", kind: "dining" }), address: "서울 종로구 종로32길", category: "음식점", ref: null }, distance_m: 600, reference: "광장시장",
        rows: [row("place", "ok", "카카오 지도 정보로 찾았어요")], fits: true, status: "ok", slack: { before: 6, after: 10 }, estimated: false, basis: "meal_inferred", reason: "점심 시간의 시장 일정이라 시장 안 식당도 함께 보여 드려요" },
    ] : scenario.candidateBasis === "lodging" ? [
      // 서버 90d9e403: 이름 없는 「호텔」 줄 — 숙소와 그 숙소 안 식사가 짝으로
      { rank: 1, place: { ...place("호텔 스카이파크 센트럴", 37.5665, 126.9849, { source: "kakao", kind: "activity" }), address: "서울 중구 명동", category: "숙소", ref: null }, distance_m: 700, reference: "경복궁",
        rows: [row("place", "ok", "카카오 지도 정보로 찾았어요")], fits: true, status: "ok", slack: { before: 10, after: 10 }, estimated: false, basis: "lodging", reason: "계획에 숙소 이름이 없어 가까운 숙소를 골랐어요 · 경복궁에서 700m" },
      { rank: 2, place: { ...place("호텔 스카이파크 센트럴", 37.5665, 126.9849, { source: "kakao", kind: "dining" }), address: "서울 중구 명동", category: "숙소 안 식사", ref: null }, distance_m: 700, reference: "경복궁",
        rows: [row("place", "ok", "카카오 지도 정보로 찾았어요")], fits: true, status: "ok", slack: { before: 10, after: 10 }, estimated: false, basis: "lodging_meal", reason: "숙소 안 식당이 있는지는 확인하지 못했어요" },
    ] : CANDIDATES;
    return json(response, 200, { revision: board.revision, item: item.id, current: item.place, reference: { before: "경복궁", after: "광장시장" }, candidates: scenario.candidateNotes.length ? [] : laddered, notes: scenario.candidateNotes }, origin);
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
    if (scenario.autofix === "none") return json(response, 200, { applied: false, dry_run: JSON.parse(raw || "{}").dry_run === true, revision: board.revision, changed: [], kept: [{ id: "0-1", title: "올리브영", reason: "no_candidates" }], view: intakeView(board.revision) }, origin);
    // `dry_run: true` (server 224e7a1b): the plan as it WOULD be, nothing saved — the board is put back afterwards, like the server rolls its save point back.
    const dry = JSON.parse(raw || "{}").dry_run === true;
    const saved = dry ? JSON.stringify(board) : null;
    const was = board.revision;
    const old = board.items.find((item) => item.status === "review");
    // (a test that patches only the answer of the read can show a need the board does not have: nothing to change then)
    if (!old) return json(response, 200, { applied: false, dry_run: dry, revision: board.revision, changed: [], kept: [{ id: "0-1", title: "올리브영", reason: "no_candidates" }], view: intakeView(board.revision) }, origin);
    board.items = settle(board.items);
    board.moves = board.moves.map((move) => ({ ...move, status: "keep", slack_min: 5, rows: move.rows.map((r) => r.row === "arrival" ? row("arrival", "ok", "5분 여유") : r) }));
    board.revision += 1;
    const answer = { applied: !dry, dry_run: dry, revision: dry ? was : board.revision, changed: [{ id: old.id, source_id: "s1", index: old.index, title: old.title,
      from: { place: scenario.autofix === "unknown_from" ? null : place("올리브영 인사동점", 37.5741, 126.9857, { source: "kakao" }), starts_at: "11:00", ends_at: "12:00" }, to: { place: place("올리브영 광화문점", 37.5717, 126.9791, { source: "kakao" }), starts_at: "11:45", ends_at: "12:15" }, reason: "place_and_time" }],
      kept: [], view: { ...intakeView(board.revision), ...(dry ? { preview: true } : {}) } };
    if (saved) board = JSON.parse(saved);
    return json(response, 200, answer, origin);
  }
  if (path === `/v1/web/trip-intakes/${INTAKE_ID}/revalidate` && request.method === "POST") return json(response, 200, intakeView(board.revision), origin);
  if ((path === `/v1/web/trip-intakes/${INTAKE_ID}/confirm` || path === `/v1/web/trip-intakes/${INTAKE_ID}/plan`) && request.method === "POST") {
    const planning = path.endsWith("/plan");
    if (!planning && broken("confirm")) return;
    if (!planning && scenario.guestLimit && auth.session && kindOf(auth.session) === "guest") {
      const why = { trip_limit: "게스트는 여행을 1개까지 만들 수 있어요. 로그인하면 더 만들 수 있어요.", too_far: "게스트는 오늘부터 1년 안에 시작하는 여행만 만들 수 있어요.", too_long: "게스트는 7일 이내의 여행만 만들 수 있어요." }[scenario.guestLimit];
      return json(response, 403, { error: { code: `guest_${scenario.guestLimit}`, message: why, login_required: true } }, origin);
    }
    if (planning && scenario.planRefusal) return json(response, 422, { error: { code: "plan_refused", message: scenario.planRefusal } }, origin);
    const register = () => {
      confirmed = true;
      deleted.delete(TRIP_ID);
      if (!rows.some((entry) => entry.trip_id === TRIP_ID)) rows = [{ trip_id: TRIP_ID, title: "내 여행", version: 1, created_at: at(7) }, ...rows];
      return { status: "confirmed", trip: { trip_id: TRIP_ID } };
    };
    if (planning && wantsStream(request)) {
      if (scenario.stream === "busy") return tooManyStreams(response, origin);
      // the server derives the request from the revision (`intake:{id}:plan:r{revision}`)
      return streamTask(request, response, origin, "plan", ["planning", "checking", "registering"], `plan:r${JSON.parse(raw || "{}").revision}`, register, scenario.planDelay);
    }
    if (planning && scenario.planDelay) await new Promise((resolve) => setTimeout(resolve, scenario.planDelay));
    return json(response, 200, register(), origin);
  }

  // ★A route this server does not have: FastAPI's own 404 body, as the real server gives (checked on the local server) — not the
  //   `{"error": …}` shape of its own refusals. The web tells "no such route" from "no such trip" by it.
  return json(response, 404, { detail: "Not Found" }, origin);
 } catch (error) {
  // a bug in this test mock server must show up as a failing request, not as a dead server that fails every later test
  if (!response.headersSent) json(response, 500, { error: { code: "stub_error", message: String(error) } }, "*");
  console.error(error);
 }
}).listen(PORT, "127.0.0.1", () => console.log(`stub server on http://127.0.0.1:${PORT}`));

/** The chat answer — the same body for the JSON answer and for the stream's `result`. */
function chatReply(body) {
  if (scenario.chat === "escalated_bare") return { case_id: "c-1", case_status: "escalated", status: "escalated", reason: "not_understood", report: null };
  // a question about where the customer is now: the real server's decision unit says so with `needs_location`
  //   (this test mock server only looks for 「여기서」). With a position it answers from there.
  const here = String(body.message).includes("여기서");
  const summary = scenario.chat === "summary" && /요약|Summarize/i.test(String(body.message));
  const answer = summary ? ["2026-10-01", "1. 08:00 · 아침 식당", "2. 09:30 · 경복궁 관람", "3. 12:00 · 점심 식당"].join("\n")
    : here && body.location ? `지금 계신 곳(${body.location.lat}, ${body.location.lng})에서 도보 12분이에요.`
    : here ? "현재 위치를 알려 주시면 지금 계신 곳에서 가는 길을 알려 드릴게요." : `서버 답: ${body.message}`;
  tripFailures = scenario.rereadFails;
  // the server records both sides; the answer's time can be a moment before the screen receives it (real server)
  turns.push({ role: "customer", text: body.message, case_id: "c-1", at: new Date(Date.now() - 50).toISOString() },
    { role: "assistant", text: answer, case_id: "c-1", at: new Date(Date.now() - 40).toISOString() });
  return { case_id: "c-1", case_status: "resolved", status: "answered", reason: "trip_fact_answered", report: { type: "question", fact: "detail" }, answer, ...(here && !body.location ? { needs_location: true } : {}) };
}

/** Asked with `Accept: text/event-stream` (and this scenario has streams). */
function wantsStream(request) {
  return (request.headers.accept ?? "").includes("text/event-stream") && scenario.stream !== "off";
}

function tooManyStreams(response, origin) {
  return json(response, 429, { error: { code: "too_many_streams", message: "열어 둔 실시간 연결이 너무 많다 — 다른 화면을 닫고 다시 시도한다" } }, origin);
}

function profileView() {
  const id = webhook ? DISCORD.exec(webhook)?.[1] ?? "" : "";
  return { recovery_email: recoveryEmail,
    discord_webhook: webhook ? { set: true, masked: `https://discord.com/api/webhooks/${id.slice(0, 4)}…/••••`, status: webhookStatus, checked_at: webhookStatus === "untested" ? null : new Date().toISOString() }
      : { set: false, masked: null, status: null, checked_at: null },
    ...(scenario.discordConnect === "off" ? {} : { discord_connect: { available: true } }), ...telegramProfile(), updated_at: null };   // telegramProfile: 텔레그램 연결 (2026-10-05)
}

/** The intake reading stream, like `op_stream.watch`: the state, never what was read. The screen re-reads the intake on each event. */
function intakeEvents(request, response, origin) {
  const write = openStream(response, origin);
  const state = () => {
    const reading = polls <= scenario.readingPolls;
    return { status: reading ? "reading" : "review", stage: reading ? "reading" : "review", stage_label: reading ? "계획을 읽는 중이에요" : "확인을 기다려요", revision: 1, fatal_code: null, quiet_seconds: 0.4 };
  };
  write("accepted", { op: "intake", state: state(), at: new Date().toISOString() });
  if (scenario.intakeEvents === "stalled") {
    setTimeout(() => { write("error", { code: "stalled", retryable: true, stage: "reading", message: "읽는 일이 멈춘 것 같아요 — 다시 올려 주세요", quiet_seconds: 181 }); response.end(); }, 300);
    return;
  }
  let ticks = 0;
  const timer = setInterval(() => {
    ticks += 1;
    const now = state();
    if (now.status !== "reading") { write("result", { state: now }); clearInterval(timer); response.end(); return; }
    write(ticks === 1 ? "stage" : "beat", { elapsed: ticks * 0.3, stage: "reading", label: now.stage_label, stage_elapsed: ticks * 0.3, slow: false, state: now });
  }, 300);
  request.on("close", () => clearInterval(timer));
}
