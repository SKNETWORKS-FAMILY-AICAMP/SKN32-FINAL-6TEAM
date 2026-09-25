import { Suspense } from "react";
import { TripRegistration } from "@/features/trip-registration/trip-registration";
import { QueryState } from "@/components/ui";

export const metadata = { title: "여행 계획 등록" };
export default function NewTripPage() {
  return <Suspense fallback={<QueryState loading error={null} />}><TripRegistration /></Suspense>;
}
