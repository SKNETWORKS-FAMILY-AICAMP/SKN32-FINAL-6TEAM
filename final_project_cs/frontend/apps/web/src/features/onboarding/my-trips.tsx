"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { seoul } from "@/lib/live/gateway";
import { listTrips } from "@/lib/live/extras";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import styles from "./my-trips.module.css";

/** How many trips the card lists before it says how many it left out. */
export const MY_TRIPS_LIMIT = 3;

/**
 * Live only: the customer's own trips (`GET /v1/web/trips`, opened by the stored user key), so someone who comes back
 * is not shown the first-visit screen as if nothing existed. No key or no trips: nothing is drawn.
 * A list that could not be read is said so — it is not the same as "no trips".
 */
export function MyTrips() {
  const t = useT();
  const { language } = useSettings();
  const query = useQuery({ queryKey: ["my-trips", language], queryFn: () => listTrips(language), retry: false, refetchOnWindowFocus: false });

  if (query.isPending) return null;
  if (query.error) {
    return <p className={styles.error} role="alert">{t("내 여행 목록을 읽지 못했어요 — ", "Could not read your trips — ")}{query.error.message}</p>;
  }
  const trips = query.data ?? [];
  if (!trips.length) return null;
  const shown = trips.slice(0, MY_TRIPS_LIMIT);
  const hidden = trips.length - shown.length;
  return <section className={styles.card} aria-labelledby="my-trips-title">
    <h2 id="my-trips-title">{t("내 여행 이어보기", "Continue your trip")}</h2>
    <ul>{shown.map((trip) => <li key={trip.tripId}>
      <Link href={routes.trip(trip.tripId)}><strong>{trip.title}</strong><span>{t(`${seoul(trip.createdAt).date} 등록`, `Registered ${seoul(trip.createdAt).date}`)}</span></Link>
    </li>)}</ul>
    {hidden > 0 && <p className={styles.cut}>{t(`전체 ${trips.length}개 중 ${hidden}개는 화면에 없어요.`, `${hidden} of ${trips.length} trips are not on screen.`)}</p>}
  </section>;
}
