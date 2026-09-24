import { Suspense } from "react";
import { JourneyShell } from "@/components/layout/journey-shell";
import { QueryState } from "@/components/ui";
import { TripRegistration } from "@/features/trip-registration/trip-registration";

export default function NewTripPage() {
  return <JourneyShell view="registration" title={["여행 계획 등록", "Add your plan"]}>
    <Suspense fallback={<QueryState loading error={null} />}><TripRegistration /></Suspense>
  </JourneyShell>;
}
