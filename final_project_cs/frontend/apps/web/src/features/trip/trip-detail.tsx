"use client";

import { useContext, useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { ArrowLeft, ExternalLink, MessageCircle } from "lucide-react";
import { HeaderSlot } from "@/components/layout/device-frame";
import pc from "@/features/plan-check/plan-check.module.css";
import { useT } from "@/lib/settings";
import type { Trip, TripStop } from "./model";
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
 * ★Only what the server gave: the server sends no photos of a place yet, so the photo part says they are coming.
 */
export function TripDetail({ trip, stopId, dayNumber, onStop, onAsk, askBusy, onSheetFull }: {
  trip: Trip; stopId: string; dayNumber: number;
  onStop: (id: string) => void; onAsk: (stop: TripStop) => void; askBusy: boolean; onSheetFull: () => void;
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
        {list.map((entry, at) => <DetailCard key={entry.id} stop={entry} next={list[at + 1]} dayNumber={dayNumber} active={entry.id === stop.id} onAsk={() => onAsk(entry)} askBusy={askBusy} />)}
      </Carousel>
      {list.length > 1 && <div className={pc.dots} role="group" aria-label={t("일정 고르기", "Choose a stop")}>{list.map((entry, at) =>
        <button key={entry.id} type="button" aria-pressed={at === index} aria-label={`${at + 1}. ${entry.title}`} onClick={() => onStop(entry.id)}><span aria-hidden="true" /></button>)}</div>}
      <button type="button" className={pc.hint} onClick={onSheetFull}>{t("시트를 위로 올리면 사진 안내 ↑", "Slide the sheet up for photos ↑")}</button>
      <section className={pc.photos} aria-labelledby="trip-photos-title">
        <h4 id="trip-photos-title">{t(`등록된 사진 · ${stop.title}`, `Photos · ${stop.title}`)}</h4>
        <p className={pc.empty}>{t("등록된 사진이 없어요 · 장소 사진은 준비 중이에요", "No photos yet · place photos are coming")}</p>
      </section>
    </div>
  </div>;
}

function DetailCard({ stop, next, dayNumber, active, onAsk, askBusy }: { stop: TripStop; next: TripStop | undefined; dayNumber: number; active: boolean; onAsk: () => void; askBusy: boolean }) {
  const t = useT();
  const info = stop.placeInfo;
  const where = [info?.category, info?.address].filter(Boolean).join(" · ");
  return <article className={pc.changeCard} data-active={active || undefined} data-card-id={stop.id} aria-labelledby={`trip-detail-card-${stop.id}`}>
    <div className={styles.detailChips}>
      <span className={pc.chip}>{t(`${dayNumber}일차`, `Day ${dayNumber}`)} {stop.time}{stop.endTime ? `–${stop.endTime}` : ""}</span>
      <span className={pc.pill} data-booked={stop.booking === "booked" || undefined}>{bookingLabel(stop, t)}</span>
      {stop.pinned && <span className={pc.pill}>{t("고정한 일정", "Pinned")}</span>}
      {stop.badges?.map((badge) => <span key={badge.code} className={pc.pill}>{badge.label}</span>)}
      {stop.paused && <span className={pc.pill} data-state="review">{t("일정 정지", "Paused")}</span>}
    </div>
    <div className={pc.nameRow}><h4 id={`trip-detail-card-${stop.id}`} className={pc.changeName}>{stop.title}</h4>{info?.sourceNote && <span className={pc.sourceTag}>{info.sourceNote}</span>}</div>
    <p className={pc.changeSub}>{where || t("장소 정보 없음", "No place details")}</p>
    <StopFacts stop={stop} next={next} brief />
    <div className={styles.detailActions}>
      <button type="button" className={styles.action} disabled={askBusy} onClick={onAsk}><MessageCircle size={16} strokeWidth={1.6} aria-hidden="true" />{t("이 일정 질문하기", "Ask about this stop")}</button>
      {stop.mapUrl && <a className={styles.action} href={stop.mapUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} strokeWidth={1.6} aria-hidden="true" />{t("지도 앱으로 열기", "Open in maps app")}</a>}
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
