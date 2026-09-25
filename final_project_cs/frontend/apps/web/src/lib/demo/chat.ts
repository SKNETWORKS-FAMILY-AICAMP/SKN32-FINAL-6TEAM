import type { TripStop } from "../../features/trip/model";
import type { Translate } from "../i18n";

type Intent = "change" | "next" | "selected" | "booking" | "day" | "unknown";

function intentFor(text: string): Intent {
  if (/변경|취소|환불|바꿔|미뤄|앞당|예약해|change|cancel|refund|reschedule|book (?:it|this|the)/i.test(text)) return "change";
  if (/다음|next|comes after/i.test(text)) return "next";
  if (/선택|상세|selected|detail|tell me about/i.test(text)) return "selected";
  if (/예약|booking|reservation|booked/i.test(text)) return "booking";
  if (/요약|일정|오늘|summar|itinerary|schedule|today|day/i.test(text)) return "day";
  return "unknown";
}

export function bookingLabel(stop: Pick<TripStop, "booking">, t: Translate) {
  if (stop.booking === "booked") return t("예약 있음", "Booking noted");
  if (stop.booking === "none") return t("예약 없음", "No booking noted");
  return t("예약 정보 없음", "Booking not specified");
}

/** Demo replies from the saved itinerary only. The message names its date, time or stop. */
export function demoReply(allStops: TripStop[], message: string, t: Translate): string {
  const intent = intentFor(message);
  if (intent === "change") return t("이 데모에서는 실제 일정·예약을 변경하거나 취소하지 않아요. 「일정 수정」에서 계획을 고치고 다시 검증할 수 있어요.", "This demo does not change or cancel actual plans or bookings. Use “Edit itinerary” to revise your plan and check it again.");
  const days = [...new Set(allStops.map((stop) => stop.date))].sort();
  const requestedDate = message.match(/\d{4}-\d{2}-\d{2}/)?.[0];
  const requestedTime = message.match(/(?:[01]\d|2[0-3]):[0-5]\d/)?.[0];
  const named = allStops
    .filter((stop) => (!requestedDate || stop.date === requestedDate) && message.includes(stop.title))
    .sort((a, b) => b.title.length - a.title.length);
  const mentioned = named.find((stop) => !requestedTime || stop.time === requestedTime) ?? named[0];
  const day = requestedDate ?? mentioned?.date ?? days[0];
  const stops = allStops.filter((stop) => stop.date === day);
  if (!stops.length) return t("이 날짜에는 등록된 일정이 없어요. 일정 수정에서 계획을 추가해 주세요.", "No stops are saved for this date. Add your plans with “Edit itinerary”.");
  const selected = mentioned?.date === day ? mentioned : stops[0];
  const next = stops[stops.indexOf(selected) + 1];
  if (intent === "day") return `${day}\n${stops.map((stop, index) => `${index + 1}. ${stop.time} · ${stop.title}`).join("\n")}`;
  if (intent === "selected") {
    const adjusted = selected.originalTime && selected.originalTime !== selected.time ? `\n${t("시간 조정", "Time adjustment")}: ${selected.originalTime} → ${selected.time}` : "";
    return `${selected.date} ${selected.time} · ${selected.title}\n${bookingLabel(selected, t)}\n${selected.notes || t("등록된 메모가 없어요.", "No notes added.")}${adjusted}\n${next ? t(`다음 일정: ${next.time} · ${next.title}`, `Next stop: ${next.time} · ${next.title}`) : t("이날 마지막 일정이에요.", "This is the last stop of the day.")}`;
  }
  if (intent === "next") {
    return next
      ? t(`${selected.title} 다음은 ${next.time} · ${next.title}입니다. 실제 이동 경로와 소요 시간은 이 개념도에서 계산하지 않아요.`, `After ${selected.title}: ${next.time} · ${next.title}. The diagram does not calculate actual routes or travel times.`)
      : t(`${selected.title}는 이날 마지막으로 등록한 일정이에요.`, `${selected.title} is the last saved stop for this day.`);
  }
  if (intent === "booking") {
    const bookedStops = stops.filter((stop) => stop.booking === "booked");
    return bookedStops.length
      ? `${t("예약 있음으로 입력된 일정:", "Stops marked as booked:")}\n${bookedStops.map((stop) => `${stop.time} · ${stop.title}`).join("\n")}\n${t("입력한 표시이며 실제 예약 내역을 조회한 결과는 아닙니다.", "These are your entered notes, not a live booking lookup.")}`
      : t("이 날짜에는 예약 있음으로 입력된 일정이 없어요. 실제 예약 여부는 예약 내역에서 확인해 주세요.", "No stops on this date are marked as booked. Check your booking records for actual reservations.");
  }
  return t("이 화면은 등록된 일정의 하루 요약·선택 일정·다음 일정·예약 표시를 조회하는 시연입니다. 아래 질문 버튼으로 확인할 내용을 골라 주세요. 자유로운 요청에 대한 실제 조회나 변경은 실행되지 않아요.", "This preview provides day summaries, selected-stop details, next stops, and booking notes from your itinerary. Choose a question below. Open-ended requests do not run live lookups or changes.");
}
