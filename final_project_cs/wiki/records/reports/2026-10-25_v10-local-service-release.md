# V10 로컬·LAN 실서비스 반영 결과

## 결론

승인된 pin `325ba25d88c91ce97da61f2bda635e5888fe3b40` 후보의 V10과 좌표 guard를 **현재 localhost·LAN API에 반영하고 기동·재조회했습니다.** 기존 프론트 artifact는 재빌드하지 않았습니다. 전체 제품/의미 품질/reader 등록의 완료 선언은 아닙니다.

| 수용 범위 | 실측 결과 |
|---|---|
| 실서비스 | `proc_194b6e03a438`, 부모 `handed_off`; listener PID27500, start `2026-10-25T02:47:13.4929830Z`, parent19504 |
| 주소 | 웹 `http://127.0.0.1:3100`, `http://192.168.0.15:3100`; API 양쪽 `:8042` |
| 코드 실체 | serving candidate `skn-develop-step1-20261025-014848/candidate/final_project_cs`; 6개 제품 모듈(좌표 guard 포함) startup/disk/실제 loaded-module SHA 모두 일치, V10 시험파일도 accepted SHA 일치 |
| 모델/tokenizer | E4B `tripilot-pointer:e4b-ft`, digest `ef0a580aca375aa9bf4547558b9b41910e5f85769b5ad3e9e99ee13af71a1025`, Ollama0.31.1, ctx8192. 실제 tags/version 확인·manifest/metadata SHA·native tokenizer/cl100k 로딩 성공 |
| runtime 준비 | isolated service Python, `pip check` exit0, 실제 앱 assembly 및 15개 runtime/helper/tokenizer/source/cache 입력 SHA startup 검사. 무음 fallback 없음 |
| HTTP | localhost/LAN health200·미인증 auth401·legal/retention200·features200·support/notices200: 10/10=100%. credential CORS 포함. 허용/거부 origin OPTIONS 4/4=100% |
| 실제 브라우저 | Edge, 양쪽 초기 미동의/검증 guest 4/4=100% GET-only 재검증. reload·홈 왕복·계획 입력 UI 유지. JS pageerror0·연결경고0·업무 POST0 |
| 승인된 새 guest 동의 | 보존 세션이 없어 새 격리 guest를 origin별 1개 생성. 필수2 true/선택4 false, 각 6/6=100% DB readback, guest 여행0. 최종 재시작 후에는 해당 세션을 GET-only로 재사용 |
| 동일 반례 재생 | **실제 결과행2, 턴2, 모델 chat2**. `--limit 0`은 정확2개 case filter 후 cap없음을 뜻함(0사례/전체코퍼스 아님). normal route TestClient와 실제 HTTP E4B 사용, 비교DB만 쓰기. 기존 Harness는 합성 시험계정에 web.dev_mode on/limits off를 적용하므로 실서비스 인증·제한 전체의 모델 E2E와 같다고 주장하지 않음 |
| 반례 결과 | answered/decision_answer_fact 2/2=100%, 실제 terminal stop2/2=100%. prompt/output 6856/382, 6954/377. 별도 read-only DB에서 답변 원문·customer/assistant log·Case exact context/degraded/omissions readback2/2=100%, TripView/버전 변경0 |
| 보호 countertest | 기존13/13=100% + 보완6/6=100%: paid/외부/raw socket·다른 모델/ctx/operation·DB host/port/db/role/service/hostaddr·source write·실공지 caller·tools/images/assistant/think 차단 |
| 이전 단위 근거 | accepted 단일 JUnit179/179=100%와 execution exit0/전후hash를 다시 파싱·현재 source/test hash 일치 검산. 이 절에서 179개를 새로 실행한 것으로 표현하지 않음 |

## 소유 교체·동작 경계

이전 API PID20768의 정확 startidentity `2026-10-24T20:20:50.2931610Z`·parent5020·launcher·8042 listener ownership을 확인한 뒤 **그 PID만** 종료했습니다. 먼저 준비한 V10 launcher는 실제 기동·HTTP·브라우저·guest DB 저장을 통과했고, loaded-module 증거를 더 엄격히 남기기 위해 그 소유 PID28536도 정확 identity 확인 후 종료했습니다. 최종 고유 `launch-final.py`는 decision/context 모듈을 사전 import하여 실제 provenance를 기록하며 SHA 입력 검사를 추가했습니다. 둘 다 제품/원본 env 변경 없이 같은 source와 policy를 사용합니다.

최종 launcher SHA256: `f9c4f76eeb601e80a2b734593197a382dfdc4c3b28522e3024b12961b18521c2`.
policy SHA256: `303f43fc383e1f6463e7bfb81d6c2e113111e81325f12bb91eb7622f17d56c85`.

shared DB는 `127.0.0.1:5433/acop_cs`, role `guguroute_app` non-superuser, datadir `C:/_proj/postgresql/data/guguroute-16`, system ID `7700321712607772424`을 실제 read-only 확인했습니다. private `C:/_proj/postgresql/run/private/app.env`를 그대로 읽고 원본 `.env/.env.apikeys` precedence를 보존했습니다. source cluster 중지 유지, SQL migration/restore0. 실서버는 비교 DB를 허용하지 않습니다. 비교 runner는 반대로 비교 role/db만 허용합니다.

네트워크는 정확 shared DB 및 승인 loopback11434 metadata/chat만 허용합니다. chat은 model/ctx/지원 text renderer와 실제 caller 경계를 검사하며 프로세스 내 동시1을 적용합니다. paid/외부 원문/실알림/별도 worker는 기동하지 않았습니다. serving model chat0, 비교 재생chat2, 아래 잘못된 보완 시험의 최소 synthetic chat1을 분리 기록합니다. 관측 프로세스 목록에 경쟁 모델 replay child가 없었고, 모델 요청은 순차였습니다. 전역 다중 프로세스 모델 mutex를 구현했다고 주장하지 않습니다.

## 보존한 시험·관측 문제

- 첫 HTTP probe의 `/v1/web/legal`, `/v1/web/notices`는 잘못 적은 URL이라404였습니다. 실제 route 목록의 `/legal/retention`, `/support/notices`로 고쳐 양쪽200을 확인했고 최초 파일도 남겼습니다. 제품 결함으로 세지 않았습니다.
- 첫 provenance 검산은 Windows `\\` 키를 `/`로 정규화하지 않아 startup lookup이 false였습니다. 동시에 lazy decision/context가 당시 import 전임을 확인했습니다. 정규화 및 최종 launcher의 명시 import 후, 최종 실제 프로세스에서 6모듈 SHA를 모두 확인했습니다.
- 보완 notice countertest의 첫 harness는 실제 경로 대신 bare filename을 compile filename으로 썼습니다. 실제 module suffix 경계를 재현하지 못해 **최소 synthetic E4B chat1이 실제 허용·완료**됐습니다(`counter-supplement/policy-counters.json`: admitted1/completed1). private 고객 글/유료/외부 전송은 없으며 이것을 차단 통과로 승격하지 않습니다. 절대경로 형태의 동일 caller countertest로 고친 뒤 실공지2+지원범위4 전부 dispatch 전 차단했습니다. 이 때문에 이번 절 전체 실제 로컬 chat은 2+1=3이며, 역사 반례 재생 성공분모는 오직2입니다.
- 브라우저 connection 종료 때 서버 로그에 WinError10054 reset가 관측됐습니다. 후속 실제 API/브라우저 요청은 정상이며 지속 장애로 확인되지는 않았습니다.

## 유지·rollback·남은 범위

서비스를 살려 부모에 인계했습니다. `HANDOFF.json`과 `service-identity.json`에 handle/PID/startidentity/cwd/URL/launcher/codehash/비밀없는 envmetadata가 있습니다. 예전 `cs-api-target-20261025/launch.py`를 rollback launcher로 보존했습니다. rollback도 먼저 현재 PID/start/command를 확인한 뒤 소유 프로세스만 종료해야 하며, 예전 launcher는 의도적으로11434를 차단한다는 제한이 있습니다. 자동 복구/상시 재시작 등록은 하지 않았습니다.

이 배포는 scratch 의존입니다. `dependency-paths.json`, `runtime-inputs.json`의 isolated Python/base runtime, candidate source, 공개 tokenizer manifest+metadata, cl100k cache, mobility datasets, private env 경로를 유지해야 합니다. ZIP은 안전한 코드/공개자산/증거 보존용이며 전체 runtime/데이터/비밀 env를 포함한 독립 설치본이 아닙니다. 의존파일 소실·SHA drift 때 거부하며 다른 모델/DB로 fallback하지 않습니다.

shared schema905 reader readiness 및 archives 차이는 그대로입니다. reader 등록 쓰기가 되게 shared schema를 바꾸지 않았습니다. 제목/장소 의미불일치2·unknown238/blocked344(분모582), 공개 chat reload의 내부 accounting/degraded projection, 전체 업무·외부 실알림·다른 기기 직접LAN접속은 미수용입니다. 새 명확 제품결함을 닫았다고 보고하지 않습니다. 원본 제품코드/환경 역복사·커밋·푸시·원격배포0입니다.
