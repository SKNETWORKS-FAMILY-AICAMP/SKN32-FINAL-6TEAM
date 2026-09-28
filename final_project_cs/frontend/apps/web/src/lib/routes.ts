export const routes = {
  home: "/",
  start: "/start",
  trips: "/trips",
  myPage: "/mypage",
  myPageEdit: "/mypage/edit",
  newTrip: "/trips/new",
  intake: (id: string) => `/intakes/${encodeURIComponent(id)}`,
  trip: (id: string) => `/trips/${encodeURIComponent(id)}`,
  verification: (id: string) => `/trips/${encodeURIComponent(id)}/verification`,
  results: (id: string) => `/trips/${encodeURIComponent(id)}/results`,
};
