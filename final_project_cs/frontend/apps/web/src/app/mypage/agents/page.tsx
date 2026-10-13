import { JourneyShell } from "@/components/layout/journey-shell";
import { AgentsPage } from "@/features/profile/profile";

export default function Page() {
  return <JourneyShell view="other" title={["에이전트 연결", "Connect an agent"]}><AgentsPage /></JourneyShell>;
}
