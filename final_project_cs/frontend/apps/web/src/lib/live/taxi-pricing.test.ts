import { describe, expect, it } from "vitest";
import { TAXI_PRODUCTS, webTaxiPricingOf } from "./taxi-pricing";

describe("호출 상품을 미확인 일반호출0원으로 바꾸지 않음", () => {
  it.each(TAXI_PRODUCTS)("keeps the confirmed $id product", ({ id }) => {
    expect(webTaxiPricingOf({ product: id, quotes: [] })).toEqual({ product: id, quotes: [] });
  });
  it.each([undefined, null, {}, { product: "blue_partners_immediate", quotes: [] },
    { product: "kakao_general" }, { product: "capsi_immediate", quotes: [{}] },
    { product: "kakao_general", quotes: [], fee: 0 }])("does not default malformed or unsupported response %# to general", (value) => {
    expect(webTaxiPricingOf(value)).toBeNull();
  });
});
