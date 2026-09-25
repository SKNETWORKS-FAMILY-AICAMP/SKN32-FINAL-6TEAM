export const routes = {
  home: "/",
  start: "/start",
  newTrip: "/trips/new",
  trip: (id: string) => `/trips/${encodeURIComponent(id)}`,
  verification: (id: string) => `/trips/${encodeURIComponent(id)}/verification`,
  results: (id: string) => `/trips/${encodeURIComponent(id)}/results`,
};
