import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { Proposal } from "@/lib/live/extras";
import { LiveError } from "@/lib/live/client";
import type { OpenChoice } from "./attention";
import type { TripStop } from "./model";
import { chooseFailure, chooseOutcome, ProposalAsk } from "./proposal-ask";
import { StopRow } from "./trip-rows";

vi.mock("@/lib/settings", () => ({ useT: () => (ko: string) => ko, useSettings: () => ({ language: "ko" }) }));
const t = (ko: string) => ko;
const stop: TripStop = { id: "stop-sky", date: "2026-10-24", time: "10:00", endTime: "10:45", title: "잠실 스카이타워 전망 관람", booking: "unknown", notes: "", kind: "activity" };
const proposal: Proposal = { id: "p-1", itemId: stop.id, baseVersion: 1, reason: "forecast_advisory", status: "open", safety: false, expiresAt: null, options: [] };
const choice: OpenChoice = { proposal, stop, text: "잠실 스카이타워 전망 관람 — 예보 주의사항이 있어요(강수확률 70%)." };

const row = (patch: Partial<Parameters<typeof StopRow>[0]> = {}) => renderToStaticMarkup(createElement(StopRow, {
  stop, open: false, selected: false, onToggle: () => {}, onDetail: () => {}, onMapApps: () => {}, choice, ...patch,
}));
const ask = (patch: Partial<OpenChoice> = {}, busy = false) => renderToStaticMarkup(createElement(ProposalAsk, {
  choice: { ...choice, ...patch }, busy, onChoose: () => {}, onEdit: () => {},
}));

describe("선택 요청이 열린 일정 카드(ST4F-704 D안)", () => {
  it("카드를 「확인 필요」처럼 칠하고 서버 문장과 「상세 보기에서 확인하세요」를 붙인다 — 단추는 펼친 카드의 「상세 보기」 하나", () => {
    const html = row();
    expect(html).toContain('data-verdict="review"');
    expect(html).toContain('data-stop-ask="stop-sky"');
    expect(html).toContain("선택이 필요해요");
    expect(html).toContain("예보 주의사항이 있어요(강수확률 70%).");
    expect(html).toContain("상세 보기에서 확인하세요");
    const mark = html.slice(html.indexOf("data-stop-ask"), html.indexOf("</div>", html.indexOf("data-stop-ask")));
    expect(mark).toContain("상세 보기에서 확인하세요");
    expect(mark).not.toContain("<button");
    expect(row({ open: true }).match(/상세 보기<svg/g)?.length).toBe(1);
  });
  it("서버 문장이 없으면 알림 센터 문장을 쓴다", () => {
    expect(row({ choice: { ...choice, text: null } })).toContain("이 일정을 어떻게 할지 골라 주세요.");
  });
  it.each([
    ["지난 일정", { past: true }],
    ["다른 일정의 선택", { choice: { ...choice, stop: { ...stop, id: "another" } } }],
    ["선택 없음", { choice: undefined }],
  ])("%s에는 표시하지 않는다", (_name, patch) => {
    const html = row(patch);
    expect(html).not.toContain("data-stop-ask");
    expect(html).not.toContain("data-verdict");
  });
});

describe("상세 보기의 선택 칸", () => {
  it("먼저 묻는 날씨 제안은 「예보에 맞게 일정 변경」 · 「직접 수정」 · 「지금 일정 그대로 두기」", () => {
    const html = ask();
    expect(html).toContain("선택 요청");
    expect(html).toContain("예보에 맞게 일정 변경");
    expect(html).toContain("직접 수정");
    expect(html).toContain("지금 일정 그대로 두기");
  });
  it("실내 여부를 모르면 「다른 곳 찾아보기」, 대안이 있으면 서버 값(메모 · 시각 · 이름 · 경고)만", () => {
    expect(ask({ proposal: { ...proposal, reason: "indoor_unknown" } })).toContain("다른 곳 찾아보기");
    const html = ask({ proposal: { ...proposal, reason: "indoor_unknown_options", options: [
      { key: "a", rank: 1, name: "롯데월드 아쿠아리움", startsAt: "2026-10-24T01:00:00Z", note: "실내", warnings: [] },
      { key: "b", rank: 2, name: "송파책박물관", startsAt: null, note: null, warnings: ["그 시각 영업을 확인할 수 없어요"] },
    ] } });
    expect(html).not.toContain("다른 곳 찾아보기");
    expect(html).toContain("실내 · 10:00 롯데월드 아쿠아리움");
    expect(html).toContain("송파책박물관");
    expect(html).toContain("그 시각 영업을 확인할 수 없어요");
  });
  it("답을 기다리는 동안 단추를 잠근다", () => {
    expect(ask({}, true).match(/disabled=""/g)?.length).toBe(3);
  });
  it("기한과 안전 여부를 적는다", () => {
    expect(ask({ proposal: { ...proposal, safety: true, expiresAt: "2026-10-24T00:00:00Z" } })).toContain("안전과 관련된 선택이에요. 2026-10-24 09:00 까지");
  });
});

describe("고른 결과 문구", () => {
  it("대안을 받는 중에는 말하지 않고, 끝난 결과는 알림 센터 문구로", () => {
    expect(chooseOutcome("options", t)).toBeNull();
    expect(chooseOutcome("no_alternate", t)).toBe("바꿀 수 있는 다른 곳을 찾지 못했어요 — 원래 일정을 그대로 둡니다.");
    expect(chooseOutcome("chosen", t)).toBe("고르신 곳으로 일정을 바꿨어요.");   // 서버가 고른 안에 주는 이름(pending.py) — 2026-10-22 실서버에서 「처리 결과: chosen」으로 보였다
    expect(chooseOutcome("adjusted", t)).toBe("처리 결과: adjusted");
    expect(chooseOutcome("kept", t)).toBe("지금 일정을 그대로 두었어요.");
  });
  it("이미 정해졌거나 일정이 바뀌었으면 그렇게, 그 밖에는 서버 말 그대로", () => {
    expect(chooseFailure(new LiveError("already_decided", "decided", undefined, 409), t)).toContain("이미 정해졌거나");
    expect(chooseFailure(new Error("서버 오류"), t)).toBe("서버 오류");
  });
});
