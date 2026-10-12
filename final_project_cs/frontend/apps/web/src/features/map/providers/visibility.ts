/** 마커를 재생성하지 않고 본체·연결선·키보드 진입만 함께 숨긴다. */
const original = new WeakMap<HTMLElement, { visibility: string; inert: boolean; ariaHidden: string | null }>();

export function setMarkerHidden(element: HTMLElement | null | undefined, hidden: boolean): void {
  if (!element || element.dataset.edgeHidden === String(hidden)) return;
  if (hidden) {
    original.set(element, { visibility: element.style.visibility, inert: element.inert, ariaHidden: element.getAttribute("aria-hidden") });
    element.style.visibility = "hidden";
    element.inert = true;
    element.setAttribute("aria-hidden", "true");
  } else {
    const before = original.get(element);
    if (before) {
      element.style.visibility = before.visibility;
      element.inert = before.inert;
      if (before.ariaHidden === null) element.removeAttribute("aria-hidden");
      else element.setAttribute("aria-hidden", before.ariaHidden);
      original.delete(element);
    }
  }
  element.dataset.edgeHidden = String(hidden);
}
