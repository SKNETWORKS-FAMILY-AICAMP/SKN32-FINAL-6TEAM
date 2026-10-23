import { JourneyShell } from "@/components/layout/journey-shell";
import { SettingsPage } from "@/features/profile/profile";

/** `[2026-10-13 회의 확정 — 메뉴 = 마이페이지]` `/mypage` is the settings screen now (the address is kept for the Discord callback and old links). */
export default function MyPagePage() {
  return <JourneyShell view="other" title={["설정", "Settings"]}><SettingsPage /></JourneyShell>;
}
