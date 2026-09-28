import { JourneyShell } from "@/components/layout/journey-shell";
import { VerificationProgress } from "@/features/verification/verification-progress";

export default async function VerificationPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return <JourneyShell view="checking" title={["계획 확인 중", "Checking your plan"]}><VerificationProgress tripId={tripId} /></JourneyShell>;
}
