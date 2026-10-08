import { redirect } from "next/navigation";
import { routes } from "@/lib/routes";

/**
 * ★`[2026-10-03]` 따로 보는 「검증 진행」 화면은 없다 — 서버는 계획을 **등록할 때** 판정하고(`_create_trip`), 그 확인은 계획 확인 화면
 * (`/intakes/…`)이 맡는다. 옛 주소로 들어온 사람은 그 여행 화면으로 보낸다(살펴볼 점·알림·변경 이력이 거기 있다).
 */
export default async function VerificationPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = await params;
  redirect(routes.trip(tripId));
}
