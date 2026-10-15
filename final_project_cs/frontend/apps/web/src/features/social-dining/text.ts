import type { Translate } from "@/lib/i18n";

const STATUS: Record<string, [string, string]> = {
  identified: ["식당 후보를 읽었어요", "Restaurant details found"], confirmed: ["방문할 식당을 확인했어요", "Restaurant confirmed"],
  needs_choice: ["방문할 곳을 골라 주세요", "Choose the restaurant"], needs_info: ["식당 정보가 더 필요해요", "More restaurant details needed"],
  inaccessible: ["게시물을 열지 못했어요", "Could not open the post"], failed: ["식당 정보를 읽지 못했어요", "Could not read the restaurant details"],
  unsupported: ["지원하는 공개 링크를 넣어 주세요", "Use a supported public link"], invalid: ["링크 주소를 확인해 주세요", "Check the link address"],
};
const REASON: Record<string, [string, string]> = {
  restaurant_choice_required: ["여러 식당이 나와요. 원하는 식당을 골라 주세요.", "The post mentions several restaurants. Choose the one you want."],
  place_choice_required: ["같은 이름의 장소가 있어요. 주소와 지점을 골라 주세요.", "Several places share this name. Choose the address and branch."],
  place_not_found: ["식당 위치를 찾지 못했어요. 이름과 지역을 보완해 주세요.", "The restaurant could not be located. Add its name and area."],
  no_meal_slots: ["아직 배치할 식사가 없어요. 일정을 만든 뒤 다시 확인해 주세요.", "There are no meal slots yet. Create an itinerary, then check again."],
  no_future_meal_slots: ["지난·고정·예약한 식사를 제외하면 바꿀 수 있는 남은 식사가 없어요.", "No remaining meals can change after excluding past, locked and booked stops."],
  unknown_facts: ["방문 가능 여부를 확인할 자료가 부족해요.", "There is not enough information to confirm this visit."],
  unknown_dietary: ["요청하신 식이 조건을 확인할 근거가 부족해요.", "There is not enough evidence to confirm your dietary requirements."],
  dietary_conflict: ["요청하신 식이 조건에 맞지 않아 넣지 않았어요.", "This restaurant conflicts with your dietary requirements, so it was left out."],
  does_not_fit: ["이동과 식사 시간을 맞출 수 없어 넣지 않았어요.", "Travel and meal times do not fit, so this restaurant was left out."],
  already_scheduled: ["이미 일정에 있는 식당이에요.", "This restaurant is already in your itinerary."],
  selected_place_unavailable: ["고르신 지점을 이번 확인에서 다시 찾지 못해 보류했어요. 선택은 그대로 두었어요.", "We could not find the branch you chose this time, so it is on hold. Your choice is kept."],
  no_available_slot: ["맞는 식사 자리를 찾지 못했어요.", "No suitable meal slot was found."],
  activity_change_required: ["다른 활동도 바꿔야 해요. 일반 일정 수정에서 확인해 주세요.", "Other activities would need to change. Review them in Edit itinerary."],
  full_validation_failed: ["전체 일정 확인을 통과하지 못해 넣지 않았어요.", "The full itinerary check did not pass, so nothing was added."],
  preview_budget_exhausted: ["이번에 모두 확인하지 못했어요. 후보는 보관되어 있어요.", "Not all candidates could be checked this time. They remain saved."],
};
export const diningStatus = (code: string, t: Translate) => t(...(STATUS[code] ?? ["추가 확인이 필요해요", "More checking is needed"]));
export const diningReason = (code: string | null | undefined, t: Translate) => !code ? "" : t(...(REASON[code] ?? ["자료를 확인한 뒤 다시 시도하거나 식당 정보를 보완해 주세요.", "Try again after checking the source, or add restaurant details."]));
