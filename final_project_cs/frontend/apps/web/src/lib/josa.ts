/** The last syllable's final consonant (받침) index, 0 when there is none or the word does not end in Hangul. */
function final(word: string): number {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return code >= 0 && code <= 11171 ? code % 28 : 0;
}

/** Korean particles that follow a word's last sound: 「경복궁을」·「창덕궁으로」·「경복궁과」. */
export const eul = (word: string) => word + (final(word) ? "을" : "를");
/** ㄹ-final words take 「로」 like vowels (「서울로」). */
export const ro = (word: string) => word + (final(word) && final(word) !== 8 ? "으로" : "로");
export const gwa = (word: string) => word + (final(word) ? "과" : "와");
