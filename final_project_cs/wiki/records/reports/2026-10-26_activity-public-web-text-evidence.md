# 2026-10-26 Activity 공개 웹 보조조회 — 공식 본문 근거 · redirect · http (pubweb2)

## 결론

- 사용자 결정(08:20) 두 규칙을 코드·wiki 계약으로 넓혔다. 모두 **설정으로 켜는 방식이며 기본 꺼짐**.
- 관광공사 운영시간이 있는 서울 20곳 실측(최종 4회차): **일치 0/20 = 0% · 오답 0/20 = 0% · 미확인 20/20 = 100%**. 켜는 기준(일치 ≥ 80% · 오답 ≤ 5%) 미달 → x600 켜는 설정안은 만들지 않았고 `official_*`는 꺼 둔다.
- 안전장치는 작동했다: 중간 회차에서 나온 오답 1건(뮤지엄한미 날짜 공지 「관람시간 단축 안내」 10:00~17:00)과 위험 1건(박을복 「오전 10시 ~ 4시」)을 회귀 시험으로 고정하고 막았다.
- 로컬 커밋 `feb24fa90332a588e71942f6d9c1b714017c5226`(기준 role-manager `a465c6022`), patch sha256 `b28e23d510bd4300cb7d568c53acbc63200b235ec694836e3b6798f346230e3e`. push 안 함. x600 · 로컬 serving 변경 없음.

## 계약 변경 (`final_project_cs/wiki/external/activity-public-web.md`)

- `travel.activity_public_web.official_text` / `official_http` / `official_max_redirects` (guardrails, 기본 false/false/0).
- 공식 읽기만: http GET(쿠키 없음, 공인 IP 고정), 공식 host와 그 하위 host 안 redirect N회(hop마다 재검사·예산), 상위·형제 host는 등록해야 허용, query 허용, robots 404/410 허용(RFC 9309), charset UTF-8/EUC-KR(CP949)만. 검색 요청·기본 설정은 그대로.
- 읽는 순서: 검토된 `homepage` → ddgs 공식 URL → 공식 페이지 안 안내 링크, `max_pages`까지. 검색 실패도 `search_failure`.
- 규칙 파서 `official_hours_text`(모델 없음), 인용 서버 위치 검증(`quote_unverified`), 본문에 identity 이름 필수, 한 공식 페이지라도 시간을 못 읽으면 장소 전체 미확인(`ambiguous_hours`), 페이지 간 충돌은 `conflicting_sources`.
- 사실 모양: `source_kind`(official_homepage) · `source_url`(redirect 뒤 최종) · `scheme` · `quotes[{quote, offset}]` · `evidence=text` · `checked_at` · `confidence=official_text` · `body_sha256`.
- 고객 문장(`review`): 「카카오에서 확인되지 않음 · 장소는 아직 확정하지 않았어요 · 공식 홈페이지 기준 운영시간 … (확인 시각 …, 출처 …) · 방문일 운영 여부는 확정하지 않았어요」. 카카오가 막힌 경우는 「카카오 조회가 막혀 확인되지 않음」.
- 출처 우선순위 체인(부모 추가 지시): 관광공사 → 카카오(장소 확인만) → 구글 Places(New) `regularOpeningHours`(키 있을 때만, 연결은 TODO) → 공식 홈페이지 웹. 네이버 지역검색 API는 영업시간 필드가 없어서, 네이버 플레이스 스크래핑은 약관 문제로 쓰지 않는다. TMAP POI는 검증하지 않아 쓰지 않는다.

## 추출 방식 (Codex CLI `codex exec --skip-git-repo-check`, 본문만 보는 검토)

- **규칙 파서만 쓰고 E4B는 쓰지 않는다**. 모델이 뽑은 값도 같은 파서로 다시 확인해야 하므로 읽을 수 있는 형태가 늘지 않는다. 그래서 지연·lease 비용만 생긴다고 봤다. 이번 작업의 E4B 호출은 0이다.
- Codex 반영: 자동 public-suffix/상위 host 허용 대신 하위 host와 등록된 host만, 요일 없는 시간을 모든 요일로 넓히지 않음, homepage 우선 + 안내 링크 탐색, robots 404 허용·5xx 중단.
- Codex 지적(H): 관광공사를 정답으로 두는 평가는 「예비 평가」 수준이다. 공식 사이트가 더 최신일 수 있다(박을복: 공식 「평일 10시-16시」, 관광공사 13:00~17:00).

## 정확도 표 (최종 run4, `acc/run4.jsonl`, 채점 `acc/score.py`)

| # | 장소 | 공식 host | 결과 | 사유 |
|---|---|---|---|---|
| 1 | 뚝섬한강공원 | hangang.seoul.go.kr | 미확인 | extract_body_too_large(1MB 제한) |
| 2 | 강동예찬시비 | www.gangdong.go.kr | 미확인 | robots_blocked |
| 3 | 노원평생학습관 | nwllc.sen.go.kr | 미확인 | robots_blocked |
| 4 | 국립4·19민주묘지 | www.mpva.go.kr | 미확인 | ambiguous_hours(하절기/동절기) |
| 5 | 서울대병원 의학박물관 | medicalmuseum.org | 미확인 | http_500 |
| 6 | 구로아트밸리 예술극장 | www.guroartsvalley.or.kr | 미확인 | 홈 본문에 시간 없음 + search_no_results |
| 7 | 관악산자연공원 | parks.seoul.go.kr | 미확인 | http_404 |
| 8 | 한강방어 백골부대 전적비 | www.ydp.go.kr | 미확인 | 공식 2쪽 시간 없음 |
| 9 | 원당마을한옥도서관 | www.unilib.dobong.kr | 미확인 | identity_unverified |
| 10 | JCC재능문화센터 | www.jeijcc.org | 미확인 | transport_or_body_error |
| 11 | 나루아트센터 | www.naruart.or.kr | 미확인 | 2쪽 시간 없음 + search_no_results |
| 12 | 신당동 박정희 가옥 | www.heritage.go.kr | 미확인 | identity_unverified |
| 13 | 갤러리 비앤에스 | gallerybns.com | 미확인 | 시간 없음 + search_no_results |
| 14 | 어둠속의대화 북촌점 | www.dialogueinthedark.co.kr | 미확인 | identity_unverified |
| 15 | 뮤지엄한미 삼청 | museumhanmi.or.kr | 미확인 | ambiguous_hours(날짜 공지) — run1~3 오답 |
| 16 | 영산양재홀 | www.youngsanhall.co.kr | 미확인 | 5쪽 시간 없음 |
| 17 | 한국광고박물관 | www.kobaco.co.kr | 미확인 | robots_blocked |
| 18 | 박을복자수박물관 | embromuseum.com | 미확인 | ambiguous_hours(오전 10시 ~ 4시 · 범위 혼재) |
| 19 | 더클라임 홍대B점 | theclimb.co.kr | 미확인 | identity_unverified(지점 다수) |
| 20 | 한생연융합교육과학관 | www.hlsi.co.kr | 미확인 | identity_unverified |

회차별: run1 0/1/19 · run2 0/1/19 · run3 0/1/19 · run4 0/0/20 (일치/오답/미확인). 마지막 오답 1건은 날짜 공지 회귀 수정으로 막았다.
표본: `activity.ac_place`(로컬 acop_cs 읽기 전용, `dbc.connect`) 중 `hours_week`·`hours_read`가 있고 서울이며 관광공사 CSV에 플랫폼이 아닌 homepage가 있는 836곳에서 시드 20261026으로 섞어 host가 겹치지 않게 20곳을 골랐다. 정답 = `hours_read` 인용과 `usetime_text`의 시간 범위, `restdate_text`의 매주 휴무 요일.
**검색 상태**: ddgs(duckduckgo)는 20곳 중 대부분이 `search_no_results`였고, 결과가 나온 곳은 4~5곳(약 8초 간격)이다. 차단 응답은 없었으나 결과가 고르게 나오지 않았다. 미확인의 주된 원인은 검색이 아니라 공식 사이트 쪽이다: robots 차단 3, HTTP 오류 3, 본문 1MB 초과 1, JS 렌더링·이름 불일치 6, 공식 페이지에 시간 없음 다수.

## 관문

- RED: 새 시험 24 failed/2 passed(기준 코드), 날짜 공지·역순 시각 2 RED, 출처 표시 1 RED, 페이지 하나 모호 2 RED. 모두 GREEN.
- 공개 웹 4파일 100/100 통과.
- 빠른 관문(격리 runner, venv `date_risk_env_312`, `-p pytest_asyncio.plugin`, 9 shard): **XML 10018건 · 실패 0 · 오류 0 · skip 173**. 새 시험 32 node가 XML에 있다. 관문 tree `a160a365` = 커밋 tree.
- ruff: 바뀐 app/test 파일 All checks passed.
- 중간 관문 한 번에서 보안 시험 `test_no_infra_in_tracked_files`가 주석 「2.3.1.3」을 IP로 오인해 실패했다. 문구를 고쳐 최종 관문은 0 실패다.

## 켜기 권고

- **x600: 켜지 않는다.** 기준 미달이다(일치 0%). 오답은 0%이므로 켜도 틀린 시간을 말하지는 않고 「미확인」만 늘어난다. 실익이 없다.
- 로컬 live 켜기안 갱신: `cache/scratch/pubweb2-20261026-082147/local-live-proposal/activity_public_web.local.yaml`(official_* 꺼짐, 수치 주석). 적용은 하지 않았다.
- 일치율을 높일 경로는 구글 Places `regularOpeningHours`(키만 있으면 됨)다. 공식 웹 경로는 대부분 JS 렌더링·robots·이름 표기 차이 때문에 막혀 있어, 규칙을 더 넓혀도 큰 개선은 어렵다고 판단한다.

## 증거 위치

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pubweb2-20261026-082147/` — `rm`(worktree, HEAD feb24fa9), `pubweb2-text-evidence.patch`, `ev/`(red*.log · green*.xml · fast-final/ · ruff.log), `acc/`(sample20.json · run1~4.jsonl · score.py), `codex-q1.md`/`codex-a1.md`, `COMMIT_MSG.txt`.
