---
type: report
title: 기상 조립 독립 검토 결함과 최소 수정 인계
status: draft
domain: travel
---

# 기상 조립 독립 검토 후속

[정적·합성경계probe] 독립 검토는 agent 메시지에서 여행 접근검사 전에 weather provider factory가 생성되는 순서를 확인했습니다. 이는 예보 HTTP 실행·정보유출의 재현이 아닙니다. 웹은 선행 소유권검사가 있습니다. agent도 거절을 먼저 해야 합니다.

[부모 순수probe 재현] OpenMeteoWeather._pick_hour에 dict모양 time을주면AttributeError가나고 FallbackWeather의성공가능2차호출은0회였습니다. 정상1차파싱실패를None/명시미스상태로정규화하는경계가없어기존대체계약이중단됩니다. 새로운fallback정책을추가하는것이아니라기존weather-wiring/chain대체계약을지키는최소수정이필요합니다. 예외전체삼키기는금지합니다.

새child에두재현RED→권한선행/공급자모양검사→GREEN과기존302회귀를인계했습니다. 소유파일은APIagentmessage와기상adapter이며다른절의intake/confirm/notices/대화변경설명은수정하지않습니다. 기존정책의대체사용시source/fell_back_from과오류를보존합니다. 로컬수정·격리시험범위만이며실HTTP/DB/모델·앱/서비스·운영변경은없습니다. 이전302통과를두결함해소증거로쓰지않습니다.

## 관계

- [배선 부모 재검증](2026-10-24_weather-wiring-parent-checkpoint.md)
- [전체 구현 인계](../../handoff/2026-10-24_travel-writing-implementation.md)
