"use client";

import Link from "next/link";
import { ArrowRight, ChevronRight, Plus } from "lucide-react";
import { Badge, Button, ButtonLink, PageHeading, Panel, QueryState } from "@/components/ui";
import { DATA_MODE } from "@/lib/gateway";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import type { TripSummary } from "./model";
import { useTrips } from "./use-trip";
import styles from "./trip-list.module.css";

const icon = { size: 18, strokeWidth: 1.6, "aria-hidden": true } as const;
/** How many recent trips the home card shows; more than this adds the link to the full list. */
const RECENT = 3;

/** Trip rows: title and registration time (never shown as the trip's dates). A row opens the trip, which points to the check or results until the trip starts. */
function TripRows({ trips, compact = false }: { trips: TripSummary[]; compact?: boolean }) {
  const t = useT();
  const { language } = useSettings();
  // Registration time in Seoul, like every time on the trip screens.
  const added = new Intl.DateTimeFormat(language === "ko" ? "ko-KR" : "en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Seoul" });
  return <ul className={`${styles.list} ${compact ? styles.compact : ""}`}>{trips.map((trip) => <li key={trip.id}>
    <Link href={routes.trip(trip.id)} className={styles.row}>
      <span className={styles.text}>
        <strong>{trip.title}</strong>
        {trip.createdAt && <small>{t(`${added.format(new Date(trip.createdAt))} 등록`, `Added ${added.format(new Date(trip.createdAt))}`)}</small>}
      </span>
      {trip.version !== null && trip.version > 1 && <Badge>{t("바뀐 일정 있음", "Updated")}</Badge>}
      <ChevronRight {...icon} />
    </Link>
  </li>)}</ul>;
}

/** "My trips" — this browser's trips, newest first. */
export function TripList() {
  const t = useT();
  const query = useTrips();
  if (query.isPending || query.error || !query.data) {
    return <QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />;
  }
  const trips = query.data;
  return <>
    <PageHeading eyebrow="MY TRIPS" title={t("내 여행", "My trips")}
      description={DATA_MODE === "demo" ? t("이 탭에서 등록한 여행이에요. 최근에 등록한 여행이 위에 있어요.", "Trips added in this tab, newest first.") : t("이 브라우저에서 등록한 여행이에요. 최근에 등록한 여행이 위에 있어요.", "Trips added in this browser, newest first.")} />
    {trips.length === 0
      ? <Panel className={styles.empty}><p>{t("아직 등록한 여행이 없어요.", "No trips yet.")}</p></Panel>
      : <TripRows trips={trips} />}
    <div className={styles.actions}><ButtonLink href={routes.newTrip} variant="primary"><Plus {...icon} />{t("새 여행 등록", "Add a trip")}</ButtonLink></div>
  </>;
}

/** Home card: the most recent trips from the same list. Loading, no trips and a failed read stay inside the card. */
export function RecentTrips() {
  const t = useT();
  const query = useTrips();
  const trips = query.data ?? [];
  return <section className={styles.recent} aria-labelledby="recent-trips-title">
    <header className={styles.recentHead}>
      <h2 id="recent-trips-title">{t("내 여행", "My trips")}</h2>
      {trips.length > RECENT && <Link href={routes.trips} className={styles.all}>{t("전체일정 보기", "View all")}<ArrowRight size={14} strokeWidth={1.8} aria-hidden="true" /></Link>}
    </header>
    {query.isPending ? <p className={styles.state} role="status">{t("여행을 불러오고 있어요.", "Loading your trips.")}</p>
      : query.error ? <div className={styles.failed} role="alert">
        <p>{query.error.message}</p>
        <Button onClick={() => void query.refetch()} disabled={query.isFetching}>{t("다시 불러오기", "Try again")}</Button>
      </div>
      : trips.length === 0 ? <p className={styles.state}>{t("아직 등록한 여행이 없어요.", "No trips yet.")}</p>
      : <TripRows trips={trips.slice(0, RECENT)} compact />}
  </section>;
}
