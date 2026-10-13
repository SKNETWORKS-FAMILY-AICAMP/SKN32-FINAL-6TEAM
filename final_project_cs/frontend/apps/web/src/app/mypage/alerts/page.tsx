import { JourneyShell } from "@/components/layout/journey-shell";
import { AlertsPage } from "@/features/profile/profile";

export default function Page() {
  return <JourneyShell view="other" title={["알림 받는 곳", "Where alerts go"]}><AlertsPage /></JourneyShell>;
}
