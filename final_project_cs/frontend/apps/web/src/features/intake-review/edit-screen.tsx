"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, Search, X } from "lucide-react";
import type { CandidatePlace, ReviewItem } from "@/lib/live/intake-review";
import { getPlacePhotos, searchPlaces, type Candidate } from "@/lib/live/intake-review";
import { useSettings, useT } from "@/lib/settings";
import { ActionButton } from "./action-button";
import { cx } from "./cx";
import { buildCards, chipText, distanceText, indexOfPlace, positionText, safePhotoUrl, type EditCard } from "./edit-model";
import { EditMap } from "./edit-map";
import { CheckRows } from "./marks";
import { statusWord } from "./review-model";
import { intakeKey } from "./use-intake-stream";
import { useCandidates } from "./use-candidates";
import { useDebounced } from "./use-debounced";
import styles from "./edit-screen.module.css";
import screenStyles from "./review-screen.module.css";
import sheetStyles from "./review-sheet.module.css";

type SheetSize = "peek" | "half" | "full";
const NEXT_SIZE: Record<SheetSize, SheetSize> = { peek: "half", half: "full", full: "peek" };
/** The server needs two characters (spaces do not count) to search. */
const MIN_QUERY = 2;
const SHOWN_PHOTOS = 6;

export interface EditActions {
  changePlace: (item: ReviewItem, place: CandidatePlace, how: "pick" | "search") => void;
  saveTimes: (item: ReviewItem, times: { date: string; starts: string; ends: string }) => void;
  overlay: ReactNode;
}

/**
 * The edit screen (mockup 「수정 화면」): the same map and sheet, with the bar turned into a place search. The sheet is a row of
 * cards — the stop as it is, then the other places the server found for it — to swipe through; the map shows the one in front.
 * Typing in the search turns the sheet into a list of results; picking one brings it in as a card.
 *
 * ★Every card shows the server's check of THAT place at THIS stop's day and time. The screen never says a place "fits" itself.
 */
export function EditScreen({ intakeId, revision, item, order, others, actions, onClose }: {
  intakeId: string;
  revision: number;
  item: ReviewItem;
  /** The stop's position in its day, and the day's other stops. */
  order: number;
  others: readonly { item: ReviewItem; order: number }[];
  actions: EditActions;
  onClose: () => void;
}) {
  const t = useT();
  const { language } = useSettings();
  const [index, setIndex] = useState(0);
  const [query, setQuery] = useState("");
  const [picks, setPicks] = useState<Candidate[]>([]);
  const [size, setSize] = useState<SheetSize>("half");
  const carousel = useRef<HTMLDivElement>(null);
  const settle = useRef<ReturnType<typeof setTimeout> | null>(null);
  const jump = useRef<number | null>(null);

  const alternatives = useCandidates(intakeId, item, revision, true);
  const cards = buildCards(item, alternatives.data, picks);
  const at = Math.min(index, cards.length - 1);
  const card = cards[at];

  const typed = query.trim();
  const debounced = useDebounced(typed, 300);
  const searching = typed !== "";
  const searchable = debounced.replace(/\s/g, "").length >= MIN_QUERY;
  const search = useQuery({
    queryKey: [...intakeKey(intakeId, language), "search", revision, item.id, debounced],
    queryFn: ({ signal }) => searchPlaces(intakeId, item, revision, debounced, language, signal),
    enabled: searching && searchable, staleTime: 30_000, retry: false, refetchOnWindowFocus: false,
  });
  const photos = useQuery({
    queryKey: ["place-photos", card?.photoRef, language],
    queryFn: () => getPlacePhotos(card!.photoRef!, language),
    enabled: Boolean(card?.photoRef), staleTime: 10 * 60_000, retry: false, refetchOnWindowFocus: false,
  });

  // The row of cards moves under the finger; the card nearest the middle is the one in front.
  const frontCard = () => {
    const row = carousel.current;
    if (!row) return;
    const middle = row.scrollLeft + row.clientWidth / 2;
    let best = 0, nearest = Infinity;
    [...row.children].forEach((child, i) => {
      const element = child as HTMLElement;
      const distance = Math.abs(element.offsetLeft + element.offsetWidth / 2 - middle);
      if (distance < nearest) { nearest = distance; best = i; }
    });
    setIndex(best);
  };
  const onScroll = () => { if (settle.current) clearTimeout(settle.current); settle.current = setTimeout(frontCard, 80); };
  const scrollToCard = (i: number) => {
    const row = carousel.current;
    const element = row?.children[i] as HTMLElement | undefined;
    if (row && element) row.scrollTo({ left: element.offsetLeft - (row.clientWidth - element.offsetWidth) / 2, behavior: "smooth" });
  };
  const goTo = (i: number) => { setIndex(i); scrollToCard(i); };
  useEffect(() => () => { if (settle.current) clearTimeout(settle.current); }, []);
  // A place picked from the search has just become a card — bring it to the front once the row has been drawn.
  useEffect(() => { if (jump.current !== null) { scrollToCard(jump.current); jump.current = null; } });

  function pick(candidate: Candidate) {
    const next = [...picks, candidate];
    const nextCards = buildCards(item, alternatives.data, next);
    const found = indexOfPlace(nextCards, candidate.place);
    setPicks(next);
    setQuery("");
    setIndex(Math.max(0, found));
    jump.current = Math.max(0, found);
  }

  return <div className={screenStyles.root} data-sheet={size}>
    <EditMap order={order} others={others} cards={cards} index={at} onPick={goTo} />
    <div className={screenStyles.bar}>
      <button type="button" className={screenStyles.back} aria-label={t("수정 닫기", "Close editing")} onClick={onClose}><ChevronLeft size={22} strokeWidth={1.8} aria-hidden="true" /></button>
      <label className={styles.search}>
        <Search aria-hidden="true" />
        <input type="text" value={query} onChange={(event) => setQuery(event.target.value)} autoComplete="off" aria-label={t("장소 검색", "Search places")}
          placeholder={t(`${item.place?.name ?? item.title} 대신 찾을 장소`, `A place instead of ${item.place?.name ?? item.title}`)}
          onKeyDown={(event) => { if (event.key === "Escape" && query) { event.preventDefault(); setQuery(""); } }} />
        {query && <button type="button" className={styles.clear} aria-label={t("검색어 지우기", "Clear the search")} onClick={() => setQuery("")}><X size={12} aria-hidden="true" /></button>}
      </label>
    </div>
    <section className={sheetStyles.sheet} aria-label={t("장소 바꾸기", "Change the place")}>
      <button type="button" className={sheetStyles.handle} aria-label={t("목록 높이 바꾸기", "Change the list height")} onClick={() => setSize(NEXT_SIZE[size])}><i /></button>
      {searching
        ? <SearchResults query={typed} ready={searchable && debounced === typed} loading={search.isFetching} failed={search.isError} results={search.data?.results ?? []} notes={search.data?.notes ?? []}
          shortQuery={!searchable} onPick={pick} />
        : <div className={styles.view}>
          <div className={styles.vhead}>
            <b>{t(`${item.place?.name ?? item.title} 바꾸기`, `Change ${item.place?.name ?? item.title}`)}</b>
            <span className={styles.pos}>{card ? positionText(card, at, cards.length, t) : ""}</span>
          </div>
          <div className={styles.vbody}>
            <div className={styles.ecar} ref={carousel} onScroll={onScroll} role="group" aria-roledescription="carousel" aria-label={t("바꿀 장소 후보", "Places to switch to")}>
              {cards.map((entry, i) => <CardView key={entry.key} card={entry} index={i} total={cards.length} on={i === at} item={item} loading={alternatives.isPending}
                onApply={() => { if (entry.place) { actions.changePlace(item, entry.place as CandidatePlace, entry.kind === "search" ? "search" : "pick"); onClose(); } }}
                onTimes={(times) => { actions.saveTimes(item, times); onClose(); }} />)}
            </div>
            <div className={styles.dots}>{cards.map((entry, i) => <button key={entry.key} type="button" className={styles.dotHit} aria-label={positionText(entry, i, cards.length, t)} aria-current={i === at} onClick={() => goTo(i)}><i className={cx(styles.dot, i === at && styles.dotOn)} /></button>)}</div>
            {alternatives.isError && <p className={styles.rnote} style={{ margin: "8px 16px 0" }} role="alert">{t("대체 후보를 불러오지 못했어요 · 검색으로 찾아 보세요", "Could not load the alternatives · try the search")}</p>}
            {alternatives.data && alternatives.data.notes.length > 0 && <p className={styles.rnote} style={{ margin: "8px 16px 0" }}>{notesText(alternatives.data.notes, t)}</p>}
            <PhotoSection card={card} loading={photos.isFetching} failed={photos.isError} data={photos.data} onShow={() => setSize("full")} />
          </div>
        </div>}
    </section>
    {actions.overlay}
  </div>;
}

/** What the server said about a short or approximate list, in words. Unknown notes are not shown as if they were facts. */
function notesText(notes: readonly string[], t: ReturnType<typeof useT>): string {
  const said = new Set<string>();
  for (const note of notes) {
    if (note === "engine_budget_exhausted") said.add(t("이동 시간 일부는 직선거리로 어림했어요", "Some travel times are straight-line estimates"));
    else if (note === "no_same_kind") said.add(t("같은 종류의 다른 장소를 찾지 못했어요", "No other place of the same kind was found"));
    else if (note === "no_other_branches") said.add(t("같은 이름의 다른 지점을 찾지 못했어요", "No other branch with the same name was found"));
    else if (note.startsWith("kakao:")) said.add(t("카카오 지도 결과를 일부 불러오지 못했어요", "Some map results could not be loaded"));
  }
  return [...said].join(" · ");
}

function CardView({ card, index, total, on, item, loading, onApply, onTimes }: {
  card: EditCard; index: number; total: number; on: boolean; item: ReviewItem; loading: boolean;
  onApply: () => void; onTimes: (times: { date: string; starts: string; ends: string }) => void;
}) {
  const t = useT();
  const name = card.place?.name ?? t("지점 미정", "No place yet");
  const distance = distanceText(card.distance, t);
  const when = item.day ? t(`${item.day}일차`, `Day ${item.day}`) : "";
  const sub = card.kind === "current" ? [when, item.starts_at && item.ends_at ? `${item.starts_at}–${item.ends_at}` : item.starts_at].filter(Boolean).join(" ") : card.subtitle;
  return <div className={cx(styles.ec, card.kind === "current" && styles.ecCurrent, on && styles.ecOn)} aria-label={`${chipText(card, index, t)} · ${name}`}>
    <div className={styles.ecTop}>
      <span className={cx(styles.chip, styles[`chip_${card.kind}`])}>{chipText(card, index, t)}</span>
      {card.kind === "current"
        ? <span className={cx(sheetStyles.pill, item.status === "adjusted" && sheetStyles.pill_adjusted, item.status === "review" && sheetStyles.pill_review)}>{statusWord(item.status, t)}</span>
        : <span className={styles.dist}>{distance}</span>}
    </div>
    <h3 className={styles.ecName}>{name}</h3>
    {sub && <p className={styles.ecSub}>{sub}</p>}
    {card.kind !== "current" && card.estimated && <p className={styles.ecEstimated}>{t("이동 시간 일부는 직선거리 어림값이에요", "Part of the travel time is a straight-line estimate")}</p>}
    {card.rows.length > 0 ? <CheckRows rows={card.rows} /> : card.kind !== "current" && loading ? <p className={styles.ecSub}>{t("확인하는 중…", "Checking…")}</p> : null}
    {card.kind === "current"
      ? <>
        <TimesForm item={item} onSave={onTimes} />
        <p className={styles.ecNext}>{total > 1 ? t(`옆으로 넘기면 다른 후보 ${total - 1}곳 →`, `Swipe for ${total - 1} other places →`) : t("다른 후보가 없어요 · 위 검색으로 찾아 보세요", "No other places · try the search above")}</p>
      </>
      : <ActionButton className={styles.ecApply} variant="primary" unavailable={!card.pickable} onClick={onApply}
        onBlocked={() => undefined}>{card.pickable ? t("이 장소로 바꾸기", "Use this place") : t("위치 정보가 없어 고를 수 없어요", "No coordinates — cannot be picked")}</ActionButton>}
  </div>;
}

/** The stop's day and time — kept from the earlier screen (the mockup has no place for it) so a time can still be corrected. */
function TimesForm({ item, onSave }: { item: ReviewItem; onSave: (times: { date: string; starts: string; ends: string }) => void }) {
  const t = useT();
  const [date, setDate] = useState(item.date ?? "");
  const [starts, setStarts] = useState(item.starts_at ?? "");
  const [ends, setEnds] = useState(item.ends_at ?? "");
  const changed = date !== (item.date ?? "") || starts !== (item.starts_at ?? "") || ends !== (item.ends_at ?? "");
  const submit = (event: FormEvent) => { event.preventDefault(); if (changed) onSave({ date, starts, ends }); };
  return <details className={styles.times}>
    <summary>{t("날짜·시각 고치기", "Fix the date and time")}</summary>
    <form className={styles.timesForm} onSubmit={submit}>
      <label>{t("날짜", "Date")} <input type="date" value={date} onChange={(event) => setDate(event.target.value)} /></label>
      <label>{t("시작", "Start")} <input type="time" value={starts} onChange={(event) => setStarts(event.target.value)} /></label>
      <label>{t("끝", "End")} <input type="time" value={ends} onChange={(event) => setEnds(event.target.value)} /></label>
      <ActionButton type="submit" variant="primary" unavailable={!changed} onClick={() => undefined}>{t("저장", "Save")}</ActionButton>
    </form>
  </details>;
}

function PhotoSection({ card, loading, failed, data, onShow }: { card: EditCard | undefined; loading: boolean; failed: boolean; data: Awaited<ReturnType<typeof getPlacePhotos>> | undefined; onShow: () => void }) {
  const t = useT();
  if (!card) return null;
  const name = card.place?.name ?? "";
  const shots = (data?.photos ?? []).flatMap((shot) => { const src = safePhotoUrl(shot.thumb) ?? safePhotoUrl(shot.url); return src ? [{ ...shot, src }] : []; }).slice(0, SHOWN_PHOTOS);
  return <>
    {shots.length > 0 && <button type="button" className={styles.hint} onClick={onShow}>{t(`시트를 위로 올리면 ${name} 사진 ${shots.length}장 ↑`, `Pull the sheet up for ${shots.length} photos of ${name} ↑`)}</button>}
    <section className={styles.photos} aria-label={t("등록된 사진", "Registered photos")}>
      <h4>{t("등록된 사진", "Registered photos")}{name && ` · ${name}`}{shots.length > 0 && <small>{t(`${shots.length}장`, `${shots.length}`)}</small>}</h4>
      {!card.photoRef ? <p className={styles.pempty}>{card.place ? t("이 장소는 사진 정보가 없어요 · 사진은 관광공사에 등록된 장소만 보여요", "No photo source for this place · photos come from the tourism organization only") : t("지점이 정해지지 않아 사진이 없어요 · 옆으로 넘겨 후보의 사진을 보세요", "No place yet, so no photos · swipe to see an alternative's photos")}</p>
        : loading && shots.length === 0 ? <p className={styles.pempty} role="status">{t("사진을 불러오는 중…", "Loading photos…")}</p>
        : failed ? <p className={styles.pempty} role="alert">{t("사진을 불러오지 못했어요", "Could not load the photos")}</p>
        : shots.length === 0 ? <p className={styles.pempty}>{t("등록된 사진이 없어요", "No registered photos")}</p>
        : <>
          <ul className={styles.pgrid}>{shots.map((shot, i) => <li key={shot.url}><figure className={styles.shot}>
            {/* The picture comes straight from the tourism organization's address — it is never stored here. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={shot.src} alt={shot.name ?? t(`${name} 사진 ${i + 1}`, `${name} photo ${i + 1}`)} loading="lazy" referrerPolicy="no-referrer" />
            {shot.name && <figcaption>{shot.name}</figcaption>}
          </figure></li>)}</ul>
          {data?.source_note && <p className={styles.pnote}>{data.source_note}</p>}
        </>}
    </section>
  </>;
}

function SearchResults({ query, ready, loading, failed, shortQuery, results, notes, onPick }: {
  query: string; ready: boolean; loading: boolean; failed: boolean; shortQuery: boolean; results: readonly Candidate[]; notes: readonly string[]; onPick: (candidate: Candidate) => void;
}) {
  const t = useT();
  return <div className={styles.results} role="region" aria-label={t("검색 결과", "Search results")}>
    {shortQuery ? <p className={styles.pempty}>{t("두 글자 이상 적어 주세요", "Type at least two characters")}</p>
      : !ready || loading ? <p className={styles.pempty} role="status">{t("찾는 중…", "Searching…")}</p>
      : failed ? <p className={styles.pempty} role="alert">{t("검색하지 못했어요 · 잠시 뒤 다시 해 주세요", "The search failed · please try again shortly")}</p>
      : <>
        <p className={styles.rhead} role="status">{t(`‘${query}’ 검색 결과 ${results.length}곳`, `${results.length} results for ‘${query}’`)}<small>{results.some((result) => result.distance_m !== null) ? t("가까운 순", "nearest first") : ""}</small></p>
        {results.length === 0
          ? <p className={styles.pempty}>{t(`‘${query}’에 맞는 장소가 없어요 · 이름을 다시 확인해 주세요`, `Nothing matches ‘${query}’ · check the name`)}</p>
          : results.map((result, i) => {
            const pickable = typeof result.place.latitude === "number" && typeof result.place.longitude === "number";
            return <button key={`${result.place.name}|${result.place.latitude}|${result.place.longitude}`} type="button" className={styles.row} aria-disabled={!pickable || undefined}
              onClick={() => { if (pickable) onPick(result); }}>
              <span className={styles.rowNo}>{i + 1}</span>
              <span className={styles.rowText}><b>{result.place.name}</b><small>{[result.place.category, result.place.address].filter(Boolean).join(" · ")}</small></span>
              <span className={styles.rowDist}>{distanceText({ from: null, meters: result.distance_m }, t)}</span>
            </button>;
          })}
        {notes.length > 0 && <p className={styles.rnote}>{notesText(notes, t)}</p>}
      </>}
  </div>;
}
