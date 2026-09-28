import { JourneyShell } from "@/components/layout/journey-shell";
import { TripList } from "@/features/trip/trip-list";

export default function TripsPage() {
  return <JourneyShell view="other" title={["내 여행", "My trips"]}><TripList /></JourneyShell>;
}
