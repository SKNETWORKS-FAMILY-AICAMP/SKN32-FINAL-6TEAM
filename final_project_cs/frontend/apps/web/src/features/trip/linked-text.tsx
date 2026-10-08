import { Fragment } from "react";

/** A piece of a chat answer: plain text, or a web link the server wrote into it. */
export type TextPart = { kind: "text"; text: string } | { kind: "link"; url: string; map: boolean };

const LINK = /https:\/\/[^\s)]+/g;

/**
 * Split an answer into text and links. Only https links are made clickable; a Google Maps link is shown as a short
 * 「지도 앱으로 열기」 instead of its long encoded address (2026-09-29: the raw address filled three lines of the answer).
 */
export function splitLinks(text: string): TextPart[] {
  const parts: TextPart[] = [];
  let at = 0;
  for (const match of text.matchAll(LINK)) {
    const url = match[0].replace(/[.,]+$/, "");
    if (match.index > at) parts.push({ kind: "text", text: text.slice(at, match.index) });
    parts.push({ kind: "link", url, map: url.startsWith("https://www.google.com/maps/") });
    at = match.index + url.length;
  }
  if (at < text.length) parts.push({ kind: "text", text: text.slice(at) });
  return parts;
}

export function LinkedText({ text, mapLabel }: { text: string; mapLabel: string }) {
  return <>{splitLinks(text).map((part, index) => part.kind === "text"
    ? <Fragment key={index}>{part.text}</Fragment>
    : <a key={index} href={part.url} target="_blank" rel="noopener noreferrer">{part.map ? mapLabel : part.url}</a>)}</>;
}
