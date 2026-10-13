"use client";

import type { ReactNode } from "react";
import { ArrowRight, BedDouble, Bike, Bus, Car, ChevronRight, ExternalLink, Footprints, MapPin, MessageCircle, TrainFront } from "lucide-react";
import type { RouteShape } from "@/lib/live/route-shapes";
import type { Translate } from "@/lib/i18n";
import { useT } from "@/lib/settings";
import { isGuess, MODE_NAMES, rideLines } from "@/features/map/route-lines";
import { freeText } from "@/features/plan-check/day-times";
import { GAP_BASE_PX, gapPx } from "@/features/plan-check/time-plan";
import { Act } from "@/features/plan-check/parts";
import pc from "@/features/plan-check/plan-check.module.css";
import { distanceText, isStay, stayNights, type StayMark, type TripLeg } from "./trip-timeline";
import type { TripStop } from "./model";
import styles from "./trip-screen.module.css";

/** 요식 원장 속성 이름 → 화면 말. 모르는 이름은 서버가 보낸 그대로 보인다(숨기지 않는다). */
const TAG_LABELS: Record<string, [string, string]> = {
  card_payment: ["카드 결제", "Cards accepted"], parking: ["주차", "Parking"], takeout: ["포장", "Takeout"],
  vegetarian_menu: ["채식 메뉴", "Vegetarian menu"], kids_allowed: ["아이 동반", "Kids welcome"], halal: ["할랄", "Halal"],
};

/** The place facts of a stop in the server's words (old trip screen's rows): only what the server sent. */
export function placeRows(stop: TripStop, t: Translate, where = true) {
  const info = stop.placeInfo;
  if (!info) return null;
  const tags = info.tags.filter((tag) => !tag.startsWith("michelin")).map((tag) => (TAG_LABELS[tag] ? t(...TAG_LABELS[tag]) : tag));
  return <>
    {where && info.category && <><dt>{t("분류", "Type")}</dt><dd>{info.category}</dd></>}
    {where && info.address && <><dt>{t("주소", "Address")}</dt><dd>{info.address}</dd></>}
    {info.phone && <><dt>{t("전화", "Phone")}</dt><dd><a href={`tel:${info.phone.replace(/[^\d+]/g, "")}`}>{info.phone}</a></dd></>}
    {info.hours.length > 0 && <><dt>{t("영업시간", "Hours")}</dt><dd>{info.hours.join(" · ")}</dd></>}
    {info.hoursNotes.length > 0 && <><dt>{info.hours.length ? t("운영 안내", "Hours notes") : t("영업시간", "Hours")}</dt><dd>{info.hoursNotes.join(" · ")}</dd></>}
    {info.michelin && <><dt>{t("미쉐린", "Michelin")}</dt><dd>{info.michelin.level}{info.michelin.year ? ` (${info.michelin.year})` : ""}</dd></>}
    {tags.length > 0 && <><dt>{t("편의", "Amenities")}</dt><dd>{tags.join(" · ")}</dd></>}
    {/* The detail (`where` false) shows the credit as a tag beside the name — said once. */}
    {where && info.sourceNote && <><dt>{t("출처", "Source")}</dt><dd>{info.sourceNote}</dd></>}
  </>;
}

/** "2026-11-06" → "11/6". */
const monthDay = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;

/** `[2026-10-13 사용자 결정 — 숙소 항목 B안]` The stay's nights and days as a pill: 「3박 · 11/6~11/9」. */
export function stayPill(stop: TripStop, t: Translate): string {
  const nights = stayNights(stop);
  return t(`${nights}박 · ${monthDay(stop.date)}~${monthDay(stop.endDate!)}`, `${nights} night${nights === 1 ? "" : "s"} · ${monthDay(stop.date)}–${monthDay(stop.endDate!)}`);
}

export function bookingLabel(stop: TripStop, t: Translate) {
  if (stop.booking === "booked") return t("예약 있음", "Booking noted");
  return null;
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
  const timeFocused = open || selected;
  const stay = isStay(stop);
  const hasTags = stay || stop.booking === "booked" || stop.pinned || stop.paused || !!stop.badges?.length;
  return <li className={`${pc.entry} ${styles.stopEntry}`} data-type="item" data-entry-id={stop.id} data-time-focused={timeFocused || undefined} data-time-follow={open || undefined} data-selected={selected || undefined} data-paused={stop.paused || undefined}>
    <span className={pc.time}><span className={pc.timeStack}><time data-stop-start>{stop.time}</time><time className={pc.rangeEnd} data-stop-end aria-hidden={!timeFocused}>~{stay ? `${monthDay(stop.endDate!)} ` : ""}{stop.endTime || "—"}</time></span></span>
    <span className={pc.rail} aria-hidden="true"><span className={`${pc.dot} ${styles.stopDot}`} data-stay={stay || undefined} /></span>
    <article id={`trip-card-${stop.id}`} className={`${pc.card} ${styles.stopCard}`} data-stay={stay || undefined} data-open={open || undefined} aria-labelledby={`${id}-title`}>
      <div className={`${pc.cardTop} ${styles.stopHead}`}>
        <button type="button" className={`${pc.cardHead} ${styles.stopToggle}`} id={`stop-button-${stop.id}`} aria-expanded={open} aria-controls={`stop-detail-${stop.id}`} onClick={onToggle}>
          {stay ? <BedDouble size={18} strokeWidth={1.8} aria-hidden="true" /> : <MapPin size={18} strokeWidth={1.8} aria-hidden="true" />}
          <span className={styles.stopName}>
            <strong id={`${id}-title`} className={pc.cardTitle}>{stay ? t(`${stop.title} 체크인`, `Check in · ${stop.title}`) : stop.title}</strong>
            {hasTags && <span className={styles.stopTags}>
              {stay && <span className={pc.pill} data-stay-nights>{stayPill(stop, t)}</span>}
              {stop.badges?.map((badge) => <span className={pc.pill} key={badge.code}>{badge.label}</span>)}
              {stop.booking === "booked" && <span className={pc.pill} data-booked>{bookingLabel(stop, t)}</span>}
              {stop.pinned && <span className={pc.pill}>{t("고정한 일정", "Pinned")}</span>}
              {stop.badges?.map((badge) => <span key={badge.code} className={pc.pill}>{badge.label}</span>)}
              {stop.paused && <span className={pc.pill} data-state="review">{t("일정 정지", "Paused")}</span>}
            </span>}
          </span>
        </button>
        {/* `[2026-10-08 사용자 지시]` 「상세 보기」는 카드를 펼쳤을 때만 나오고, ＋/－ 는 늘 맨 오른쪽이다. 오른쪽 끝의 ＋/－ 는 같은 접기 단추의 누르는 자리일 뿐이라
             화면 읽기와 키보드에는 앞의 이름 단추 하나만 있다. */}
        {open && <Act className={styles.detailButton} why={detailWhy} explain={explain} onPress={onDetail} aria-label={t(`${stop.title} 상세 보기`, `Details of ${stop.title}`)}>{t("상세 보기", "Details")}<ChevronRight size={15} strokeWidth={1.8} aria-hidden="true" /></Act>}
        <button type="button" className={styles.toggleEnd} onClick={onToggle} tabIndex={-1} aria-hidden="true" data-toggle-mark><span className={styles.toggleMark}>{open ? "−" : "+"}</span></button>
      </div>
      {open && <div className={styles.stopBody} id={`stop-detail-${stop.id}`}>
        <StopFacts stop={stop} next={next} />
        <div className={styles.detailActions}>
          <button type="button" className={styles.action} onClick={onShowOnMap}><MapPin size={16} strokeWidth={1.6} aria-hidden="true" />{t("지도에서 보기", "Show on map")}</button>
          <button type="button" className={styles.action} disabled={askBusy} onClick={onAsk}><MessageCircle size={16} strokeWidth={1.6} aria-hidden="true" />{t("이 일정 질문하기", "Ask about this stop")}</button>
          {stop.mapUrl && <a className={styles.action} href={stop.mapUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} strokeWidth={1.6} aria-hidden="true" />{t("지도 앱으로 열기", "Open in maps app")}</a>}
        </div>
      </div>}
    </article>
  </li>;
}

/**
 * The facts of a stop (the old trip screen's card), in the server's words: the opened card shows them all; the detail (`brief`) leaves out what it shows above them (date, time, kind, address, credit).
 */
export function StopFacts({ stop, next, brief = false }: { stop: TripStop; next: TripStop | undefined; brief?: boolean }) {
  const t = useT();
  // Michelin already has its own row from the place facts (`placeRows`) — the mark row does not repeat it.
  const marks = (stop.badges ?? []).filter((badge) => !(badge.code === "michelin" && stop.placeInfo?.michelin));
  return <dl className={styles.details}>
    {!brief && <><dt>{t("날짜", "Date")}</dt><dd>{stop.date}</dd>
      <dt>{t("예정 시간", "Planned time")}</dt><dd>{stop.time}</dd></>}
    {placeRows(stop, t, !brief)}
    {stop.booking === "booked" && <><dt>{t("예약 표시", "Booking note")}</dt><dd>{bookingLabel(stop, t)}</dd></>}
    <dt>{t("다음 일정", "Next stop")}</dt><dd>{next ? `${next.time} · ${next.title}` : t("이날 마지막 일정", "Last stop of the day")}</dd>
    {stop.otherOptions && stop.otherOptions.length > 0 && <><dt>{t("다른 안", "Other options")}</dt><dd>{stop.otherOptions.map((option) => option.name).join(" · ")}</dd></>}
    {marks.length > 0 && <><dt>{t("식당 표시", "Restaurant marks")}</dt><dd>{marks.map((badge) => badge.label).join(" · ")}</dd></>}
    <dt>{t("입력한 메모", "Your notes")}</dt><dd>{stop.notes || t("등록된 메모가 없어요.", "No notes added.")}</dd>
  </dl>;
}

/**
 * `[2026-10-13 사용자 결정 — 숙소 항목 B안]` A stay on a day after its check-in. 「from」: a band at the top — the day starts from the hotel (the move from it is drawn only when the server keeps one).
 * 「checkout」: the check-out at its time, as a stop-like row. Pressing either shows the stay itself (`onShow`) — the stay is one item.
 */
export function StayRow({ stay, onShow }: { stay: StayMark; onShow: () => void }) {
  const t = useT();
  const { stop, phase, night, nights } = stay;
  if (phase === "from") {
    const which = night > nights ? t("마지막 날", "Last day") : t(`${night}박째`, `Night ${night}`);
    return <li className={styles.stayBand} data-type="stay" data-entry-id={`${stop.id}:from`}>
      <button type="button" className={styles.stayBandButton} onClick={onShow} aria-label={t(`${stop.title}에서 출발 — 숙소 보기`, `Leaving from ${stop.title} — show the stay`)}>
        <BedDouble size={16} strokeWidth={1.8} aria-hidden="true" />
        <span>{t(`${stop.title}에서 출발`, `Leaving from ${stop.title}`)}</span>
        <small>{which}</small>
      </button>
    </li>;
  }
  return <li className={`${pc.entry} ${styles.stopEntry}`} data-type="stay" data-entry-id={`${stop.id}:checkout`}>
    <span className={pc.time}><span className={pc.timeStack}><time data-stay-checkout>{stop.endTime || "—"}</time></span></span>
    <span className={pc.rail} aria-hidden="true"><span className={`${pc.dot} ${styles.stopDot}`} data-stay /></span>
    <article className={`${pc.card} ${styles.stopCard}`} data-stay>
      <div className={`${pc.cardTop} ${styles.stopHead}`}>
        <button type="button" className={`${pc.cardHead} ${styles.stopToggle}`} onClick={onShow}>
          <BedDouble size={18} strokeWidth={1.8} aria-hidden="true" />
          <span className={styles.stopName}>
            <strong className={pc.cardTitle}>{t(`${stop.title} 체크아웃`, `Check out · ${stop.title}`)}</strong>
            <span className={styles.stayNote}>{t("퇴실 마감", "Check-out time")}</span>
          </span>
        </button>
      </div>
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
  const time: ReactNode = leg.move ? <span className={pc.timeStack}><time data-move-departure>{leg.move.departAt || t("미정", "TBD")}</time><time className={pc.rangeEnd} data-move-arrival aria-hidden={!open}>{leg.move.arriveAt ? `~${leg.move.arriveAt}` : t("미정", "TBD")}</time></span> : null;
  if (!summary) {
    return <li className={`${pc.entry} ${styles.legEntry}`} data-type="move" data-entry-id={leg.id}>
      <span className={pc.time} />
      <span className={pc.rail} aria-hidden="true"><span className={`${pc.dot} ${pc.departureMark}`}>−</span></span>
      <div className={pc.moveCol}><p className={`${pc.move} ${styles.legPlain}`}><span className={pc.modeIcon}><ModeIcon mode={null} /></span>{t("이동 정보가 아직 없어요", "Travel details are not available yet")}{directions && <><br />{directions}</>}</p></div>
    </li>;
  }
  const guess = leg.shape && isGuess(leg.shape);
  const lines = [
    leg.move?.title,
    leg.move ? [t(`${leg.move.departAt} 출발`, `Leave ${leg.move.departAt}`), leg.move.arriveAt && t(`${leg.move.arriveAt} 도착`, `arrive ${leg.move.arriveAt}`)].filter(Boolean).join(" → ") : null,
    ...(leg.shape ? rideLines(leg.shape, t) : []),
  ].filter(Boolean) as string[];
  return <li className={`${pc.entry} ${styles.legEntry}`} data-type="move" data-entry-id={leg.id} data-time-focused={open || undefined}>
    <div className={pc.moveClock}><span className={pc.time}>{time}</span></div>
    <span className={pc.rail} aria-hidden="true"><span className={`${pc.dot} ${pc.departureMark}`}>−</span></span>
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
