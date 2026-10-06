"use client";

import { routeTags } from "@/features/map/route-lines";
import type { RouteShape } from "@/lib/live/route-shapes";
import { useT } from "@/lib/settings";
import styles from "./plan-check.module.css";

/**
 * `[2026-10-05 사용자 지시 — 지도에 포커스가 있을 때 하단 안내 칸 옆에 「(선 색) ── 지하철」처럼 태그로, 이상하다 싶은 경로만 더 말하게]` The legend over the map: a small tag for each kind of route that is drawn
 * (a bit of line in the colour its lines have, and its name), and ONE more for the routes that are only a guess (a dashed straight line) - the odd ones. Everything else about a route is under the line when it is pressed.
 * The tags take no press (the map under them does). Nothing is shown for a map with no lines.
 */
export function RouteTags({ shapes }: { shapes: RouteShape[] }) {
  const t = useT();
  const { kinds, guessed } = routeTags(shapes);
  if (kinds.length === 0) return null;
  return <ul className={styles.routeTags} aria-label={t("지도의 선 색", "What the lines on the map are")} data-route-tags>
    {kinds.map((kind) => <li key={kind.mode} data-mode={kind.mode}>
      <span className={styles.sample} style={{ background: `var(${kind.variable})` }} aria-hidden="true" />{kind.label}
    </li>)}
    {guessed > 0 && <li data-guess>
      <span className={styles.sampleDashed} aria-hidden="true" />{t(`직선으로 이은 ${guessed}구간`, `${guessed} joined by a straight line`)}
    </li>}
  </ul>;
}
