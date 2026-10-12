# 여행 규정 코퍼스(final_project_cs/knowledge/travel, 12문서 130절)를 시험용 JSON 으로 뽑는다 — 절마다 출처 id · 갈래 · 문서/절 제목 · 본문(임베딩에 쓰는 직원용 글) · 고객용 문장(있으면).
#  운영 검색(`app/infrastructure/rag/retriever.py`)은 본문을 임베딩하고, 답(`itinerary_team.question_answer`)은 고객용 문장만 싣는다 — 같은 대응을 그대로 옮긴다.
# 사용: python export_policy_chunks.py → fixtures/policy_chunks.json
import json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CS = HERE.parents[2] / 'final_project_cs'
sys.path.insert(0, str(CS))
from knowledge.ingest import load_corpus  # noqa: E402

docs = load_corpus(CS / 'knowledge' / 'travel' / 'manifest.json')
rows = []
for d in docs:
    ans = d.frontmatter.get('customer_answers') or {}
    for s in d.sections:
        line = ans.get(s.title)
        rows.append({'source': f"{d.frontmatter['document_id']}#c{s.number}", 'scope': d.frontmatter.get('scope'), 'doc_title': d.frontmatter.get('title'),
                     'section': s.title, 'content': s.content, 'line': str(line).strip() if line and str(line).strip() else None})
json.dump(rows, open(HERE / 'fixtures' / 'policy_chunks.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('절', len(rows), '· 고객용 문장 있는 절', sum(bool(r['line']) for r in rows), '· 갈래', sorted({r['scope'] for r in rows}))
print('본문 길이 평균', sum(len(r['content']) for r in rows) // len(rows))
