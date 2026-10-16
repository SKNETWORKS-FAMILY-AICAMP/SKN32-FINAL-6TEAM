export const routes = {
  home: "/",
  start: "/start",
  trips: "/trips",
  /** `[2026-10-13 회의 확정 — 메뉴 = 마이페이지]` The settings screen (the menu is My page now); the address is kept for the Discord callback and old links. */
  myPage: "/mypage",
  myPageEdit: "/mypage/edit",
  /** `[2026-10-13 사용자 결정 — 마이페이지 A안]` The settings screen shows only how things stand; each of these changes one of them. The account one is also where a guest signs in (`?returnTo=` brings them back). */
  myPageAccount: "/mypage/account",
  myPageAlerts: "/mypage/alerts",
  myPageConsents: "/mypage/consents",
  myPageAgents: "/mypage/agents",
  /** `[2026-10-12 사용자 지시]` 문의하기: the list of my inquiries (`/support`) and the form that writes a new one (`/support/new`). */
  support: "/support",
  supportNew: "/support/new",
  /** One of my inquiries: its title and text, and the answer under them once there is one. */
  supportInquiry: (id: string) => `/support/${encodeURIComponent(id)}`,
  /** `[2026-10-17 사용자 결정 — ST4F-604]` 공지사항 게시판: the notices posted now and the ones that ended. */
  notices: "/notices",
  /** One notice on its own page (like one inquiry): its kind, when it was posted, and the text. */
  notice: (id: string) => `/notices/${encodeURIComponent(id)}`,
  /** Where a social sign-in sends the browser back to (with a one-time ticket in the address, which the page removes at once). */
  authDone: "/auth/done",
  newTrip: "/trips/new",
  intake: (id: string) => `/intakes/${encodeURIComponent(id)}`,
  /** The plan check while the plan is still on its way to the server (before the server has given it an id). */
  intakeStarting: "/intakes/starting",
  trip: (id: string) => `/trips/${encodeURIComponent(id)}`,
};
