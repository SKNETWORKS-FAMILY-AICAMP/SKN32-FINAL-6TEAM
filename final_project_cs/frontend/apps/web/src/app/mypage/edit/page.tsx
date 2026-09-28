import { JourneyShell } from "@/components/layout/journey-shell";
import { ProfileEdit } from "@/features/profile/profile";

export default function ProfileEditPage() {
  return <JourneyShell view="other" title={["프로필 수정", "Edit profile"]}><ProfileEdit /></JourneyShell>;
}
