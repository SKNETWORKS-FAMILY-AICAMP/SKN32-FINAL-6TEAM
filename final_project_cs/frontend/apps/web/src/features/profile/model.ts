/** The editable part of the profile. The token is not part of it: it cannot be changed. */
export interface ProfileDraft {
  nickname: string;
}

export interface DraftProblems {
  nickname?: "required";
}

/** A blank nickname. Length limits wait for the server's contract; none is invented here. */
export function checkDraft(draft: ProfileDraft): DraftProblems {
  return !draft.nickname.trim() ? { nickname: "required" } : {};
}
