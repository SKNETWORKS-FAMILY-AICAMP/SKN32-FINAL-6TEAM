import type { Language, Translate } from "../i18n";

/**
 * `[2026-10-17 사용자 승인 · ST4F-611 문구 대조표 113]` The sentence a customer sees when the server refuses.
 * The server's `error.message` is written for developers in many places (해라체 「…다시 한다」, English 「resource not found」) and
 * is Korean only, so it is not shown as it is:
 * - Korean screen: a server sentence that is already polite (해요체 · 합니다체) is kept — it carries the case's own details
 *   (「여행을 1개까지」, 「키가 10개예요」). Otherwise this table's sentence.
 * - English screen: this table's sentence.
 * - A code the table does not know: a general sentence with the code, so a report can name it.
 * The code list is a negotiation item with the server (`wiki/external/web-screen-api.md`) — a new code needs a line here.
 */
type Detail = Record<string, unknown> | undefined;
type Text = readonly [ko: string, en: string] | ((detail: Detail) => readonly [ko: string, en: string]);

const AGAIN = ["잠시 뒤 다시 해 주세요.", "Please try again shortly."] as const;
const BROWSER = ["브라우저에서 로그인한 뒤 쓸 수 있어요.", "Sign in in your browser to use this."] as const;
const REFRESH = ["화면을 새로 고친 뒤 다시 해 주세요.", "Refresh the page and try again."] as const;
const number = (detail: Detail, key: string) => (typeof detail?.[key] === "number" ? detail[key] as number : null);

/**
 * `[2026-10-26]` Every stop of a new plan is before today (server d2ab93a65 「reject only wholly past calendar plans」): the registration refusal
 * (`itinerary_infeasible` with a `violations[].code` of `all_dates_in_past`) and the review's `date` line carry this sentence. Korean is the
 * server's own sentence, kept as it is; English is the web's.
 */
export const ALL_PAST_TEXT = ["모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요", "Every stop is before today. Please check the trip dates."] as const;
/**
 * `[2026-10-26 사용자 지시]` The same code names it everywhere: the registration refusal's `violations[].code`, and the `fatal.code` of an intake the server
 * ended on the plan entry because every stop it read is before today (`wiki/external/rest-endpoints/web-intakes.md` 「전부 과거인 계획은 계획 담기에서 막는다」).
 */
export const ALL_PAST_CODE = "all_dates_in_past";
const allDatesInPast = (detail: Detail) => Array.isArray(detail?.violations)
  && detail.violations.some((violation) => (violation as { code?: unknown } | null)?.code === ALL_PAST_CODE);

export const REFUSAL_TEXT: Record<string, Text> = {
  // 로그인 · 세션
  unauthenticated: ["로그인이 끝났어요. 다시 로그인해 주세요.", "Your sign-in has ended. Please sign in again."],
  session_expired: ["로그인이 끝났어요. 다시 로그인해 주세요.", "Your sign-in has ended. Please sign in again."],
  // `[2026-10-23 F-02]` The session was refreshed without resending the refused request.
  session_changed: ["로그인 상태가 바뀌어 요청을 보내지 않았어요. 화면을 확인하고 다시 시도해 주세요.", "Your sign-in changed, so the request was not sent. Please check the screen and try again."],
  too_many_auth: [`로그인을 너무 자주 시도했어요. ${AGAIN[0]}`, `Too many sign-in attempts. ${AGAIN[1]}`],
  too_many_sessions: [`요청이 너무 많아요. ${AGAIN[0]}`, `Too many requests. ${AGAIN[1]}`],
  too_many_requests: [`연결을 너무 자주 시도했어요. ${AGAIN[0]}`, `Too many attempts to connect. ${AGAIN[1]}`],
  too_many_streams: ["열어 둔 화면이 너무 많아요. 다른 창을 닫고 다시 해 주세요.", "Too many screens are open. Close other windows and try again."],
  ticket_invalid: ["로그인 시간이 지났어요. 처음부터 다시 해 주세요.", "This sign-in has expired. Please start again."],
  human_check_failed: ["사람 확인을 통과하지 못했어요. 다시 확인해 주세요.", "The human check did not pass. Please try again."],
  human_check_required: ["사람 확인이 필요해요. 확인한 뒤 다시 해 주세요.", "Please complete the human check and try again."],
  human_check_unavailable: [`지금은 사람 확인을 할 수 없어요. ${AGAIN[0]}`, `The human check is unavailable right now. ${AGAIN[1]}`],
  csrf_failed: [`요청을 확인하지 못했어요. ${REFRESH[0]}`, `We couldn't verify the request. ${REFRESH[1]}`],
  ambiguous_credentials: [`요청을 확인하지 못했어요. ${REFRESH[0]}`, `We couldn't verify the request. ${REFRESH[1]}`],
  use_adopt: [`이 기기는 이미 로그인돼 있어요. ${REFRESH[0]}`, `This device is already signed in. ${REFRESH[1]}`],
  not_linked: ["이 로그인 방법은 연결돼 있지 않아요.", "This sign-in method isn't linked."],
  provider_not_enabled: ["이 로그인 방법은 아직 쓸 수 없어요.", "This sign-in method isn't available yet."],
  web_origin_not_configured: [`지금은 로그인을 마칠 수 없어요. ${AGAIN[0]}`, `Sign-in can't finish right now. ${AGAIN[1]}`],
  guest_transfer_changed: ["로그인하는 사이 계정 상태가 바뀌었어요. 지금 일정은 그대로 두었으니 다시 로그인해 주세요.", "Your account changed while you were signing in. Your plan is unchanged — please sign in again."],
  member_only: ["로그인하면 쓸 수 있어요.", "Sign in to use this."],
  member_cookie_required: BROWSER,
  cookie_required: BROWSER,
  cookie_session_required: BROWSER,
  agent_forbidden: BROWSER,
  agent_scope: ["이 키는 읽기 전용이에요. 쓰기 권한이 있는 키가 필요해요.", "This key is read-only. A key with write access is needed."],
  agent_key_limit: ["에이전트 키를 더 만들 수 없어요. 안 쓰는 키를 폐기한 뒤 다시 만들어 주세요.", "You can't create more agent keys. Revoke one you don't use, then try again."],
  invalid_agent_key: ["이름(1~60자) · 권한 · 사용 기간을 확인해 주세요.", "Check the name (1–60 characters), the access and how long it lasts."],
  user_blocked: ["이 계정은 이용이 제한됐어요.", "This account is restricted."],
  // 한도 · 서버 상태
  usage_limit: (detail) => {
    const cap = number(detail, "cap");
    return cap ? [`오늘 쓸 수 있는 횟수(${cap}번)를 다 썼어요.`, `You've reached today's limit (${cap}).`] : ["사용 한도에 닿았어요.", "You've reached the usage limit."];
  },
  service_daily_cap: ["오늘 서비스 사용량이 다 찼어요.", "Today's service capacity is full."],
  // `[2026-10-22 사용자 지시]` 서비스 모드의 한 시간 한도 — 게스트는 로그인하면 한도가 넉넉해진다는 것까지 말한다(`limit`: member_hour · guest_hour)
  hourly_limit: (detail) => {
    const cap = number(detail, "cap");
    const guest = detail?.limit === "guest_hour";
    const ko = cap ? `한 시간에 쓸 수 있는 횟수(${cap}번)를 다 썼어요.` : "한 시간 사용 한도에 닿았어요.";
    const en = cap ? `You've reached the hourly limit (${cap}).` : "You've reached the hourly limit.";
    return guest ? [`${ko} 로그인하면 더 쓸 수 있어요.`, `${en} Sign in for more.`] : [ko, en];
  },
  guest_trip_limit: (detail) => {
    const cap = number(detail, "cap");
    return cap ? [`로그인하지 않으면 여행을 ${cap}개까지 만들 수 있어요.`, `Without signing in you can keep up to ${cap} ${cap === 1 ? "trip" : "trips"}.`]
      : ["로그인하지 않으면 여행을 더 만들 수 없어요.", "Sign in to add more trips."];
  },
  busy: [`지금 요청이 몰려 있어요. ${AGAIN[0]}`, `It's busy right now. ${AGAIN[1]}`],
  maintenance: [`지금 점검 중이에요. ${AGAIN[0]}`, `We're under maintenance. ${AGAIN[1]}`],
  // `[2026-10-20 D-CS-019]` 새 판으로 바꾸는 동안 api 대신 Caddy 가 답한다(`deploy/Caddyfile.tripilot` 「handle_errors」)
  service_updating: [`서비스를 새 판으로 바꾸는 중이에요. ${AGAIN[0]}`, `The service is switching to a new version. ${AGAIN[1]}`],
  risk_check_unavailable: [`지금은 일정 위험을 점검할 수 없어요. ${AGAIN[0]}`, `The trip risk check is unavailable right now. ${AGAIN[1]}`],
  // `[2026-10-26 묶음 M]` 「일정 수정」 「완료」가 새 판을 쓰다 저장소 오류로 멈췄고, 다시 읽어 판이 그대로인 것을 확인한 때(web-intakes /confirm 7)
  save_failed: [`지금 일정을 저장하지 못했어요. 일정은 바꾸지 않았어요. ${AGAIN[0]}`, `We couldn't save the plan just now. Nothing was changed. ${AGAIN[1]}`],
  // 여행 · 계획
  not_found: ["찾을 수 없어요. 지워졌거나 주소가 바뀌었을 수 있어요.", "Not found. It may have been removed."],
  item_not_found: [`그 일정을 찾지 못했어요. ${REFRESH[0]}`, `We couldn't find that item. ${REFRESH[1]}`],
  stale_itinerary: ["그 사이 일정이 바뀌었어요. 새로 불러와 주세요.", "The plan changed in the meantime. Please reload it."],
  stale_revision: ["그 사이 다른 곳에서 바뀌었어요. 새로 불러와 주세요.", "It changed elsewhere in the meantime. Please reload it."],
  intake_confirmed: ["이미 등록한 계획이에요.", "This plan is already registered."],
  intake_incomplete: ["등록하기 전에 채워야 할 곳이 있어요.", "Some details are needed before registering."],
  intake_reopened: ["등록한 여행을 고치는 중이에요. 일정 짜기는 새 여행에서 해 주세요.", "You're editing a registered trip. Plan a new schedule in a new trip."],
  read_items_outside_days: ["읽은 일정 중 고른 날짜 밖의 것이 있어요. 첫날 · 일수를 맞추거나 새로 짜기를 골라 주세요.", "Some items fall outside the chosen dates. Adjust the first day and number of days, or plan anew."],
  trip_field_locked: ["등록한 여행의 설문은 여기서 바꾸지 않아요.", "Survey answers of a registered trip can't be changed here."],
  option_gone: ["그 날짜에 남은 객실이 없어요. 일정은 그대로 두었어요. 다른 후보를 골라 주세요.", "No rooms are left on that date. Your plan is unchanged — please pick another option."],
  item_locked: ["고정한 일정이라 바꾸지 않았어요. 먼저 고정을 풀어 주세요.", "That item is locked, so it wasn't changed. Unlock it first."],
  invalid_place: ["그 일정에는 장소 위치가 없어 이동을 판단할 수 없어요.", "That item has no location, so travel to it can't be checked."],
  not_available: ["이 구간은 이동 수단을 고를 수 없어요.", "You can't choose transport for this leg."],
  mode_not_fit: ["이 구간은 그 이동 수단을 고를 수 없어요.", "That transport can't be used for this leg."],
  query_too_short: ["검색어를 두 글자 이상 넣어 주세요.", "Enter at least two characters."],
  invalid_answers: ["저장하지 못했어요. 답을 다시 골라 주세요.", "Couldn't save. Please choose your answers again."],
  invalid_survey: ["저장하지 못했어요. 답을 다시 골라 주세요.", "Couldn't save. Please choose your answers again."],
  stalled: ["읽는 일이 멈춘 것 같아요. 다시 올려 주세요.", "Reading seems to have stopped. Please upload it again."],
  already_decided: ["이미 다른 곳에서 골랐어요. 이번 선택으로 바뀐 것은 없어요.", "It was already decided elsewhere. Nothing was changed."],
  // `[2026-10-26]` The plan can't be carried out as it is — every stop before today has its own sentence (`ALL_PAST_TEXT`).
  itinerary_infeasible: (detail) => allDatesInPast(detail) ? ALL_PAST_TEXT
    : ["이 일정은 그대로 진행할 수 없어요. 문제가 된 일정을 고쳐 주세요.", "This plan can't go ahead as it is. Please fix the stops that don't work."],
  // 동의
  consent_required: ["이 기능을 쓰려면 동의가 필요해요.", "Consent is needed to use this."],
  terms_version_changed: ["약관이 바뀌었어요. 새 약관을 보고 다시 동의해 주세요.", "The terms have changed. Please read them and agree again."],
  invalid_items: [`동의를 저장하지 못했어요. ${REFRESH[0]}`, `Couldn't save your consent. ${REFRESH[1]}`],
  // 알림 받는 곳
  invalid_webhook: ["디스코드 웹훅 주소 모양이 아니에요. https://discord.com/api/webhooks/ 로 시작하는 주소를 넣어 주세요.", "That isn't a Discord webhook address. Use one that starts with https://discord.com/api/webhooks/."],
  no_webhook: ["저장된 디스코드 웹훅이 없어요.", "No Discord webhook is saved."],
  no_telegram: ["연결된 텔레그램이 없어요.", "No Telegram is connected."],
  channel_not_connected: ["그 알림 채널은 연결돼 있지 않아요.", "That alert channel isn't connected."],
  unreadable: ["저장된 텔레그램 연결을 읽을 수 없어요. 다시 연결해 주세요.", "The saved Telegram connection can't be read. Please connect again."],
  too_soon: ["시험 발송은 잠시 뒤 다시 할 수 있어요.", "You can send a test again shortly."],
  invalid_email: ["이메일 모양이 아니에요.", "That isn't an email address."],
};

/** A polite Korean sentence (해요체 · 합니다체), possibly ending with a bracketed note: 「…있어요(30초 뒤)」. */
const POLITE_KOREAN = /(요|니다)[.!?]?(\s*\([^)]*\))?$/;

export function refusalSentence(code: string, serverMessage: string | undefined, detail: unknown, language: Language): string {
  const own = REFUSAL_TEXT[code];
  const server = serverMessage?.trim();
  if (language === "ko" && server && POLITE_KOREAN.test(server)) return server;
  if (own) {
    const [ko, en] = typeof own === "function" ? own(detail as Detail) : own;
    return language === "ko" ? ko : en;
  }
  return language === "ko" ? `요청을 처리하지 못했어요. ${AGAIN[0]} (${code})` : `The request could not be completed. ${AGAIN[1]} (${code})`;
}

/** The same sentence, whatever spaces or closing full stop the server put in. */
const sameSentence = (a: string, b: string) => a.replace(/[\s.]/g, "") === b.replace(/[\s.]/g, "");

/**
 * `[2026-10-26]` A check line of the plan check in the screen's language. The server writes them in Korean; the Korean screen shows them as
 * they came, and on the English screen a line the web has words for is said in English — any other stays as the server wrote it.
 */
export function checkLineText(line: { kind: string; text: string }, t: Translate): string {
  if (line.kind === "date" && sameSentence(line.text, ALL_PAST_TEXT[0])) return t(line.text, ALL_PAST_TEXT[1]);
  return line.text;
}
