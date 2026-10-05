import { describe, expect, it } from "vitest";
import { CONSENT_CODES, REQUIRED_CONSENTS } from "./consent-model";
import { DRAFT_NOTICE, OPERATOR, RETENTION, TERMS_DOCS, TERMS_STATUS, type TermsDoc } from "./terms-content";

const PLACEHOLDER = "【확정 필요:";

/** A document's every string: title, summary, and each section's heading and body, Korean and English. */
function texts(doc: TermsDoc): string[] {
  return [...doc.title, ...doc.summary, ...doc.sections.flatMap((section) => [...section.heading, ...section.body])];
}

/** The values the bodies are allowed to interpolate: the operator details and the retention periods (both languages). */
const constantValues: string[] = [
  ...Object.values(OPERATOR),
  ...Object.values(RETENTION).flatMap((pair) => [...pair]),
].sort((a, b) => b.length - a.length); // longest first, so a value that contains another is removed whole

describe("terms documents (one per consent item)", () => {
  it("has exactly one document for each consent code", () => {
    expect(TERMS_DOCS.map((doc) => doc.code).sort()).toEqual([...CONSENT_CODES].sort());
  });

  it("marks as required exactly the consents the app is gated on", () => {
    for (const doc of TERMS_DOCS) expect(doc.required, doc.code).toBe(REQUIRED_CONSENTS.includes(doc.code));
  });

  it("has a non-empty Korean and English title, summary, heading and body everywhere", () => {
    for (const doc of TERMS_DOCS) {
      expect(doc.sections.length, doc.code).toBeGreaterThan(0);
      for (const value of texts(doc)) expect(value.trim().length, `${doc.code}: «${value.slice(0, 40)}»`).toBeGreaterThan(0);
    }
  });

  it("writes lists as lines starting with “- ” and separates paragraphs with one blank line", () => {
    for (const doc of TERMS_DOCS) {
      for (const section of doc.sections) {
        for (const body of section.body) {
          expect(body, `${doc.code} / ${section.heading[0]}`).not.toMatch(/\n{3,}/);
          expect(body, `${doc.code} / ${section.heading[0]}`).not.toMatch(/^[ \t]+-\s/m); // no indented list markers
          expect(body.trim()).toBe(body);
        }
      }
    }
  });

  it("says in every document that the Korean text prevails over the English translation", () => {
    for (const doc of TERMS_DOCS) {
      const [ko, en] = doc.sections[doc.sections.length - 1].body;
      expect(ko, doc.code).toContain("한국어본이 우선");
      expect(en, doc.code).toContain("Korean version prevails");
    }
  });

  it("takes every “to be decided” placeholder from OPERATOR or RETENTION, never typed into a body", () => {
    for (const doc of TERMS_DOCS) {
      for (const value of texts(doc)) {
        let rest = value;
        for (const constant of constantValues) rest = rest.split(constant).join("");
        expect(rest, `${doc.code}: «${value.slice(0, 60)}»`).not.toContain(PLACEHOLDER);
        expect(rest, `${doc.code}: «${value.slice(0, 60)}»`).not.toMatch(/【|】/);
      }
    }
  });

  it("keeps placeholders while the terms are a draft, and none once reviewed", () => {
    const operatorPlaceholders = Object.values(OPERATOR).filter((value) => value.includes(PLACEHOLDER));
    const allPlaceholders = constantValues.filter((value) => value.includes(PLACEHOLDER));
    if (TERMS_STATUS === "draft") {
      expect(allPlaceholders.length).toBeGreaterThan(0);        // `[2026-10-05]` the operator details are filled; what is still open are the retention periods
      expect(operatorPlaceholders).toEqual([]);
      expect(DRAFT_NOTICE[0]).toContain("AI 작성 초안");
    } else {
      expect(allPlaceholders).toEqual([]);
    }
  });

  it("gives every retention period in both languages", () => {
    for (const [key, [ko, en]] of Object.entries(RETENTION)) {
      expect(ko.trim().length, key).toBeGreaterThan(0);
      expect(en.trim().length, key).toBeGreaterThan(0);
    }
  });
});
