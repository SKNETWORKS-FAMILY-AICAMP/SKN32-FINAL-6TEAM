import { JourneyShell } from "@/components/layout/journey-shell";
import { HelpPage } from "@/features/help/help-page";

export default async function Page({ searchParams }: { searchParams: Promise<{ tab?: string; screen?: string }> }) {
  const params = await searchParams;
  return <JourneyShell view="other" title={["이용 방법", "How to use"]}><HelpPage key={`${params.tab}|${params.screen}`} tab={params.tab} screen={params.screen} /></JourneyShell>;
}
