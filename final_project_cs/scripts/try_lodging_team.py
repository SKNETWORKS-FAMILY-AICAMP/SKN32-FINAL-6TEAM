"""숙소 팀을 문장 하나로 직접 돌려 본다 — DB · 서버 없이, 모델과 마이리얼트립은 실제로 부른다.

- 팀 본체(`LodgingTeam.execute`)와 도구함(`ReadToolbox`) · 어댑터(`MyRealTripMcp`)는 제품 코드 그대로다.
- 다른 것은 모델 객체 하나다: 제품은 프롬프트를 DB(`prompts` 표)에서 읽지만, 여기서는 파일
  `prompts/lodging/interpret.v1.md` 를 바로 읽는다. 보내는 글의 모양(prompt_key · input_text · context · instructions)은
  `OpenAITeamLLM` 과 같게 맞췄다. 호출 기록은 남기지 않는다.
- 문장 하나 = 모델 호출 1번 + 마이리얼트립 호출 최대 4번(목록 1 + 상세 3). 예약 · 결제는 하지 않는다.
- 설정(.env)의 OpenAI 키와 모델 이름을 쓴다. 키 값은 출력하지 않는다.

실행 위치: final_project_cs
  python -m scripts.try_lodging_team "11월 6일부터 9일까지 성인 2명 용산 근처 호텔 찾아줘"
  python -m scripts.try_lodging_team "해밀톤 호텔 11월 6일부터 3박 예약했어. 위치 알려줘"
"""
import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import platform
import sys
import time
from uuid import uuid4
from zoneinfo import ZoneInfo


class FilePromptLLM:
    """`OpenAITeamLLM.complete` 와 같은 모양으로 부르되, 지시문을 파일에서 읽는다."""

    def __init__(self):
        self.seen = []

    async def complete(self, prompt_key, input_text, context, *, run_id=None):
        from openai import OpenAI

        from app.core.settings import get_settings

        settings = get_settings()
        if not settings.openai_api_key.strip():
            raise RuntimeError("OpenAI API key is missing")
        folder, _, stem = prompt_key.partition(".")
        files = sorted(Path("prompts", folder).glob(f"{stem}.v*.md"))
        if len(files) != 1:
            raise RuntimeError(f"expected exactly one prompt file for {prompt_key}, found {len(files)}")
        prompt = json.dumps({"prompt_key": prompt_key, "input_text": input_text, "context": context,
                             "instructions": files[0].read_text(encoding="utf-8")}, ensure_ascii=False, default=str)

        def call():
            response = OpenAI(api_key=settings.openai_api_key, timeout=30).chat.completions.create(
                model=settings.llm_model, messages=[{"role": "user", "content": prompt}],
                temperature=settings.llm_temperature, seed=settings.llm_seed, response_format={"type": "json_object"})
            return json.loads(response.choices[0].message.content or "{}")

        started = time.perf_counter()
        result = await asyncio.to_thread(call)
        self.seen.append((settings.llm_model, time.perf_counter() - started, result))
        return result


def main():
    from app.core.contracts import ContextPack, TeamTask
    from app.domains.travel_ops.instances.lodging import LodgingTeam
    from app.domains.travel_ops.ports.data_sources.base import TravelSources
    from app.domains.travel_ops.ports.data_sources.myrealtrip import MyRealTripMcp
    from app.tools.read_tools import ReadToolbox

    sentences = sys.argv[1:]
    if not sentences:
        raise SystemExit(__doc__)
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')}")
    for text in sentences:
        source, llm = MyRealTripMcp(), FilePromptLLM()
        team = LodgingTeam(ReadToolbox(lambda: None, travel=TravelSources(travel_search=source)), llm)
        case_id = uuid4()
        pack = ContextPack(pack_id=uuid4(), case_id=case_id, team_id="lodging", tenant_id="try", knowledge_scope=["lodging"],
                           current_state={"customer_id": str(uuid4())}, estimated_input_tokens=1)
        task = TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=case_id, team_id="lodging", capability="lodging.assist",
                        case_version=1, input_text=text, context=pack, allowed_tools=team.manifest.allowed_tools,
                        deadline_at=datetime.now(UTC) + timedelta(seconds=90))
        started = time.perf_counter()
        result = asyncio.run(team.execute(task))
        took = time.perf_counter() - started
        print(f"\n[문장] {text}")
        for model, seconds, raw in llm.seen:
            print(f"[해석] 모델 {model} · {seconds:.1f}초 · {json.dumps(raw, ensure_ascii=False)}")
        print(f"[결과] {took:.1f}초 · outcome {result.outcome} · next_action {result.next_action.value}"
              + (f" · failure_code {result.failure_code}" if result.failure_code else "")
              + (f" · warnings {result.warnings}" if result.warnings else ""))
        decision = (result.decisions or [{}])[0]
        print(f"[판단] task {decision.get('task')} · needs {decision.get('needs')} · found {decision.get('found')}")
        print(f"[근거] {[item.source_id for item in result.evidence]} · 못 가져온 것 {dict(source.misses) or '없음'}")
        print("[답]")
        print(result.answer or "(없음)")


if __name__ == "__main__":
    main()
