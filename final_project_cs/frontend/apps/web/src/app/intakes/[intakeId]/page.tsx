import { IntakeReview } from "@/features/intake-review/intake-review";

/** The intake's own screen picks its frame: the plan-check screen while reading, the journey shell for the review. */
export default async function IntakePage({ params }: { params: Promise<{ intakeId: string }> }) {
  const { intakeId } = await params;
  return <IntakeReview intakeId={intakeId} />;
}
