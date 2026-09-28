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

/**
 * The recovery email rule shared by My page and onboarding. Only the ends are trimmed: blank (or spaces only)
 * means "not entered", anything else must be an email address. No provider is singled out.
 */
export function recoveryEmailProblem(email: string): "format" | undefined {
  const value = email.trim();
  return value && !z.string().email().safeParse(value).success ? "format" : undefined;
}

/** Blank nickname and a malformed email. Length limits wait for the server's contract; none is invented here. */
export function checkDraft(draft: ProfileDraft): DraftProblems {
  const email = recoveryEmailProblem(draft.email);
  return {
    ...(!draft.nickname.trim() && { nickname: "required" as const }),
    ...(email && { email }),
  };
}
