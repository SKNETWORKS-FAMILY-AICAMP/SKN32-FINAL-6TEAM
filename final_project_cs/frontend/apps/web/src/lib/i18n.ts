export type Language = "en" | "ko";
export type Translate = (ko: string, en: string) => string;

export function translator(language: Language): Translate {
  return (ko, en) => language === "ko" ? ko : en;
}
