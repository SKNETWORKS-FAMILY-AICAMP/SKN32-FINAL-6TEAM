"use client";

import { useEffect, useState } from "react";
import { ro } from "@/lib/josa";
import { useT } from "@/lib/settings";
import type { PlanCandidate, PlanItem } from "./model";
import { Act, placeMeta, reason } from "./parts";
import styles from "./unfound-place.module.css";

/** The card's three answers, wired by the screen (`plan-check.tsx`): a candidate as it is, the stop's own place change with the search open, or 「장소 없음」. */
export interface UnfoundActions {
  pick: (item: PlanItem, candidate: PlanCandidate) => void;
  myself: (item: PlanItem) => void;
  none: (item: PlanItem) => void;
}

const SHOWN = 3;

/**
 * `[2026-10-19 사용자 결정 — 못 찾은 장소는 후보 보이고 묻기 + 직접 고르기]` On the card of a stop whose place the server could not find (`item.unfound`): the server's question as it is,
 * up to three candidates (the stop's own `GET …/candidates`, the same list as the change screen), 「직접 고르기」 (the stop's place change with the search open — the plan check IS the
 * edit screen, so nothing else opens) and 「장소 없이 두기」. The customer decides; the page names no place of its own.
 */
export function UnfoundPlace({ item, prefix, candidates, why, explain, on }: {
  item: PlanItem & { unfound: NonNullable<PlanItem["unfound"]> };
  prefix: string;
  candidates?: (id: string) => Promise<PlanCandidate[]>;
  /** Why nothing here can act now (locked, being sent, marked for deletion) — null when it can. */
  why: string | null;
  explain: (why: string) => void;
  on: UnfoundActions;
}) {
  const t = useT();
  const [found, setFound] = useState<{ state: "loading" | "ready" | "failed"; list: PlanCandidate[]; message?: string }>(
    // `[2026-10-26 12:52 사용자 보고]` The candidates the server put on the question show at once; the stop's own list (same calculation) replaces them when it comes.
    () => item.unfound.candidates?.length ? { state: "ready", list: item.unfound.candidates.slice(0, SHOWN) } : candidates ? { state: "loading", list: [] } : { state: "ready", list: [] });
  useEffect(() => {
    if (!candidates) return;
    let live = true;
    // Asked a moment later: the page's own effects (which hand the calls the plan on screen) run after this card's, so asked at once the stop is not known yet.
    const timer = setTimeout(() => {
      candidates(item.id).then((list) => { if (live) setFound((now) => ({ state: "ready", list: list.length || !now.list.length ? list.slice(0, SHOWN) : now.list })); },
        (error: unknown) => { if (live) setFound((now) => now.list.length ? now : { state: "failed", list: [], message: reason(error) }); });
    }, 0);
    return () => { live = false; clearTimeout(timer); };
  }, [candidates, item.id]);
  const titleId = `${prefix}plan-unfound-${item.id}`;
  return <section className={styles.box} aria-labelledby={titleId} data-unfound={item.id} data-blocked={item.unfound.blocked || undefined} data-details>
    <p id={titleId} className={styles.question}>{item.unfound.question}</p>
    {found.state === "loading" && <p className={styles.note} role="status">{t("후보를 찾는 중…", "Finding candidates…")}</p>}
    {found.state === "failed" && <p className={styles.note} role="alert">{found.message}</p>}
    {found.state === "ready" && found.list.length > 0 && <ul className={styles.list} aria-label={t("후보", "Candidates")}>
      {found.list.map((candidate) => <li key={candidate.id}>
        <Act className={styles.candidate} why={why} explain={explain} onPress={() => on.pick(item, candidate)}
          aria-label={t(`${ro(candidate.name)} 정하기`, `Choose ${candidate.name}`)}>
          <b>{candidate.name}</b>
          {(placeMeta(candidate.info, t) || candidate.distance) && <small>{[placeMeta(candidate.info, t),
            candidate.distance ? t(`${candidate.distance.from}에서 ${candidate.distance.km.toFixed(1)}km`, `${candidate.distance.km.toFixed(1)} km from ${candidate.distance.from}`) : ""].filter(Boolean).join(" · ")}</small>}
        </Act>
      </li>)}
    </ul>}
    <div className={styles.actions}>
      <Act className={styles.action} data-primary why={why} explain={explain} onPress={() => on.myself(item)}>{t("직접 고르기", "Choose myself")}</Act>
      <Act className={styles.action} why={why} explain={explain} onPress={() => on.none(item)}>{t("장소 없이 두기", "Keep without a place")}</Act>
    </div>
  </section>;
}
