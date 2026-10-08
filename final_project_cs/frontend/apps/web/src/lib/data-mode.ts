// ★`[2026-10-03 사용자 지시]` 화면에 모방 데이터(데모)는 없다 — 웹은 실제 서버(`NEXT_PUBLIC_API_BASE`)에만 붙는다.
//   `NEXT_PUBLIC_DATA_MODE` 가 가질 수 있는 값은 `live` 하나다. 없거나 다른 값이면 앱은 아무 화면도 열지 않고
//   「서버 연결이 설정되지 않았어요」 한 화면만 보인다(`components/server-not-connected.tsx`).
export const DATA_MODE: "live" | "unconfigured" = process.env.NEXT_PUBLIC_DATA_MODE === "live" ? "live" : "unconfigured";
