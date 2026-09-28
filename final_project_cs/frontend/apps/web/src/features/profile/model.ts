import { z } from "zod";

/** The editable part of the profile. The token is not part of it: it cannot be changed. */
export interface ProfileDraft {
  nickname: string;
  email: string;
}

export interface DraftProblems {
  nickname?: "required";
  email?: "format";
}

/** Blank nickname and a malformed email. Length limits wait for the server's contract; none is invented here. */
export function checkDraft(draft: ProfileDraft): DraftProblems {
  const email = draft.email.trim();
  return {
    ...(!draft.nickname.trim() && { nickname: "required" as const }),
    ...(email && !z.string().email().safeParse(email).success && { email: "format" as const }),
  };
}
