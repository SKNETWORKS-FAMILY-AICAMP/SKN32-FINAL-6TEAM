export const routes = {
  home: "/",
  start: "/start",
  trips: "/trips",
  myPage: "/mypage",
  myPageEdit: "/mypage/edit",
  /** Where a social sign-in sends the browser back to (with a one-time ticket in the address, which the page removes at once). */
  authDone: "/auth/done",
  newTrip: "/trips/new",
  intake: (id: string) => `/intakes/${encodeURIComponent(id)}`,
  /** The plan check while the plan is still on its way to the server (before the server has given it an id). */
  intakeStarting: "/intakes/starting",
  trip: (id: string) => `/trips/${encodeURIComponent(id)}`,
};
