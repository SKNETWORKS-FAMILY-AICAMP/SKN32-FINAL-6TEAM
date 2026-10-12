# AI Hub 「주제별 텍스트 일상 대화」(카카오·페이스북·인스타·밴드·네이트온) 라벨링 zip 을 풀지 않고 읽어 짧은 채팅 문장 풀을 만든다.
#  용도: ① 앞단(학습 임베딩) 학습의 「정답 없음」 잡담 표본 ② 말투 증강(끝말·줄임·붙여쓰기 패턴)의 실제 빈도.  여행 이야기가 아니라 **말투와 잡담**의 출처다.
#  처리: 라벨링 JSON 의 annotations.text 가 「번호 : 문장」 줄들 — 한글이 있는 3~60자 문장만, 같은 문장은 한 번, 전화번호·이메일·URL 이 든 줄은 버린다.
# 사용: python build_chat_pool.py → datasets/travel/020.주제별 텍스트 일상 대화 데이터/processed/chat_utterances.jsonl + chat_stats.json
import collections, glob, json, os, re, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', '020.주제별 텍스트 일상 대화 데이터')
OUT = os.path.join(ROOT, 'processed')
os.makedirs(OUT, exist_ok=True)
LINE = re.compile(r'^\s*\d+\s*:\s*(.+?)\s*$')
BAD = re.compile(r'(\d{2,4}[- ]?\d{3,4}[- ]?\d{4})|@\w+\.|https?://|www\.|#@|\*{2,}')
HANGUL = re.compile(r'[가-힣]')
seen, rows = set(), []
src_count = collections.Counter()
for zp in sorted(glob.glob(os.path.join(ROOT, '01.데이터', '*', '라벨링데이터*', '*.zip'))):
    tag = os.path.basename(zp).split('.')[0] + '_' + os.path.basename(zp).split('. ')[1][:8]
    z = zipfile.ZipFile(zp)
    for n in z.namelist():
        if not n.endswith('.json'):
            continue
        try:
            d = json.loads(z.read(n).decode('utf-8'))
            info = d['info'][0]['annotations']
        except Exception:  # noqa: BLE001
            continue
        subj = info.get('subject', '')
        for ln in str(info.get('text', '')).split('\n'):
            m = LINE.match(ln)
            if not m:
                continue
            t = m.group(1).strip()
            if not (3 <= len(t) <= 60) or not HANGUL.search(t) or BAD.search(t) or t in seen:
                continue
            seen.add(t)
            rows.append({'t': t, 'src': tag, 'subject': subj})
            src_count[tag] += 1
with open(os.path.join(OUT, 'chat_utterances.jsonl'), 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
# 말투 통계: 끝 두 글자 · ㅋ/ㅠ 비율 · 띄어쓰기 없는 비율
end = collections.Counter(r['t'][-2:] for r in rows)
stats = {'문장 수': len(rows), '출처별': dict(src_count), 'ㅋ 포함': sum('ㅋ' in r['t'] for r in rows) / len(rows), 'ㅠㅜ 포함': sum(('ㅠ' in r['t'] or 'ㅜ' in r['t']) for r in rows) / len(rows),
         '공백 없음': sum(' ' not in r['t'] for r in rows) / len(rows), '길이 중앙값': sorted(len(r['t']) for r in rows)[len(rows) // 2], '끝 두 글자 상위 30': end.most_common(30)}
json.dump(stats, open(os.path.join(OUT, 'chat_stats.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in stats.items() if k != '끝 두 글자 상위 30'}, ensure_ascii=False))
print(stats['끝 두 글자 상위 30'][:20])
