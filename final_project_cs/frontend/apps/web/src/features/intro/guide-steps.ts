/**
 * How-it-works steps: the intro's second page and the 「이용 방법」 screen (`features/help`) show the same seven, so they live here once.
 * Each has a screen capture per language in `public/images/guguroute-guide-<language>-<shot>.jpg`.
 * `[2026-10-22 사용자 지시]` Seven whole phone screens (780×1594 — a 375×766 screen, its rounded corners kept), shown uncropped: plan → reading and
 * survey → check → fix and register → trip → notices → chat.
 * `[2026-10-22 사용자 결정 — 목업 A+E]` Over the dimmed screen, the part of each screen that step is about pops out: the same picture cut to `area`
 * (x0, y0, x1, y1 in the 780×1594 picture, inside the screen's own borders), wider than the screen, with a glow ring and a chip above it.
 * `fill` is the cut's own background, for the card's inner margin. Mockup: `mockups/guguroute-guide-highlight-2026-10-22.html`.
 * `withoutGuardian`: `[2026-10-22 사용자 결정 — ST4F-717]` the 「이용 방법」 screen's text while the operator has switched the Course Keeper off (the intro keeps its own).
 */
type Pair = readonly [ko: string, en: string];

export interface GuideStep {
  shot: string;
  area: readonly [number, number, number, number];
  fill: string;
  title: Pair;
  detail: Pair;
  chip: Pair;
  withoutGuardian?: Pair;
}

export const SHOT_W = 780, SHOT_H = 1594;

export const guideSteps: readonly GuideStep[] = [
  { shot: "1-input", area: [44, 560, 726, 1345], fill: "#ffffff", title: ["준비한 일정 붙여 넣기", "Paste the plan you have"],
    detail: ["여행 일정을 예시와 같이 입력하거나 자유롭게 입력해 주세요.", "Enter your trip like the example, or write it freely."], chip: ["자유롭게 입력", "Write it freely"] },
  { shot: "2-reading", area: [45, 745, 725, 1250], fill: "#ffffff", title: ["읽는 동안 취향 알려 주기", "Share your style while we read"],
    detail: ["계획을 읽는 동안 함께 가는 사람과 여행 취향을 물어봐요.", "While we read your plan, we ask who’s coming and what you enjoy."], chip: ["읽는 동안 취향 질문", "Questions while we read"] },
  { shot: "3-check", area: [188, 527, 731, 1060], fill: "#ffffff", title: ["하나씩 함께 확인하기", "Check it stop by stop"],
    detail: ["장소 · 운영시간 · 이동을 일정마다 확인하고, 고칠 곳이 있으면 멈춰서 물어봐요.", "Places, opening hours and travel are checked for each stop. We pause and ask when one needs a fix."], chip: ["일정마다 확인", "Checked stop by stop"] },
  { shot: "4-result", area: [10, 1180, 770, 1560], fill: "#ffffff", title: ["고치고 여행 등록하기", "Fix it and register"],
    detail: ["시간과 장소를 고치고 다시 확인한 뒤 여행으로 등록해요.", "Adjust times and places, check again, then register it as your trip."], chip: ["확인 끝나면 바로 등록", "Registered once checked"] },
  { shot: "5-trip", area: [24, 778, 756, 1565], fill: "#ffffff", title: ["내 여행 한눈에 보기", "See your trip at a glance"],
    detail: ["일차별 일정과 지도, 이동을 한 화면에서 봐요.", "Each day’s stops, the map and the travel between them on one screen."], chip: ["일정 · 이동 한눈에", "Stops and travel at a glance"] },
  { shot: "6-notices", area: [44, 248, 736, 805], fill: "#fbf7ec", title: ["여행 중에도 지켜보기", "Watched during the trip"],
    detail: ["휴무 · 날씨 · 재난이 생기면 알리고 대안을 먼저 물어봐요. 항로 지킴이를 켜면 알아서 고쳐요.", "If a place closes or the weather or a disaster hits, we tell you and ask first. Turn on the Course Keeper to let it fix things."],
    chip: ["문제 생기면 먼저 묻기", "We ask first when it changes"],
    withoutGuardian: ["휴무 · 날씨 · 재난이 생기면 알리고 대안을 먼저 물어봐요.", "If a place closes or the weather or a disaster hits, we tell you and ask first."] },
  { shot: "7-chat", area: [20, 430, 760, 1185], fill: "#ffffff", title: ["대화하며 다듬기", "Refine as you go"],
    detail: ["궁금한 점이나 바꾸고 싶은 일정을 채팅으로 말해 보세요.", "Ask about your plan or tell us what to change in chat."], chip: ["말로 바꾸기", "Change it by chatting"] },
];

export const guideImage = (language: string, shot: string) => `/images/guguroute-guide-${language}-${shot}.jpg`;
