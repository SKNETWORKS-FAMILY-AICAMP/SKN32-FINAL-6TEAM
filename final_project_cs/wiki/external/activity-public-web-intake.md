# Activity 공개 웹 접수 bridge — 후속 계약

담당: 독립 followup-42c9. 병합/런타임/egress 승인: rollout 9238ab26. 별도 원본·이전 candidate 쓰기와 서비스 restart 없음.

정상 호출은 인증된 trip_api background process → pipeline.read_source → places.resolve입니다. 기존 canonical/별칭/대표장소/DB/Kakao 선택을 먼저 유지하고 unresolved Activity에만 public_web evidence를 추가합니다. 웹 사실은 장소 선택 자체가 아니므로 place=null/needs_review 유지, title과 selected place 구분. Dining/lodging 및 고객이 이미 고른 장소를 웹으로 바꾸지 않습니다.

provider unknown은 source=public_web, method=public_web_supplement, reason, 실제 checked_at, facts, unknown, upstream_status/blocked를 intake_claims(method=lookup) evidence에 저장합니다. review의 기존 장소 검사줄은 미확인 reason/확인시각/검증된 공식 source_url을 소비합니다. 검색 snippet은 사실로 쓰지 않습니다. 웹 주소·시각·휴무가 검증되지 않으면 unknown 그대로 보존합니다.

외부 전송은 public_catalog 정식 이름/주소 또는 정식 이름+고정 '공식' suffix만 가능합니다. 고객 원문/식별자/일정/쿠키/키는 외부 전송하지 않습니다. 원격 x600 원장 복원과 별개입니다.

실검색은 공개 instance metadata, 운영 privacy/public terms, robots 및 HTTPS/TLS를 통과해야 합니다. HTTP429/robots 거부를 다른 인스턴스로 우회하거나 HTML 모드로 우회하지 않습니다. JSON이 공식적으로 비활성이고 robots가 허용하는 경우에만 지원되는 HTML을 별도 검토합니다. 현재 Docker executable 부재 확인; 설치/서비스 시작 없음.
