"use client";

import { useEffect, useRef, type ReactNode } from "react";
import type { Translate } from "@/lib/i18n";
import { ro } from "@/lib/josa";
import { useT } from "@/lib/settings";
import type { PlacePhoto, PlanCandidate, PlanItem } from "./model";
import { Act, Checks, letter, placeKindLabel, placeMeta, SourceTag, VerdictPill } from "./parts";
import styles from "./plan-check.module.css";

/** One stop being changed: the alternatives found for it (card 0 is the stop as it is) and the card in view. */
export interface ChangeSession {
  id: string;
  list: PlanCandidate[];
  /** 0 — the stop as it is; 1… — `list[index - 1]`. */
  index: number;
  state: "loading" | "ready" | "failed";
  message?: string;
  /** The server's reasons for a short or empty list (`candidates` call `notes`). */
  notes?: string[];
}

/**
 * `[2026-10-03]` Why there is nothing to swipe to, in the server's own terms (`notes`, server 8b0d4c88): a booked stop is not offered other places
 * (the booked place's name is asked), a stop with no same-kind place gets none of another kind, and an area with nothing of that kind says so.
 * Null for a note it does not know — the general line is then shown, never a made-up reason.
 */
export function candidateNoteText(notes: readonly string[] | undefined, t: Translate): string | null {
  const has = (note: string) => notes?.includes(note);
  if (has("booked_needs_name")) return t("예약하신 곳이라 다른 후보를 권하지 않아요 · 위 검색창에 예약한 곳의 이름을 쓰면 바꿔요", "This is booked, so no other places are offered · type the booked place's name above to set it");
  if (has("no_candidates_in_area")) return t("글에 적힌 지역 둘레에 같은 종류의 장소가 없어요 · 위 검색창에서 찾아 보세요", "Nothing of the same kind around the area you wrote · search above");
  if (has("no_same_kind")) return t("같은 종류의 후보가 없어요 · 위 검색창에서 찾아 바꿀 수 있어요", "No place of the same kind · search above to change it");
  if (has("no_reference_point")) return t("기준이 될 위치를 정하지 못해 후보를 찾지 못했어요 · 위 검색창에서 찾아 보세요", "No point to measure from, so no candidates · search above");
  return null;
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
            <CandidateCard key={candidate.id} candidate={candidate} current={item} index={at + 1} active={session.index === at + 1} applyWhy={applyWhy} explain={explain} onApply={() => onApply(candidate)} />)}
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
        : candidatesSupported ? candidateNoteText(session.notes, t) ?? t("다른 후보가 없어요 · 위 검색창에서 찾아 바꿀 수 있어요", "No other places · search above to change it")
          : t("대체 후보는 준비 중이에요 · 위 검색창에 장소 이름을 쓰면 바꿀 수 있어요", "Alternatives are coming · type a place name above to change it");
  return <article className={styles.changeCard} data-current aria-labelledby={`plan-change-card-${item.id}`}>
    <div className={styles.changeTop}><span className={styles.chip}>{t("지금 일정", "Now")}</span>{item.verdict && <VerdictPill verdict={item.verdict} />}</div>
    <div className={styles.nameRow}><h4 id={`plan-change-card-${item.id}`} className={styles.changeName}>{item.title}</h4><SourceTag origin={item.info?.origin} /></div>
    {item.written && <p className={styles.changeSub}>{t(`원문 「${item.written}」`, `As written: “${item.written}”`)}</p>}
    <p className={styles.changeSub}>{t(`${item.day}일차`, `Day ${item.day}`)} {time}{` · ${placeMeta(item.info, t) || (item.coordinates ? t("장소 정보 없음", "no place details") : t("지점 미정", "branch not set"))}`}</p>
    {item.checks.length > 0 && <Checks rows={item.checks} />}
    <p className={styles.changeNext} role={session.state === "failed" ? "alert" : undefined}>{next}</p>
  </article>;
}

/**
 * `[2026-10-03 합의: 사용자 + Claude·Codex]` A place picked from the search (or an alternative) is changed to only after this card, never by the
 * press on the result: the server's fit judgement does not yet guarantee the KIND (a pharmacy among the restaurants), so every change is
 * looked at once. What the card adds is the server's own values side by side — never a judgement of its own: the kind the stop has now
 * and the kind of this place when both are known and differ, or that the server named no kind.
 */
export function kindNote(current: PlanItem, candidate: PlanCandidate, t: Translate): { text: string; mismatch: boolean } | null {
  const mine = current.info?.kind, theirs = candidate.info?.kind;
  if (!theirs) return { text: t("이 장소의 종류 정보가 없어요", "No category was given for this place"), mismatch: false };
  const mineLabel = placeKindLabel(mine, t), theirLabel = placeKindLabel(theirs, t);
  if (mine && theirs && mine !== theirs && mineLabel && theirLabel)
    return { text: t(`지금 일정은 ${mineLabel}, 이곳은 ${theirLabel}으로 분류돼 있어요`, `Your stop is ${mineLabel}; this place is listed as ${theirLabel}`), mismatch: true };
  return null;
}

function CandidateCard({ candidate, current, index, active, applyWhy, explain, onApply }: {
  candidate: PlanCandidate; current: PlanItem; index: number; active: boolean; applyWhy: string | null; explain: (why: string) => void; onApply: () => void;
}) {
  const t = useT();
  const note = kindNote(current, candidate, t);
  const chip = candidate.source === "search" ? t(`검색으로 고른 곳 ${letter(index)}`, `From search ${letter(index)}`)
    : t(`대체 후보 ${letter(index)}${candidate.rank ? ` · ${candidate.rank}순위` : ""}`, `Alternative ${letter(index)}${candidate.rank ? ` · #${candidate.rank}` : ""}`);
  // `[2026-10-07 서버 c0ca7054]` Which step of the ladder the server took it from, said beside the chip; and its reason under the name.
  // An id may not hold spaces (`aria-labelledby` reads them as several ids — a place named 「광장시장 순희네 빈대떡」 left its card with no name).
  const headingId = `plan-change-card-${candidate.id.replace(/\s+/g, "_")}`;
  const step = candidate.basis === "same_kind" ? t("같은 종류", "Same kind") : candidate.basis === "similar_experience" ? t("비슷한 경험", "Similar experience")
    : candidate.basis === "meal_inferred" ? t("식사 시간 식당", "Meal-time place") : candidate.basis === "lodging" ? t("숙소", "Stay")
      : candidate.basis === "lodging_meal" ? t("숙소 안 식사", "Meal at the stay") : candidate.basis === "taste" ? t("취향 추천", "For your taste") : null;
  return <article className={styles.changeCard} data-active={active || undefined} aria-labelledby={headingId}>
    <div className={styles.changeTop}>
      <span className={styles.chip} data-source={candidate.source}>{chip}</span>
      {step && <span className={styles.stepTag} data-basis={candidate.basis}>{step}</span>}
      {candidate.distance && <span className={styles.distance}>{t(`${candidate.distance.from}에서 ${candidate.distance.km.toFixed(1)}km`, `${candidate.distance.km.toFixed(1)} km from ${candidate.distance.from}`)}</span>}
    </div>
    <div className={styles.nameRow}><h4 id={headingId} className={styles.changeName}>{candidate.name}</h4><SourceTag origin={candidate.info?.origin} /></div>
    {placeMeta(candidate.info, t) && <p className={styles.changeSub}>{placeMeta(candidate.info, t)}</p>}
    {candidate.reason && <p className={styles.changeReason}>{candidate.reason}</p>}
    {note && <p className={styles.kindNote} data-mismatch={note.mismatch || undefined}>{note.text}</p>}
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
        ? <><div className={styles.photoGrid}>{photos.map((photo, index) => <figure key={`${photo.caption}-${index}`} className={styles.photo}>
            {/* eslint-disable-next-line @next/next/no-img-element -- place photos come from hosts the place data names, not configured in advance */}
            <img src={photo.url} alt={photo.caption} loading="lazy" />
            <figcaption>{photo.caption}</figcaption>
          </figure>)}</div></>
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
              <span className={styles.resultBody}><span className={styles.nameRow}><b>{entry.name}</b><SourceTag origin={entry.info?.origin} /></span>{placeMeta(entry.info, t) && <small>{placeMeta(entry.info, t)}</small>}</span>
              {entry.distance && <span className={styles.resultKm}>{entry.distance.km.toFixed(1)}km</span>}
            </button></li>)}</ol>
          : <p className={styles.empty}>{t(`‘${query}’에 맞는 장소가 없어요 · 이름을 다시 확인해 주세요`, `No place matches ‘${query}’ · check the name`)}</p>}
  </div>;
}
