/** Keep at least half of a small map for geography instead of spending it on fixed camera gutters. */
export function fitPadding(width: number, height: number, topInset = 0, bottomInset = 0, margin = 50) {
  const horizontal = Math.min(margin, Math.max(0, width) / 4);
  const budget = Math.max(0, height) / 2;
  const top = Math.max(0, topInset), bottom = Math.max(0, bottomInset);
  const scale = top + bottom > budget ? budget / (top + bottom) : 1;
  const vertical = Math.min(margin, Math.max(0, budget - top - bottom) / 2);
  return { top: top * scale + vertical, right: horizontal, bottom: bottom * scale + vertical, left: horizontal };
}

/** `[2026-10-22 ST4F-722]` How far (px) below the middle of the map the middle of its visible part is — between the bar on top and the sheet below. */
export function visibleLift(topInset = 0, bottomInset = 0) {
  return (Math.max(0, topInset) - Math.max(0, bottomInset)) / 2;
}
