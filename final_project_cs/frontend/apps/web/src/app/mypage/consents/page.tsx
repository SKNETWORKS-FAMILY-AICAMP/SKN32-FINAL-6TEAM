import { JourneyShell } from "@/components/layout/journey-shell";
import { ConsentsPage } from "@/features/profile/profile";

export default function Page() {
  return <JourneyShell view="other" title={["약관 · 동의", "Terms & consents"]}><ConsentsPage /></JourneyShell>;
}
