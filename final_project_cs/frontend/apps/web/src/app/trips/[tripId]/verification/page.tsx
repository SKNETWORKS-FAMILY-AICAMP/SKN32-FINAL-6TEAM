import { VerificationProgress } from "@/features/verification/verification-progress";

export const metadata = { title: "검증 중" };
export default async function VerificationPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  return <VerificationProgress tripId={tripId} />;
}
