import { JourneyShell } from "@/components/layout/journey-shell";
import { TripList } from "@/features/trip/trip-list";

export default function TripsPage() {
  return <JourneyShell view="other" title={["여행 목록", "Trip list"]}><TripList /></JourneyShell>;
}
