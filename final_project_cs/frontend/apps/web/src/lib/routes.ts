export const routes = {
  home: "/",
  start: "/start",
  trips: "/trips",
  myPage: "/mypage",
  myPageEdit: "/mypage/edit",
  /** `[2026-10-12 사용자 지시]` 문의하기: the list of my inquiries (`/support`) and the form that writes a new one (`/support/new`). */
  support: "/support",
  supportNew: "/support/new",
  /** Where a social sign-in sends the browser back to (with a one-time ticket in the address, which the page removes at once). */
  authDone: "/auth/done",
  newTrip: "/trips/new",
  intake: (id: string) => `/intakes/${encodeURIComponent(id)}`,
  /** The plan check while the plan is still on its way to the server (before the server has given it an id). */
  intakeStarting: "/intakes/starting",
  trip: (id: string) => `/trips/${encodeURIComponent(id)}`,
};
