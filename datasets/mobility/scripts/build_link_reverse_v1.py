# datasets/mobility/scripts/build_link_reverse_v1.py — 전국 표준 노드·링크에서 링크마다 반대 방향 링크를 찾는다 (2026-10-14)
#
# 왜: 도로 사건(경찰청 UTIC)의 원문은 한 방향 구간 번호만 싣는다. 「양방향 통제」 사건이 반대쪽으로 가는 경로에 걸리는지,
#     또 서울 실경보 재현에서 반대 방향 시험을 만들려면 그 구간의 반대 방향 번호가 필요하다. 기존 OSM↔TOPIS 대응표로는 20건 중 16건이 비었다.
# 규칙(자료 그대로 — 추정 없음):
#   · 링크 A 의 반대 방향 = 시작 노드·끝 노드가 A 와 뒤바뀐 링크(F_NODE=A.T_NODE · T_NODE=A.F_NODE).
#   · 그런 링크가 0개면 반대 방향 없음(일방통행 등), 2개 이상이면 모호 — 둘 다 기록하고 고르지 않는다.
# 입력: raw/its_nodelink_20261014_v1/extract/MOCT_LINK.dbf (국가교통정보센터 전국표준노드링크, 2026-10-14판)
# 출력: processed/mobility/link_reverse_v1/link_reverse.csv.gz · MANIFEST.json (기존 폴더를 덮지 않는다)
import argparse, csv, gzip, hashlib, io, json, struct, datetime as dt
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def dbf_rows(path, want):
    with open(path, 'rb') as f:
        h = f.read(32)
        n, hl, rl = struct.unpack('<IHH', h[4:12])
        fields = []
        while True:
            d = f.read(32)
            if d[0] == 0x0D:
                break
            fields.append((d[:11].split(b'\0')[0].decode('ascii'), d[16]))
        f.seek(hl)
        idx, pos = {}, 1
        for name, ln in fields:
            idx[name] = (pos, pos + ln)
            pos += ln
        for _ in range(n):
            r = f.read(rl)
            if not r or r[:1] == b'*':          # 지운 행
                continue
            yield {k: r[idx[k][0]:idx[k][1]].decode('cp949', 'replace').strip() for k in want}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=str(ROOT / 'datasets/mobility/raw/its_nodelink_20261014_v1/extract/MOCT_LINK.dbf'))
    ap.add_argument('--out', default=str(ROOT / 'datasets/mobility/processed/mobility/link_reverse_v1'))
    a = ap.parse_args()
    out = Path(a.out)
    if (out / 'link_reverse.csv.gz').exists():
        raise SystemExit(f'이미 있다 — 덮지 않는다: {out}')
    out.mkdir(parents=True, exist_ok=True)
    links, by_ft = [], defaultdict(list)
    for r in dbf_rows(a.src, ('LINK_ID', 'F_NODE', 'T_NODE', 'ROAD_NAME', 'ROAD_RANK')):
        links.append(r)
        by_ft[(r['F_NODE'], r['T_NODE'])].append(r['LINK_ID'])
    stat = {'links': len(links), 'one_reverse': 0, 'no_reverse': 0, 'ambiguous_reverse': 0}
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=buf, mode='wb', mtime=0) as gz:
        w = io.TextIOWrapper(gz, encoding='utf-8', newline='')
        cw = csv.writer(w)
        cw.writerow(['link_id', 'reverse_link_ids', 'f_node', 't_node', 'road_name', 'road_rank'])
        for r in links:
            rev = [x for x in by_ft.get((r['T_NODE'], r['F_NODE']), []) if x != r['LINK_ID']]
            stat['one_reverse' if len(rev) == 1 else 'no_reverse' if not rev else 'ambiguous_reverse'] += 1
            cw.writerow([r['LINK_ID'], ' '.join(rev), r['F_NODE'], r['T_NODE'], r['ROAD_NAME'], r['ROAD_RANK']])
        w.flush()
    (out / 'link_reverse.csv.gz').write_bytes(buf.getvalue())
    src = Path(a.src)
    man = {'version': 'link_reverse_v1', 'built_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds'),
           'builder': 'datasets/mobility/scripts/build_link_reverse_v1.py',
           'source': '국가교통정보센터 전국표준노드링크 NODELINKDATA.zip (2026-10-14판) MOCT_LINK',
           'source_url': 'https://www.its.go.kr/nodelink/nodelinkRef',
           'input_sha256': hashlib.sha256(src.read_bytes()).hexdigest(), 'counts': stat,
           'rule': '반대 방향 = 시작·끝 노드가 뒤바뀐 링크. 0개 없음 · 2개 이상 모호(고르지 않음)',
           'files': {'link_reverse.csv.gz': {'md5': hashlib.md5(buf.getvalue()).hexdigest(), 'rows': len(links)}}}
    (out / 'MANIFEST.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(stat, ensure_ascii=False))


if __name__ == '__main__':
    main()
