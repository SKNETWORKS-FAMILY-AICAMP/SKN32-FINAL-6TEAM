import { routes } from "@/lib/routes";
import { openApi } from "@/lib/live/client";
import type { Language } from "@/lib/i18n";

/** 본인 여행인지 확인할 뿐, 실제 여행 읽기·변경의 동의·권한 검사는 생략하지 않는다. */
export async function notificationTripAccess(pathname: string, language: Language): Promise<boolean> {
  const match = /^\/trips\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i.exec(pathname);
  if (!match) return false;
  const result = await openApi<{ trip_access?: boolean }>(`/v1/web/auth/me?trip_id=${match[1]}`, language);
  return result.trip_access === true;
}

/** 알림의 여행 링크는 로그인부터 확인한다. 주소 자체는 여행 접근 권한을 주지 않는다. */
export function notificationLoginPath(pathname: string, search: string, canAccess: boolean): string | null {
  if (canAccess || !/^\/trips\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(pathname) || new URLSearchParams(search).get("notices") !== "1") return null;
  return `${routes.myPageAccount}?login=1&returnTo=${encodeURIComponent(pathname + search)}`;
}
