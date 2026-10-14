"""Download the public sources cited in the baseline research; no paid book text."""
from pathlib import Path
import concurrent.futures, datetime, hashlib, json, shutil, urllib.request

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'sources'
SOURCES = [
 ('S01','swebok-v4.pdf','https://ieeecs-media.computer.org/media/education/swebok/swebok-v4.pdf','IEEE Computer Society SWEBOK','공개 PDF 전문'),
 ('S02','sei-1991-cm-models.pdf','https://www.sei.cmu.edu/documents/1022/1991_005_001_645586.pdf','SEI Configuration Management Models in Commercial Environments','공개 PDF 전문'),
 ('S03','usaf-history-2002.pdf','https://www.govinfo.gov/content/pkg/GOVPUB-D301-PURL-LPS48767/pdf/GOVPUB-D301-PURL-LPS48767.pdf','US Air Force Culture of Innovation 1945–1965','공개 PDF 전문'),
 ('S04','scm-patterns-publisher.html','https://www.informit.com/store/software-configuration-management-patterns-effective-9780201741179','SCM Patterns publisher page','공개 소개·목차·서문 페이지. 유료 책 전문 아님'),
 ('S05','github-flow.html','https://docs.github.com/en/get-started/using-github/github-flow','GitHub flow','공개 웹 본문'),
 ('S06','dora-version-control.html','https://dora.dev/capabilities/version-control/','DORA Version control','공개 웹 본문'),
 ('S07','dora-continuous-integration.html','https://dora.dev/capabilities/continuous-integration/','DORA Continuous integration','공개 웹 본문'),
 ('S08','google-rules-of-ml.html','https://developers.google.com/machine-learning/guides/rules-of-ml','Google Rules of Machine Learning','공개 웹 본문'),
 ('S09','git-tagging.html','https://git-scm.com/book/en/v2/Git-Basics-Tagging','Pro Git Tagging','공개 웹 본문'),
 ('S10','nasa-technical-management.html','https://www.nasa.gov/reference/6-0-crosscutting-technical-management/','NASA Crosscutting Technical Management','공개 웹 본문'),
 ('S11','fowler-continuous-integration.html','https://martinfowler.com/articles/continuousIntegration.html','Martin Fowler Continuous Integration','추가 참고 공개 웹 본문'),
]

def fetch(item):
    sid, filename, url, title, scope = item
    record = dict(id=sid, file='sources/'+filename, url=url, title=title, scope=scope)
    target=DEST/filename
    try:
        if target.exists():
            backup=ROOT/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_download')/'sources'
            backup.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,backup/filename)
        # Reuse the complete official history PDF already fetched in this chat.
        prior=Path(r'C:\Users\PLAYDA~1\AppData\Local\Temp\baseline-research-syulhr9o\usaf-history.pdf')
        if sid=='S03' and prior.exists() and prior.stat().st_size==34414226:
            data=prior.read_bytes()
            record['download_origin']='이 대화에서 앞서 같은 공식 URL로 받은 완전한 PDF 복사'
        else:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; research-archive)'})
            with urllib.request.urlopen(req, timeout=45) as res:
                data=res.read()
                record['resolved_url']=res.url
                record['content_type']=res.headers.get('Content-Type','')
        if filename.endswith('.pdf') and not data.startswith(b'%PDF-'):
            raise ValueError('Response is not a PDF')
        if filename.endswith('.html') and b'<html' not in data[:10000].lower():
            raise ValueError('Response is not HTML')
        target.write_bytes(data)
        record.update(status='downloaded',bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        if filename.endswith('.pdf'):
            from pypdf import PdfReader
            record['pdf_pages']=len(PdfReader(target).pages)
    except Exception as exc:
        record.update(status='failed',error=str(exc))
    print(sid,record['status'],record.get('bytes',record.get('error')),flush=True)
    return record

if __name__=='__main__':
    DEST.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        records=list(pool.map(fetch,SOURCES))
    out=ROOT/'source-manifest.json'
    if out.exists():
        backup=ROOT/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_download')
        backup.mkdir(parents=True,exist_ok=True); shutil.copy2(out,backup/out.name)
    out.write_text(json.dumps({'retrieved_date_kst':'2026-10-10','sources':records},ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESULT',sum(r['status']=='downloaded' for r in records),'/',len(records),flush=True)
