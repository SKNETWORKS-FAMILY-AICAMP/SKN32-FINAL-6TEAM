import { JourneyShell } from "@/components/layout/journey-shell";
import { SupportPage } from "@/features/support/support";

export default function Page() {
  return <JourneyShell view="other" title={["문의하기", "Contact support"]}><SupportPage /></JourneyShell>;
}
