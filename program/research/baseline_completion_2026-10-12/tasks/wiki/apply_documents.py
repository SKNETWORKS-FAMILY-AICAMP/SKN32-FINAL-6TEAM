"""기존 본문을 새 기록으로 보존하고 현재 안내만 정리하는 일회성 작업."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import shutil

ROOT = Path(__file__).resolve().parents[5]
records = ROOT/'wiki/records/reports'
for name in ('review-policy', 'evidence-grades'):
    source = ROOT/f'wiki/governance/{name}.md'
    archive = records/f'2026-10-12_{name}-before-followup.md'
    if not archive.exists():
        archive.write_bytes(source.read_bytes())

def overwrite(path, text):
    stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S_%f_document-output')
    backup = path.parent/'_backup'/stamp/path.name
    backup.parent.mkdir(parents=True)
    shutil.copy2(path, backup)
    path.write_text(text, encoding='utf-8')


p = ROOT/'wiki/governance/review-policy.md'
raw = (records/'2026-10-12_review-policy-before-followup.md').read_text(encoding='utf-8')
raw = raw.split('## ★ [2026-09-01 추가]', 1)[0]
raw += '## 현재 정합성 점검\n'
raw += '''
마일스톤 직전에는 현재 wiki 결정·계약과 코드·제출물의 반복 사실을 대조합니다. 계약 변경 때는 인용 문서를 확인합니다. v11 등 옛 계획은 그 시점의 기록이며 현재 결정을 재승인하는 근거로 쓰지 않습니다.

| 대조 항목 | 확인 범위 |
|---|---|
| 변경 경로·기준선 링크 | 현재 wiki 정본과 실제 파일 |
| 에이전트 팀 집합·완료 기준 | 현재 결정의 적용 범위. 참고 구현과 제품을 구분 |
| 절 번호·인용 수치 | 실제 제목·정의 표·실행 기록 |
| 구현·검증·배포 상태 | 해당 변경·환경·확인 시각·근거. 미확인은 unverified |

정본 / 충돌 문서 / 판정 / 확인자 / 날짜를 기록합니다. 자동 검사 오류가 없다는 사실만으로 의미상 사양 일치·시험 통과·독립 검토 승인을 선언하지 않습니다. 이번 현재 대상은 [상태 적용 목록](implementation-inventory.generated.md)에서 자동 열거합니다.

## 병합과 과거 기록

[문서 병합 지침](../../program/research/_prompts/문서병합_지침.md)의 보완·중복·모순 분류를 따릅니다. 이미 승인된 후속 결정을 옛 문서와 다르다는 이유로 다시 승인 대기로 돌리지 않습니다. 의미가 미확정인 모순은 근거와 확인 필요 사항으로 남깁니다.

8~9월의 정본 포인터·도구·DoD 실측과 사고 사례는 [정리 전 원문](../records/reports/2026-10-12_review-policy-before-followup.md)에 보존했습니다. 과거 시점의 “현재”·미결정·집계 숫자를 오늘 지시처럼 사용하지 않습니다.

## 변경 이력

결론·수치·검토 상태·소유자가 바뀌면 저장소별 `log.md`에 기록합니다. 이번 분담의 변경·검사 결과·백업은 [후속 결과](../../program/research/baseline_completion_2026-10-12/tasks/wiki/report.md)에 연결하고 최종 통합 때 저장소 이력에 반영합니다.

## 관계

- [문서 작성 표준](document-standard.md) — 현재 규칙 먼저·근거·기록 분리
- [머리말](front-matter.md) — 문서 검토 상태와 소유자
- [상태 표시](implementation-state.md) — 결정·구현·검증·환경 구분
'''
overwrite(p, raw)

p = ROOT/'wiki/governance/evidence-grades.md'
raw = (records/'2026-10-12_evidence-grades-before-followup.md').read_text(encoding='utf-8').split('## ★ [2026-09-10] 코드 실측', 1)[0]
raw += '''## 코드·자료 실측의 범위

작업 트리에서 센 값과 `git ls-files`로 센 값을 구분합니다. 둘이 다르면 둘 다 적고 미커밋 작업이 바뀔 수 있음을 표시합니다. 검사기는 디스크에 있는 미추적 코드 참조를 별도 집계하지만 수치 주장·제품 동작을 판정하지 않습니다.

데이터 분포를 말하기 전에 표집 방법과 해당 데이터의 보고서를 확인합니다. 층화·정량 표집의 그룹 비율을 실제 서비스의 자연 분포로 일반화하지 않습니다. 코드 경로가 있다는 사실, 카탈로그 등록 수, 실행·통과 수는 서로 다른 근거입니다.

## 시점과 증거 갱신

이전 조사 원문·해시·확인일은 보존하고 현재 확인 결과를 별도로 추가합니다. 파일을 다시 읽은 시각은 그 파일 안의 실제 DB 조회·시험 시각을 대신하지 않습니다. 오래된 `completion_evidence`를 현재 완료 근거로 재사용하지 않습니다. 실행하지 않은 구현·환경은 `unverified`로 남깁니다.

8~9월 사례의 전체 원문은 [정리 전 기록](../records/reports/2026-10-12_evidence-grades-before-followup.md)에 보존했습니다. 당시의 비용·집계·도구 상태는 현재 측정값이 아닙니다.

## 관계

- [머리말 규격](front-matter.md) — sources와 상태 필드
- [문서 표준](document-standard.md) — 주장과 근거 연결
- [상태 표시](implementation-state.md) — 환경·확인 시각·증거
'''
overwrite(p, raw)
