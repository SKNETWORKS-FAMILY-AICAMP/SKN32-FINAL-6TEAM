import { TripHome } from "@/features/trip/trip-home";

export const metadata = { title: "여행 홈" };
export default async function TripPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return <TripHome tripId={tripId} />;
}
