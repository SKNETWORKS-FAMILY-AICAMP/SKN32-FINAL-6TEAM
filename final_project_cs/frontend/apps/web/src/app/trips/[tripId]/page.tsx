import { TripScreen } from "@/features/trip/trip-screen";

export default async function TripPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return <TripScreen tripId={tripId} />;
}
