import { JourneyShell } from "@/components/layout/journey-shell";
import { TripHome } from "@/features/trip/trip-home";

export default async function TripPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return <JourneyShell view="trip" title={["나의 여행", "Your trip"]}><TripHome tripId={tripId} /></JourneyShell>;
}
