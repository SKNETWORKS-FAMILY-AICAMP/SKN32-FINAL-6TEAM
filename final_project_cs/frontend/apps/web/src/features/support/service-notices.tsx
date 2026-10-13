"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSettings, useT } from "@/lib/settings";
import { serviceStatus } from "./client";
import styles from "./support.module.css";

const NOTICE_REFRESH_MS = 60_000;

export function ServiceNotices() {
  const t = useT();
  const { language } = useSettings();
  const query = useQuery({ queryKey: ["service-notices", language], queryFn: () => serviceStatus(language), staleTime: NOTICE_REFRESH_MS, refetchInterval: NOTICE_REFRESH_MS, refetchOnWindowFocus: true });
  const [dismissed, setDismissed] = useState<string | null>(null);
  const data = query.data;
  const identity = JSON.stringify([data?.maintenance, data?.notices]);
  if ((query.isPending || (!query.error && !data?.maintenance.enabled && !data?.notices.length)) || dismissed === identity) return null;
  return <aside className={styles.banner} aria-label={t("서비스 공지", "Service notices")} aria-live="polite">
    {query.error && <><h2>{t("서비스 공지를 확인하지 못했어요", "Could not check service notices")}</h2><p>{t("공지와 점검 상태를 다시 확인해 주세요.", "Please check notices and maintenance status again.")}</p><button type="button" disabled={query.isFetching} onClick={() => void query.refetch()}>{t("다시 확인", "Check again")}</button></>}
    {data?.maintenance.enabled && <><h2>{t("서비스 점검 안내", "Service maintenance")}</h2><p>{language === "en" && data.maintenance.messageEn ? data.maintenance.messageEn : data.maintenance.message}</p>{data.maintenance.endsAt && <p>{t("종료 예정: ", "Expected end: ")}<time dateTime={data.maintenance.endsAt}>{new Date(data.maintenance.endsAt).toLocaleString(language)}</time></p>}</>}
    {data?.notices.map((notice) => <div key={notice.id}><h2>{language === "en" && notice.titleEn ? notice.titleEn : notice.title}</h2><p>{language === "en" && notice.bodyEn ? notice.bodyEn : notice.body}</p></div>)}
    <div className={styles.bannerActions}><Link href="/support">{t("문의하기", "Contact support")}</Link><button type="button" onClick={() => setDismissed(identity)}>{t("공지 닫기", "Dismiss notice")}</button></div>
  </aside>;
}
