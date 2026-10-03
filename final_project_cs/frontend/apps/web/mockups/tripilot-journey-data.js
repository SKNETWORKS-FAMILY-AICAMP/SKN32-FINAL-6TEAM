/* Local preview data only. No place, routing, booking, or AI services are called. */
(() => {
  'use strict';

  const plans = {
    ko: `1일차 · 2026-09-15
09:00 호텔 조식
10:00 잠실 스카이타워 · 10:45 종료
11:00 성수동 쇼핑 · 향수, K-뷰티
13:00 성수 예약 식당 · 예약 있음
15:00 경복궁 · 한복 체험, 17:00 종료
18:00 서울역 인근 저녁 식당 · 예약 없이 방문
19:30 롯데마트 서울역점 · 식료품 쇼핑

2일차 · 2026-09-16
09:00 호텔 조식
10:00 국립중앙박물관 · 전시 관람
12:00 이촌동 점심 식당 · 예약 있음
14:00 이태원 소품숍 · 기념품 구경
16:00 이촌 한강공원 · 산책
18:00 용산 저녁 식당 · 예약 없이 방문
20:00 호텔 복귀 · 짐 정리`,
    en: `DAY 1 · 2026-09-15
09:00 Hotel breakfast
10:00 Jamsil Sky Tower · ends 10:45
11:00 Seongsu shopping · Perfume and K-beauty
13:00 Seongsu restaurant · booked
15:00 Gyeongbokgung Palace · Hanbok experience, ends 17:00
18:00 Dinner near Seoul Station · no reservation
19:30 Lotte Mart Seoul Station · Grocery shopping

DAY 2 · 2026-09-16
09:00 Hotel breakfast
10:00 National Museum of Korea · Exhibition visit
12:00 Lunch in Ichon-dong · booked
14:00 Itaewon gift shops · Souvenir browsing
16:00 Ichon Hangang Park · Walk
18:00 Dinner in Yongsan · no reservation
20:00 Return to the hotel · Packing`,
  };

  function sample(lang) {
    return plans[lang === 'en' ? 'en' : 'ko'];
  }

  function validDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(value + 'T00:00:00Z');
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
  }

  function validTime(value) {
    return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
  }

  function parse(source, lang) {
    const t = (ko, en) => lang === 'en' ? en : ko;
    if (typeof source !== 'string' || !source.trim()) {
      throw new Error(t('시간과 장소가 있는 여행 계획을 입력해 주세요.', 'Enter a travel plan with times and places.'));
    }
    if (source.length > 12000) {
      throw new Error(t('여행 계획은 12,000자 이내로 입력해 주세요.', 'Keep your travel plan within 12,000 characters.'));
    }
    const text = source.replace(/\r\n?/g, '\n');
    const isSample = text.trim() === plans.ko || text.trim() === plans.en;
    const stops = [];
    let date = '';
    let firstDate = '';

    function inputError(index, ko, en) {
      return new Error(t(`${index + 1}번째 줄: ${ko}`, `Line ${index + 1}: ${en}`));
    }

    for (const [index, raw] of text.split('\n').entries()) {
      const line = raw.trim();
      if (!line) continue;
      const heading = line.match(/^(?:\[)?(?:(\d+)일차|DAY\s*(\d+))(?:\s|[·:：\]-]|$)/i);
      if (heading || /^\d{4}-\d{2}-\d{2}$/.test(line)) {
        const explicit = line.match(/\d{4}-\d{2}-\d{2}/)?.[0];
        const day = heading ? Number(heading[1] || heading[2]) : 1;
        if (!Number.isSafeInteger(day) || day < 1 || day > 366) {
          throw inputError(index, '일차는 1일부터 366일까지 적어 주세요.', 'Use a day number from 1 to 366.');
        }
        if (explicit) date = explicit;
        else if (firstDate && heading) {
          const next = new Date(firstDate + 'T00:00:00Z');
          next.setUTCDate(next.getUTCDate() + day - 1);
          date = next.toISOString().slice(0, 10);
        } else date = '';
        if (!validDate(date)) {
          throw inputError(index, '일차 제목에 올바른 날짜(YYYY-MM-DD)를 적어 주세요.', 'Add a valid date (YYYY-MM-DD) to the day heading.');
        }
        if (!firstDate) firstDate = date;
        continue;
      }
      if (!date) {
        throw inputError(index, '먼저 일차와 날짜를 적어 주세요. 예: 1일차 · 2026-09-15', 'Start with a day and date, for example: DAY 1 · 2026-09-15.');
      }
      const match = line.match(/^(\d{1,2}:\d{2})\s+(.+)$/);
      const time = match ? match[1].padStart(5, '0') : '';
      if (!match || !validTime(time)) {
        throw inputError(index, '시작 시각과 장소를 적어 주세요. 예: 09:00 호텔 조식', 'Add a valid start time and place, for example: 09:00 Hotel breakfast.');
      }
      const notes = match[2].trim();
      const title = notes.split(/\s*[·|]\s*/)[0].trim();
      if (!title) throw inputError(index, '장소를 적어 주세요.', 'Enter a place.');
      const endMatch = notes.match(/(\S+)\s*종료|\bends?(?:\s+at)?\s+(\S+)/i);
      const endTime = endMatch ? (endMatch[1] || endMatch[2]).padStart(5, '0') : undefined;
      if (endTime && (!validTime(endTime) || endTime <= time)) {
        throw inputError(index, '종료 시각은 같은 날의 시작 시각보다 뒤여야 해요.', 'Use a valid end time after the start time on the same day.');
      }
      const notBooked = /예약\s*(?:없이|없음)|미예약|\b(?:not\s+(?:booked|reserved)|unreserved|walk[- ]in|no\s+reservations?|without\s+(?:a\s+)?reservation)\b/i.test(notes);
      const booked = /예약\s*(?:있음|완료|확정)|\b(?:reserved|booked)\b/i.test(notes);
      stops.push({
        id: 'stop-' + (stops.length + 1), date, time,
        ...(endTime ? { endTime } : {}),
        title, notes,
        booking: notBooked ? 'none' : booked ? 'booked' : isSample ? 'none' : 'unknown',
      });
      if (stops.length > 100) {
        throw new Error(t('목업에서는 한 번에 100개 일정까지 등록할 수 있어요.', 'This preview supports up to 100 itinerary items at a time.'));
      }
    }
    if (!stops.length) {
      throw new Error(t('날짜 아래에 시간과 장소가 있는 일정을 하나 이상 적어 주세요.', 'Add at least one time and place below a date heading.'));
    }
    return stops.sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
  }

  function addFifteen(time) {
    const [hours, minutes] = time.split(':').map(Number);
    const next = hours * 60 + minutes + 15;
    return next < 1440 ? `${String(Math.floor(next / 60)).padStart(2, '0')}:${String(next % 60).padStart(2, '0')}` : null;
  }

  function priority(time) {
    return time === '11:00' ? 0 : time === '14:00' ? 1 : 2;
  }

  function verify(stops, scenario, lang) {
    const t = (ko, en) => lang === 'en' ? en : ko;
    if (scenario !== 'success' && scenario !== 'needs-review') {
      throw new Error(t('지원하지 않는 시연 검증 결과예요.', 'Unsupported preview verification scenario.'));
    }
    const blockedId = scenario === 'needs-review' && stops.length ? stops[stops.length - 1].id : null;
    const candidates = stops.filter((stop, index) => {
      const proposed = addFifteen(stop.time);
      const next = stops[index + 1];
      return stop.id !== blockedId && stop.booking === 'none' && proposed &&
        (!stop.endTime || proposed < stop.endTime) &&
        (!next || next.date !== stop.date || proposed < next.time);
    }).sort((a, b) => priority(a.time) - priority(b.time)).slice(0, 2);
    const adjusted = new Set(candidates.map(stop => stop.id));
    const results = stops.map(stop => {
      const base = { id: 'result-' + stop.id, stopId: stop.id, date: stop.date, title: stop.title, originalValue: stop.time };
      if (stop.id === blockedId) return {
        ...base, status: 'needs_review',
        reason: t('[시연] 이 일정의 이동 정보 확인을 마치지 못한 상황이에요.', '[Preview] This demonstrates an item whose travel information could not be verified.'),
        impact: t('다시 검증하기 전에는 여행 관리를 시작할 수 없어요.', 'Travel management stays unavailable until verification is completed.'),
      };
      if (adjusted.has(stop.id)) return {
        ...base, status: 'adjusted', proposedValue: addFifteen(stop.time),
        reason: t('[시연] 이동 여유 15분을 더한 조정 예시예요. 실제 이동 시간은 조회하지 않았어요.', '[Preview] This example adds a 15-minute buffer. Actual travel times have not been checked.'),
        impact: t('시연된 시작 시각 변경이 여행 일정에 반영돼요. 예약 변경은 실행하지 않아요.', 'The example start-time change appears in your itinerary. No bookings are changed.'),
      };
      return {
        ...base, status: 'unchanged', proposedValue: stop.time,
        reason: stop.booking === 'booked'
          ? t('입력 내용에 예약이 있어 시작 시각을 유지했어요. 실제 업체 예약 확인은 하지 않았어요.', 'The entered plan marks this item as booked, so its start time is unchanged. The provider booking has not been checked.')
          : t('[시연] 입력한 시작 시각을 유지하는 결과예요. 실제 운영·이동 정보는 확인하지 않았어요.', '[Preview] This example keeps the entered start time. Actual opening hours and travel information have not been checked.'),
        impact: t('입력한 일정 유지 · 예약 변경 및 취소 실행 없음', 'Entered schedule preserved; no bookings changed or cancelled.'),
      };
    });
    return {
      stops: stops.map(stop => adjusted.has(stop.id)
        ? { ...stop, originalTime: stop.time, time: addFifteen(stop.time) }
        : { ...stop }),
      results,
    };
  }

  window.triPilotJourneyData = { sample, parse, verify };
})();
