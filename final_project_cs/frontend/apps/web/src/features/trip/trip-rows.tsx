"use client";

import type { ReactNode } from "react";
import { ArrowRight, Bike, Bus, Car, ChevronRight, ExternalLink, Footprints, MapPin, MessageCircle, TrainFront } from "lucide-react";
import type { RouteShape } from "@/lib/live/route-shapes";
import type { Translate } from "@/lib/i18n";
import { useT } from "@/lib/settings";
import { isGuess, MODE_NAMES, rideLines } from "@/features/map/route-lines";
import { freeText } from "@/features/plan-check/day-times";
import { GAP_BASE_PX, gapPx } from "@/features/plan-check/time-plan";
import { Act } from "@/features/plan-check/parts";
import pc from "@/features/plan-check/plan-check.module.css";
import { distanceText, type TripLeg } from "./trip-timeline";
import type { TripStop } from "./model";
import styles from "./trip-screen.module.css";

/** 요식 원장 속성 이름 → 화면 말. 모르는 이름은 서버가 보낸 그대로 보인다(숨기지 않는다). */
const TAG_LABELS: Record<string, [string, string]> = {
  card_payment: ["카드 결제", "Cards accepted"], parking: ["주차", "Parking"], takeout: ["포장", "Takeout"],
  vegetarian_menu: ["채식 메뉴", "Vegetarian menu"], kids_allowed: ["아이 동반", "Kids welcome"], halal: ["할랄", "Halal"],
};

/** The place facts of a stop in the server's words (old trip screen's rows): only what the server sent. */
export function placeRows(stop: TripStop, t: Translate) {
  const info = stop.placeInfo;
  if (!info) return null;
  const tags = info.tags.filter((tag) => !tag.startsWith("michelin")).map((tag) => (TAG_LABELS[tag] ? t(...TAG_LABELS[tag]) : tag));
  return <>
    {info.category && <><dt>{t("분류", "Type")}</dt><dd>{info.category}</dd></>}
    {info.address && <><dt>{t("주소", "Address")}</dt><dd>{info.address}</dd></>}
    {info.phone && <><dt>{t("전화", "Phone")}</dt><dd><a href={`tel:${info.phone.replace(/[^\d+]/g, "")}`}>{info.phone}</a></dd></>}
    {info.hours.length > 0 && <><dt>{t("영업시간", "Hours")}</dt><dd>{info.hours.join(" · ")}</dd></>}
    {info.hoursNotes.length > 0 && <><dt>{info.hours.length ? t("운영 안내", "Hours notes") : t("영업시간", "Hours")}</dt><dd>{info.hoursNotes.join(" · ")}</dd></>}
    {info.michelin && <><dt>{t("미쉐린", "Michelin")}</dt><dd>{info.michelin.level}{info.michelin.year ? ` (${info.michelin.year})` : ""}</dd></>}
    {tags.length > 0 && <><dt>{t("편의", "Amenities")}</dt><dd>{tags.join(" · ")}</dd></>}
    {info.sourceNote && <><dt>{t("출처", "Source")}</dt><dd>{info.sourceNote}</dd></>}
  </>;
}

export function bookingLabel(stop: TripStop, t: Translate) {
  if (stop.booking === "booked") return t("예약 있음", "Booking noted");
  return t("예약 정보 없음", "Booking not specified");
}

/**
 * `[2026-10-07 사용자 결정 — 목업 C안]` One stop of a registered trip, on the plan check's timeline: its time at the left (start, and the end small; it stays at the top of the list while
 * the stop is in view), the card with its name and badges, 「상세 보기」, and — opened — the facts of the old trip screen's card with its three buttons.
 */
export function StopRow({ stop, next, open, selected, onToggle, onDetail, detailWhy, explain, onShowOnMap, onAsk, askBusy }: {
  stop: TripStop; next: TripStop | undefined; open: boolean; selected: boolean;
  onToggle: () => void; onDetail: () => void; detailWhy: string | null; explain: (why: string) => void;
  onShowOnMap: () => void; onAsk: () => void; askBusy: boolean;
}) {
  const t = useT();
  const id = `trip-stop-${stop.id}`;
  return <li className={`${pc.entry} ${styles.stopEntry}`} data-entry-id={stop.id} data-selected={selected || undefined} data-paused={stop.paused || undefined}>
    <span className={`${pc.time} ${styles.stopTime}`}><time>{stop.time}</time>{stop.endTime && <small>{stop.endTime}</small>}</span>
    <span className={pc.rail} aria-hidden="true"><span className={`${pc.dot} ${styles.stopDot}`} /></span>
    <article id={`trip-card-${stop.id}`} className={`${pc.card} ${styles.stopCard}`} data-open={open || undefined} aria-labelledby={`${id}-title`}>
      <div className={styles.stopHead}>
        <button type="button" className={styles.stopToggle} id={`stop-button-${stop.id}`} aria-expanded={open} aria-controls={`stop-detail-${stop.id}`} onClick={onToggle}>
          <span className={styles.stopName}>
            <strong id={`${id}-title`} className={pc.cardTitle}>{stop.title}</strong>
            <span className={styles.stopTags}>
              <span className={pc.pill} data-booked={stop.booking === "booked" || undefined}>{bookingLabel(stop, t)}</span>
              {stop.pinned && <span className={pc.pill}>{t("고정한 일정", "Pinned")}</span>}
              {stop.paused && <span className={pc.pill} data-state="review">{t("일정 정지", "Paused")}</span>}
            </span>
          </span>
          <span className={styles.toggleMark} aria-hidden="true">{open ? "−" : "+"}</span>
        </button>
        <Act className={styles.detailButton} why={detailWhy} explain={explain} onPress={onDetail} aria-label={t(`${stop.title} 상세 보기`, `Details of ${stop.title}`)}>{t("상세 보기", "Details")}<ChevronRight size={15} strokeWidth={1.8} aria-hidden="true" /></Act>
      </div>
      {open && <div className={styles.stopBody} id={`stop-detail-${stop.id}`}>
        <dl className={styles.details}>
          <dt>{t("날짜", "Date")}</dt><dd>{stop.date}</dd>
          <dt>{t("예정 시간", "Planned time")}</dt><dd>{stop.time}</dd>
          {placeRows(stop, t)}
          <dt>{t("예약 표시", "Booking note")}</dt><dd>{bookingLabel(stop, t)}</dd>
          <dt>{t("다음 일정", "Next stop")}</dt><dd>{next ? `${next.time} · ${next.title}` : t("이날 마지막 일정", "Last stop of the day")}</dd>
          {stop.otherOptions && stop.otherOptions.length > 0 && <><dt>{t("다른 안", "Other options")}</dt><dd>{stop.otherOptions.map((option) => option.name).join(" · ")}</dd></>}
          <dt>{t("입력한 메모", "Your notes")}</dt><dd>{stop.notes || t("등록된 메모가 없어요.", "No notes added.")}</dd>
        </dl>
        <div className={styles.detailActions}>
          <button type="button" className={styles.action} onClick={onShowOnMap}><MapPin size={16} strokeWidth={1.6} aria-hidden="true" />{t("지도에서 보기", "Show on map")}</button>
          <button type="button" className={styles.action} disabled={askBusy} onClick={onAsk}><MessageCircle size={16} strokeWidth={1.6} aria-hidden="true" />{t("이 일정 질문하기", "Ask about this stop")}</button>
          {stop.mapUrl && <a className={styles.action} href={stop.mapUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} strokeWidth={1.6} aria-hidden="true" />{t("지도 앱으로 열기", "Open in maps app")}</a>}
        </div>
      </div>}
    </article>
  </li>;
}

/** The icon of how a leg is travelled (the route line's mode); a plain arrow when the server did not say. */
export function ModeIcon({ mode }: { mode: RouteShape["mode"] | null }) {
  const props = { size: 14, strokeWidth: 1.8, "aria-hidden": true as const };
  if (mode === "walk") return <Footprints {...props} />;
  if (mode === "subway" || mode === "mixed") return <TrainFront {...props} />;
  if (mode === "bus") return <Bus {...props} />;
  if (mode === "taxi") return <Car {...props} />;
  if (mode === "bike") return <Bike {...props} />;
  return <ArrowRight {...props} />;
}

const MODE_EN: Record<RouteShape["mode"], string> = { walk: "Walk", bike: "Bike", taxi: "Taxi", subway: "Subway", bus: "Bus", mixed: "Transit", unknown: "Move" };

/** How the leg is travelled, in one line from what the server gave (「지하철 3호선→1호선 15분 · 2.1km」 · 「도보 12분」 · 「이동 20분」); null when it gave nothing to say. */
export function legSummary(leg: TripLeg, t: Translate): string | null {
  const how = leg.shape?.rides.length ? leg.shape.rides.map((ride) => ride.line).join("→") : leg.shape ? t(MODE_NAMES[leg.shape.mode], MODE_EN[leg.shape.mode]) : leg.move ? t("이동", "Move") : null;
  if (!how) return null;
  const time = leg.minutes !== null ? t(`${leg.minutes}분`, `${leg.minutes} min`) : null;
  const far = distanceText(leg.shape?.distanceM);
  return [[how, time].filter(Boolean).join(" "), far].filter(Boolean).join(" · ");
}

/**
 * `[2026-10-07 사용자 결정 — 목업 C안 · 계획 확인 화면과 같게]` The way from one stop to the next: 「출발」 time at the left (it stays at the top while the leg is in view), the mode, how long and
 * how far, and the free time after it (15 minutes or more; late says so) — the space after it grows with the free time. Opened: the server's own line for the move, when to leave and arrive,
 * what it rides, whether the line is a guess, and the customer's map app. A plan that keeps no moves (typed in) shows only the way to the next stop, as the old screen did.
 */
export function LegRow({ leg, open, onToggle }: { leg: TripLeg; open: boolean; onToggle: () => void }) {
  const t = useT();
  const summary = legSummary(leg, t);
  const late = leg.slack !== null && leg.slack < 0;
  const free = leg.slack !== null && !late ? freeText(leg.slack) : null;
  const freeSays = late ? t(`${Math.abs(leg.slack!)}분 늦어요`, `${Math.abs(leg.slack!)} min late`) : free ? t(`여유 ${free}`, `${free} free`) : null;
  const extra = gapPx(leg.slack) - GAP_BASE_PX;
  const directions = leg.directions && <a className={styles.legLink} href={leg.directions} target="_blank" rel="noopener noreferrer"><ExternalLink size={14} strokeWidth={1.8} aria-hidden="true" />{t("지도 앱에서 길찾기", "Directions in maps app")}</a>;
  const time: ReactNode = leg.move ? <><b>{leg.move.departAt}</b><small>{t("출발", "leave")}</small></> : null;
  if (!summary) {
    return <li className={`${pc.entry} ${styles.legEntry}`} data-type="move" data-entry-id={leg.id}>
      <span className={pc.time} />
      <span className={pc.rail} aria-hidden="true"><span className={pc.dot} /></span>
      <div className={pc.moveCol}><p className={`${pc.move} ${styles.legPlain}`}><span className={pc.modeIcon}><ModeIcon mode={null} /></span>{t("다음 일정으로", "Next stop")}{directions && <> · {directions}</>}</p></div>
    </li>;
  }
  const guess = leg.shape && isGuess(leg.shape);
  const lines = [
    leg.move?.title,
    leg.move ? [t(`${leg.move.departAt} 출발`, `Leave ${leg.move.departAt}`), leg.move.arriveAt && t(`${leg.move.arriveAt} 도착`, `arrive ${leg.move.arriveAt}`)].filter(Boolean).join(" → ") : null,
    ...(leg.shape ? rideLines(leg.shape, t) : []),
  ].filter(Boolean) as string[];
  return <li className={`${pc.entry} ${styles.legEntry}`} data-type="move" data-entry-id={leg.id}>
    <span className={pc.time}>{time}</span>
    <span className={pc.rail} aria-hidden="true"><span className={pc.dot} /></span>
    <div className={pc.moveCol}>
      <div className={pc.move} data-open={open || undefined}>
        <button type="button" className={pc.moveHead} aria-expanded={open} aria-controls={`trip-leg-${leg.id}`} onClick={onToggle}>
          <span className={pc.modeIcon}><ModeIcon mode={leg.shape?.mode ?? null} /></span>
          <span className={pc.moveText}>{summary}</span>
          {freeSays && <span className={pc.moveFree} data-late={late || undefined}>{freeSays}</span>}
        </button>
        {open && <div id={`trip-leg-${leg.id}`} className={styles.legBody}>
          {lines.map((line) => <p key={line}>{line}</p>)}
          {guess && <p className={styles.legGuess}>{t("길을 몰라 두 곳을 직선으로 이은 구간이에요.", "The way is not known: the two places are joined by a straight line.")}{leg.shape?.note ? ` ${leg.shape.note}` : ""}</p>}
          {directions}
        </div>}
      </div>
      {extra > 0 && <div className={pc.freeGap} aria-hidden="true" style={{ height: `${extra}px` }} />}
    </div>
  </li>;
}
