/** Join class names, skipping the ones that are off (a CSS module has no class for a state that needs no style). */
export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");
