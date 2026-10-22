"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Check, ChevronDown } from "lucide-react";
import { LiveError } from "@/lib/live/client";
import { MODE_WORDS, refusalWhy, type MoveOption, type MoveOptions, type MoveOptionMode, type MoveRoute } from "@/lib/live/move-options";
import type { Translate } from "@/lib/i18n";
import { useT } from "@/lib/settings";
import type { PlanItem, PlanMove } from "./model";
import type { RowContext } from "./plan-rows";
import styles from "./plan-check.module.css";

/** The searching line says it is still going after this long (the calculator takes 0.2-10 s a leg - the slow ones are the ones that do not reach), and offers to ask again after this. */
const STILL_MS = 8_000;
const LONG_MS = 20_000;

/** `[2026-10-23]` The routes after the first ones: nothing asked yet, being asked, all there, or the server could not finish (ask again). */
type More = { status: "idle" | "loading" | "done" } | { status: "error"; message: string };

type Load =
  | { status: "idle" }
  | { status: "loading"; waited: 0 | 1 | 2 }
  | { status: "ready"; data: MoveOptions }
  | { status: "error"; message: string };

const won = (value: number) => `${value.toLocaleString("ko-KR")}원`;

/** What a way costs, as the server said it (`[2026-10-20 C안]` also the taxi option of the question asked at a late stop). */
export function fareText(option: MoveOption, t: Translate): string {
  return option.fareKrw === null ? t("요금 미상", "Fare unknown") : option.fareKrw === 0 ? t("요금 없음", "No fare") : option.fareIsEstimate ? t(`예상 ${won(option.fareKrw)}`, `Estimated ${won(option.fareKrw)}`) : option.fareIsFloor ? t(`약 ${won(option.fareKrw)}~`, `from about ${won(option.fareKrw)}`) : won(option.fareKrw);
}

/**
 * `[2026-10-07 사용자 지시 — 이동수단 고르기 · 화면 계획서 2026-10-05_이동수단_선택_화면_계획서.md]` In a leg that is open: 「이동 수단 [지금 수단 ▾]」. Opened, it asks the server for THIS leg only and lists the ways - subway, bus,
 * taxi, walking - each with how long, what it costs and how much time is left, in the server's order (a grey row keeps its place). A way that reaches in time can be picked; one that does not says why (the server's sentence)
 * when pressed, and one the server could not finish says 「확인 못 함」 (that is not 「late」). The server counts the leg again with the way and answers with the whole plan, so nothing has to be sent again.
 * ★No fake button: where the server has nothing for this leg (an older server, 404) the box is gone; no time, fare or reason is made up.
 */
export function MoveModeBox({ move, to, ctx, locked }: { move: PlanMove; to: PlanItem | undefined; ctx: RowContext; locked: string | null }) {
  const t = useT();
  const id = useId();
  const [list, setList] = useState(false);
  const [load, setLoad] = useState<Load>({ status: "idle" });
  const [busy, setBusy] = useState<MoveOptionMode | "recommended" | null>(null);
  const [problem, setProblem] = useState("");
  const [gone, setGone] = useState(false);
  const listBox = useRef<HTMLDivElement>(null);
  const ask = ctx.actions.moveOptions;
  // `[2026-10-23 사용자 지시 — 경로 후보 먼저 3개 · 목록을 내리면 더]` The plan already carries the first routes of the leg; the list's end (seen on the screen) asks the server for the next ones.
  const [extra, setExtra] = useState<MoveRoute[]>([]);
  const [more, setMore] = useState<More>({ status: "idle" });
  const [hasMore, setHasMore] = useState(Boolean(move.routesMore));
  const [routeBusy, setRouteBusy] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const firstRoutes = move.routes ?? [];
  const routes = [...firstRoutes, ...extra.filter((route) => !firstRoutes.some((shown) => shown.key === route.key))];
  const askRoutes = ctx.actions.moveRoutes;
  const canRoute = Boolean(askRoutes && ctx.actions.setMoveRoute) && routes.length > 0;

  function loadMore() {
    if (!askRoutes || more.status === "loading") return;
    setMore({ status: "loading" });
    void askRoutes(move.id, routes.length).then(
      (page) => {
        if (!page) { setHasMore(false); setMore({ status: "done" }); return; }
        setExtra((current) => [...current, ...page.routes.filter((route) => !current.some((shown) => shown.key === route.key))]);
        setHasMore(page.hasMore);
        setMore(page.routes.length === 0 && page.why ? { status: "error", message: page.why } : { status: page.hasMore ? "idle" : "done" });
      },
      (error: unknown) => setMore({ status: "error", message: error instanceof Error ? error.message : String(error) }),
    );
  }

  // The end of the route list coming into view asks for the next routes (once at a time; a refusal waits for 「다시 불러오기」).
  const watching = list && canRoute && hasMore && more.status === "idle";
  useEffect(() => {
    const spot = end.current;
    if (!watching || !spot || typeof IntersectionObserver === "undefined") return;
    const seen = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) loadMore(); }, { rootMargin: "120px 0px" });
    seen.observe(spot);
    return () => seen.disconnect();
  });

  // The searching line grows a second and third sentence the longer it takes (timers set from the effect, never while drawing).
  const waiting = load.status === "loading";
  useEffect(() => {
    if (!waiting) return;
    const still = setTimeout(() => setLoad((current) => current.status === "loading" ? { status: "loading", waited: 1 } : current), STILL_MS);
    const long = setTimeout(() => setLoad((current) => current.status === "loading" ? { status: "loading", waited: 2 } : current), LONG_MS);
    return () => { clearTimeout(still); clearTimeout(long); };
  }, [waiting]);

  if (!ask || gone) return null;

  function fetchWays() {
    setLoad({ status: "loading", waited: 0 });
    setProblem("");
    void ask!(move.id).then(
      (found) => { if (found) setLoad({ status: "ready", data: found }); else setGone(true); },
      (error: unknown) => setLoad({ status: "error", message: error instanceof Error ? error.message : String(error) }),
    );
  }

  function toggle() {
    if (locked) { ctx.explain(locked); return; }
    const next = !list;
    setList(next);
    setProblem("");
    // Opened: ask for this leg (the actions keep an answer for the revision); a list that holds a way the server could not finish is asked again.
    if (next && (load.status === "idle" || load.status === "error" || (load.status === "ready" && load.data.options.some((option) => option.fits === null)))) fetchWays();
  }

  const current = load.status === "ready" ? load.data.currentMode : null;
  const recommended = load.status === "ready" ? load.data.recommendedMode : null;
  const picked = (option: MoveOption) => (current ?? move.modeKey) === option.mode;

  async function choose(option: MoveOption) {
    if (busy) return;
    if (option.fits !== true) { ctx.explain(option.whyNot ?? (option.fits === null ? t("계산이 오래 걸려 확인하지 못했어요", "The server could not finish counting this one") : t("다음 일정 시작 안에 닿지 않아요", "It does not reach before the next stop starts"))); return; }
    if (picked(option)) { setList(false); return; }
    setBusy(option.mode);
    setProblem("");
    try {
      await ctx.onSetMode(move, { mode: option.mode, label: option.label });
      setList(false);
      setLoad({ status: "idle" });                                  // the plan is the server's new one: the ways are asked again the next time
    } catch (error) {
      setProblem(error instanceof LiveError && error.code === "stale_revision" ? t("그 사이 일정이 바뀌었어요. 다시 골라 주세요.", "The plan changed in the meantime. Please choose again.")
        : error instanceof LiveError && error.code === "mode_not_fit" ? refusalWhy(error) ?? error.message
          : error instanceof Error ? error.message : String(error));
      setLoad({ status: "idle" });
    } finally { setBusy(null); }
  }

  async function chooseRoute(route: MoveRoute) {
    if (routeBusy || busy) return;
    if (route.slackMin !== null && route.slackMin < 0) { ctx.explain(t(`이 경로는 ${Math.abs(route.slackMin)}분 늦어요`, `This route is ${Math.abs(route.slackMin)} min late`)); return; }
    if (route.key === move.routeKey) { setList(false); return; }
    setRouteBusy(route.key);
    setProblem("");
    try {
      await ctx.onSetRoute(move, { key: route.key, label: routeName(route, t) });
      setList(false);
      setLoad({ status: "idle" });
    } catch (error) {
      setProblem(error instanceof LiveError && error.code === "stale_revision" ? t("그 사이 일정이 바뀌었어요. 다시 골라 주세요.", "The plan changed in the meantime. Please choose again.")
        : error instanceof LiveError && error.code === "mode_not_fit" ? refusalWhy(error) ?? error.message
          : error instanceof Error ? error.message : String(error));
    } finally { setRouteBusy(null); }
  }

  /** Arrow keys move through the ways, Escape closes the list (the focus goes back to the box). */
  function keys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") { event.stopPropagation(); setList(false); (event.currentTarget.parentElement?.querySelector("button[aria-haspopup]") as HTMLElement | null)?.focus(); return; }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const rows = Array.from(listBox.current?.querySelectorAll<HTMLElement>('[role="option"]') ?? []);
    const at = rows.indexOf(document.activeElement as HTMLElement);
    if (!rows.length) return;
    event.preventDefault();
    rows[(Math.max(at, 0) + (event.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length]?.focus();
  }

  const options = load.status === "ready" ? load.data.options : [];
  const none = load.status === "ready" && options.length > 0 && options.every((option) => option.fits !== true);
  const chosenByCustomer = Boolean(move.modeKey && move.recommendedMode && move.modeKey !== move.recommendedMode);
  const dropped = move.modeChoice?.state === "dropped";

  return <div className={styles.modeBox} data-locked={locked ? true : undefined}>
    <button type="button" className={styles.modeButton} aria-haspopup="listbox" aria-expanded={list} aria-controls={`${id}-ways`} aria-disabled={locked ? true : undefined} onClick={toggle}>
      <span className={styles.modeLabel}>{t("이동 수단", "Way to go")}</span>
      <span className={styles.modeNow}>{move.mode || t("수단 미정", "Not set")}{chosenByCustomer && <em>{t("내가 고름", "My pick")}</em>}</span>
      <ChevronDown size={16} strokeWidth={1.8} aria-hidden="true" data-open={list || undefined} />
    </button>
    {dropped && !list && <p className={styles.modeNote}>{t("고른 수단으로는 닿지 않아 추천 수단으로 돌아왔어요", "The way you picked no longer reaches in time, so it went back to the recommended one")}{move.modeChoice?.why ? ` · ${move.modeChoice.why}` : ""}</p>}
    {list && <div id={`${id}-ways`} ref={listBox} className={styles.modeList} role="listbox" aria-label={t("이동 수단 고르기", "Choose a way to go")} aria-busy={load.status === "loading" || undefined} onKeyDown={keys}>
      {load.status === "loading" && <>
        {[0, 1, 2, 3].map((row) => <div key={row} className={styles.modeWait} aria-hidden="true">{row === 0 ? t("찾는 중…", "Looking…") : ""}</div>)}
        <p className={styles.modeNote} role="status">{load.waited === 0 ? t("이 구간의 이동 수단을 찾고 있어요", "Looking for the ways to go on this leg")
          : load.waited === 1 ? t("아직 찾고 있어요 · 못 닿는 구간은 몇 초 더 걸려요", "Still looking - a leg that does not reach takes a few seconds longer")
            : t("오래 걸려요 — 닫았다가 다시 열면 다시 불러와요", "It is taking long - close and open it again to ask again")}</p>
        {load.waited === 2 && <button type="button" className={styles.modeRetry} onClick={fetchWays}>{t("다시 불러오기", "Ask again")}</button>}
      </>}
      {load.status === "error" && <p className={styles.modeNote} role="alert">{load.message} <button type="button" className={styles.modeRetry} onClick={fetchWays}>{t("다시 불러오기", "Ask again")}</button></p>}
      {load.status === "ready" && options.length === 0 && <p className={styles.modeNote} role="status">{t("이 구간의 이동 수단을 찾지 못했어요", "No way to go was found for this leg")}</p>}
      {options.map((option) => {
        const on = picked(option);
        const reaches = option.fits === true;
        const fare = fareText(option, t);
        const slack = option.fits === null ? t("확인 못 함", "Not checked")
          : option.slackMin === null ? "" : option.slackMin < 0 ? t(`늦어요 ${Math.abs(option.slackMin)}분`, `${Math.abs(option.slackMin)} min late`) : t(`여유 ${option.slackMin}분`, `${option.slackMin} min to spare`);
        const unsure = option.grade === "추정" || option.grade === "근거없음";
        return <button key={option.mode} type="button" role="option" className={styles.modeOption} aria-selected={on} aria-disabled={!reaches || busy !== null ? true : undefined}
          data-fits={option.fits === null ? "unknown" : option.fits ? "yes" : "no"} data-busy={busy === option.mode || undefined} onClick={() => void choose(option)}>
          <span className={styles.modeDot} aria-hidden="true">{on && <Check size={12} strokeWidth={3} />}</span>
          <span className={styles.modeOptionBody}>
            <span className={styles.modeOptionTop}>
              <strong>{option.label || t(...MODE_WORDS[option.mode])}</strong>
              {option.minutes !== null && <span>{t(`${option.minutes}분`, `${option.minutes} min`)}{option.km !== null ? ` · ${option.km}km` : ""}</span>}
              <span>{fare}</span>
              {slack && <span className={styles.modeSlack} data-late={option.fits === false || undefined}>{slack}</span>}
            </span>
            <span className={styles.modeTags}>
              {option.mode === recommended && <em>{t("추천", "Suggested")}</em>}
              {unsure && <em data-tone="guess">{option.grade === "근거없음" ? t("근거 없음", "No basis") : t("추정", "Estimate")}</em>}
              {on && chosenByCustomer && <em>{t("내가 고름", "My pick")}</em>}
              {!reaches && <em data-tone="no">{option.fits === null ? t("고를 수 없어요", "Cannot pick") : t("고를 수 없어요", "Cannot pick")}</em>}
            </span>
            {option.whyNot && !reaches && <span className={styles.modeWhy}>{option.whyNot}</span>}
            {option.fareIsEstimate && <span className={styles.modeWhy}>{t("예상 요금이에요. 실제 결제액은 교통·대기·호출료·할증에 따라 달라질 수 있어요.", "Estimated fare. Traffic, waiting, booking fees and surcharges may change the final price.")}</span>}
          </span>
        </button>;
      })}
      {none && <div className={styles.modeNone} role="status">
        <p>{t("여유 안에 닿는 수단이 없어요. 다음 일정 시작을 늦추면 고를 수 있어요.", "No way reaches in time. Start the next stop later to be able to pick one.")}</p>
        {to && <button type="button" className={styles.modeRetry} onClick={() => { setList(false); ctx.onOpenTime(to); }}>{t("시간 고치기", "Change the time")}</button>}
      </div>}
      {canRoute && <>
        <p className={styles.routeHead}>{t("경로 후보", "Routes")}<span>{t("내리면 더 보여요", "Scroll for more")}</span></p>
        {routes.map((route) => {
          const on = route.key === move.routeKey;
          const late = route.slackMin !== null && route.slackMin < 0;
          const slack = route.slackMin === null ? "" : late ? t(`늦어요 ${Math.abs(route.slackMin)}분`, `${Math.abs(route.slackMin)} min late`) : t(`여유 ${route.slackMin}분`, `${route.slackMin} min to spare`);
          return <button key={route.key} type="button" role="option" className={styles.modeOption} aria-selected={on} aria-disabled={late || routeBusy !== null ? true : undefined}
            data-fits={late ? "no" : "yes"} data-busy={routeBusy === route.key || undefined} onClick={() => void chooseRoute(route)}>
            <span className={styles.modeDot} aria-hidden="true">{on && <Check size={12} strokeWidth={3} />}</span>
            <span className={styles.modeOptionBody}>
              <span className={styles.modeOptionTop}>
                <strong>{routeName(route, t)}</strong>
                {route.minutes !== null && <span>{t(`${route.minutes}분`, `${route.minutes} min`)}</span>}
                {route.depart && route.arrive && <span>{`${route.depart} → ${route.arrive}`}</span>}
                {slack && <span className={styles.modeSlack} data-late={late || undefined}>{slack}</span>}
              </span>
              <span className={styles.modeTags}>
                {route.planned && <em>{t("추천", "Suggested")}</em>}
                {route.transfers !== null && route.transfers > 0 && <em data-tone="no">{t(`환승 ${route.transfers}회`, `${route.transfers} transfer${route.transfers > 1 ? "s" : ""}`)}</em>}
                {route.early && <em data-tone="guess">{t("조금 일찍 출발", "Leaves earlier")}</em>}
                {on && move.routeChoice?.state === "kept" && <em>{t("내가 고름", "My pick")}</em>}
              </span>
            </span>
          </button>;
        })}
        {more.status === "loading" && <div className={styles.modeWait} role="status">{t("경로를 더 찾는 중…", "Looking for more routes…")}</div>}
        {more.status === "error" && <p className={styles.modeNote} role="alert">{more.message} <button type="button" className={styles.modeRetry} onClick={() => { setMore({ status: "idle" }); loadMore(); }}>{t("다시 불러오기", "Ask again")}</button></p>}
        {hasMore && more.status === "idle" && <button type="button" className={styles.modeRetry} onClick={loadMore}>{t("경로 더 보기", "More routes")}</button>}
        {!hasMore && extra.length > 0 && <p className={styles.modeNote}>{t("찾은 경로를 다 보여 드렸어요", "These are all the routes found")}</p>}
        <div ref={end} aria-hidden="true" />
      </>}
      {move.routeChoice?.state === "dropped" && <p className={styles.modeNote}>{t("고른 경로로는 닿지 않아 추천 경로로 돌아왔어요", "The route you picked no longer works, so it went back to the recommended one")}{move.routeChoice.why ? ` · ${move.routeChoice.why}` : ""}</p>}
      {problem && <p className={styles.modeNote} role="alert">{problem}</p>}
    </div>}
  </div>;
}

/** A route's name: the lines ridden in order (「3호선 → 2호선」), else the server's name for its way. */
function routeName(route: MoveRoute, t: Translate): string {
  if (route.lines.length) return route.lines.join(" → ");
  return route.modeLabel || (route.mode === "walk" ? t("도보", "Walk") : route.mode === "taxi" ? t("택시", "Taxi") : t("대중교통", "Transit"));
}
