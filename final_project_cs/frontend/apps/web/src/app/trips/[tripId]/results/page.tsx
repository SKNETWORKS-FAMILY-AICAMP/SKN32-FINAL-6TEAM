import { redirect } from "next/navigation";
import { routes } from "@/lib/routes";

/** 따로 보는 「검증 결과」 화면은 없다 — `../verification/page.tsx` 와 같은 이유로 그 여행 화면으로 보낸다. */
export default async function ResultsPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  redirect(routes.trip(tripId));
}
