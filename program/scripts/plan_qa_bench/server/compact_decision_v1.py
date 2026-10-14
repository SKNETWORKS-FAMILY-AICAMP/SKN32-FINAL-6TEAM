"""ARM 요청 해석의 짧은 출력 실험판. 제품 경로에는 연결하지 않는다."""
from copy import deepcopy

SYSTEM = '여행 요청을 일정·변경 이력·직전 대화·선택 항목에 근거해 해석한다. JSON만 출력한다.\na=행동, i=일정 id, c=변경 id, f=사실 종류, m=문장에 있는 지연 분, q=목록 범위, o=애매할 때 해석 후보.\n필요 없는 필드는 생략한다. 확실한 요청에는 o를 내지 않는다. 값을 지어내거나 실제로 변경하지 않는다.\n행동: answer_fact=기존 여행 사실 조회; apply_change=실제로 다른 곳으로 변경 요청; propose_alternatives=새로운 대체 장소 추천 요청;\nrollback=변경 되돌리기; redo=되돌린 변경 재적용; report_delay=늦음 신고; report_closed=휴무 신고;\nask_policy=취소·위약금·환불 조건; answer_service=서비스 기능·정체·지원 범위; other=잡담·인사; clarify=행동·대상이 불명확.\nanswer_fact의 f: time=방문 시각, hours=운영시간, address=위치, phone=연락처, booking=예약, next=다음 일정,\nday=하루 요약, move=일정 장소 사이 이동, route_here=현재 위치에서 목적지 이동, nearby_dining=현재 위치 근처 식당,\nnearby_activity=현재 위치 근처 활동, detail=장소 자체 설명, schedule=기존 일정 목록, changeability=기존 일정의 변경 가능 여부.\nschedule/changeability는 i,c 없이 q={day,period,kind}를 필수로 낸다. day=all/today/tomorrow/dN, period=all/morning/afternoon/evening, kind=all/activity/dining/lodging.\n기존 항목 중 바꿀 수 있는 것을 물으면 changeability다. 다른 장소 후보 요청과 구분한다. 항목이 없어도 요청 범위를 유지한다.\n목록 외 사실에는 q를 내지 않는다. time과 hours를 구분한다. 이름만 알려 달라면 detail.\n일정 id는 목록에서 고른다. 날짜·끼니·같은 종류 순번은 목록 표시를 따른다. 날 없는 순번은 첫날이다.\n그곳·그 식당은 직전 대화·선택·이력으로 판단한다. 문장의 명시 대상이 화면 선택보다 우선한다.\n변경 이력 없는 rollback/redo나 여러 대상을 구분 못 하면 clarify. 후보 o는 서로 다른 해석 1~3개, 각각 a/i/c/f만 사용한다.\n서비스 기능 안내·잡담에는 일정 대상과 사실을 내지 않는다. 지연 m은 원문 숫자만 낸다.'
KEYS = {"action":"a", "target_item":"i", "target_change":"c", "fact":"f", "minutes":"m", "query":"q", "choices":"o"}
REVERSE = {v:k for k,v in KEYS.items()}

def schema(full):
    properties = {KEYS[k]:deepcopy(v) for k,v in full["properties"].items()}
    choice = properties["o"]["items"]
    properties["o"]["items"] = {"type":"object", "properties":{KEYS[k]:v for k,v in choice["properties"].items()}, "required":["a"], "additionalProperties":False}
    return {"type":"object", "properties":properties, "required":["a"], "additionalProperties":False}

def decode(raw):
    """필드명만 복원한다. 의미·대상·실행 허용 판단은 기존 결정 검증기를 거친다."""
    if not isinstance(raw,dict) or "a" not in raw or set(raw)-set(REVERSE):
        raise ValueError("짧은 결정 출력의 필드가 유효하지 않습니다")
    result={"action":raw["a"],"target_item":"none","target_change":"none","fact":"none","minutes":0,"choices":[]}
    result.update({REVERSE[k]:v for k,v in raw.items()})
    choices=raw.get("o",[])
    if not isinstance(choices,list) or len(choices)>3:
        raise ValueError("해석 후보가 유효하지 않습니다")
    result["choices"]=[]
    for choice in choices:
        if not isinstance(choice,dict) or "a" not in choice or set(choice)-{"a","i","c","f"}:
            raise ValueError("해석 후보 필드가 유효하지 않습니다")
        value={"target_item":"none","target_change":"none","fact":"none"}
        value.update({REVERSE[k]:v for k,v in choice.items()})
        result["choices"].append(value)
    return result

class ExperimentalChat:
    """기존 decide의 검사·안전 경계를 우회하지 않는 개발 시험용 연결."""
    def __init__(self, chat):
        self.chat=chat
        self.last_wire=None

    def structured(self, system, user, full_schema, *, num_predict=400):
        self.last_wire=self.chat.structured(SYSTEM,user,schema(full_schema),num_predict=num_predict)
        result=decode(self.last_wire)
        result["experimental_wire"]={"version":"compact-v1","raw":self.last_wire}
        return result
