import { JourneyShell } from "@/components/layout/journey-shell";
import { IntakeReview } from "@/features/intake-review/intake-review";

export default async function IntakePage({ params }: { params: Promise<{ intakeId: string }> }) {
  const { intakeId } = await params;
  return <JourneyShell view="checking" title={["계획 확인", "Check your plan"]}><IntakeReview intakeId={intakeId} /></JourneyShell>;
}
