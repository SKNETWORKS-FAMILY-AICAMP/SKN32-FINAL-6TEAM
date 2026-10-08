import { IntakeStarting } from "@/features/intake-review/intake-starting";

/** The plan check while the plan is still being sent — a fixed path, so it never collides with an intake's id. */
export default function IntakeStartingPage() {
  return <IntakeStarting />;
}
