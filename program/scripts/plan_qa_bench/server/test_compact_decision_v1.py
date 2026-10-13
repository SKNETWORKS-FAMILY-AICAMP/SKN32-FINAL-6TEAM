"""짧은 출력이 기존 요청 검증·변경 안전 경계를 우회하지 않는지 확인한다."""
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import importlib.util
import sys
import pytest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'final_project_cs'))
from app.domains.travel_ops.components.conversation import decision_unit as du
spec=importlib.util.spec_from_file_location('compact_candidate',Path(__file__).with_name('compact_decision_v1.py'))
codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec)

def run(raw, message='첫 일정은 몇 시인가요?'):
    start=datetime.fromisoformat('2030-01-01T09:00:00+09:00')
    item=SimpleNamespace(item_id=uuid4(),title='경복궁 관람',kind='activity',seq=1,starts_at=start,
                         ends_at=start+timedelta(hours=1),place={'name':'경복궁'},detail={},locked=False,booking_id=None)
    class Model:
        def structured(self,*args,**kwargs):return raw
    return du.decide(codec.ExperimentalChat(Model()),stops=du.stops_of([item]),changes=[],history=[],selected_item_id=None,message=message)

def test_valid_time_retains_actual_schedule_reference():
    result=run({'a':'answer_fact','i':'i1','f':'time'})
    assert result.item.title=='경복궁 관람' and result.fact=='time'
    assert result.raw['experimental_wire']['raw']=={'a':'answer_fact','i':'i1','f':'time'}

@pytest.mark.parametrize('raw',[
    {'a':'apply_change','i':'outside'},
    {'a':'rollback','c':'not-in-history'},
    {'a':'delete_everything'},
    {'a':'answer_service','i':'i1'},
    {'a':'apply_change','i':'i1','f':'changeability','q':{'day':'all','period':'afternoon','kind':'all'}},
    {'a':'answer_fact','f':'changeability','q':{'day':'d9','period':'afternoon','kind':'all'}},
    {'a':'answer_fact','f':'changeability','q':{'day':'all','period':'midnight','kind':'all'}},
    {'a':'answer_fact','f':'time','i':'i1','q':{'day':'all','period':'all','kind':'all'}},
])
def test_unsafe_or_out_of_scope_decisions_remain_rejected(raw):
    with pytest.raises(du.DecisionFailed):run(raw)

def test_scope_read_does_not_choose_morning_item_for_empty_afternoon():
    result=run({'a':'answer_fact','f':'changeability','q':{'day':'all','period':'afternoon','kind':'all'}},'오후에 변경 가능한 일정들을 확인해 주세요')
    assert result.item is None and result.action=='answer_fact'
    assert result.query['period']=='afternoon'

def test_invented_delay_number_is_not_accepted():
    result=run({'a':'report_delay','m':45},'조금 늦어요')
    assert result.minutes is None

@pytest.mark.parametrize('raw',[None,[],{}, {'a':'other','unknown':True},{'a':'clarify','o':None},
                              {'a':'clarify','o':[{'a':'apply_change','q':{}}]}])
def test_broken_wire_fails_without_guessing(raw):
    with pytest.raises(du.DecisionFailed):run(raw)

def test_clarification_preserves_distinct_read_and_write_candidates():
    result=run({'a':'clarify','o':[{'a':'apply_change','i':'i1'},{'a':'answer_fact','i':'i1','f':'detail'}]})
    assert result.action=='clarify' and result.item is None
    assert [choice['action'] for choice in result.choices]==['apply_change','answer_fact']
