export type Language = "en" | "ko";
export type Translate = (ko: string, en: string) => string;

/** Each language named in itself, for the settings menu and the intro card. */
export const languages: [Language, string][] = [["en", "English"], ["ko", "한국어"]];

export function translator(language: Language): Translate {
  return (ko, en) => language === "ko" ? ko : en;
}
