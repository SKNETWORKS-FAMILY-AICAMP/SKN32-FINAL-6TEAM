"use client";

import { stopDisplayName, stopPlaceNote } from "./stop-display";

import { useContext, useEffect, useRef, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { createPortal } from "react-dom";
import { ArrowLeft, MapPin, MessageCircle, Pencil } from "lucide-react";
import { HeaderSlot } from "@/components/layout/device-frame";
import { safePhotoUrl } from "@/features/plan-check/from-review";
import pc from "@/features/plan-check/plan-check.module.css";
import { getPlacePhotos } from "@/lib/live/intake-review";
import { useSettings, useT } from "@/lib/settings";
import { mapAppName, placeLinks } from "./map-apps";
import type { OpenChoice } from "./attention";
import type { Trip, TripStop } from "./model";
import { ProposalAsk } from "./proposal-ask";
import { bookingLabel, StopFacts } from "./trip-rows";
import styles from "./trip-screen.module.css";

/** `[2026-10-07 목업 C안]` The header while a stop's detail is open: ← and the stop's name (the brand and the trip's name give way, as on the plan check's change screen). */
export function DetailHeader({ title, onBack }: { title: string; onBack: () => void }) {
  const t = useT();
  const slot = useContext(HeaderSlot);
  return slot && createPortal(<div className={styles.detailHead} data-hide-brand>
    <button type="button" id="trip-detail-back" className={styles.detailBack} onClick={onBack} aria-label={t("상세 보기 닫기", "Close the details")}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>
    <p className={styles.detailName}><span>{title}</span><small>{t("상세", "Details")}</small></p>
  </div>, slot);
}

/**
 * `[2026-10-07 사용자 결정 — 목업 C안 「상세 보기」]` One stop's detail, the plan check's change screen laid out for a registered trip: 「○○ 상세 · n일차 · i/N」, a card for each stop of that day
 * (swiped, or a dot pressed, to the next — the map follows), and the photos below (slide the sheet up).
 * A card: the day and times, the booking note, the name and where the facts come from, kind · address, then the facts of the list card and 「이 일정 질문하기 · 지도 앱으로 열기」.
 * `[2026-10-14 사용자 결정 — ST4F-492]` 「지도 앱으로 열기」 became three buttons in a row under the ask button — the place in Naver Map · KakaoMap · Google Maps (`map-apps.tsx`).
 * Photos: the plan check's change screen asks the same call for a place's registered photos (`GET /v1/web/places/photos?ref=tour:…`). A stop of a registered trip has that ref only when
 * the server sends it (`place_ref` — not yet, asked of the backend); without it the photo part says they are coming. ★Only what the server gave — no photo is made up.
 * `[2026-10-21 사용자 결정 — ST4F-704]` A card answers here the choice the server waits for on its stop (`ProposalAsk` — the trip card says 「상세 보기에서 확인하세요」; not the notice center),
 * and every stop still to come has ✎ 「일정 수정」 at the right of its day and times: the edit opens on that stop as its ✎ opens it (「직접 수정」 of a choice — with 「직접 고치기」 open).
 * A stop that is over has neither (the edit keeps it as it is).
 */
export function TripDetail({ trip, stopId, dayNumber, onStop, onAsk, askBusy, onSheetFull, choiceOf, past, chooseBusy, onChoose, onEdit }: {
  trip: Trip; stopId: string; dayNumber: number;
  onStop: (id: string) => void; onAsk: (stop: TripStop) => void; askBusy: boolean; onSheetFull: () => void;
  choiceOf: (stopId: string) => OpenChoice | undefined; past: ReadonlySet<string>; chooseBusy: boolean;
  onChoose: (choice: OpenChoice, key: string | null) => void; onEdit: (stop: TripStop, how: "plain" | "direct") => void;
}) {
  const t = useT();
  const stop = trip.stops.find((entry) => entry.id === stopId);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  if (!stop) return null;
  const list = trip.stops.filter((entry) => entry.date === stop.date);
  const index = list.indexOf(stop);
  return <div className={styles.detail}>
    <header className={pc.changeHead}>
      <h3 id="trip-detail-title" ref={heading} className={pc.changeTitle} tabIndex={-1}>{t(`${stop.title} 상세`, `${stop.title} · details`)}</h3>
      <span className={pc.changePos}>{t(`${dayNumber}일차 · ${index + 1}/${list.length}`, `Day ${dayNumber} · ${index + 1}/${list.length}`)}</span>
    </header>
    <div className={styles.detailBody}>
      <Carousel index={index} onIndex={(at) => onStop(list[at].id)} label={t(`${dayNumber}일차 일정 상세 · 옆으로 넘기면 다른 일정`, `Day ${dayNumber} details · swipe for the other stops`)}>
        {list.map((entry, at) => {
          const over = past.has(entry.id), choice = over ? undefined : choiceOf(entry.id);
          return <DetailCard key={entry.id} stop={entry} next={list[at + 1]} dayNumber={dayNumber} active={entry.id === stop.id} onAsk={() => onAsk(entry)} askBusy={askBusy}
            onEdit={over ? undefined : (how) => onEdit(entry, how)}
            ask={choice && <ProposalAsk choice={choice} busy={chooseBusy} onChoose={(key) => onChoose(choice, key)} onEdit={() => onEdit(entry, "direct")} />} />;
        })}
      </Carousel>
      {list.length > 1 && <div className={pc.dots} role="group" aria-label={t("일정 고르기", "Choose a stop")}>{list.map((entry, at) =>
        <button key={entry.id} type="button" aria-pressed={at === index} aria-label={`${at + 1}. ${entry.title}`} onClick={() => onStop(entry.id)}><span aria-hidden="true" /></button>)}</div>}
      <Photos stop={stop} onSheetFull={onSheetFull} />
    </div>
  </div>;
}

/**
 * The registered photos of the stop in view (the plan check's photo part): the hint to slide the sheet up, then the photos with the source's credit. Fetched each time (never stored —
 * the server's rule for the tourism photos); a photo that cannot be fetched is just not shown.
 */
function Photos({ stop, onSheetFull }: { stop: TripStop; onSheetFull: () => void }) {
  const t = useT();
  const { language } = useSettings();
  const ref = stop.placeRef?.startsWith("tour:") ? stop.placeRef : null;
  const found = useQuery({ queryKey: ["place-photos", ref, language], queryFn: () => getPlacePhotos(ref!, language), enabled: Boolean(ref), staleTime: 5 * 60_000, retry: false });
  const photos = (found.data?.photos ?? []).flatMap((photo) => {
    const url = safePhotoUrl(photo.url);
    return url ? [{ url, caption: [photo.name ?? stopDisplayName(stop), found.data?.source_note].filter(Boolean).join(" ") }] : [];
  });
  const empty = !ref ? t("등록된 사진이 없어요 · 장소 사진은 준비 중이에요", "No photos yet · place photos are coming")
    : found.isPending ? t("사진을 불러오고 있어요…", "Loading the photos…")
      : found.isError ? t("사진을 불러오지 못했어요.", "Could not load the photos.")
        : t("등록된 사진이 없어요.", "No photos for this place.");
  return <>
    <button type="button" className={pc.hint} onClick={onSheetFull}>{photos.length
      ? t(`시트를 위로 올리면 ${stopDisplayName(stop)} 사진 ${photos.length}장 ↑`, `Slide the sheet up for ${photos.length} photos of ${stopDisplayName(stop)} ↑`)
      : t("시트를 위로 올리면 사진 안내 ↑", "Slide the sheet up for photos ↑")}</button>
    <section className={pc.photos} aria-labelledby="trip-photos-title">
      <h4 id="trip-photos-title">{t(`등록된 사진 · ${stopDisplayName(stop)}`, `Photos · ${stopDisplayName(stop)}`)}{photos.length > 0 && <small>{t(`${photos.length}장`, `${photos.length}`)}</small>}</h4>
      {photos.length
        ? <div className={pc.photoGrid}>{photos.map((photo, index) => <figure key={`${photo.url}-${index}`} className={pc.photo}>
            {/* eslint-disable-next-line @next/next/no-img-element -- place photos come from hosts the place data names, not configured in advance */}
            <img src={photo.url} alt={photo.caption} loading="lazy" />
            <figcaption>{photo.caption}</figcaption>
          </figure>)}</div>
        : <p className={pc.empty} role={found.isError ? "alert" : undefined}>{empty}</p>}
    </section>
  </>;
}

function DetailCard({ stop, next, dayNumber, active, onAsk, askBusy, onEdit, ask }: { stop: TripStop; next: TripStop | undefined; dayNumber: number; active: boolean; onAsk: () => void; askBusy: boolean;
  onEdit?: (how: "plain" | "direct") => void; ask?: ReactNode }) {
  const t = useT();
  const info = stop.placeInfo;
  const where = [info?.category, info?.address].filter(Boolean).join(" · ");
  const place = stopPlaceNote(stop);
  const maps = placeLinks(stop);
  return <article className={pc.changeCard} data-active={active || undefined} data-card-id={stop.id} aria-labelledby={`trip-detail-card-${stop.id}`}>
    <div className={styles.detailChips}>
      <span className={pc.chip}>{t(`${dayNumber}일차`, `Day ${dayNumber}`)} {stop.time}{stop.endTime ? `–${stop.endTime}` : ""}</span>
      {stop.booking === "booked" && <span className={pc.pill} data-booked>{bookingLabel(stop, t)}</span>}
      {stop.pinned && <span className={pc.pill}>{t("고정한 일정", "Pinned")}</span>}
      {stop.badges?.map((badge) => <span key={badge.code} className={pc.pill}>{badge.label}</span>)}
      {stop.paused && <span className={pc.pill} data-state="review">{t("일정 정지", "Paused")}</span>}
      {/* `[2026-10-21 ST4F-706 후속]` 앞 일정을 대신한 일정(서버 `changed`) — 「입력한 메모」 줄을 빼며 함께 사라진 표시를 이 줄로(서버 공유 계획서의 「변경됨」과 같은 말) */}
      {stop.changed && <span className={pc.pill} data-state="changed">{t("변경됨", "Changed")}</span>}
      {/* `[2026-10-21 사용자 지시 — ST4F-704]` 이 줄 오른쪽 끝, 「전체」 일차 칩 모양 — 수정 모드를 이 일정의 ✎ 자리로 연다 */}
      {onEdit && <button type="button" className={`${pc.dayChip} ${styles.detailEdit}`} onClick={() => onEdit("plain")}
        aria-label={t(`${stop.title} 일정 수정`, `Edit ${stop.title}`)}><Pencil size={14} strokeWidth={1.8} aria-hidden="true" />{t("일정 수정", "Edit itinerary")}</button>}
    </div>
    <div className={pc.nameRow}><h4 id={`trip-detail-card-${stop.id}`} className={pc.changeName}>{stop.title}</h4>{info?.sourceNote && <span className={pc.sourceTag}>{info.sourceNote}</span>}</div>
    {/* `[2026-10-21 사용자 결정 C — ST4F-706]` 제목 아래 선택한 장소 이름(제목과 다를 때) — 카드와 같다 */}
    {place && <p className={`${pc.changeSub} ${styles.detailPlace}`} data-stop-place><MapPin size={14} strokeWidth={1.8} aria-hidden="true" />{place}</p>}
    <p className={pc.changeSub}>{where || t("장소 정보 없음", "No place details")}</p>
    {ask}
    <StopFacts stop={stop} next={next} brief />
    <div className={styles.detailActions}>
      <button type="button" className={styles.action} disabled={askBusy} onClick={onAsk}><MessageCircle size={16} strokeWidth={1.6} aria-hidden="true" />{t("이 일정 질문하기", "Ask about this stop")}</button>
      {maps && <div className={styles.detailMaps} role="group" aria-label={t("지도 앱으로 열기", "Open in a maps app")}>{maps.map((link) =>
        <a key={link.app} className={styles.action} href={link.url} target="_blank" rel="noopener noreferrer" data-map-app={link.app}>{mapAppName(link.app, t)}</a>)}</div>}
    </div>
  </article>;
}

/** Cards side by side (the plan check's change carousel): the card swiped into the middle becomes the one in view; one chosen elsewhere comes into the middle. */
function Carousel({ index, onIndex, label, children }: { index: number; onIndex: (index: number) => void; label: string; children: ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    const current = box.current, element = current?.children[index] as HTMLElement | undefined;
    if (!current || !element) return;
    const left = element.offsetLeft - (current.clientWidth - element.offsetWidth) / 2;
    if (Math.abs(current.scrollLeft - left) > 4) current.scrollTo({ left, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [index]);
  useEffect(() => () => clearTimeout(timer.current), []);
  function settle() {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const current = box.current;
      if (!current) return;
      const middle = current.scrollLeft + current.clientWidth / 2;
      let best = 0, distance = Infinity;
      Array.from(current.children).forEach((child, at) => {
        const element = child as HTMLElement, gap = Math.abs(element.offsetLeft + element.offsetWidth / 2 - middle);
        if (gap < distance) { distance = gap; best = at; }
      });
      if (best !== index) onIndex(best);
    }, 90);
  }
  return <div ref={box} className={pc.carousel} onScroll={settle} tabIndex={0} role="region" aria-label={label}>{children}</div>;
}
