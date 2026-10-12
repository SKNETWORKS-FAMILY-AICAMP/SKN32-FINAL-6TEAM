import { JourneyShell } from "@/components/layout/journey-shell";
import { SupportForm } from "@/features/support/support";

export default function Page() {
  return <JourneyShell view="other" title={["문의 작성", "Write an inquiry"]}><SupportForm /></JourneyShell>;
}
