# datasets/mobility/scripts/graph_03a_convert_xlsx.py — 택시·자동차 소요의 도로 구간별 시간대 속도(graph/ 5파일) 만들기 ③a · 달마다 `python … YYYYMM`
#   원래 이름 03a_convert_xlsx.py · 원래 자리 DATA_DIR\travel\processed\mobility\graph\_build\ (2026-09-19 · 9/30 저장소 사본 · 82 에서 이 자리로)
#   ★ **작업 폴더를 cwd 로 두고** 실행한다 — 입력·중간 산출을 전부 cwd 상대경로로 읽고 쓴다(원래 방식 그대로 · 코드 무변경):
#       cd <DATA_DIR>\travel\processed\mobility\graph\_build ;  python <저장소>\datasets\mobility\scripts\graph_03a_convert_xlsx.py
#   입력(cwd 기준): raw/topis/topis_speed_daily_YYYYMM.xlsx   →   출력(cwd): speed/topis_YYYYMM.npz
#   순서·결과를 판정기 자리로 옮기는 법은 README 「갱신 순서」.
"""TOPIS 월별 xlsx → 압축 npz (link_id str, date int yyyymmdd, dist, cls, v[24] float32). 실행: python step3a_convert.py YYYYMM"""
import sys, time, numpy as np, openpyxl
ym=sys.argv[1]; t0=time.time()
ws=openpyxl.load_workbook(f'raw/topis/topis_speed_daily_{ym}.xlsx',read_only=True).worksheets[0]
H=['일자','요일','도로명','링크아이디','시점명','종점명','방향','거리','차선수','기능유형구분','도심/외곽구분','권역구분']+[f'~{h:02d}시' for h in range(1,25)]
links=[];dates=[];dist=[];cls=[];V=[]
for i,row in enumerate(ws.iter_rows(values_only=True)):
    if i==0:
        assert list(row)==H, row; continue
    links.append(str(row[3])); dates.append(int(str(row[0]).replace('-','')[:8])); dist.append(float(row[7])); cls.append(row[9])
    V.append([np.nan if v in (None,'') else float(v) for v in row[12:36]])
np.savez_compressed(f'speed/topis_{ym}.npz',link=np.array(links),date=np.array(dates,dtype=np.int32),dist=np.array(dist,dtype=np.float32),cls=np.array(cls),v=np.array(V,dtype=np.float32))
print(ym,'rows',len(links),'sec',round(time.time()-t0),flush=True)
