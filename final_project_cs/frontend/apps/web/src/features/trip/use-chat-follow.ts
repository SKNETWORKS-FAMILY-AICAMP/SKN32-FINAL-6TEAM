"use client";

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { nearBottom } from "@/features/plan-check/use-follow-scroll";

/** 대화 끝을 따라 보던 경우만 새 답변을 따라간다. 직접 보낸 메시지는 최신 대화로 이동한다. */
export function useChatFollow(box: RefObject<HTMLElement | null>, active: boolean, lastId: string | undefined, pending: boolean) {
  const follow = useRef(true);
  const previous = useRef({ lastId, pending: false });
  const [away, setAway] = useState(false);
  const [unread, setUnread] = useState(false);
  const jump = () => {
    const element = box.current;
    if (!element) return;
    follow.current = true;
    element.scrollTo({ top: element.scrollHeight, behavior: "instant" });
    setAway(false); setUnread(false);
  };
  useLayoutEffect(() => {
    if (!active) return;
    const sent = pending && !previous.current.pending;
    if (sent || follow.current) {
      follow.current = true;
      if (box.current) box.current.scrollTo({ top: box.current.scrollHeight, behavior: "instant" });
      setAway(false); setUnread(false);
    } else if (lastId !== previous.current.lastId) setUnread(true);
    previous.current = { lastId, pending };
  }, [active, box, lastId, pending]);
  useEffect(() => {
    const element = box.current;
    if (!element || !active) return;
    const resize = () => { if (follow.current) element.scrollTo({ top: element.scrollHeight, behavior: "instant" }); };
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    for (const child of element.children) observer.observe(child);
    return () => observer.disconnect();
  }, [active, box, lastId, pending]);
  const onScroll = () => {
    const element = box.current;
    if (!element) return;
    const atEnd = nearBottom(element);
    follow.current = atEnd;
    setAway(!atEnd);
    if (atEnd) setUnread(false);
  };
  return { away, unread, jump, onScroll };
}
