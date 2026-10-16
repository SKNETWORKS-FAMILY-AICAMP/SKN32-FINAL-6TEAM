"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSettings, useT } from "@/lib/settings";
import { serviceStatus } from "./client";
import styles from "./support.module.css";

/**
 * `[2026-10-17 사용자 지적 — ST4F-603]` 운영 앱에서 보낸 공지가 60초 동안 안 보였다 — 15초마다 읽고, 탭으로 돌아오면 바로 읽는다(`staleTime` 0).
 *   숨긴 탭에서는 읽지 않는다(React Query 기본). 바로 받는 길(서버가 미는 신호)은 서버 몫이라 이 값은 늦음을 줄일 뿐이다.
 */
const NOTICE_REFRESH_MS = 15_000;
/**
 * `[2026-10-14 x600 실서버 확인]` 공지는 배경 정보라 한 번 실패로 띠를 띄우지 않는다 — 두 번 더 묻고(1초 · 2초 뒤) 그래도 못 받을 때만 「확인하지 못했어요」.
 * 앱 전체 기본값은 다시 묻지 않음(`providers.tsx` `retry: false`)이라, 첫 화면에서 화면 이동에 끊긴 요청(ERR_ABORTED) 하나로 띠가 떴다.
 */
const NOTICE_RETRIES = 2;

/**
 * `[2026-10-17 사용자 결정 — ST4F-603]` 운영 앱의 공지 종류(`kind` — 운영 앱이 고르는 「안내」 · 「기능 차질·장애」 · 「점검 예고」)를 딱지와 색으로 가른다.
 *   장애 빨강 · 점검 예고 노랑 · 안내 기본색, 장애가 가장 위. 모르는 종류는 안내 모양에 그 이름 그대로(옛: 세 종류가 같은 노란 띠에 제목 · 본문만).
 */
const KINDS: Record<string, { tone: "error" | "warning" | "info"; rank: number; en: string }> = {
  "기능 차질·장애": { tone: "error", rank: 0, en: "Service disruption" },
  "점검 예고": { tone: "warning", rank: 1, en: "Planned maintenance" },
  "안내": { tone: "info", rank: 2, en: "Notice" },
};
const kindOf = (kind: string) => KINDS[kind] ?? { tone: "info" as const, rank: 3, en: kind };

export function ServiceNotices() {
  const t = useT();
  const { language } = useSettings();
  const query = useQuery({ queryKey: ["service-notices", language], queryFn: () => serviceStatus(language), staleTime: 0, refetchInterval: NOTICE_REFRESH_MS, refetchOnWindowFocus: true,
    retry: NOTICE_RETRIES, retryDelay: (attempt) => 1000 * 2 ** attempt });
  const [dismissed, setDismissed] = useState<string | null>(null);
  const data = query.data;
  const identity = JSON.stringify([data?.maintenance, data?.notices]);
  // 앞서 받은 공지가 있으면 다시 묻다 실패해도 그것을 그대로 둔다 — 「확인하지 못했어요」는 한 번도 못 받았을 때만
  const failed = Boolean(query.error) && !data;
  const shown = !((query.isPending || (!failed && !data?.maintenance.enabled && !data?.notices.length)) || dismissed === identity);
  const box = useRef<HTMLElement>(null);
  // ★`[2026-10-17 사용자 지시 — ST4F-603]` 배너는 화면 맨 위에 뜬다(옛: 아래 — 10-08 `bf42b659` 운영 앱 연결 때 들어왔고 아래로 정한 근거는 문서 · 커밋에 없다).
  //   서버가 늦을 때의 안내(`wait-notice`)도 맨 위라, 배너가 떠 있는 동안 그 높이만큼 아래로 내린다(`--service-notice-space`).
  useEffect(() => {
    const node = box.current;
    if (!shown || !node) return;
    const root = document.documentElement;
    const observer = new ResizeObserver(() => root.style.setProperty("--service-notice-space", `${node.offsetHeight + 8}px`));
    observer.observe(node);
    return () => { observer.disconnect(); root.style.removeProperty("--service-notice-space"); };
  }, [shown]);
  if (!shown) return null;
  return <aside ref={box} className={styles.banner} aria-label={t("서비스 공지", "Service notices")} aria-live="polite">
    {failed && <><h2>{t("서비스 공지를 확인하지 못했어요", "Could not check service notices")}</h2><p>{t("공지와 점검 상태를 다시 확인해 주세요.", "Please check notices and maintenance status again.")}</p><button type="button" disabled={query.isFetching} onClick={() => void query.refetch()}>{t("다시 확인", "Check again")}</button></>}
    {data?.maintenance.enabled && <><h2>{t("서비스 점검 안내", "Service maintenance")}</h2><p>{language === "en" && data.maintenance.messageEn ? data.maintenance.messageEn : data.maintenance.message}</p>{data.maintenance.endsAt && <p>{t("종료 예정: ", "Expected end: ")}<time dateTime={data.maintenance.endsAt}>{new Date(data.maintenance.endsAt).toLocaleString(language)}</time></p>}</>}
    {[...(data?.notices ?? [])].sort((a, b) => kindOf(a.kind).rank - kindOf(b.kind).rank).map((notice) => {
      const kind = kindOf(notice.kind);
      return <div key={notice.id} className={styles.noticeItem} data-tone={kind.tone}>
        <span className={styles.noticeKind}>{language === "en" ? kind.en : notice.kind}</span>
        <h2>{language === "en" && notice.titleEn ? notice.titleEn : notice.title}</h2><p>{language === "en" && notice.bodyEn ? notice.bodyEn : notice.body}</p>
      </div>;
    })}
    <div className={styles.bannerActions}><Link href="/support">{t("문의하기", "Contact support")}</Link><button type="button" onClick={() => setDismissed(identity)}>{t("공지 닫기", "Dismiss notice")}</button></div>
  </aside>;
}
