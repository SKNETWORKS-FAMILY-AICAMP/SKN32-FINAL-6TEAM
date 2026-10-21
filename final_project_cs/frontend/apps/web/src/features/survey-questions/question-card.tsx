"use client";

import { canPickPartySize, type Area } from "@/features/onboarding/model";
import { AREA_ICONS, ChoiceChips, OtherField, PairRows, PriorityAreas, TravelerSizes, usePressFeedback } from "@/features/onboarding/survey-fields";
import { useT } from "@/lib/settings";
import type { MouseEvent } from "react";
import { asksSize, companionsOf, CUSTOM, exactPicks, pickArea, pickChoice, pickDetail, pickPart, pickSize, sizeOf, type Draft, type SurveyQuestion } from "./model";

/**
 * `[2026-10-20 ST4F-665]` The body of a loading question: the start survey's card pieces with the server's question in them (`features/onboarding/survey-fields.tsx`),
 * so the two screens show the same card under the same rules. It changes only the card being answered (`draft`); the pager sends it when 「다음」 is pressed.
 */
export function QuestionCard({ question, draft, setDraft }: { question: SurveyQuestion; draft: Draft; setDraft: (next: Draft) => void }) {
  const t = useT();
  const { touched, feedback } = usePressFeedback();
  const press = (event: MouseEvent<HTMLButtonElement>, next: Draft, key: string) => { setDraft(next); feedback(event.currentTarget, key); };
  const prefix = `loading-${question.id}`;

  switch (question.kind) {
    case "single": {
      const options = question.allowCustom ? [...question.options, { id: CUSTOM, label: question.customLabel }] : question.options;
      const companions = asksSize(question);
      return <>
        <ChoiceChips name={question.id} options={options} selected={draft.choice} touched={touched} onPick={(event, id) => press(event, pickChoice(draft, id), `${question.id}:${id}`)} />
        {draft.choice === CUSTOM && <OtherField t={t} id={`${prefix}-other`} value={draft.custom} maxLength={question.customMaxLength}
          {...(!companions && { label: t("원하는 답을 적어 주세요.", "Write your answer."), placeholder: "" })} onChange={(custom) => setDraft({ ...draft, custom })} />}
        {companions && draft.choice && <TravelerSizes t={t} labelId={`${prefix}-size`} size={sizeOf(draft)} canPick={(n) => canPickPartySize(companionsOf(draft), n)} touched={touched}
          onPick={(event, n) => press(event, pickSize(draft, n), `partySize:${n}`)} />}
      </>;
    }
    case "priority":
      return <PriorityAreas t={t} idPrefix={`${prefix}-`} order={draft.areas} details={draft.details}
        areas={question.options.map((area) => {
          const group = question.groups.find((entry) => entry.id === area.id)!;
          return { id: area.id, label: area.label, icon: AREA_ICONS[area.id as Area] ?? area.id, options: group.options, exact: exactPicks(group), read: group.read };
        })}
        onArea={(event, area) => press(event, pickArea(draft, area), `area:${area}`)}
        onDetail={(event, area, id) => press(event, pickDetail(question, draft, area, id), `${area}:${id}`)} />;
    case "pair":
      return <PairRows t={t} touched={touched} selected={draft.parts}
        parts={question.parts.map((part) => ({ id: part.id, name: `${question.id}.${part.id}`, label: part.label, options: part.options, read: part.read }))}
        onPick={(event, part, id) => press(event, pickPart(draft, part, id), `${question.id}.${part}:${id}`)} />;
  }
}
