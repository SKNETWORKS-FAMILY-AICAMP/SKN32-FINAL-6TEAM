import { IntakeReview } from "@/features/intake-review/intake-review";

/** The check screen frames itself: the phone-sized screen while the plan is read, the journey frame for the rest. */
export default async function IntakePage({ params }: { params: Promise<{ intakeId: string }> }) {
  const { intakeId } = await params;
  return <IntakeReview key={intakeId} intakeId={intakeId} />;
}
