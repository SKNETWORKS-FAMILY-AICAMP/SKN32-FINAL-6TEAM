import { VerificationResults } from "@/features/verification/verification-results";

export const metadata = { title: "검증 결과" };
export default async function ResultsPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return <VerificationResults tripId={tripId} />;
}
