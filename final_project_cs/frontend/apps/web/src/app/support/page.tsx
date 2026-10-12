import { JourneyShell } from "@/components/layout/journey-shell";
import { SupportPage } from "@/features/support/support";

export default async function Page({ searchParams }: { searchParams: Promise<{ sent?: string }> }) {
  const params = await searchParams;
  return <JourneyShell view="other" title={["문의하기", "Contact support"]}><SupportPage sent={params.sent === "1"} /></JourneyShell>;
}
