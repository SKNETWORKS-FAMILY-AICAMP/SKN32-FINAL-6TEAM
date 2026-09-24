import { JourneyShell } from "@/components/layout/journey-shell";
import { VerificationResults } from "@/features/verification/verification-results";

export default async function ResultsPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return <JourneyShell view="results" title={["검증 결과", "Your results"]}><VerificationResults tripId={tripId} /></JourneyShell>;
}
