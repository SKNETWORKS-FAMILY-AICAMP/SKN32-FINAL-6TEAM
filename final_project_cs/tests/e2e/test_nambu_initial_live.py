"""실제 해석 모델과 카카오로 최초 요청의 날짜·지시어·상대 시각을 확인한다."""
import json
import os
from datetime import datetime
from uuid import uuid4

import pytest


@pytest.mark.skipif(os.environ.get('NAMBU_LIVE_MODEL')!='1',reason='명시적 외부 API 시험에서만 실행')
def test_now_origin_relative_meal_and_default_deadline_with_actual_model():
    from app.core.settings import get_settings
    from app.infrastructure.ollama_chat import from_settings
    from app.domains.travel_ops.components.intake.pipeline import read_source
    from app.domains.travel_ops.components.intake.assemble import assemble
    from app.domains.travel_ops.ports.data_sources.kakao_local import KakaoLocal
    settings=get_settings()
    chat=from_settings(settings)
    class Budget:
        count=0
        def try_reserve(self,_meter):
            self.count+=1
            return self.count<=12
    budget=Budget()
    kakao=KakaoLocal(api_key=settings.kakao_rest_api_key,budget=budget,timeout=8)
    text='지금 남부터미널에서 8시에 시작해서 10분뒤에 거기서 밥먹고 다이소 갔다가 노래방 가는 일정 짜줘. 11시 전에는 일정을 마칠 거야.'
    moment=datetime.fromisoformat('2026-10-17T19:50:00+09:00')
    # 이미 선택한 세 장소를 재사용한다. 식당은 실제 카카오 응답이다.
    our=[{'place_id':str(uuid4()),'name':name,'kind':'activity','latitude':lat,'longitude':lon}
         for name,lat,lon in [('남부터미널',37.4849,127.0162),('다이소 남부터미널점',37.4845,127.0155),
                               ('노래방',37.4847,127.0158)]]
    rows=read_source(text,today=moment.date(),now=moment,agent=chat,agent_mode='on',our_places=our,kakao=kakao)
    built=assemble(intake_id='initial-live',revision=1,sources=[{'source_id':'s','position':0,'transcript':text}],
        claims=[{**row,'source_id':'s'} for row in rows])
    print('NAMBU_INITIAL_LIVE='+json.dumps({'body':built.body,'problems':[p.as_dict() for p in built.problems],
        'kakao_calls':budget.count},ensure_ascii=False,default=str))
    items=built.body['items']
    assert len(items)==4,built.body
    assert items[0]['detail'].get('origin') is True and items[0]['ends_at'] is None
    assert items[0]['starts_at']=='2026-10-17T20:00:00+09:00'
    assert items[1]['kind']=='dining' and items[1]['starts_at']=='2026-10-17T20:10:00+09:00'
    assert items[1]['place'] is not None and '거기' not in items[1]['title']
    assert items[-1]['ends_at']<='2026-10-17T23:00:00+09:00'
