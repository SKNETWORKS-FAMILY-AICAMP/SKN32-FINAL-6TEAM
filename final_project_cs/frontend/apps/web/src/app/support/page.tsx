import { JourneyShell } from "@/components/layout/journey-shell";
import { SupportPage } from "@/features/support/support";

export default function Page() {
  return <JourneyShell view="other" title={["문제 신고·건의 기록", "Reports and suggestions"]}><SupportPage /></JourneyShell>;
}
