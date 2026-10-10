import { expect, it } from "vitest";
import { fromPixels, toPixels } from "./map-geometry";
import { pinArea } from "./providers/pin";

it("지도 클릭 좌표는 Mercator 위도·경도와 화면 위치가 왕복 일치한다", () => {
  for (const view of [
    { south:37.4, north:37.72, west:126.7, east:127.3, width:375, height:500, zoom:12 },
    { south:-60, north:80, west:-150, east:150, width:1280, height:720, zoom:3 },
  ]) for (const at of [{ x:0,y:0 },{ x:view.width,y:view.height },{ x:123,y:234 }]) {
    const result = toPixels(view, fromPixels(view, at));
    expect(result.x).toBeCloseTo(at.x,8); expect(result.y).toBeCloseTo(at.y,8);
  }
});

it("마커는 거리·화살표 버튼과 거리 칩만 피하고 확장 도구 영역은 예약하지 않는다", () => {
  const rect = (left:number, top:number, right:number, bottom:number) => ({getBoundingClientRect:()=>({left,top,right,bottom})});
  const nodes = { '[data-map-obstacle]':rect(320,80,364,124), '[data-edge-chip]':rect(0,180,90,224), '[data-map-controls]':rect(140,80,364,124) };
  const live = { querySelectorAll:(selector:string) => Object.entries(nodes).filter(([key])=>selector.includes(key)).map(([,node])=>node) };
  const container = {...rect(0,0,375,500),closest:()=>live} as unknown as HTMLElement;
  expect(pinArea(container, {topInset:64,bottomInset:20}).obstacles).toEqual([
    {left:314,top:74,right:370,bottom:130}, {left:-6,top:174,right:96,bottom:230},
  ]);
});
