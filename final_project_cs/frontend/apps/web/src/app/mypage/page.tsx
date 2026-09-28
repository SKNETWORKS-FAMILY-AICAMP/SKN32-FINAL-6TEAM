import { JourneyShell } from "@/components/layout/journey-shell";
import { MyPage } from "@/features/profile/profile";

export default function MyPagePage() {
  return <JourneyShell view="other" title={["마이페이지", "My page"]}><MyPage /></JourneyShell>;
}
