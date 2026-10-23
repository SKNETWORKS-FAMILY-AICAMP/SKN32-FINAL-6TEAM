"""guguroute product film. Deterministic local graphics and original synthesized score.

Run: python -X utf8 render_demo.py [--preview]
Existing generated artifacts are copied to _backup before replacement.
Customer screens are explanatory reconstructions, admin captures are untouched crops.
"""
from pathlib import Path
from functools import lru_cache
from datetime import datetime
import math, shutil, subprocess, sys, wave, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = next(p for p in HERE.parents if (p / 'final_project_cs').is_dir())
S = 1.5
W, H = 1920, 1080
FPS, DURATION = 30, 53
PAPER, INK, MUTED = '#fbfcfd', '#161c28', '#6b7488'
BLUE, GOLD, LINE = '#2f5bd8', '#a8720c', '#dbe0ea'
NAVY, PALE, GOLDPALE = '#141821', '#edf2fd', '#fbf3e2'
WHITE = '#ffffff'
REG = 'C:/Windows/Fonts/malgun.ttf'
BOLD = 'C:/Windows/Fonts/malgunbd.ttf'
FFMPEG = shutil.which('ffmpeg')
SCENES = [(0,4,'여행의 변수'),(4,9,'여섯 가지 감시'),(9,19,'예보와 일정'),
          (19,25,'알림의 역할'),(25,33,'감시 현황과 로그'),
          (33,39,'API 한도'),(39,48,'재난 시뮬레이션'),(48,53,'guguroute')]

def backup(path):
    if path.exists():
        folder = OUT / '_backup' / (datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_영상재생성전')
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, folder / path.name)

def save_image(im, path):
    backup(path); im.save(path)

def clamp(v): return max(0., min(1., v))
def ease(v):
    v=clamp(v); return 1-(1-v)**3
def smooth(v):
    v=clamp(v); return v*v*(3-2*v)
def q(v): return int(round(v*S))
def box(bounds): return tuple(q(v) for v in bounds)
def canvas(color=PAPER): return Image.new('RGBA',(W,H),color)

@lru_cache(maxsize=80)
def font(size,bold=False): return ImageFont.truetype(BOLD if bold else REG,q(size))

@lru_cache(maxsize=500)
def glyph(value,size,color,bold):
    f=font(size,bold)
    b=f.getbbox(value)
    im=Image.new('RGBA',(b[2]-b[0]+6,b[3]-b[1]+6))
    ImageDraw.Draw(im).text((3-b[0],3-b[1]),value,font=f,fill=color)
    return im

def txt(im,value,x,y,size=24,color=INK,bold=False,alpha=1,anchor='left'):
    g=glyph(str(value),size,color,bold)
    px=q(x)-(g.width//2 if anchor=='center' else g.width if anchor=='right' else 0)
    if alpha<1:
        g=g.copy();g.putalpha(g.getchannel('A').point(lambda a:int(a*clamp(alpha))))
    im.alpha_composite(g,(px,q(y)))

def rect(im,x,y,w,h,fill=WHITE,stroke=None,r=12,width=1):
    ImageDraw.Draw(im).rounded_rectangle(box((x,y,x+w,y+h)),radius=q(r),fill=fill,outline=stroke,width=q(width))
def line(im,pts,color=LINE,width=2):
    ImageDraw.Draw(im).line([(q(x),q(y)) for x,y in pts],fill=color,width=q(width),joint='curve')
def circle(im,x,y,r,fill=None,stroke=None,width=2):
    ImageDraw.Draw(im).ellipse(box((x-r,y-r,x+r,y+r)),fill=fill,outline=stroke,width=q(width))

def pill(im,label,x,y,fill=PALE,color=BLUE,size=15):
    width=glyph(label,size,color,True).width/S+28
    rect(im,x,y,width,32,fill,r=16)
    txt(im,label,x+14,y+7,size,color,True)
    return width

def heading(im,number,lines,sub=None):
    pill(im,number,64,124)
    for i,s in enumerate(lines): txt(im,s,64,184+i*64,48,INK,True)
    if sub:
        for i,s in enumerate(sub): txt(im,s,66,348+i*31,20,MUTED)

def pop(im,layer,x,y,progress):
    p=ease(progress)
    if p<=0: return
    layer=layer.copy()
    if p<1: layer.putalpha(layer.getchannel('A').point(lambda a:int(a*p)))
    im.alpha_composite(layer,(q(x),q(y+24*(1-p))))

def check(im,x,y,color=BLUE,scale=1):
    line(im,[(x,y+7*scale),(x+7*scale,y+14*scale),(x+21*scale,y)],color,3*scale)

def icon(im,kind,x,y,color=BLUE,scale=1):
    # Simple editorial symbols. Coordinates are local logical pixels.
    def l(p,w=3):line(im,[(x+a*scale,y+b*scale) for a,b in p],color,w*scale)
    def c(a,b,r):circle(im,x+a*scale,y+b*scale,r*scale,None,color,3*scale)
    if kind==0:
        c(4,-3,11);c(19,-10,16);c(34,-1,10)
        rect(im,x-7*scale,y-1*scale,52*scale,15*scale,PAPER,r=0)
        l([(-8,11),(44,11)])
        for z in [0,16,32]:l([(z,21),(z-4,29)],2)
    elif kind==1:
        l([(18,-23),(-9,24),(45,24),(18,-23)])
        l([(18,-7),(18,9)],4);c(18,17,1)
    elif kind==2:
        rect(im,x-6*scale,y-23*scale,48*scale,48*scale,None,color,r=6*scale,width=3*scale)
        l([(4,-10),(31,-10)],2);l([(4,0),(24,0)],2);l([(4,10),(29,10)],2)
    elif kind==3:
        l([(0,-25),(-8,27)],3);l([(34,-25),(42,27)],3)
        l([(17,-20),(17,-8)],2);l([(17,3),(17,18)],2)
    elif kind==4:
        for yy in [-14,1,16]: l([(-8,yy),(31,yy),(40,yy-6)],3)
    else:
        l([(-10,5),(0,5),(9,-14),(18,24),(26,-5),(34,5),(45,5)],3)

def chrome(im,index,t,dark=False):
    fg='#e9edf4' if dark else INK
    muted='#9aa4b6' if dark else MUTED
    txt(im,'guguroute',64,40,25,fg,True)
    circle(im,194,57,4,BLUE)
    txt(im,'여행 모니터링',210,47,15,muted)
    txt(im,'로컬 구현 기준 · 예시 데이터',1216,49,14,muted,anchor='right')
    line(im,[(64,666),(1216,666)],'#343c4c' if dark else LINE,1)
    line(im,[(64,666),(64+1152*clamp(t/DURATION),666)],'#7fa0e8' if dark else BLUE,2)
    txt(im,SCENES[index][2],64,685,14,muted)
    txt(im,f'{index+1:02d} / 08',1216,683,14,muted,anchor='right')

CAPTURES={
 'logs':Image.open(ROOT/'final_project_cs/wiki/records/evidence/2026-10-09_watch_monitoring/admin-monitoring-v4.png').convert('RGBA'),
 'sim':Image.open(ROOT/'final_project_cs/wiki/records/evidence/2026-10-09_watch_simulation/admin-simulation-v2.png').convert('RGBA'),
 'quota':Image.open(ROOT/'final_project_cs/wiki/records/evidence/2026-10-09_watch_api_limits/monitoring-api-limits-final.png').convert('RGBA')}

def capture(im,key,source_rect,target,zoom=1):
    x,y,w,h=target
    # Original capture pixels are only cropped and scaled; labels/data are not altered.
    crop=CAPTURES[key].crop(tuple(map(int,source_rect)))
    crop=crop.resize((q(w*zoom),q(h*zoom)),Image.Resampling.LANCZOS)
    if zoom!=1:
        dx=(crop.width-q(w))//2;dy=(crop.height-q(h))//2
        crop=crop.crop((dx,dy,dx+q(w),dy+q(h)))
    im.alpha_composite(crop,(q(x),q(y)))
    ImageDraw.Draw(im).rectangle(box((x,y,x+w,y+h)),outline=LINE,width=2)

@lru_cache(maxsize=16)
def forecast_card(state):
    im=Image.new('RGBA',(q(666),q(450)))
    rect(im,0,0,664,448,WHITE,LINE,12)
    txt(im,'나의 서울 여행',30,24,21,INK,True)
    pill(im,'고객 화면 흐름 재구성 · 예시',353,20,size=13)
    line(im,[(30,72),(634,72)],LINE,1)
    if state==0:
        rect(im,30,94,604,137,GOLDPALE,r=8)
        pill(im,'예보 주의',48,110,GOLDPALE,GOLD)
        txt(im,'방문 시간에 비가 예보되어 있어요',48,154,23,INK,True)
        txt(im,'강수확률 80% · 원래 일정은 유지됩니다',48,191,17,MUTED)
        txt(im,'14:00',34,269,18,MUTED)
        txt(im,'야외 공원 방문',134,264,25,INK,True)
        rect(im,30,335,390,62,BLUE,r=8)
        txt(im,'예보에 맞게 일정 변경',225,354,21,WHITE,True,anchor='center')
        txt(im,'그대로 유지',454,358,19,MUTED)
    elif state==1:
        pill(im,'대체 일정 제안',30,96)
        txt(im,'실내에서 이어가는 오후',30,145,30,INK,True)
        rect(im,30,205,604,106,PALE,BLUE,r=8)
        txt(im,'14:00',51,226,18,BLUE,True)
        txt(im,'실내 전시 관람',150,225,26,INK,True)
        txt(im,'후보 예시 · 적용 전 다시 확인합니다',150,267,16,MUTED)
        rect(im,30,335,390,62,BLUE,r=8)
        txt(im,'이 일정으로 변경',225,354,21,WHITE,True,anchor='center')
        txt(im,'원래 일정 유지',444,358,19,MUTED)
    else:
        circle(im,58,128,28,PALE);check(im,47,120)
        txt(im,'선택한 일정으로 바뀌었어요',103,115,27,INK,True)
        txt(im,'후보와 전체 일정 검증을 마친 뒤 반영합니다',30,177,17,MUTED)
        rect(im,30,239,604,100,PALE,r=8)
        txt(im,'14:00',51,261,18,BLUE,True)
        txt(im,'실내 전시 관람',150,257,26,INK,True)
        txt(im,'최신 일정은 여행 화면에서 확인',150,299,16,MUTED)
        pill(im,'예보만으로 자동 변경하지 않습니다',30,371,GOLDPALE,GOLD,size=16)
    return im

def pointer(im,x,y,press=0):
    pts=[(x,y),(x+5,y+29),(x+13,y+21),(x+21,y+32),(x+27,y+28),(x+19,y+17),(x+31,y+15)]
    ImageDraw.Draw(im).polygon([(q(a),q(b)) for a,b in pts],fill=INK,outline=WHITE,width=2)
    if press>0:circle(im,x+8,y+12,20+25*press,None,BLUE,max(1,3*(1-press)))

def scene(index,u):
    im=canvas(NAVY if index in (0,7) else PAPER)
    if index==0:
        # The itinerary card moves as one object, then the six observations replace it.
        p=ease(u/.85)
        txt(im,'여행 중,',64,188+30*(1-p),70,'#e9edf4',True,alpha=p)
        txt(im,'일정이 흔들리면?',64,282+30*(1-p),70,'#e9edf4',True,alpha=p)
        txt(im,'계획한 다음도, guguroute이 지켜봅니다.',68,414,25,'#9aa4b6',alpha=ease((u-.65)/.7))
        yy=187+14*math.sin(u*.9)
        rect(im,827,yy,341,298,'#1c222d','#343c4c',12)
        pill(im,'오늘의 일정',850,yy+25,'#2b3448','#b7c9ff',size=16)
        txt(im,'14:00  공원 산책',852,yy+91,24,'#e9edf4',True)
        line(im,[(853,yy+145),(1140,yy+145)],'#343c4c',1)
        txt(im,'15:30  전시 관람',852,yy+175,24,'#9aa4b6')
        if u>1:
            a=ease((u-1)/.6)
            layer=Image.new('RGBA',(q(305),q(74)))
            rect(layer,0,0,304,72,GOLDPALE,r=8)
            txt(layer,'비 예보가 도착했어요',22,26,20,GOLD,True)
            pop(im,layer,797,yy-36,a)
    elif index==1:
        heading(im,'01  미리 살피기',['일정에 영향을 주는','여섯 가지 신호.'],['3분 주기로 관련 여행과 일정을 확인합니다.'])
        cats=['날씨 예보','기상 특보','재난문자','도로 상황','대기질','지진']
        for j,label in enumerate(cats):
            x=635+(j%3)*192;y=184+(j//3)*192
            p=ease((u-j*.13)/.6)
            layer=Image.new('RGBA',(q(172),q(169)))
            rect(layer,0,0,170,167,WHITE,LINE,10)
            icon(layer,j,62,57,BLUE)
            txt(layer,label,85,117,20,INK,True,anchor='center')
            pop(im,layer,x,y,p)
        txt(im,'캐시가 유효하면 재사용 · 점검 횟수와 API 호출 수는 다릅니다',66,575,18,MUTED)
        pill(im,'03:00',65,438,PALE,BLUE,30)
    elif index==2:
        state=0 if u<3.7 else 1 if u<7.0 else 2
        headings=[['비 예보가 오면,','먼저 알려드립니다.'],['바꾸고 싶을 때,','대체 일정을 봅니다.'],['내가 선택하면,','검증 후 바뀝니다.']]
        subs=[['예보는 주의사항으로 안내합니다.','일정 변경 버튼을 함께 보여줍니다.'],['버튼을 누르면 후보를 제안합니다.','그대로 유지할 수도 있습니다.'],['예보만으로 일정을 바꾸지 않습니다.','변경 결과는 여행 화면에 남습니다.']]
        heading(im,'02  예보에 대응하기',headings[state],subs[state])
        card=forecast_card(state)
        local=u if state==0 else u-3.7 if state==1 else u-7
        pop(im,card,550,153,ease(local/.45))
        if 2.65<u<3.7:
            p=smooth((u-2.65)/.65);pointer(im,1134-400*p,590-70*p,clamp((u-3.3)/.4))
        if 6.1<u<7:
            p=smooth((u-6.1)/.5);pointer(im,1070-335*p,590-70*p,clamp((u-6.65)/.35))
    elif index==3:
        heading(im,'03  알림 확인하기',['외부 알림이 꺼져도,','앱에서 확인.'],['고객 안내는 여행 화면 상단에 표시합니다.','앱을 다시 열어 저장된 알림을 봅니다.'])
        rect(im,592,148,620,220,WHITE,LINE,12)
        txt(im,'나의 여행',619,175,23,INK,True)
        circle(im,1165,190,14,PALE);txt(im,'1',1165,181,16,BLUE,True,anchor='center')
        a=ease((u-.4)/.65)
        notice=Image.new('RGBA',(q(567),q(109)))
        rect(notice,0,0,565,107,GOLDPALE,r=8)
        txt(notice,'방문 일정에 주의사항이 있어요',20,22,23,INK,True)
        txt(notice,'알림 보기   ·   예보에 맞게 일정 변경',20,66,18,GOLD,True)
        pop(im,notice,618,228,a)
        if u>1.2:
            layer=Image.new('RGBA',(q(620),q(152)))
            rect(layer,0,0,618,150,NAVY,r=12)
            txt(layer,'개발용 디스코드',26,24,22,'#e9edf4',True)
            txt(layer,'버그·운영 장애 보고',26,69,27,'#e9edf4',True)
            txt(layer,'고객 채널 미연결은 발송 실패가 아닙니다',26,115,17,'#9aa4b6')
            pop(im,layer,592,404,ease((u-1.2)/.6))
        pill(im,'외부 채널 미연결 시 외부 발송 건너뜀',66,476,GOLDPALE,GOLD,size=16)
    elif index==4:
        heading(im,'04  운영자가 확인하기',['무엇을 확인했고,','무슨 결과였는지.'],['최근 회차 · 다음 예정 · 이전 기록','문제가 생긴 항목까지 확인합니다.'])
        if u<3.9:
            capture(im,'logs',(270,142,1235,850),(558,151,654,480),1+.025*smooth(u/3.9))
            pill(im,'3분 감시 현황',582,115,PALE,BLUE,size=16)
        else:
            capture(im,'logs',(278,887,1225,1581),(558,151,654,480),1+.02*smooth((u-3.9)/4.1))
            pill(im,'지난 회차와 항목별 결과',582,115,PALE,BLUE,size=16)
        txt(im,'관리자웹앱 실제 화면 · 시험 데이터',66,550,17,MUTED)
        txt(im,'화면은 10초마다 저장된 기록을 읽습니다.',66,587,17,MUTED)
    elif index==5:
        heading(im,'05  사용 한도 확인하기',['감시 정보 옆에,','API별 설정 한도.'],['하루·월 한도와 설정 출처를 확인합니다.','제공 기관의 실시간 잔여량과는 다릅니다.'])
        yy=148+int(120*smooth(u/6))
        capture(im,'quota',(0,yy,936,yy+704),(558,140,654,492))
        pill(im,'설정값 예시 · 현재 운영 한도 아님',575,100,GOLDPALE,GOLD,size=16)
        txt(im,'관리자웹앱 실제 화면 · 시험 데이터',66,550,17,MUTED)
        txt(im,'감시 현황·로그 화면에서 함께 확인합니다.',66,587,17,MUTED)
    elif index==6:
        heading(im,'06  재난 상황 시험하기',['필요한 상황만 켜고,','내 일정에 시험.'],['6개 중 N개를 선택할 수 있습니다.','다음 감시 회차가 선택한 입력을 처리합니다.'])
        if u<4.8:
            capture(im,'sim',(277,480,1237,1120),(558,165,654,436))
            pill(im,'예시: 6개 중 3개 선택',576,118,PALE,BLUE,size=16)
            if u>1.7:
                pointer(im,660,550,clamp((u-2.0)/.6))
        else:
            card=Image.new('RGBA',(q(654),q(436)))
            rect(card,0,0,652,434,WHITE,LINE,12)
            pill(card,'시뮬레이션 결과 예시',25,25,GOLDPALE,GOLD,size=16)
            txt(card,'안전이 먼저인 상황이라면',25,93,31,INK,True)
            txt(card,'남은 일정이 일시 정지됩니다',25,144,26,INK,True)
            rect(card,25,218,604,122,GOLDPALE,r=8)
            txt(card,'[시뮬레이션] 재난 위험 안내',45,238,22,GOLD,True)
            txt(card,'시험 알림은 고객 앱에서만 확인합니다',45,281,21,INK)
            txt(card,'실제 고객 외부 채널에는 보내지 않습니다',45,314,16,MUTED)
            txt(card,'N개 입력이 N개 알림을 뜻하지는 않습니다',25,379,18,MUTED)
            pop(im,card,558,165,ease((u-4.8)/.55))
        txt(im,'관리자 화면·결과 모두 시험 데이터',66,551,17,MUTED)
        txt(im,'중지해도 이미 적용한 변경은 되돌리지 않습니다.',66,586,16,MUTED)
    else:
        p=ease(u/.8)
        txt(im,'여행은 계속.',640,182+24*(1-p),72,'#e9edf4',True,alpha=p,anchor='center')
        txt(im,'변화는 먼저 확인.',640,282+24*(1-p),72,'#e9edf4',True,alpha=p,anchor='center')
        txt(im,'여행자는 최신 일정을, 운영자는 확인 근거를.',640,403,25,'#9aa4b6',alpha=ease((u-.5)/.7),anchor='center')
        txt(im,'guguroute',640,505,46,'#e9edf4',True,alpha=ease((u-1)/.7),anchor='center')
    return im

def frame(t):
    index=max(i for i,(start,end,_) in enumerate(SCENES) if t>=start)
    start,end,_=SCENES[index]
    im=scene(index,t-start)
    if index<7 and t>end-.55:
        p=smooth((t-(end-.55))/.55)
        nxt=scene(index+1,0.0)
        mixed=canvas()
        mixed.alpha_composite(im,(-int(W*p),0))
        mixed.alpha_composite(nxt,(int(W*(1-p)),0))
        im=mixed
    chrome(im,index,t,index in (0,7))
    return im.convert('RGB')

def original_score(path):
    """53-second original instrumental: warm keys, bass, restrained electronic drums."""
    sr=44100;n=sr*DURATION
    music=np.zeros((n,2),dtype=np.float64)
    rng=np.random.default_rng(20261010)
    bpm=108;beat=60/bpm
    def add(start,a,pan=0):
        k=int(start*sr)
        if k>=n:return
        a=a[:min(len(a),n-k)]
        music[k:k+len(a),0]+=a*math.sqrt((1-pan)/2)
        music[k:k+len(a),1]+=a*math.sqrt((1+pan)/2)
    def note(freq,dur,amp=.1,decay=2):
        t=np.arange(int(sr*dur))/sr
        sig=np.sin(2*np.pi*freq*t)+.28*np.sin(4*np.pi*freq*t)+.08*np.sin(6*np.pi*freq*t)
        env=(1-np.exp(-t*70))*np.exp(-t*decay)*np.minimum(1,(dur-t)*25)
        return amp*sig*env
    # Cmaj9 / Am7 / Fmaj7 / Gadd9. A newly synthesized score, no sampled music.
    chords=[[48,55,59,62,64],[45,52,55,59,60],[41,48,52,55,57],[43,50,55,57,59]]
    for b in range(int(DURATION/beat)+1):
        at=b*beat;ch=chords[(b//8)%4]
        energy=.35 if at<4 else .66 if at<9 else .85 if at<19 else .5 if at<25 else .8 if at<33 else .47 if at<39 else 1 if at<48 else .32
        if b%4==0:
            for j,m in enumerate(ch):add(at,note(440*2**((m-69)/12),3,.055,1.0),(-.5+j*.25))
        if at>3.8 and at<48:
            tt=np.arange(int(sr*.23))/sr
            phase=2*np.pi*(44*tt+55*.04*(1-np.exp(-tt/.04)))
            kick=.34*np.sin(phase)*np.exp(-tt*23)
            if b%2==0:add(at,kick*energy)
            if b%4 in (1,3):
                tt=np.arange(int(sr*.16))/sr
                noise=rng.normal(size=len(tt))
                snare=.12*(noise*.7+np.sin(2*np.pi*185*tt)*.5)*np.exp(-tt*30)
                add(at,snare*energy,.12)
            for off in (0,.5):
                tt=np.arange(int(sr*.055))/sr
                noise=rng.normal(size=len(tt));noise=np.r_[0,np.diff(noise)]
                add(at+beat*off,.026*energy*noise*np.exp(-tt*90),-.3 if off else .3)
            if b%2==0:add(at,note(440*2**((ch[0]-12-69)/12),beat*1.7,.14*energy,2.5))
        if b%2==0:
            m=ch[2+(b//2)%3]+12
            add(at+beat*.5,note(440*2**((m-69)/12),1.4,.08*energy,3.8),.35*math.sin(b))
    for start,_,_ in SCENES[1:]:
        tt=np.arange(int(sr*.45))/sr
        # Soft tonal lift rather than a harsh flash/cut effect.
        add(start-.35,.028*np.sin(2*np.pi*(340*tt+700*tt*tt))*np.sin(np.pi*tt/.45)**2,-.15)
    # Musical closure at 48 seconds, no hard audio cut.
    for m in [48,55,60,64,71]: add(48,note(440*2**((m-69)/12),5,.09,.7))
    t=np.arange(n)/sr
    music*=np.minimum(1,t/1.5)[:,None]*np.minimum(1,(DURATION-t)/2.2)[:,None]
    music=np.tanh(music*.85)
    peak=np.max(np.abs(music));music*=.67/max(peak,1e-9)
    backup(path)
    with wave.open(str(path),'wb') as out:
        out.setnchannels(2);out.setsampwidth(2);out.setframerate(sr)
        out.writeframes((music*32767).astype('<i2').tobytes())

def previews():
    moments=[1.8,6.2,11,14.4,17.4,22,27,31,36,42,45.8,50]
    sheet=Image.new('RGB',(1280,720*3),PAPER)
    for j,t in enumerate(moments):
        f=frame(t).resize((640,360),Image.Resampling.LANCZOS)
        sheet.paste(f,((j%2)*640,(j//2)*360))
    save_image(sheet,OUT/'contact-sheet.jpg')
    save_image(frame(11),OUT/'poster.jpg')
    print('Preview frames saved.',flush=True)

def render():
    if not FFMPEG:raise RuntimeError('FFmpeg executable unavailable')
    wav=OUT/'original-score.wav';original_score(wav)
    target=OUT/'triPilot-monitoring-demo.mp4';backup(target)
    args=[FFMPEG,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
          '-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-i',str(wav),
          '-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p',
          '-c:a','aac','-b:a','192k','-movflags','+faststart','-t',str(DURATION),str(target)]
    p=subprocess.Popen(args,stdin=subprocess.PIPE)
    try:
        for f in range(FPS*DURATION):
            p.stdin.write(frame(f/FPS).tobytes())
            if f%(FPS*5)==0:print(f'Frames {f}/{FPS*DURATION}',flush=True)
        p.stdin.close()
        if p.wait()!=0:raise RuntimeError('FFmpeg encoding failed')
    except BaseException:
        p.kill();raise
    print(f'Complete: {target}',flush=True)

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    previews()
    if '--preview' not in sys.argv:render()
