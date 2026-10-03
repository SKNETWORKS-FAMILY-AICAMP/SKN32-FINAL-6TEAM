"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { ro } from "@/lib/josa";
import { useT } from "@/lib/settings";
import type { PlacePhoto, PlanCandidate, PlanItem } from "./model";
import { Act, Checks, letter, VerdictPill } from "./parts";
import styles from "./plan-check.module.css";

/** One stop being changed: the alternatives found for it (card 0 is the stop as it is) and the card in view. */
export interface ChangeSession {
  id: string;
  list: PlanCandidate[];
  /** 0 — the stop as it is; 1… — `list[index - 1]`. */
  index: number;
  state: "loading" | "ready" | "failed";
  message?: string;
}

/** What the top bar's search found. `unsupported` — no search on this server yet (the place can still be changed by name). */
export interface SearchState { query: string; list: PlanCandidate[]; state: "loading" | "ready" | "failed" | "unsupported"; message?: string }

/**
 * ⑤ Changing one stop's place (mockup scenario 4, 개정 4): the map and the sheet stay, the content changes. Cards to swipe —
 * the stop as it is, then alternative A, B, C (and a place picked from the search) — each with its checks and
 * 「이 장소로 바꾸기」; the place's photos below (slide the sheet up); the search results while the top bar has words.
 * The page decides what each source gives; a part with no source says so instead of disappearing.
 */
export function PlaceChange({ item, session, search, onIndex, onApply, onApplyName, onPick, onSheetFull, explain, applyWhy, candidatesSupported, editor }: {
  item: PlanItem; session: ChangeSession; search: SearchState | null;
  onIndex: (index: number) => void; onApply: (candidate: PlanCandidate) => void; onApplyName: (name: string) => void;
  onPick: (candidate: PlanCandidate) => void; onSheetFull: () => void; explain: (why: string) => void;
  /** Why 「이 장소로 바꾸기」 cannot act (no way to change a place here, or the stop is locked) — null when it can. */
  applyWhy: string | null;
  candidatesSupported: boolean;
  /** The stop's own details (name, date, times, 「장소 없음」) — the editor, when the page can save them. */
  editor?: ReactNode;
}) {
  const t = useT();
  const cards = session.list.length + 1;
  const card = session.index === 0 ? null : session.list[session.index - 1];
  const position = session.index === 0 ? t("지금 일정", "Now")
    : card?.source === "search" ? t("검색으로 고른 곳", "From search") : t(`대체 후보 ${letter(session.index)}`, `Alternative ${letter(session.index)}`);
  return <div className={styles.change}>
    <header className={styles.changeHead}>
      <h3 id="plan-change-title" className={styles.changeTitle} tabIndex={-1}>{t(`${item.title} 바꾸기`, `Change ${item.title}`)}</h3>
      <span className={styles.changePos}>{position} · {session.index + 1}/{cards}</span>
    </header>
    {search
      ? <SearchResults search={search} onPick={onPick} onApplyName={onApplyName} applyWhy={applyWhy} explain={explain} />
      : <div className={styles.changeBody}>
        <Carousel session={session} onIndex={onIndex}>
          <CurrentCard item={item} session={session} candidatesSupported={candidatesSupported} />
          {session.list.map((candidate, at) =>
            <CandidateCard key={candidate.id} candidate={candidate} index={at + 1} active={session.index === at + 1} applyWhy={applyWhy} explain={explain} onApply={() => onApply(candidate)} />)}
        </Carousel>
        {cards > 1 && <div className={styles.dots} role="group" aria-label={t("카드 고르기", "Choose a card")}>{Array.from({ length: cards }, (_, index) =>
          <button key={index} type="button" aria-pressed={index === session.index} aria-label={index === 0 ? t("지금 일정", "Now") : t(`후보 ${letter(index)}`, `Alternative ${letter(index)}`)}
            onClick={() => onIndex(index)}><span aria-hidden="true" /></button>)}</div>}
        <Photos item={item} card={card} others={session.list.length} onSheetFull={onSheetFull} />
        {editor}
      </div>}
  </div>;
}

/** Cards side by side; swiping one into the middle makes it the card in view (and its pin on the map). */
function Carousel({ session, onIndex, children }: { session: ChangeSession; onIndex: (index: number) => void; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // A card chosen from a dot or a pin comes into the middle.
  useEffect(() => {
    const element = box.current?.children[session.index] as HTMLElement | undefined;
    if (!box.current || !element) return;
    const left = element.offsetLeft - (box.current.clientWidth - element.offsetWidth) / 2;
    if (Math.abs(box.current.scrollLeft - left) > 4) box.current.scrollTo({ left, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [session.index]);
  useEffect(() => () => clearTimeout(timer.current), []);
  function settle() {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const current = box.current;
      if (!current) return;
      const middle = current.scrollLeft + current.clientWidth / 2;
      let best = 0, distance = Infinity;
      Array.from(current.children).forEach((child, index) => {
        const element = child as HTMLElement, gap = Math.abs(element.offsetLeft + element.offsetWidth / 2 - middle);
        if (gap < distance) { distance = gap; best = index; }
      });
      if (best !== session.index) onIndex(best);
    }, 90);
  }
  return <div ref={box} className={styles.carousel} onScroll={settle}>{children}</div>;
}

function CurrentCard({ item, session, candidatesSupported }: { item: PlanItem; session: ChangeSession; candidatesSupported: boolean }) {
  const t = useT();
  const time = [item.startsAt, item.endsAt].filter(Boolean).join("–");
  const others = session.list.length;
  const next = others ? t(`옆으로 넘기면 다른 후보 ${others}곳 →`, `Swipe for ${others} other place${others > 1 ? "s" : ""} →`)
    : session.state === "loading" ? t("다른 후보를 찾는 중…", "Finding other places…")
      : session.state === "failed" ? session.message ?? t("다른 후보를 불러오지 못했어요.", "Could not load other places.")
        : candidatesSupported ? t("다른 후보가 없어요 · 위 검색창에서 찾아 바꿀 수 있어요", "No other places · search above to change it")
          : t("대체 후보는 준비 중이에요 · 위 검색창에 장소 이름을 쓰면 바꿀 수 있어요", "Alternatives are coming · type a place name above to change it");
  return <article className={styles.changeCard} data-current aria-labelledby={`plan-change-card-${item.id}`}>
    <div className={styles.changeTop}><span className={styles.chip}>{t("지금 일정", "Now")}</span>{item.verdict && <VerdictPill verdict={item.verdict} />}</div>
    <h4 id={`plan-change-card-${item.id}`} className={styles.changeName}>{item.title}</h4>
    <p className={styles.changeSub}>{t(`${item.day}일차`, `Day ${item.day}`)} {time}{` · ${item.info?.category ?? (item.coordinates ? t("장소 정보 없음", "no place details") : t("지점 미정", "branch not set"))}`}</p>
    {item.info?.address && <p className={styles.changeSub}>{item.info.address}</p>}
    {item.checks.length > 0 && <Checks rows={item.checks} />}
    <p className={styles.changeNext} role={session.state === "failed" ? "alert" : undefined}>{next}</p>
  </article>;
}

function CandidateCard({ candidate, index, active, applyWhy, explain, onApply }: {
  candidate: PlanCandidate; index: number; active: boolean; applyWhy: string | null; explain: (why: string) => void; onApply: () => void;
}) {
  const t = useT();
  const chip = candidate.source === "search" ? t(`검색으로 고른 곳 ${letter(index)}`, `From search ${letter(index)}`)
    : t(`대체 후보 ${letter(index)}${candidate.rank ? ` · ${candidate.rank}순위` : ""}`, `Alternative ${letter(index)}${candidate.rank ? ` · #${candidate.rank}` : ""}`);
  return <article className={styles.changeCard} data-active={active || undefined} aria-labelledby={`plan-change-card-${candidate.id}`}>
    <div className={styles.changeTop}>
      <span className={styles.chip} data-source={candidate.source}>{chip}</span>
      {candidate.distance && <span className={styles.distance}>{t(`${candidate.distance.from}에서 ${candidate.distance.km.toFixed(1)}km`, `${candidate.distance.km.toFixed(1)} km from ${candidate.distance.from}`)}</span>}
    </div>
    <h4 id={`plan-change-card-${candidate.id}`} className={styles.changeName}>{candidate.name}</h4>
    {(candidate.info?.category || candidate.info?.address) && <p className={styles.changeSub}>{[candidate.info.category, candidate.info.address].filter(Boolean).join(" · ")}</p>}
    {candidate.checks.length
      ? <Checks rows={candidate.checks} />
      : <p className={styles.changeSub}>{t("바꾸면 서버가 이 장소로 일정을 다시 확인해요.", "Once changed, the server checks the plan with this place.")}</p>}
    <Act className={styles.action} data-primary why={applyWhy} explain={explain} onPress={onApply}>{t("이 장소로 바꾸기", "Change to this place")}</Act>
  </article>;
}

function Photos({ item, card, others, onSheetFull }: { item: PlanItem; card: PlanCandidate | null; others: number; onSheetFull: () => void }) {
  const t = useT();
  const name = card ? card.name : item.title;
  const info = card ? card.info : item.info;
  // A stop with no place yet has no photos; with alternatives to swipe to, theirs are a swipe away.
  const unset = !card && !item.coordinates && others > 0;
  const photos: PlacePhoto[] = info?.photos ?? [];
  return <>
    <button type="button" className={styles.hint} onClick={onSheetFull}>{photos.length
      ? t(`시트를 위로 올리면 ${name} 사진 ${photos.length}장 ↑`, `Slide the sheet up for ${photos.length} photos of ${name} ↑`)
      : t("시트를 위로 올리면 사진 안내 ↑", "Slide the sheet up for photos ↑")}</button>
    <section className={styles.photos} aria-labelledby="plan-photos-title">
      <h4 id="plan-photos-title">{photos.length ? <>{t(`등록된 사진 · ${name}`, `Photos · ${name}`)}<small>{t(`${photos.length}장`, `${photos.length}`)}</small></> : t("등록된 사진", "Photos")}</h4>
      {photos.length
        ? <><div className={styles.photoGrid}>{photos.map((photo, index) => <figure key={`${photo.caption}-${index}`} className={styles.photo} data-example={photo.url ? undefined : true}>
            {/* eslint-disable-next-line @next/next/no-img-element -- place photos come from hosts the place data names, not configured in advance */}
            {photo.url ? <img src={photo.url} alt={photo.caption} loading="lazy" /> : <span className={styles.photoExample} aria-hidden="true">{t("예시", "Example")}</span>}
            <figcaption>{photo.caption}</figcaption>
          </figure>)}</div>
          {photos.some((photo) => !photo.url) && <p className={styles.photoNote}>{t("장소 정보(관광공사·카카오)에 등록된 사진이 들어갈 자리예요 · 지금은 예시 그림", "Where the place data's photos go · example drawings for now")}</p>}</>
        : <p className={styles.empty}>{unset
          ? t("지점이 정해지지 않아 사진이 없어요 · 옆으로 넘겨 후보 매장의 사진을 보세요", "No branch is set, so there are no photos · swipe to see a candidate's")
          : t("등록된 사진이 없어요 · 장소 사진은 준비 중이에요", "No photos yet · place photos are coming")}</p>}
    </section>
  </>;
}

function SearchResults({ search, onPick, onApplyName, applyWhy, explain }: {
  search: SearchState; onPick: (candidate: PlanCandidate) => void; onApplyName: (name: string) => void; applyWhy: string | null; explain: (why: string) => void;
}) {
  const t = useT();
  const query = search.query.trim();
  if (search.state === "unsupported") {
    return <div className={styles.results}>
      <p className={styles.empty}>{t("장소 검색은 준비 중이에요.", "Place search is coming.")}<br />{t("이름을 그대로 보내면 서버가 그 이름으로 장소를 찾아 다시 확인해요.", "Send the name as it is and the server looks the place up and checks the plan again.")}</p>
      <Act className={styles.action} data-primary why={applyWhy} explain={explain} onPress={() => onApplyName(query)}>{t(`「${query}」${ro(query).slice(query.length)} 바꾸기`, `Change to “${query}”`)}</Act>
    </div>;
  }
  const near = search.list.some((entry) => entry.distance);
  return <div className={styles.results} aria-busy={search.state === "loading"}>
    <p className={styles.resultsHead}>{t(`‘${query}’ 검색 결과 ${search.list.length}곳`, `${search.list.length} result${search.list.length === 1 ? "" : "s"} for ‘${query}’`)}{near && <small>{t("가까운 순", "nearest first")}</small>}</p>
    {search.state === "loading" ? <p className={styles.empty}>{t("찾는 중…", "Searching…")}</p>
      : search.state === "failed" ? <p className={styles.empty} role="alert">{search.message}</p>
        : search.list.length
          ? <ol className={styles.resultList}>{search.list.map((entry, index) => <li key={entry.id}><button type="button" className={styles.result} onClick={() => onPick(entry)}>
              <span className={styles.resultNo}>{index + 1}</span>
              <span className={styles.resultBody}><b>{entry.name}</b>{entry.info && <small>{[entry.info.category, entry.info.address].filter(Boolean).join(" · ")}</small>}</span>
              {entry.distance && <span className={styles.resultKm}>{entry.distance.km.toFixed(1)}km</span>}
            </button></li>)}</ol>
          : <p className={styles.empty}>{t(`‘${query}’에 맞는 장소가 없어요 · 이름을 다시 확인해 주세요`, `No place matches ‘${query}’ · check the name`)}</p>}
  </div>;
}
