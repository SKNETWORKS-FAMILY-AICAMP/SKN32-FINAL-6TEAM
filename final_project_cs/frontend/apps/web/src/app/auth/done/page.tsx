import { JourneyShell } from "@/components/layout/journey-shell";
import { SocialDone } from "@/features/account/social-done";

/** Where the server sends the browser after a social sign-in (`/auth/done?ticket=…` or `?error=…`). */
export default function AuthDonePage() {
  return <JourneyShell view="other" title={["로그인", "Sign in"]}><SocialDone /></JourneyShell>;
}
