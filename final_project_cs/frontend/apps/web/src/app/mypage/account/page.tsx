import { JourneyShell } from "@/components/layout/journey-shell";
import { AccountPage } from "@/features/profile/profile";

export default function Page() {
  return <JourneyShell view="other" title={["로그인 · 계정", "Sign-in & accounts"]}><AccountPage /></JourneyShell>;
}
