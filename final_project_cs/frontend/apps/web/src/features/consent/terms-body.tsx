import { Fragment, type ReactNode } from "react";
import type { Translate } from "@/lib/i18n";
import type { TermsDoc } from "./terms-content";

/** A section's text: paragraphs are separated by a blank line, and lines starting with 「- 」 are a list. */
export function paragraphs(text: string): ReactNode {
  return text.split(/\n{2,}/).map((block, index) => {
    const lines = block.split("\n");
    if (lines.every((line) => line.startsWith("- "))) return <ul key={index}>{lines.map((line, at) => <li key={at}>{line.slice(2)}</li>)}</ul>;
    return <p key={index}>{lines.map((line, at) => <Fragment key={at}>{at > 0 && <br />}{line}</Fragment>)}</p>;
  });
}

/** All sections of one document (each heading already carries its 「제1조」 number), in the chosen language (Korean is the binding text). */
export function TermsBody({ doc, t }: { doc: TermsDoc; t: Translate }) {
  return <>{doc.sections.map((section) => <section key={section.heading[0]}><h3>{t(section.heading[0], section.heading[1])}</h3>{paragraphs(t(section.body[0], section.body[1]))}</section>)}</>;
}
