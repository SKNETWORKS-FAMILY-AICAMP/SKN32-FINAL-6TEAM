export const routes = {
  home: "/",
  start: "/start",
  trips: "/trips",
  myPage: "/mypage",
  myPageEdit: "/mypage/edit",
  newTrip: "/trips/new",
  intake: (id: string) => `/intakes/${encodeURIComponent(id)}`,
  /** The plan check while the plan is still on its way to the server (before the server has given it an id). */
  intakeStarting: "/intakes/starting",
  trip: (id: string) => `/trips/${encodeURIComponent(id)}`,
  verification: (id: string) => `/trips/${encodeURIComponent(id)}/verification`,
  results: (id: string) => `/trips/${encodeURIComponent(id)}/results`,
};
