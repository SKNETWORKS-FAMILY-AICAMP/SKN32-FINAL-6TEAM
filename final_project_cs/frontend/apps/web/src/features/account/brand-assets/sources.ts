/** Official brand sources checked 2026-10-09. No third-party or hand-drawn corporate symbols. */
export const BRAND_ASSET_SOURCES = {
  google: "https://developers.google.com/identity/branding-guidelines",
  kakao: "https://developers.kakao.com/tool/images/resource/preview/login-complete-en.svg",
  naver: "https://developers.naver.com/inc/devcenter/downloads/bi/NAVER_login_EN.zip",
  discord: "https://cdn.prod.website-files.com/6257adef93867e50d84d30e2/66e3d7f4ef6498ac018f2c55_Symbol.svg",
} as const;
// kakao.svg: first official SVG path, d/fill unchanged; viewBox fits the symbol without stretching.
// naver.png: NAVER_login_EN/NAVER_login_Light_EN_green_icon_H48.png, bytes unchanged.
// discord.svg: official branding page Symbol link, bytes unchanged (white symbol on Blurple).
// Google: existing official HTML configurator SVG paths in google-button.tsx, unchanged.
