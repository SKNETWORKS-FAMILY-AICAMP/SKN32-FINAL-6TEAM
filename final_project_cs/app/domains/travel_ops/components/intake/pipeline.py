# -*- coding: utf-8 -*-
"""계획 읽기 한 건 — 접수 · 글자로 · 규칙 읽기 · 읽은 값 저장. `[2026-09-27]` 설계서 §3·§6

    open_intake   접수 행 + 원본 행(글자 판별·sha256). ★여기서는 읽지 않는다 — 요청이 45초를 기다리지 않게
    process       뒤에서: 원본마다 글자로(받아쓰기 포함) → 규칙 읽기 → `intake_claims` (revision 1) → review
    view          화면이 읽는 모양: 진행 단계 · 원본별 줄 번호 글 · 읽은 항목 · 확인 필요 · 남은 줄

★실패를 숨기지 않는다 — 형식을 못 읽으면 `fatal`(코드·사유), 받아쓰기 모델이 죽으면 `fatal` + 다시 시도 가능.
  「읽은 항목 0개」는 실패가 아니다 — 확인 화면이 남은 줄을 보여 주고 고객이 고친다(2주차부터 LLM 이 남은 줄을 돕는다).
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import re
import logging
import threading
from typing import Any, Callable
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components import settings_hook
from . import progress as progress_module
from . import screen as screen_module
from . import reading_prefs
from . import review as review_module
from . import survey_answers
from .areas import areas_for
from . import agent_read as agent_module
from . import interpretations as interpretations_module
from . import schedule_cards
from .assemble import assemble, effective
from .catalog_names import with_catalog
from .landmarks import load_table as load_landmarks
from .line_parts import lookup_title
from .rules import read_plan
from .sources import UnsupportedSource, other_reading, sniff, to_text

KST = ZoneInfo("Asia/Seoul")
log = logging.getLogger(__name__)

#: 받는 크기 · 개수 — 우리가 고른 값(설계서 §9 「악성 파일·압축 폭탄」). 넘으면 접수하지 않는다
MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 20_000

STAGES = {"received": "받았어요", "transcribing": "글자로 옮기는 중", "reading": "일정 읽는 중",
          # ★`[2026-10-02]` 읽은 장소의 운영시간 · 휴무 · 이동을 확인하는 단계 — 목업의 「장소·운영시간 확인」(`review.py`)
          "checking": "장소·운영시간 확인", "review": "확인해 주세요", "confirmed": "등록했어요", "fatal": "읽지 못했어요"}


class _Abandoned(Exception):
    """이 일꾼이 맡은 접수가 더는 `reading` 이 아니다(실패로 확정됐거나 다른 곳에서 끝났다) — 더 쓰지 않고 물러난다."""


class _Heartbeat:
    """읽는 동안 **일꾼이 살아 있다는 표시**를 주기적으로 남긴다(접수의 갱신 시각을 올린다). 사진 받아쓰기처럼 한 번의 긴 호출 동안에는 값이 안 적혀
    갱신 시각이 멈추는데, 그때 조회가 「죽은 일꾼」으로 오해해 실패로 확정하지 않게(`reap_stalled`) 한다. 일꾼이 정말 죽으면 표시도 멎는다(스레드가 같이 죽는다).

    ★접수가 이미 `reading` 이 아니면 아무것도 쓰지 않는다 — 실패로 확정된 접수를 되살리지 않는다."""

    def __init__(self, connect: Callable[[], Any], tenant_id: str, intake_id: UUID, every: float = 20.0) -> None:
        self._connect, self._tenant, self._intake, self._every = connect, tenant_id, intake_id, every
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"intake-heartbeat-{intake_id}", daemon=True)

    def __enter__(self) -> "_Heartbeat":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self._every):
            try:
                with self._connect() as conn, conn.transaction(), conn.cursor() as cur:
                    cur.execute("UPDATE trip_intakes SET updated_at=now() WHERE tenant_id=%s AND intake_id=%s "
                                "AND (status='reading' OR (status='review' AND stage='checking'))",
                                (self._tenant, self._intake))
            except Exception:                                  # noqa: BLE001 — 표시 한 번을 못 남겨도 읽기는 계속한다
                log.warning("intake heartbeat failed intake=%s", self._intake, exc_info=True)


class IntakeRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


def open_intake(conn, *, tenant_id: str, customer_id: UUID, text: str | None,
                files: list[tuple[str, bytes]]) -> UUID:
    """접수 한 건. `files` = [(파일 이름, 바이트)]. ★종류는 첫 바이트로 — 모르는 형식은 여기서 거절한다."""
    text = (text or "").strip()
    from .test_plans import TestPlanRejected, expand

    try:
        text, test_scenario = expand(text, tenant_id=tenant_id, has_files=bool(files))
    except TestPlanRejected as exc:
        raise IntakeRejected(exc.code, exc.message) from None
    if not text and not files:
        # ★`[2026-09-30 사용자 결정 — ui 세션 전달]` 입력칸을 비운 채 「계획 확인하기」를 눌러도 **다음 화면으로 넘어간다** —
        #   읽을 것이 없으니 곧바로 확인 화면 상태(`review`)로 만든다. 그 화면에 「읽은 일정이 없어요 — 대신 짜 드릴까요?」 짜기 칸이
        #   이미 있다. 「짜 달라는 요청」 표시(`trip.plan_request`)는 넣지 않는다 — 고객이 그 칸에서 직접 고른다.
        #   ☆전에는 422 `empty_intake` 로 거절했다. 사람 확인 · 남용 방어 한도는 부르는 쪽이 그대로 적용한다(빈 접수도 한 건).
        # ★`[2026-10-19 사용자 결정]` 빠른 거름 — 빈 접수는 `screened: empty` 로 남고 로딩 설문을 내지 않는다(`screen.py`)
        return _screened_intake(conn, tenant_id=tenant_id, customer_id=customer_id, text="", screened={"code": "empty", "rule": "empty"})
    if len(text) > MAX_TEXT_CHARS:
        raise IntakeRejected("text_too_long", f"글은 {MAX_TEXT_CHARS:,}자까지 받아요")
    if not files:
        # ★`[2026-10-19 사용자 결정]` 접수 입구의 빠른 거름 — 여행 단서가 하나도 없는 글은 모델 읽기 전에 바로 「일정 없음」으로 돌려보낸다
        #   (규칙만 · 모델 호출 0). 애매하면 지금처럼 읽는다 · 파일이 붙으면 거르지 않는다(`screen.py` · 설계서 §5)
        screened = screen_module.screen(text, has_files=False, place_names=_catalog_names(conn, tenant_id),
                                        area_keys=_area_keys(conn, tenant_id), landmark_keys=set(load_landmarks().by_alias))
        if screened is not None:
            log.info("intake screened code=%s rule=%s", screened["code"], screened["rule"])
            return _screened_intake(conn, tenant_id=tenant_id, customer_id=customer_id, text=text, screened=screened)
    if len(files) > MAX_FILES:
        raise IntakeRejected("too_many_files", f"파일은 {MAX_FILES}개까지 받아요")
    kinds = []
    for name, data in files:
        if len(data) > MAX_FILE_BYTES:
            raise IntakeRejected("file_too_large", f"{name}: 파일 하나는 {MAX_FILE_BYTES // 1024 // 1024}MB 까지 받아요")
        try:
            kinds.append(sniff(data, filename=name))
        except UnsupportedSource as exc:
            raise IntakeRejected("unsupported_format", f"{name}: {exc}") from None
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, stage) VALUES (%s,%s,'received') "
                    "RETURNING intake_id", (tenant_id, customer_id))
        intake_id = cur.fetchone()[0]
        if test_scenario is not None:
            cur.execute("INSERT INTO intake_test_scenarios (tenant_id, intake_id, customer_id, metadata) "
                        "VALUES (%s,%s,%s,%s::jsonb)",
                        (tenant_id, intake_id, customer_id, json.dumps(test_scenario, ensure_ascii=False)))
        survey_answers.inherit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
        position = 0
        if text:
            raw = text.encode("utf-8")
            cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, sha256, size_bytes, "
                        "transcript) VALUES (%s,%s,%s,'chat',%s,%s,%s)",
                        (intake_id, tenant_id, position, hashlib.sha256(raw).hexdigest(), len(raw), text))
            position += 1
        for (name, data), kind in zip(files, kinds):
            # ★원본은 DB 에 두지 않는다 — 뒤에서 읽을 동안만 메모리/임시 저장소(`blobs`)에 둔다
            cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, filename, sha256, "
                        "size_bytes) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (intake_id, tenant_id, position, kind, name[:200], hashlib.sha256(data).hexdigest(),
                         len(data)))
            position += 1
    return intake_id


def _screened_intake(conn, *, tenant_id: str, customer_id: UUID, text: str, screened: dict[str, str]) -> UUID:
    """거른 접수 — 읽지 않고 곧바로 확인 화면 상태(`review`). 원문(글 원본 줄)과 걸린 규칙(`screened`, 907)을 남긴다 — 사후에 오판을 센다.
    ★907 이 안 올라간 DB 면 규칙 기록 없이 같은 상태로 만든다(경고) — 접수를 막지 않는다."""
    with conn.transaction(), conn.cursor() as cur:
        try:
            with conn.transaction():
                cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, status, stage, screened) VALUES (%s,%s,'review','review',%s::jsonb) "
                            "RETURNING intake_id", (tenant_id, customer_id, json.dumps(screened, ensure_ascii=False)))
        except Exception:                                  # noqa: BLE001 — 907 없음
            log.warning("intake screened mark not stored (migration 907?)", exc_info=True)
            cur.execute("INSERT INTO trip_intakes (tenant_id, customer_id, status, stage) VALUES (%s,%s,'review','review') "
                        "RETURNING intake_id", (tenant_id, customer_id))
        intake_id = cur.fetchone()[0]
        if text:
            raw = text.encode("utf-8")
            cur.execute("INSERT INTO intake_sources (intake_id, tenant_id, position, kind, sha256, size_bytes, transcript) "
                        "VALUES (%s,%s,0,'chat',%s,%s,%s)", (intake_id, tenant_id, hashlib.sha256(raw).hexdigest(), len(raw), text))
    return intake_id


def _catalog_names(conn, tenant_id: str) -> Callable[[str], bool]:
    """빠른 거름의 장소 단서 — 우리 장소 표 · 관광공사 목록의 이름이 글 안에 글자 그대로 있나. ★못 읽으면 「있다」(거르지 않는다)."""
    def has(text: str) -> bool:
        try:
            with conn.transaction(), conn.cursor() as cur:
                cur.execute("SELECT 1 FROM place_catalog WHERE tenant_id=%s AND length(title) >= 2 AND strpos(%s, title) > 0 "
                            "UNION ALL SELECT 1 FROM places WHERE tenant_id=%s AND length(name) >= 2 AND strpos(%s, name) > 0 LIMIT 1",
                            (tenant_id, text, tenant_id, text))
                return cur.fetchone() is not None
        except Exception:                                  # noqa: BLE001 — 거름은 읽기를 막지 않는다
            log.warning("intake screen place lookup failed — not screening", exc_info=True)
            return True
    return has


def _area_keys(conn, tenant_id: str) -> set[str]:
    """빠른 거름의 지명 단서(지명 사전 열쇠). 못 읽으면 빈 묶음 — 다른 단서로 본다."""
    try:
        return set(areas_for(conn, tenant_id).keys())
    except Exception:                                      # noqa: BLE001
        log.warning("intake screen area dictionary unreadable", exc_info=True)
        return set()


def process(connect: Callable[[], Any], *, tenant_id: str, intake_id: UUID, blobs: dict[int, bytes],
            see: Callable[[str, bytes], str] | None, chat: Any = None, tour: Any = None, kakao: Any = None,
            today: date | None = None, dining: Any = None) -> str:
    """뒤에서 한 건을 읽는다. 돌려주는 값은 마지막 상태(review · fatal). `blobs` = {position: 바이트}.

    ★2주차(2026-09-27): 규칙 → 남은 줄은 모델이 **가리키기만**(`chat`) → 날짜 해석 → 장소 찾기(`tour` 관광공사 ·
      `kakao`). 넣지 않은 것은 건너뛴다 — 그 값은 「확인 필요」로 남고 확인 화면에서 고객이 고친다.
    """
    try:
        with connect() as conn, conn.transaction(), conn.cursor() as cur:
            # ★읽기는 한 접수에 한 번만 — **한 번의 조건부 갱신으로 맡는다**(받은 직후 단계 `received` 인 접수만 읽는 중으로 바꾼다). 이미 읽었거나(확인 화면 · 등록 · 실패)
            #   다른 일꾼이 맡았으면 건드리지 않는다: 두 일꾼이 서로의 값을 지우거나 늦은 쪽이 등록된 접수를 확인 화면으로 되돌리는 일이 없다
            cur.execute("UPDATE trip_intakes SET stage='reading', updated_at=now() WHERE tenant_id=%s AND intake_id=%s "
                        "AND status='reading' AND stage='received' RETURNING received_at", (tenant_id, intake_id))
            claimed = cur.fetchone()
            if claimed is None:
                cur.execute("SELECT status FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
                row = cur.fetchone()
                return row[0] if row else "fatal"
            received_at = claimed[0]
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=KST)
            received_at = received_at.astimezone(KST)
        beat = _Heartbeat(connect, tenant_id, intake_id)
        beat.__enter__()
        with connect() as conn:
            sources = _sources(conn, tenant_id, intake_id)
        for source in sources:
            if source["transcript"] is None:
                _stage(connect, tenant_id, intake_id, "transcribing")
                data = blobs.get(source["position"])
                if data is None:
                    raise IntakeRejected("source_missing", f"{source['filename']}: 원본을 찾지 못했다")
                result = to_text(data, filename=source["filename"] or "", see=see)
                with connect() as conn, conn.transaction(), conn.cursor() as cur:
                    _hold_reading(cur, tenant_id, intake_id)          # 받아쓰는 동안 실패로 확정됐으면 결과를 저장하지 않고 물러난다
                    _store_transcript(conn, cur, source["source_id"], tenant_id, result)
                source["transcript"] = result.text
                source["differs_json"] = result.differs
        _stage(connect, tenant_id, intake_id, "reading")
        tour = with_catalog(tour, connect, tenant_id)          # ★`[2026-10-15]` 관광공사 조회가 못 찾으면 우리 장소 목록에서(공백 · 괄호 무시 · 정확히 하나일 때만)
        with connect() as conn:
            our_places = _our_places(conn, tenant_id)
            with conn.cursor() as cur:
                cur.execute("SELECT customer_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s",
                            (tenant_id, intake_id))
                owner = cur.fetchone()[0]
            aliases = load_aliases(conn, tenant_id, owner)
            areas = areas_for(conn, tenant_id)               # 지명 사전 — 이름 없는 줄(「성수 예약 식당」)을 알아보는 데 쓴다(`areas.py`, DB 만 읽는다 · 한 시간 기억)
            # ★다시 읽는 접수면 앞에 읽은 값부터 지운다(고객이 고친 값은 남긴다). 값은 이제 읽는 **동안** 바로바로 적힌다 —
            #   실시간 진행(`GET …/events`)이 읽은 줄 · 찾은 일정을 그때그때 보여 주려면 끝에 한꺼번에 적을 수 없다
            with conn.transaction(), conn.cursor() as cur:
                _hold_reading(cur, tenant_id, intake_id)              # 같은 트랜잭션에서 접수 행을 잠그고 확인한 뒤 지운다(실패 확정과 겹치지 않게)
                cur.execute("DELETE FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=1 "
                            "AND method <> 'customer'", (tenant_id, intake_id))
        push = progress_module.sink(intake_id)             # ★검사가 끝나기 전에 장소 n/m · 일정 · 검사 줄 · 이동을 실시간 진행에 알린다(`progress.py`)
        # ★`[2026-10-16 D-025]` 이해 · 분류 에이전트 — 채팅과 같은 모델 클라이언트 그대로(넘김 장치가 켜져 있으면 9초 넘을 때 유료 대체 1회).
        #   실패하면 규칙 미리보기 + 못 읽은 줄 표시로 읽는다(`read_source`)
        reader = agent_reader_config(tenant_id)
        agent = chat if callable(getattr(chat, "structured", None)) and reader["mode"] in ("on", "shadow") else None
        for source in sources:
            def places_progress(phase, done, total, index, title, _position=source["position"]):
                push("progress", {"phase": phase, "done": done, "total": total, "current": {"id": f"{_position}-{index}", "title": title}})

            def reading_progress(body):
                # ★`[2026-10-16 2회차 합의]` 남은 줄 모델이 답을 쓰는 동안 「읽는 중 n/m 줄」(`llm_spans.label_lines`) — 원문 검사를 통과한 줄 수 / 보낸 줄 수.
                #   유료로 처음부터 다시 읽으면 `phase: reading_api` 로 0 부터 다시 센다
                push("progress", body)

            read_source(source["transcript"] or "", chat=chat, tour=tour, kakao=kakao, our_places=our_places,
                        aliases=aliases, areas=areas, dining=dining, today=(today or received_at.date()), now=received_at,
                        on_rows=_claim_sink(connect, tenant_id, intake_id, source["source_id"]), on_progress=places_progress,
                        differs=differs_by_line(source.get("differs_json")), agent=agent, agent_mode=reader["mode"],
                        position=int(source["position"]), agent_num_predict=reader["num_predict"],
                        agent_chunk_chars=reader["chunk_chars"], on_reading=reading_progress, connect=connect)
        # 검사 — 읽은 장소의 운영시간 · 휴무 · 이동(`review.py`). 실패해도 읽은 값은 그대로 확인 화면으로 간다(검사만 비고 이유가 남는다)
        _stage(connect, tenant_id, intake_id, "checking")
        try:
            with connect() as conn, conn.transaction():
                review_module.ensure(conn, tenant_id=tenant_id, intake_id=intake_id, revision=1,
                                     sources=_sources(conn, tenant_id, intake_id),
                                     claims=_claims(conn, tenant_id, intake_id, 1), force=True, on_event=push)
        except Exception:                                  # noqa: BLE001 — 검사 장애가 읽기를 지우지 않는다
            log.warning("intake review failed intake=%s", intake_id, exc_info=True)
        filling = reader["prefill"] == "on" and reader["mode"] == "on"
        # ★`[2026-10-20 사용자 지시]` 해석 확인 질문(`interpretations.py`)이 있으면 그 답을 반영할 때까지 고객에게는 「읽는 중」(첫 기다림)으로 둔다
        asking = _has_questions(connect, tenant_id, intake_id)
        with connect() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("UPDATE trip_intakes SET status='review', stage=%s, updated_at=now() "
                        "WHERE tenant_id=%s AND intake_id=%s AND status='reading'",
                        ("checking" if filling or asking else "review", tenant_id, intake_id))
        if filling:
            _prefill(connect, tenant_id, intake_id, tour=tour, kakao=kakao, dining=dining)
        if filling or asking:
            # 로딩 중에 받아 둔 해석 답을 첫 검사 · 먼저 채우기 뒤에 반영한다(그 지점부터 다시 검사 — `pipeline.edit`)
            _apply_interpretations(connect, tenant_id, intake_id, tour=tour, kakao=kakao, dining=dining)
            with connect() as conn, conn.transaction(), conn.cursor() as cur:
                cur.execute("UPDATE trip_intakes SET stage='review', updated_at=now() "
                            "WHERE tenant_id=%s AND intake_id=%s AND status='review' AND stage='checking'", (tenant_id, intake_id))
            # 상태를 바꾸는 사이에 들어온 답(접수 행 잠금으로 순서가 정해진다 — `interpretations.answer`)을 한 번 더 본다
            _apply_interpretations(connect, tenant_id, intake_id, tour=tour, kakao=kakao, dining=dining)
        # ★`[2026-10-19]` 판정은 **지금 판**을 본다 — 먼저 채우기가 새 판을 만들었으면 그 판이다. 전에는 늘 1판을 봐서 채운 판에는 판정이 안 붙었다
        #   (1판 판정은 합치기 직전 「지난 판」으로 막히고 · 1판에서 장소가 없던 이름 없는 식사는 판정 입력조차 못 됐다)
        _dining_judge(connect, tenant_id, intake_id, sources, revision=None)
        # ★`[2026-10-19 사용자 지시]` 문제 난 일정의 대안을 완성본으로 미리 준비한다(팀 대안 → 두 구간 이동 → 판정 → 이유 문장) — 「바꾸기」가 계산 없이 뜨게.
        #   확인 화면으로 넘긴 뒤라 고객은 기다리지 않는다. 실패해도 접수 · 확인 화면은 그대로다(「바꾸기」가 그때 계산한다)
        _prepare_alternatives(connect, tenant_id, intake_id, kakao=kakao, chat=chat)
        return "review"
    except _Abandoned:                               # 읽는 사이 실패로 확정됐다(`reap_stalled`) — 값도 상태도 더 건드리지 않는다
        return "fatal"
    except (IntakeRejected, UnsupportedSource) as exc:
        code = getattr(exc, "code", "unsupported_format")
        _fatal(connect, tenant_id, intake_id, code, str(exc))
        return "fatal"
    except Exception as exc:                         # ★받아쓰기 모델 장애 등 — 숨기지 않고 남긴다
        _fatal(connect, tenant_id, intake_id, "reading_failed", f"{type(exc).__name__}: {exc}"[:300])
        return "fatal"
    finally:
        if "beat" in locals():
            beat.__exit__()
        progress_module.clear(str(intake_id))                # 끝났다 — 최종 값은 DB 에서 읽히므로 보관소는 비운다(`progress.py`)


def _has_questions(connect: Callable[[], Any], tenant_id: str, intake_id: UUID) -> bool:
    """이 접수에 해석 확인 질문이 있나(첫 판). 못 읽으면 False — 질문 장치가 접수를 막지 않는다."""
    from . import interpretations

    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=1 AND field LIKE %s LIMIT 1",
                        (tenant_id, intake_id, interpretations.QUESTION_FIELD + "%"))
            return cur.fetchone() is not None
    except Exception:                                  # noqa: BLE001
        log.warning("intake interpretation questions unreadable intake=%s", intake_id, exc_info=True)
        return False


def _apply_interpretations(connect: Callable[[], Any], tenant_id: str, intake_id: UUID, *, tour: Any, kakao: Any, dining: Any) -> None:
    """`[2026-10-20]` 로딩 중에 저장만 해 둔 해석 답 → 새 판(`interpretations.apply_pending`). 실패해도 확인 화면은 1안(AI 의 읽기)으로 간다."""
    from . import interpretations

    try:
        with connect() as conn:
            new = interpretations.apply_pending(conn, tenant_id=tenant_id, intake_id=intake_id, tour=tour, kakao=kakao, dining=dining)
        if new is not None:
            log.info("intake interpretation answers applied intake=%s revision=%s", intake_id, new)
    except Exception:                                  # noqa: BLE001 — 답 반영 장애가 접수를 막지 않는다(고객이 확인 화면에서 다시 고른다)
        log.warning("intake interpretation answers not applied intake=%s", intake_id, exc_info=True)


def _prepare_alternatives(connect: Callable[[], Any], tenant_id: str, intake_id: UUID, *, kakao: Any, chat: Any) -> None:
    """`[2026-10-19]` 접수 대안 미리 준비(`prepared.prepare`) — 가드레일 `travel.candidates.prepare_on_intake`(기본 켜짐)가 끄면 하지 않는다."""
    from app.core.settings import get_guardrails

    from . import prepared

    try:
        if get_guardrails().get("travel.candidates.prepare_on_intake") is False:
            return
        done = prepared.prepare(connect, tenant_id=tenant_id, intake_id=intake_id, kakao=kakao, chat=chat)
        log.info("intake alternatives prepared intake=%s %s", intake_id, done)
    except Exception:                                  # noqa: BLE001 — 준비 장애가 접수를 건드리지 않는다
        log.warning("intake alternatives prepare failed intake=%s", intake_id, exc_info=True)


def agent_reader_config(tenant_id: str) -> dict[str, Any]:
    """이해 · 분류 에이전트 설정 — 운영 설정 `travel.intake_reader.mode`(관리 콘솔, 재기동 없이)가 먼저, 없으면 가드레일 `travel.intake_reader`.
    못 읽으면 `off`(규칙으로 읽는다). ★기다리는 시간은 여기서 정하지 않는다 — 채팅과 같은 넘김 장치(`llm_failover_primary_timeout_seconds`)를 따른다."""
    from app.core.settings import get_guardrails

    default = {"mode": "off", "num_predict": 3072, "chunk_chars": agent_module.fragments_module.CHUNK_CHARS, "prefill": "off"}
    try:
        guard = get_guardrails()
        mode = str(guard.get("travel.intake_reader.mode"))
        num_predict = int(guard.get("travel.intake_reader.num_predict"))
        chunk_chars = int(guard.get("travel.intake_reader.chunk_chars"))
        prefill = str(guard.get("travel.intake_reader.prefill"))
    except Exception:                                  # noqa: BLE001 — 설정이 없으면 규칙으로
        return default
    console = settings_hook.operator_setting(tenant_id, "travel.intake_reader.mode")
    if console in ("on", "shadow", "off"):
        mode = console
    return {"mode": mode if mode in ("on", "shadow", "off") else "off", "num_predict": num_predict,
            "chunk_chars": max(200, chunk_chars), "prefill": prefill if prefill in ("on", "off") else "off"}


def _prefill(connect: Callable[[], Any], tenant_id: str, intake_id: UUID, *, tour: Any, kakao: Any, dining: Any) -> None:
    """`[2026-10-16 D-025]` 비서처럼 먼저 채우기(`prefill.py`) — 빈칸을 담당에게 보내 제안을 받고 맞춰 본 것만 「우리가 채움」으로 싣는다.
    ★실패해도 읽은 값 · 확인 화면은 그대로다(채우기만 빠지고 경고가 남는다). 그 사이 고객이 먼저 고쳤으면(판이 바뀌었으면) 하지 않는다."""
    from . import prefill as prefill_module

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT customer_id, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND status='review'",
                            (tenant_id, intake_id))
                row = cur.fetchone()
            if row is None or int(row[1]) != 1:
                return
            prefill_module.run(conn, tenant_id=tenant_id, customer_id=row[0], intake_id=intake_id, revision=1,
                               tour=tour, kakao=kakao, dining=dining)
    except Exception:                                  # noqa: BLE001 — 채우기 장애가 확인 화면을 막지 않는다
        log.warning("intake prefill failed intake=%s", intake_id, exc_info=True)


def rejudge(connect: Callable[[], Any], tenant_id: str, intake_id: UUID, revision: int) -> None:
    """고객이 고쳐 생긴 **새 판**의 식사를 다시 판정한다(뒤에서 — 고치기 응답을 기다리게 하지 않는다). `[2026-10-16 설계 대조 P2]`
    ★그 사이 또 고쳤거나(판이 바뀜) 등록했으면 돌리지 않는다 — 지난 판을 판정하는 데 모델을 부르지 않는다.
      판정 중에 판이 바뀌면 합치기 직전에 한 번 더 막는다(`judge.run`)."""
    from app.domains.travel_ops.components.team_hooks import dining_ledger

    if dining_ledger.agent_judge_runner() is None:
        return
    try:
        with connect() as conn:
            if review_module.intake_state(conn, tenant_id, intake_id) != ("review", revision):
                return
            sources = _sources(conn, tenant_id, intake_id)
    except Exception:                                  # noqa: BLE001 — 판정 장애가 고치기를 건드리지 않는다
        log.warning("dining agent rejudge failed intake=%s revision=%s", intake_id, revision, exc_info=True)
        return
    _dining_judge(connect, tenant_id, intake_id, sources, revision=revision)


def _dining_judge(connect: Callable[[], Any], tenant_id: str, intake_id: UUID, sources: list[dict[str, Any]],
                  revision: int | None = 1) -> None:
    """요식 판정 에이전트 — 확인 화면으로 넘긴 **뒤에** 식사를 판정해 그 판의 검사 줄에 합친다(`instances/dining/judge.run`). `[2026-10-13 · 2026-10-16]`
    ★규칙이 모르던 영업 · 휴무를 에이전트가 도구로 정했으면 그 줄을 바꾸고, 고객 조건 확인은 줄을 더한다. 화면 문장은 코드가 만든다.
      ★가드레일 `travel.dining.agent_judge.enabled`(기본 켜짐) · 모델이 있어야 돈다.
      실패해도 접수에 영향이 없다(그 줄은 규칙 검사 그대로 · 경고만 남긴다).
    `revision=None` 이면 지금 판(확인 화면일 때만 — 그 사이 등록 · 실패로 넘어갔으면 돌리지 않는다)."""
    from app.domains.travel_ops.components.team_hooks import dining_ledger

    runner = dining_ledger.agent_judge_runner()
    if runner is None:
        return
    try:
        with connect() as conn:
            if revision is None:
                with conn.cursor() as cur:
                    cur.execute("SELECT status, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
                    row = cur.fetchone()
                if row is None or row[0] != "review":
                    return
                revision = int(row[1])
            payload = review_module.load(conn, tenant_id, intake_id, revision)
        if not payload:
            return
        notes = "\n".join(s.get("transcript") or "" for s in sources)
        runner(connect, tenant_id=tenant_id, intake_id=intake_id, revision=revision, review=payload, notes=notes)
    except Exception:                                  # noqa: BLE001 — 판정 장애가 접수를 건드리지 않는다
        log.warning("dining agent judge failed intake=%s", intake_id, exc_info=True)


def reap_stalled(conn, *, tenant_id: str, intake_id: UUID) -> None:
    """뒤에서 읽던 일꾼이 죽어(서버 재시작 · 읽다 난 오류를 실패로 적지도 못한 DB 장애) **오래 갱신이 없는** 접수를 `fatal`(`stalled`)로 확정한다.

    ★이게 없으면 그 접수는 영원히 「읽는 중」으로 남는다(실시간 진행은 `stalled` 오류로 연결만 끝낼 뿐 접수 상태를 안 바꾼다). 기준은 실시간 진행의 `travel.op_stream.intake_stalled_seconds` 의 두 배. 읽는 동안 값이 적힐 때마다 갱신 시각이 오르므로(`_claim_sink`) 느리게 읽는 중인 접수는 해당되지 않는다."""
    from app.core.settings import get_guardrails

    # 실시간 진행의 「멈춤」(`stalled`, 연결만 끝내고 다시 연결할 수 있다)보다 두 배 기다린 뒤에야 **실패로 확정**한다 — 사진 받아쓰기 한 번은
    # 한 번의 긴 호출이라 그동안 갱신 시각이 오르지 않는다(실측 45~90초). 확정은 되돌릴 수 없으니 여유를 둔다
    seconds = 2 * float(get_guardrails().get("travel.op_stream.intake_stalled_seconds"))
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='fatal', stage='fatal', fatal_code='stalled', "
                    "fatal_detail='읽던 일이 멈춰 끝내지 못했다 — 다시 올려 주세요', updated_at=now() "
                    "WHERE tenant_id=%s AND intake_id=%s AND (status='reading' OR (status='review' AND stage='checking')) "
                    "AND now() - updated_at > make_interval(secs => %s)", (tenant_id, intake_id, seconds))
        if cur.rowcount:
            cur.execute("DELETE FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=1 AND method <> 'customer'",
                        (tenant_id, intake_id))


def public_status(status: str, stage: str) -> str:
    """조회와 실시간 진행 모두 먼저 채우기가 끝난 뒤에만 완료를 알린다."""
    return "reading" if status == "review" and stage == "checking" else status


def view(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID) -> dict[str, Any] | None:
    """확인 화면이 읽는 모양. ★남의 접수는 없는 것과 같다(None)."""
    from .reopen import frozen_entries as reopen_frozen_entries
    reap_stalled(conn, tenant_id=tenant_id, intake_id=intake_id)
    with conn.cursor() as cur:
        cur.execute("SELECT status, stage, revision, fatal_code, fatal_detail, trip_id, received_at, "
                    "reopen_trip_id, reopen_version, reopen_frozen "
                    "FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s",
                    (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            return None
        status, stage, revision, fatal_code, fatal_detail, trip_id, received_at, reopen_trip, reopen_version, frozen = row
        raw_status = status
        # 내부 수정은 review 상태가 필요하다. 먼저 채우는 동안 고객에게 완료를 알리지 않는다.
        status = public_status(status, stage)
        cur.execute("SELECT metadata FROM intake_test_scenarios WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s",
                    (tenant_id, intake_id, customer_id))
        scenario_row = cur.fetchone()
        test_scenario = scenario_row[0] if scenario_row else None
        sources = _sources(conn, tenant_id, intake_id)
        cur.execute("SELECT source_id, field, value_json, method, evidence, needs_review, note FROM intake_claims "
                    "WHERE tenant_id=%s AND intake_id=%s AND revision=%s ORDER BY created_at, claim_id",
                    (tenant_id, intake_id, revision))
        claims = [dict(zip(("source_id", "field", "value", "method", "evidence", "needs_review", "note"), r))
                  for r in cur.fetchall()]
    # ★고객이 고친 값이 같은 칸의 앞 값을 덮는다 — 화면에는 칸마다 하나만(이전 값은 이전 판에 남아 있다)
    raw_claims = claims
    claims = effective(claims)
    check = None
    review = review_error = None
    if status in ("review", "confirmed"):
        built = assemble(intake_id=str(intake_id), revision=revision, sources=sources, claims=claims)
        check = {"ready": not built.problems and bool(built.body["items"]),
                 "problems": [p.as_dict() for p in built.problems],
                 "filled": built.filled, "items": len(built.body["items"]), "title": built.body["title"],
                 "plan": built.plan,
                 # ★`[2026-10-16 D-025 후속]` 읽은 성향 · 조건을 담당에 넘길 것 — 열쇠 · 담당 · 원문 조각 · 「우리가 채움」(filled) / 「고객 답 먼저」(customer)
                 "handoff": reading_prefs.view(built.reading, survey=survey_answers.to_survey(
                     survey_answers.stored(conn, tenant_id=tenant_id, intake_id=intake_id)))}
        review, review_error = _review_of(conn, tenant_id, intake_id, revision, sources, claims)
        review = review_module.public(review, tenant_id=tenant_id)               # 내부 칸(이동 재사용 키 · 장소 행 번호)은 응답에 싣지 않는다
        missing_cards = [p.as_dict() for p in built.problems if p.code == "source_item_missing"]
        if review is not None and missing_cards:
            review = {**review, "ready": False, "source_coverage": {"status": "missing", "problems": missing_cards}}
    out_sources = []
    for source in sources:
        mine = [c for c in claims if c["source_id"] == source["source_id"]]
        lines = (source["transcript"] or "").splitlines()
        # ★읽힌 줄은 덮이기 전의 모든 값에서 센다 — 「2026-10-15」 · 「2026-10-16」 두 날짜 줄은 같은 칸 이름(`days[?].date`)이라 `effective` 가
        #   앞 줄을 지워 첫 날짜 줄이 「안 읽은 줄」로 보였다(2026-10-03 실서버 확인)
        read_lines = {c["evidence"].get("line") for c in raw_claims if c["source_id"] == source["source_id"]}
        out_sources.append({
            "source_id": str(source["source_id"]), "kind": source["kind"], "filename": source["filename"],
            "transcribed": source["transcribed"], "missing": source["missing_json"], "differs": source.get("differs_json") or [], "seconds": source["seconds"],
            "lines": [{"no": n, "text": text, "read": n in read_lines} for n, text in enumerate(lines, start=1)],
            "items": _items(mine), "trip": _trip_fields(mine),
            # 남은 줄에 모델이 가리킨 결과 — 몇 개 받고 무엇을 버렸나(원문에 없는 인용). 모델을 안 불렀으면 None
            "reading": next((c["value"] for c in mine if c["field"] == "reading.llm"), None),
            # ★`[2026-10-16 D-025]` 이해 에이전트가 읽은 것 중 일정 칸이 아닌 것 — 구간 수단 · 조건 · 성향 · 요청 조각 · 가드 판정(확인 화면 「이렇게 이해했어요」)
            "understanding": _understanding(next((c["value"] for c in mine if c["field"] == "reading.agent"), None))})
    if review is not None and test_scenario is not None:
        review = {**review, "test_scenario": test_scenario}
    # ★`[2026-10-19 사용자 지시]` 로딩 중 질문 — 계획서에서 읽은 칸은 빼고 빈 칸만(상한 없음). 이해 단계 결과(`reading.agent`)가 원본마다 다 나왔거나
    #   읽기가 끝났으면(확인 화면 · 실패) 둘째 목록을 한 번 정한다(`survey_answers.loading_questions`)
    agent_rows = {c["source_id"] for c in raw_claims if c["field"] == "reading.agent"}
    reading_done = raw_status != "reading" or (bool(sources) and all(s["source_id"] in agent_rows for s in sources))
    # ★`[2026-10-19 사용자 결정]` 빠른 거름에 걸린 접수(`screened`)는 로딩 설문을 내지 않는다 — 웹은 입력 화면으로 되돌린다(고객 글 보존)
    screened = _screened_mark(conn, tenant_id, intake_id)
    loading = ({"questions": [], "skipped_by_reading": [], "phase": None} if screened is not None else
               survey_answers.loading_questions(conn, tenant_id=tenant_id, intake_id=intake_id, reading_done=reading_done,
                                                found=reading_prefs.carry(raw_claims)))
    return {"intake_id": str(intake_id), "status": status, "stage": stage, "stage_label": STAGES.get(stage, stage),
            "test_scenario": test_scenario,
            # ★`[2026-10-19]` 빠른 거름 — `{code: empty | off_topic, rule}` 이면 읽지 않고 돌려보낸 접수다(그 밖에는 null)
            "screened": screened,
            "revision": revision, "fatal": {"code": fatal_code, "detail": fatal_detail} if fatal_code else None,
            "trip_id": str(trip_id) if trip_id else None, "received_at": received_at.isoformat(),
            # ★`[2026-10-13]` 등록한 여행을 다시 연 수정 접수(`reopen.py`) — 어느 여행의 몇 판인가 · 접수에 넣지 않고 그대로 두는 일정. 보통 접수는 None
            "reopen": ({"trip_id": str(reopen_trip), "version": reopen_version,
                        "frozen_item_ids": [e["item_id"] for e in reopen_frozen_entries(frozen)],
                        # `[2026-10-15 ST4F-490]` 고정한 이유 — 화면은 `past` 만 「지난 일정」이라 부른다
                        "frozen": reopen_frozen_entries(frozen)}
                       if reopen_trip else None),
            "sources": out_sources, "check": check, "review": review, "review_error": review_error,
            # ★`[2026-10-16 D-025]` 먼저 채운 기록 — 일정마다 「우리가 채움」 + 이유(`filled[].item` = 검사의 일정 id) · 고객에게 물을 것(`questions`)
            "prefill": _prefill_view(next((c["value"] for c in reversed(claims) if c["field"] == "reading.prefill"), None)),
            # ★`[2026-10-20 사용자 지시]` 해석 확인 질문 — 읽기 AI 와 규칙이 다르게 읽은 줄. 1안(AI 의 읽기)이 맨 위 · 답은 `POST …/interpretations`
            "interpretations": interpretations_module.view(raw_claims, {str(s["source_id"]): int(s["position"]) for s in sources}),
            # ★`[2026-10-06]` 로딩 중 질문. 답은 `POST …/survey` 로 한 문항씩 저장한다(`survey_answers.py`).
            #   `[2026-10-19]` 계획서에서 읽은 칸은 빼고(`skipped_by_reading`) 빈 칸만 · 상한 없음 · 두 번에 정한다(`questions_phase`)
            "questions": loading["questions"], "skipped_by_reading": loading["skipped_by_reading"],
            "questions_phase": loading["phase"], "questions_version": survey_answers.QUESTION_SET_VERSION,
            "needs_review": [{"field": c["field"], "value": c["value"], "note": c["note"],
                              "evidence": c["evidence"]} for c in claims if c["needs_review"]]}


def _screened_mark(conn, tenant_id: str, intake_id: UUID) -> dict[str, Any] | None:
    """빠른 거름 기록(907). 칸이 없는 DB 면 None(경고) — 그때는 거른 접수가 없다."""
    try:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SELECT screened FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s", (tenant_id, intake_id))
            row = cur.fetchone()
    except Exception:                                  # noqa: BLE001
        log.warning("intake screened mark unreadable intake=%s (migration 907?)", intake_id, exc_info=True)
        return None
    value = row[0] if row else None
    return {"code": value.get("code"), "rule": value.get("rule")} if isinstance(value, dict) else None


def _understanding(value: Any) -> dict[str, Any] | None:
    """`reading.agent` 값 줄 → 화면에 보일 것만(걸린 초 · 버린 수 · 모델 이름은 빼고). 에이전트를 안 썼으면(실패 · 그림자) None."""
    if not isinstance(value, dict) or not value.get("used"):
        return None
    return {k: value.get(k) or ([] if k != "guard" else None)
            for k in ("moves", "conditions", "preferences", "pieces", "gaps", "missing", "guard")}


def _prefill_view(value: Any) -> dict[str, Any] | None:
    """`reading.prefill` 값 줄 → 화면 모양. 담당의 제안 원본(`proposals` · `rounds`)은 싣지 않는다 — 운영 기록이다."""
    if not isinstance(value, dict):
        return None
    return {"filled": value.get("filled") or [], "questions": value.get("questions") or [], "kept": value.get("kept") or []}


def _review_of(conn, tenant_id: str, intake_id: UUID, revision: int, sources: list[dict[str, Any]],
               claims: list[dict[str, Any]], *, force: bool = False, quick: bool = False,
               **options: Any) -> tuple[dict[str, Any] | None, str | None]:
    """그 판의 검사(`review.py`) — 저장된 것이 있으면 그것, 없으면 지금 계산한다. 실패하면 (None, 코드): 확인 화면은 읽은 값으로 계속 간다.
    ★DB 오류가 바깥 트랜잭션을 망가뜨리지 않게 세이브포인트 안에서 부른다(마이그레이션 040 이 안 올라간 DB 도 읽기는 된다)."""
    try:
        with conn.transaction():
            review_module.intake_state(conn, tenant_id, intake_id)
            return review_module.ensure(conn, tenant_id=tenant_id, intake_id=intake_id, revision=revision,
                                        sources=sources, claims=claims, force=force, quick=quick,
                                        previous_revision=revision - 1 if revision > 1 else None, **options), None
    except Exception:                                     # noqa: BLE001
        log.warning("intake review failed intake=%s revision=%s", intake_id, revision, exc_info=True)
        return None, "review_failed"


# ── 고치기 · 등록 준비 (3주차) ───────────────────────────────────────
#: 고객이 고칠 수 있는 칸. ★값은 서버가 모양을 확인한다 — 받은 글자를 그대로 믿지 않는다
#: `locked` — 고객이 「꼭 넣을 일정」으로 고정(등록되면 `detail.customer_pinned`). `removed` — true 로 빼고 false 로 되돌린다
_ITEM_FIELDS = {"title", "date", "starts_at", "ends_at", "kind", "place", "booking_no", "removed", "locked"}
#: 고객이 지도·후보·검색에서 고른 장소를 받는 범위 — 서울 하나(루트 사실표). ★우리가 고른 값(2026-09-30 「지도에서 장소 고르기」 계획과 같다)
SEOUL_LAT, SEOUL_LON = (37.4, 37.72), (126.7, 127.3)
_PICK_ORIGINS = ("tour_api", "kakao", "places", "search", "map", "customer_pick")
_CONTENT_ID = re.compile(r"^\d{1,12}$")
_TRIP_FIELDS = {"title", "party_size", "first_day", "taxi_pricing"}
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
#: 「일정 짜 줘」 모양 — 일정·코스·계획을 짜/만들어/추천해 달라는 말
PLAN_ASK = re.compile(r"(일정|코스|계획|동선|여행)\S{0,3}\s*(?:(?:좀|다시|새로)\s*)?(짜|만들어|추천해|세워|잡아)\s*"
                      r"(줘|주세요|줄래|주실|주라|달라)")


class IntakeConflict(ValueError):
    """낡은 확인 화면 — 그 사이 판이 바뀌었거나 아직 등록할 수 없는 상태다."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail


def edit(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int,
         edits: list[dict[str, Any]], tour: Any = None, kakao: Any = None, via: str | None = None,
         dining: Any = None, learn_aliases: bool = True, reflow: bool = False, check: bool = True) -> int:
    """고객이 고친 값 → **새 판**(revision + 1). 앞 판의 값은 그대로 남는다(근거를 지우지 않는다, 설계서 §5).

    ★`[2026-10-20 사용자 지시 — 수정 화면은 저장만, 검사는 「다시 제출」 때 한 번]` `check=False` 면 **저장만** 한다: 장소를 바꿔도 앞뒤 시각 재배치
    (`direct_schedule.fit` — 이동 계산기를 부른다)를 하지 않고, 새 판의 검사는 계산기 없이(`review.ensure(quick=True)`) `checked: false` 로 남긴다.
    고객이 「다시 제출」을 누르면 `revalidate` 가 계산기로 한 번에 검사한다. 일정 수 · 기간(7일) 같은 값 검사는 그대로 한다.

    `edits` = [{"source_id", "field", "value"}]. 장소는 `{"name": "…"}` 로 받아 **다시 찾고**, 찾은 곳 하나를
    싣는다. `{"none": true}` 는 「장소 없음」(자유시간 · 이름 없는 호텔). 돌려주는 값은 새 판 번호.
    """
    if not edits:
        raise IntakeRejected("no_edits", "고칠 값이 없습니다")
    from contextlib import nullcontext

    tour = with_catalog(tour, lambda: nullcontext(conn), tenant_id)       # ★`[2026-10-15]` 고객이 친 장소 이름도 관광공사가 못 찾으면 우리 장소 목록에서
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, revision, reopen_trip_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s "
                    "AND customer_id=%s FOR UPDATE", (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            raise LookupError("intake")
        status, current, reopened = row
        if status != "review":
            raise IntakeConflict("intake_not_editable", f"지금은 고칠 수 없습니다(상태 {status})", status=status)
        if revision != current:
            raise IntakeConflict("stale_revision", "그 사이 다른 화면에서 고쳤습니다 — 새로 불러와 주세요",
                                 current_revision=current)
        if reopened is not None and any(str(e.get("field") or "").startswith("trip.") for e in edits):
            # ★`[2026-10-13]` 수정 접수(`reopen.py`)는 일정만 고친다 — 등록한 여행의 이름 · 인원 · 첫날은 「완료」가 새 판에 싣지 않는다
            raise IntakeRejected("trip_field_locked", "등록한 여행의 이름 · 인원 · 첫날은 여기서 바꾸지 않아요")
        source_rows = _sources(conn, tenant_id, intake_id)
        sources = {str(s["source_id"]) for s in source_rows}
        our_places = None
        rows = []
        current_claims = effective(_claims(conn, tenant_id, intake_id, current))
        locked_now = {(str(c["source_id"]), _item_no(c["field"])) for c in current_claims
                      if c["field"].startswith("items[") and c["field"].endswith(".locked") and c["value"] is True}
        # ★칸 이름을 하나로 맞춘다 — `items[01].locked` · `items[ 1 ].place` 처럼 같은 항목을 다르게 적어 잠금 검사를 피하지 못하게
        edits = [{**e, "field": _canonical(str(e.get("field") or ""))} for e in edits]
        batch = [(str(e.get("source_id") or ""), str(e.get("field") or ""), e.get("value")) for e in edits]
        unlocking = {(sid, _item_no(f)) for sid, f, v in batch if f.endswith(".locked") and v is False}
        existing = {(str(c["source_id"]), _item_no(c["field"])) for c in current_claims if c["field"].startswith("items[")}
        added = _new_items(batch, existing, sources)
        locking = {(sid, _item_no(f)) for sid, f, v in batch if f.endswith(".locked") and v is True}
        for sid, field_name, value in batch:
            # 신규 항목은 다음 번호와 필수 여섯 칸을 한 번에 보낸 요청만 허용한다.
            if field_name.startswith("items[") and field_name.count("]") == 1 and (sid, _item_no(field_name)) not in existing | added:
                raise IntakeRejected("unknown_item", f"{field_name}: 이 접수에 없는 일정입니다")
            # ★고정은 그 판의 검사로만 판단한다 — 같은 요청에서 장소를 비우거나 시각을 바꾸는 것과 섞으면 고정이 바뀐 값에 걸린다. 고정은 따로 보낸다
            if field_name.startswith("items[") and not field_name.endswith(".locked") and (sid, _item_no(field_name)) in locking:
                raise IntakeRejected("lock_with_changes", f"{field_name}: 일정을 고정하는 요청에 다른 고치기를 섞을 수 없습니다 — 따로 보내 주세요")
            # ★고정한 일정은 바꾸거나 빼지 못한다 — 잠금을 먼저 풀어야 한다(같은 요청에 잠금 풀기가 있으면 함께 된다)
            if field_name.startswith("items[") and not field_name.endswith(".locked") and field_name.count("]") == 1:
                key = (sid, _item_no(field_name))
                if key in locked_now and key not in unlocking:
                    raise IntakeConflict("item_locked", "고정한 일정이라 바꿀 수 없습니다 — 잠금을 먼저 풀어 주세요",
                                         field=field_name)
        for entry in edits:
            source_id, field_name = str(entry.get("source_id") or ""), str(entry.get("field") or "")
            if field_name.startswith("items[") and source_id not in sources:
                raise IntakeRejected("unknown_source", f"{field_name}: 이 접수의 원본이 아닙니다")
            if field_name == "trip.taxi_pricing" and not settings_hook.taxi_call_product_enabled(tenant_id):
                # ★`[2026-10-14 핫픽스]` 화면에서 칸을 감췄어도 직접 보내는 요청은 여기서 막는다(관리 콘솔 스위치가 켜져야 받는다)
                raise IntakeRejected("taxi_pricing_disabled", "택시 호출 상품 고르기는 지금 쓰지 않습니다")
            value, evidence, note = _checked(field_name, entry.get("value"))
            if field_name.startswith("items[") and field_name.endswith(".title"):
                previous_title = next((c for c in current_claims if str(c["source_id"]) == source_id and c["field"] == field_name), {})
                evidence = schedule_cards.edited_title_evidence(evidence, previous_title)
            if field_name.endswith(".locked") and value is True:
                _require_lockable(conn, tenant_id, intake_id, current, source_rows, current_claims, source_id, field_name)
            if field_name.endswith(".place") and isinstance(value, dict) and value.get("content_id"):
                value = _verified_content_id(conn, tenant_id, value)
            if field_name.endswith(".place") and isinstance(value, dict) and value.get("source") == "customer_pick":
                value = _linked_ledger_pick(conn, tenant_id, value)
            if field_name.endswith(".place") and value is not None and "latitude" not in value:
                if our_places is None:
                    our_places = _our_places(conn, tenant_id, trip_id=reopened)
                typed = str(value["name"]).strip()
                # ★`[2026-10-05]` 식사 항목이면 요식 원장부터 찾는다(팀 판 — 같은 요청에서 함께 고친 종류가 먼저, 없으면 지금 판의 종류)
                kind = _item_kind(cur, tenant_id, intake_id, current, source_id, field_name, edits)
                value, evidence, note = _typed_place(value, our_places, tour, kakao, dining,
                                                     kind_hint="dining" if kind == "dining" else None,
                                                     near=_edit_place_anchor(cur, tenant_id, intake_id, current, source_id, field_name),
                                                     conn=conn)
                # 원래 읽은 이름 → 고객이 고친 이름을 별칭으로 쌓는다(다음 고객은 안 고쳐도 되게)
                cur.execute("SELECT value_json FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=%s "
                            "AND source_id=%s AND field=%s ORDER BY created_at DESC LIMIT 1",
                            (tenant_id, intake_id, current, source_id, field_name[:-len("place")] + "title"))
                was = cur.fetchone()
                if learn_aliases and was and isinstance(was[0], str):
                    # ★`[2026-10-15]` 채팅 「A 대신 B 가자」는 이름 고침이 아니라 **일정 바꾸기**다 — 별칭으로 쌓으면 다음 계획에서 A 라고 적어도 B 로 읽힌다
                    #   (x600 실서버: 「경복궁 대신 창덕궁」 뒤 새 계획의 「경복궁」이 창덕궁으로 찾아졌다). 채팅 고치기는 `learn_aliases=False`
                    remember_alias(cur, tenant_id, customer_id, was[0], typed)
            if via:
                evidence = {**evidence, "via": via}            # 전체 자동 추천이 낸 값이면 그렇게 적는다(고객이 고른 값과 구별)
            rows.append((source_id if field_name.startswith("items[") else None, field_name, value, evidence, note))
        if any(field.endswith(".place") and isinstance(value, dict) and value.get("latitude") is not None
               for _, field, value, _, _ in rows):
            rows = _link_stay_places(review_module.load(conn, tenant_id, intake_id, current), rows)
        # 직접 고른 장소도 자동 추천과 마찬가지로 이동시간을 반영한다. 저장 전에
        # 계산하므로 불가능한 배치는 claim·별칭·revision을 모두 원래대로 유지한다.
        touched = {(str(sid), _item_no(field)) for sid, field, value, _, _ in rows
                   if field.endswith(".place") and isinstance(value, dict) and value.get("latitude") is not None}
        explicit_times = {(str(sid), _item_no(field)) for sid, field, value, _, _ in rows
                          if field.startswith("items[") and field.endswith((".starts_at", ".ends_at", ".date"))} if reflow else set()
        touched |= explicit_times
        if added and not check:
            from ..planning.planner import MAX_DAYS
            from .assemble import collect
            prospective = [{**c, "source_id": str(c["source_id"]) if c["source_id"] is not None else None}
                           for c in current_claims] + [
                {"source_id": sid, "field": field, "value": value, "method": "customer", "evidence": evidence,
                 "needs_review": False, "note": note} for sid, field, value, evidence, note in rows]
            got = collect(sources=[{**s, "source_id": str(s["source_id"])} for s in source_rows], claims=prospective)
            dates = sorted({r["date"] for r in got.rows if r["date"]})
            if dates and (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days >= MAX_DAYS:
                raise IntakeRejected("trip_too_long", "서울 여행은 최대 7일까지 추가할 수 있습니다")
        if (touched or added) and via != "autofix" and check:
            from . import direct_schedule
            from .assemble import collect
            prospective = [{**c, "source_id": str(c["source_id"]) if c["source_id"] is not None else None}
                           for c in current_claims] + [
                {"source_id": sid, "field": field, "value": value, "method": "customer", "evidence": evidence,
                 "needs_review": False, "note": note} for sid, field, value, evidence, note in rows]
            got = collect(sources=[{**s, "source_id": str(s["source_id"])} for s in source_rows], claims=prospective)
            if added:
                from ..planning.planner import MAX_DAYS
                dates = sorted({r["date"] for r in got.rows if r["date"]})
                if dates and (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days >= MAX_DAYS:
                    raise IntakeRejected("trip_too_long", "서울 여행은 최대 7일까지 추가할 수 있습니다")
            party = (got.trip.get("party_size") or {}).get("value")
            try:
                adjusted = direct_schedule.fit(conn, tenant_id=tenant_id, rows=got.rows, touched=touched, party_size=party,
                                               mode_picks=review_module.picked_modes(prospective), fixed_times=explicit_times, forward_only=reflow)
            except direct_schedule.ScheduleConflict as exc:
                raise IntakeConflict(exc.code, str(exc)) from exc
            for change in adjusted:
                evidence = {"source": "customer", "via": "direct_schedule", "basis": change["basis"]}
                if change.get("derived_stay_end") is True:
                    evidence["derived_stay_end"] = True
                note = "장소 변경에 따라 앞뒤 이동시간을 반영해 재배치" + ("(어림 이동시간)" if change["basis"] == "estimate" else "")
                rows.append((change["source_id"], change["field"], change["value"], evidence, note))
        new = current + 1
        # 앞 판을 그대로 옮기고(만든 순서 유지) 고친 값을 뒤에 얹는다 — 칸마다 마지막 값이 이긴다
        cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, method, "
                    "evidence, needs_review, note, created_at) SELECT intake_id, tenant_id, %s, source_id, field, "
                    "value_json, method, evidence, needs_review, note, created_at FROM intake_claims "
                    "WHERE tenant_id=%s AND intake_id=%s AND revision=%s",
                    (new, tenant_id, intake_id, current))
        for source_id, field_name, value, evidence, note in rows:
            cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, value_json, "
                        "method, evidence, needs_review, note, created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,'customer',%s,false,%s, clock_timestamp())",
                        (intake_id, tenant_id, new, source_id or None, field_name,
                         json.dumps(value, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False, default=str),
                         note))
        cur.execute("UPDATE trip_intakes SET revision=%s, updated_at=now() WHERE tenant_id=%s AND intake_id=%s",
                    (new, tenant_id, intake_id))
        # 검사까지 같은 트랜잭션에 저장한다. 새 장소만 반영되고 이동 검사는
        # 옛 상태인 중간 판을 다른 화면에서 읽지 않게 한다.
        # ★`[2026-10-20 사용자 결정]` 시각 맞추기가 이동 계산 시간 한도에 닿아 어림으로 맞춘 판이 있으므로, 시간표로 못 구한 구간은 「확인 필요」로 센다
        found, error = _review_of(conn, tenant_id, intake_id, new, source_rows,
                                  effective(_claims(conn, tenant_id, intake_id, new)), force=True, quick=not check,
                                  estimate_needs_review=check)
        if found is None:
            raise IntakeConflict("schedule_check_failed", "변경 후 검사를 끝내지 못해 저장하지 않았어요. 다시 시도해 주세요.", reason=error)
    return new


def restore(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int,
            restore_revision: int, item: tuple[UUID, int] | None = None) -> dict[str, Any]:
    """완료된 과거 판의 원값을 새 판으로 복원한다. 보호·검사 실패는 전체 롤백한다."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SELECT status, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s "
                    "FOR UPDATE", (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            raise LookupError("intake")
        status, current = row
        if status != "review":
            raise IntakeConflict("intake_not_editable", "지금은 전체 되돌리기를 할 수 없습니다", status=status)
        if revision != current:
            raise IntakeConflict("stale_revision", "그 사이 다른 화면에서 고쳤습니다 — 새로 불러와 주세요",
                                 current_revision=current)
        old_review = review_module.load(conn, tenant_id, intake_id, restore_revision)
        if not 1 <= restore_revision < current or not old_review or old_review.get("revision") != restore_revision:
            raise IntakeConflict("restore_revision_invalid", "복원할 완료된 이전 판을 찾지 못했어요")
        before = effective(_claims(conn, tenant_id, intake_id, restore_revision))
        now = effective(_claims(conn, tenant_id, intake_id, current))
        if not before:
            raise IntakeConflict("restore_revision_invalid", "복원할 이전 값이 없어요")
        if item is not None:
            source_id, index = item
            from . import lodging_context
            keys = {(str(source_id), index)}
            for snapshot in (old_review, review_module.load(conn, tenant_id, intake_id, current) or {}):
                target = next((x for x in snapshot.get("items", []) if (str(x["source_id"]), x["index"]) == (str(source_id), index)), None)
                if target:
                    keys.update((str(x["source_id"]), x["index"]) for x in lodging_context.group_for(snapshot["items"], target))
            def selected(claim):
                return claim["field"].startswith("items[") and (str(claim["source_id"]), _item_no(claim["field"])) in keys
            old_item = [claim for claim in before if selected(claim)]
            if not old_item or not any(selected(claim) for claim in now):
                raise IntakeConflict("restore_item_invalid", "복원할 일정을 현재 판과 이전 판에서 확인하지 못했어요")
            before = [claim for claim in now if not selected(claim)] + old_item
        source_rows = _sources(conn, tenant_id, intake_id)
        _protect_restore(now, before, source_rows)
        new = current + 1
        # 유효 값만 복사하여 같은 시각 claim의 UUID 정렬에 따라 값이 뒤집히지 않게 한다.
        # 원래 method/evidence도 유지한다. 빈 값·없던 장소를 임의의 값으로 바꾸지 않는다.
        for claim in before:
            cur.execute("INSERT INTO intake_claims (intake_id,tenant_id,revision,source_id,field,value_json,method,"
                        "evidence,needs_review,note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (intake_id, tenant_id, new, claim["source_id"], claim["field"],
                         json.dumps(claim["value"], ensure_ascii=False, default=str), claim["method"],
                         json.dumps(claim["evidence"], ensure_ascii=False, default=str), claim["needs_review"], claim["note"]))
        cur.execute("UPDATE trip_intakes SET revision=%s, updated_at=now() WHERE tenant_id=%s AND intake_id=%s",
                    (new, tenant_id, intake_id))
        # 장소 재조회나 direct_schedule.fit 없이 원값 그대로 다시 검사한다.
        found, error = _review_of(conn, tenant_id, intake_id, new, source_rows, before, force=True)
        if found is None:
            raise IntakeConflict("schedule_check_failed", "되돌린 후 검사를 끝내지 못해 저장하지 않았어요", reason=error)
        return view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)


def _link_stay_places(snapshot, rows):
    """검증된 장소 선택을 연결된 호텔·조식에 함께 싣는다. 보호 항목은 우회하지 않는다."""
    from . import lodging_context as context
    items = (snapshot or {}).get("items", [])
    proposed = {(str(sid), _item_no(field)): (value, evidence, note)
                for sid, field, value, evidence, note in rows if field.endswith(".place")}
    out = list(rows)
    for members in context.groups(items):
        if len(members) < 2:
            continue
        choices = [proposed[(str(x["source_id"]), x["index"])] for x in members
                   if (str(x["source_id"]), x["index"]) in proposed]
        located = [c for c in choices if isinstance(c[0], dict) and c[0].get("latitude") is not None]
        if not located:
            continue
        value, evidence, note = located[0]
        if any(not context.same_place(value, c[0]) for c in located[1:]):
            raise IntakeConflict("conflicting_stays", "같은 숙소에 서로 다른 장소를 함께 지정할 수 없어요")
        if len(located) != len(choices):
            raise IntakeConflict("conflicting_stays", "공통 숙소 선택과 장소 비우기를 함께 할 수 없어요")
        for member in members:
            if context.protected(member):
                if not context.same_place(value, member.get("place")):
                    raise IntakeConflict("item_locked" if member.get("locked") else "item_booked",
                                         "연결된 고정·예약 숙소와 달라서 저장하지 않았어요")
                continue
            key = (str(member["source_id"]), member["index"])
            parts = member.get("parts") or member.get("_lodging_parts")
            if key in proposed and parts:
                out = [(sid, field, val, {**ev, "lodging_parts": parts}, nt)
                       if (str(sid), _item_no(field)) == key and field.endswith(".place") else (sid, field, val, ev, nt)
                       for sid, field, val, ev, nt in out]
            if key not in proposed and not context.same_place(value, member.get("place")):
                linked = context.as_place(value, member)
                linked = {k: v for k, v in linked.items() if k not in ("basis", "content_type_id", "ref")}
                out.append((key[0], f"items[{key[1]}].place", linked, {**evidence, "linked_stay": members[0]["id"], "lodging_parts": parts},
                            note or "여행 공통 숙소에 연결"))
    return out


def _protect_restore(now, before, sources) -> None:
    """현재 보호 일정의 값·상태·실제 조립 시각을 바꾸는 역사 복원을 막는다."""
    def fields(claims):
        out = {}
        for claim in claims:
            field = claim["field"]
            if field.startswith("items["):
                out.setdefault((str(claim["source_id"]), _item_no(field)), {})[field.split("].", 1)[-1]] = claim["value"]
        return out

    current, target = fields(now), fields(before)
    from .assemble import collect
    def assembled(claims):
        return {(str(r["source_id"]), r["index"]): r for r in collect(sources=sources, claims=claims).rows}
    current_rows, target_rows = assembled(now), assembled(before)
    for key, values in current.items():
        locked = values.get("locked") is True
        booked = values.get("booked") is True or bool(values.get("booking_no"))
        if not locked and not booked:
            continue
        desired = target.get(key)
        # 잠금·예약 상태 자체를 되돌려 보호를 없애는 것도 허용하지 않는다.
        same_values = desired is not None and {**values, "removed": values.get("removed", False),
                                               "locked": values.get("locked", False)} == {
            **desired, "removed": desired.get("removed", False), "locked": desired.get("locked", False)}
        a, b = current_rows.get(key), target_rows.get(key)
        same_slot = (a is None and b is None) or (a is not None and b is not None and
                    all(a.get(f) == b.get(f) for f in ("date", "start", "end", "place", "kind", "title")))
        if not same_values or not same_slot:
            raise IntakeConflict("item_locked" if locked else "item_booked",
                                 "잠금·예약 일정이 달라져 전체 되돌리기를 저장하지 않았어요")


def _new_items(batch, existing, sources) -> set[tuple[str, int]]:
    """신규 한 항목을 기존 edits 계약으로 생성한다. 삭제 번호도 재사용하지 않는다."""
    required = {"title", "date", "starts_at", "ends_at", "kind", "place"}
    added = {(sid, _item_no(f)) for sid, f, _ in batch if f.startswith("items[") and (sid, _item_no(f)) not in existing}
    if not added:
        return set()
    if len(added) != 1:
        raise IntakeRejected("unknown_item", "새 일정은 한 번에 하나씩 추가해 주세요")
    sid, index = next(iter(added))
    next_index = max((i for s, i in existing if s == sid), default=-1) + 1
    fields = {f.rsplit(".", 1)[-1]: v for s, f, v in batch if s == sid and _item_no(f) == index}
    if sid not in sources or index != next_index or not required <= fields.keys():
        raise IntakeRejected("unknown_item", "새 일정은 다음 번호에 이름·날짜·시작·끝·종류·장소를 함께 보내 주세요")
    if len([1 for s, f, _ in batch if s == sid and _item_no(f) == index]) != len(fields):
        raise IntakeRejected("invalid_value", "새 일정의 같은 칸을 두 번 보낼 수 없습니다")
    for name in required:
        _checked(f"items[{index}].{name}", fields[name])
    if fields["starts_at"] >= fields["ends_at"]:
        raise IntakeRejected("invalid_value", "새 일정의 끝은 시작보다 늦어야 합니다")
    if fields.get("removed") is True or fields.get("locked") is True:
        raise IntakeRejected("invalid_value", "새 일정은 추가한 뒤 확인하고 고정하거나 빼 주세요")
    place = fields["place"]
    if not isinstance(place, dict) or place.get("none") is True:
        raise IntakeRejected("invalid_value", "새 일정의 장소를 먼저 골라 주세요")
    return added


def current_review(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int | None = None,
                   force: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    """(접수 상태, 현재 판의 검사). 남의 접수는 LookupError · 아직 확인 화면이 아니면 IntakeConflict · `revision` 이 낡았으면 IntakeConflict.
    후보 · 검색 · 자동 추천 · 재검증이 같은 앞문으로 들어온다."""
    with conn.cursor() as cur:
        cur.execute("SELECT status, revision FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND customer_id=%s",
                    (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
    if row is None:
        raise LookupError("intake")
    status, current = row
    if status != "review":
        raise IntakeConflict("intake_not_editable", f"지금은 고칠 수 없습니다(상태 {status})", status=status)
    if revision is not None and revision != current:
        raise IntakeConflict("stale_revision", "그 사이 다른 화면에서 고쳤습니다 — 새로 불러와 주세요", current_revision=current)
    sources = _sources(conn, tenant_id, intake_id)
    claims = effective(_claims(conn, tenant_id, intake_id, current))
    found, error = _review_of(conn, tenant_id, intake_id, current, sources, claims, force=force)
    if found is None:
        raise IntakeConflict("review_failed", "검사를 계산하지 못했습니다 — 잠시 뒤 다시 시도해 주세요", reason=error)
    return {"status": status, "revision": current}, found


def revalidate(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int) -> dict[str, Any]:
    """**새 판을 만들지 않고** 같은 판의 검사를 처음부터 다시 계산해 그 판의 저장된 검사를 바꾼다 — 운영시간 표가 새벽에 바뀌었거나 이동 계산기 답이 달라졌을 수 있다.
    돌려주는 것은 `view` 와 같은 모양. 이동은 앞 판의 값을 재사용하지 않고 다시 잰다."""
    with conn.transaction():
        current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision, force=True)
    return view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)


class _DryRunRollback(Exception):
    """미리 보기를 읽은 뒤 저장 구간을 되돌리려고 던지는 것 — 오류가 아니다."""


def autofix(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int, tour: Any = None,
            kakao: Any = None, dry_run: bool = False, dining: Any = None, item_id: str | None = None) -> dict[str, Any]:
    """**전체 자동 추천** — 확인이 필요한 일정을 검증한 대체 일정(장소 · 시각)으로 한 번에 바꾼다(`autofix.py`).
    바꿀 것이 있으면 `edits` 와 같은 길로 **새 판** 하나가 된다. 없으면 판을 만들지 않고 이유(`kept`)만 돌려준다.

    ★`dry_run` `[2026-10-03 ui 세션 요청서 3번]` — **저장하지 않고** 바뀔 모습만 돌려준다. 실제 적용과 **같은 길**(`edit`)로 새 판을 만들어 `view` 를 읽은 뒤 그 저장 구간을
      되돌린다(세이브포인트 롤백) — 그래서 미리 보기의 검사가 적용한 결과와 같다(따로 흉내 내는 계산이 아니다). 응답의 `view.preview` 가 참이고 `view.revision` 은 적용하면 생길 판 번호다.
      바꿀 것이 없으면 현재 모습 그대로(`preview` 없음)."""
    from . import autofix as autofix_module

    _, found = current_review(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision)
    if item_id is not None and not any(item["id"] == item_id for item in found["items"]):
        raise LookupError("intake item not found")
    got = autofix_module.plan(conn, tenant_id=tenant_id, review=found, kakao=kakao, item_id=item_id)
    edits = [{"source_id": c["source_id"], "field": f"items[{c['index']}].{e['field']}", "value": e["value"]}
             for c in got["changes"] for e in c["edits"]]
    new = revision
    changed = [{k: v for k, v in c.items() if k != "edits"} for c in got["changes"]]
    if edits and dry_run:
        preview: dict[str, Any] | None = None
        try:
            with conn.transaction():                       # 세이브포인트 — 안에서 만든 새 판 · 저장된 검사가 나갈 때 사라진다
                edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision, edits=edits,
                     tour=tour, kakao=kakao, via="autofix", dining=dining)
                preview = view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)
                raise _DryRunRollback()
        except _DryRunRollback:
            pass
        if preview is not None:
            preview["preview"] = True
        return {"applied": False, "dry_run": True, "revision": revision, "changed": changed, "kept": got["kept"], "view": preview}
    if edits:
        new = edit(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id, revision=revision, edits=edits,
                   tour=tour, kakao=kakao, via="autofix", dining=dining)
    return {"applied": bool(edits), "dry_run": dry_run, "revision": new, "changed": changed, "kept": got["kept"],
            **({"view": view(conn, tenant_id=tenant_id, customer_id=customer_id, intake_id=intake_id)} if dry_run else {})}


#: 고객이 보낸 관광공사 번호가 그 좌표의 장소 것으로 인정되는 거리(m) — `place_info.CATALOG_MATCH_M` 와 같은 값
CONTENT_ID_MATCH_M = 500


def _verified_content_id(conn, tenant_id: str, value: dict[str, Any]) -> dict[str, Any]:
    """고객이 후보·검색에서 고른 값의 관광공사 번호(`content_id`)를 **서버의 관광공사 목록과 대조**한다 — 그 번호의 장소가 보낸 좌표 500m 안이면 쓰고,
    아니면 번호만 뗀다(운영시간 조회가 다른 장소의 값으로 새지 않게. 틀린 번호를 붙여 내 일정에 남의 운영시간을 끌어오는 것을 막는다)."""
    from .hours import _tenants
    from .places import distance_m

    with conn.cursor() as cur:
        cur.execute("SELECT latitude, longitude FROM place_catalog WHERE tenant_id = ANY(%s) AND source='tour_api' AND content_id=%s LIMIT 1",
                    (_tenants(tenant_id), str(value["content_id"])))
        row = cur.fetchone()
    ok = (bool(row) and row[0] is not None and row[1] is not None
          and distance_m(float(row[0]), float(row[1]), float(value["latitude"]), float(value["longitude"])) <= CONTENT_ID_MATCH_M)
    return value if ok else {**value, "content_id": None, "content_type_id": None}


#: 고른 식당을 공용 원장 식당 행과 같은 곳으로 보는 거리 — 후보는 그 행의 좌표를 그대로 돌려보내므로 넉넉할 필요가 없다(우리가 고른 값)
LEDGER_PICK_MATCH_M = 50


def _linked_ledger_pick(conn, tenant_id: str, value: dict[str, Any]) -> dict[str, Any]:
    """고객이 후보 · 검색에서 고른 식당을 **요식 원장 가게 번호**(`dining_place_uid`)와 잇는다. `[2026-10-10]`

    ★왜. 원장 후보(`candidates._ledger_places`)는 `ref: place:{id}` 만 싣고, 웹은 고른 곳을 이름 · 좌표로만 돌려보낸다. 서버는 `place_id` 를
      받지 않으므로(남의 여행 전용 행을 가리킬 수 있다) 고른 식당이 원장과 끊겨 확인 화면 · 등록 판정이 「모름」이 됐다.
      결함: `wiki/records/reports/debugs/2026-10-10_고른_원장식당이_원장과_끊긴다.md`
    ★고객이 보낸 번호를 믿지 않고 서버가 찾는다 — **공용**(`trip_scope IS NULL`) 원장 식당 행 중 이름이 **정확히 같고** 좌표가
      `LEDGER_PICK_MATCH_M` 안인 곳이 **한 가게**일 때만 잇는다. 둘 이상이거나 없으면 전처럼 둔다(고르지 않는다 — 다른 가게의 영업시간으로
      판정하는 것이 가장 나쁘다). 활동으로 고른 곳은 건드리지 않는다.
    """
    if value.get("kind") not in (None, "dining"):
        return value
    from .hours import _tenants
    from .places import distance_m

    try:
        with conn.transaction(), conn.cursor() as cur:       # 세이브포인트 — 원장 열이 없는 DB 에서도 바깥 트랜잭션을 깨지 않는다
            cur.execute("SELECT latitude, longitude, attributes->>'dining_place_uid' FROM places "
                        "WHERE tenant_id = ANY(%s) AND source_name = 'dining_ledger' AND trip_scope IS NULL AND kind = 'dining' "
                        "AND name = %s AND attributes ? 'dining_place_uid'", (_tenants(tenant_id), str(value["name"])))
            rows = cur.fetchall()
    except Exception as exc:                                  # noqa: BLE001 — 원장 열이 없는 DB(시험 · 다른 조립)면 잇지 않는다
        if type(exc).__name__ not in ("UndefinedColumn", "UndefinedTable"):
            raise
        return value
    uids = {str(uid) for lat, lon, uid in rows
            if uid and lat is not None and lon is not None
            and distance_m(float(lat), float(lon), float(value["latitude"]), float(value["longitude"])) <= LEDGER_PICK_MATCH_M}
    return {**value, "dining_place_uid": uids.pop()} if len(uids) == 1 else value


def _canonical(field_name: str) -> str:
    """`items[ 01 ].place` → `items[1].place`. 항목 칸이 아니거나 번호를 못 읽으면 그대로(틀린 칸은 `_checked` 가 거절한다)."""
    if not field_name.startswith("items[") or "]" not in field_name:
        return field_name
    try:
        number = int(field_name[6:field_name.index("]")])
    except ValueError:
        return field_name
    return f"items[{number}]{field_name[field_name.index(']') + 1:]}"


def _item_no(field_name: str) -> int:
    """`items[3].place` → 3. 모양이 틀리면 -1(이 함수는 비교용이고, 틀린 칸은 `_checked` 가 거절한다)."""
    try:
        return int(field_name[6:field_name.index("]")])
    except ValueError:
        return -1


def _require_lockable(conn, tenant_id: str, intake_id: UUID, revision: int, sources: list[dict[str, Any]],
                      claims: list[dict[str, Any]], source_id: str, field_name: str) -> None:
    """확인이 필요한 일정은 고정하지 않는다 — 「꼭 넣을 일정」은 장소가 정해지고 검사를 통과한 것만(목업: 먼저 고쳐야 고정할 수 있어요)."""
    found, _ = _review_of(conn, tenant_id, intake_id, revision, sources, claims)
    item = next((i for i in (found or {}).get("items", [])
                 if i["source_id"] == source_id and i["index"] == _item_no(field_name)), None)
    if item is None:
        raise IntakeRejected("lock_needs_confirmed_item", f"{field_name}: 이 일정을 찾지 못했습니다")
    if not item["can_lock"]:
        raise IntakeRejected("lock_needs_confirmed_item", "확인이 필요한 일정은 먼저 고쳐야 고정할 수 있습니다")


def draft(conn, *, tenant_id: str, customer_id: UUID, intake_id: UUID, revision: int):
    """등록 직전 — (현재 상태, 이미 만든 여행 id, 조립 결과). ★판이 다르면 낡은 화면이라 막는다."""
    with conn.cursor() as cur:
        cur.execute("SELECT status, revision, trip_id FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s "
                    "AND customer_id=%s", (tenant_id, intake_id, customer_id))
        row = cur.fetchone()
        if row is None:
            raise LookupError("intake")
        status, current, trip_id = row
        if status not in ("review", "confirmed"):
            raise IntakeConflict("intake_not_ready", f"아직 등록할 수 없습니다(상태 {status})", status=status)
        if revision != current:
            raise IntakeConflict("stale_revision", "그 사이 다른 화면에서 고쳤습니다 — 새로 불러와 주세요",
                                 current_revision=current)
        cur.execute("SELECT source_id, field, value_json, method, evidence, needs_review, note FROM intake_claims "
                    "WHERE tenant_id=%s AND intake_id=%s AND revision=%s ORDER BY created_at, claim_id",
                    (tenant_id, intake_id, current))
        claims = [dict(zip(("source_id", "field", "value", "method", "evidence", "needs_review", "note"), r))
                  for r in cur.fetchall()]
    built = assemble(intake_id=str(intake_id), revision=current, sources=_sources(conn, tenant_id, intake_id),
                     claims=claims)
    return status, trip_id, built


def mark_confirmed(conn, *, tenant_id: str, intake_id: UUID, trip_id: Any) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET status='confirmed', stage='confirmed', trip_id=%s, updated_at=now() "
                    "WHERE tenant_id=%s AND intake_id=%s", (trip_id, tenant_id, intake_id))


def _checked(field_name: str, value: Any) -> tuple[Any, dict[str, Any], str | None]:
    """칸 이름과 값의 모양을 확인한다. 돌려주는 것 = (값, 근거, 메모)."""
    evidence = {"source": "customer"}
    if field_name.startswith("trip."):
        name = field_name[5:]
        if name not in _TRIP_FIELDS:
            raise IntakeRejected("unknown_field", f"{field_name}: 고칠 수 없는 칸입니다")
        if name == "taxi_pricing":
            from .taxi_pricing import normalize
            try:
                value = normalize(value)
            except ValueError as exc:
                raise IntakeRejected("invalid_taxi_pricing", str(exc)) from exc
        elif name == "party_size":
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 4:
                raise IntakeRejected("invalid_value", "인원은 1~4명입니다")
        elif name == "first_day":
            _iso_date(field_name, value)
        elif not isinstance(value, str) or not value.strip() or len(value) > 80:
            raise IntakeRejected("invalid_value", "여행 이름은 1~80자입니다")
        return value, evidence, None
    if not field_name.startswith("items[") or "]." not in field_name:
        raise IntakeRejected("unknown_field", f"{field_name}: 고칠 수 없는 칸입니다")
    try:
        index = int(field_name[6:field_name.index("]")])
    except ValueError:
        raise IntakeRejected("unknown_field", f"{field_name}: 항목 번호가 숫자가 아닙니다") from None
    name = field_name[field_name.index("]") + 2:]
    if index < 0 or index > 500 or name not in _ITEM_FIELDS:
        raise IntakeRejected("unknown_field", f"{field_name}: 고칠 수 없는 칸입니다")
    if name in ("starts_at", "ends_at"):
        if not isinstance(value, str) or not _HHMM.match(value):
            raise IntakeRejected("invalid_value", f"{field_name}: 시각은 HH:MM 입니다")
    elif name == "date":
        _iso_date(field_name, value)
    elif name == "kind":
        if value not in ("activity", "dining"):
            raise IntakeRejected("invalid_value", f"{field_name}: 종류는 activity · dining 입니다")
    elif name == "removed":
        if value is not True and value is not False:
            raise IntakeRejected("invalid_value", f"{field_name}: 빼려면 true, 되돌리려면 false 를 보냅니다")
    elif name == "locked":
        if value is not True and value is not False:
            raise IntakeRejected("invalid_value", f"{field_name}: 고정은 true, 풀기는 false 입니다")
    elif name == "place":
        if isinstance(value, dict) and value.get("none") is True:
            return None, {"source": "customer", "none": True}, "고객이 「장소 없음」으로 두었다"
        if isinstance(value, dict) and ("latitude" in value or "longitude" in value):
            picked = _checked_pick(field_name, value)
            return picked, {"source": "customer", "picked_from": picked["origin"], "query": picked["name"]}, "고객이 직접 고른 장소"
        if not isinstance(value, dict) or not str(value.get("name") or "").strip():
            raise IntakeRejected("invalid_value", f'{field_name}: 장소는 {{"name": …}} · {{"name", "latitude", "longitude", "source"}} · '
                                                  f'{{"none": true}} 중 하나입니다')
    elif not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise IntakeRejected("invalid_value", f"{field_name}: 1~80자 글이어야 합니다")
    return value, evidence, None


def _checked_pick(field_name: str, value: dict[str, Any]) -> dict[str, Any]:
    """고객이 후보 · 검색 · 지도에서 **고른** 장소 — `{name, latitude, longitude, source, origin?, kind?, content_id?}`.

    서버는 다시 찾지 않고 모양만 확인한다(후보 조회 결과는 저장하지 않으므로 서버가 다시 확인할 수 없다 — 고객이 본 것을 그대로 받는다).
    ★관광공사 번호와 좌표의 대조는 DB 가 필요해 여기서 못 한다 — `edit()` 가 `_verified_content_id` 로 한다.
    ★출처는 늘 `customer_pick` 으로 적는다 — 고객이 보낸 값은 관광공사 · 카카오 값이 아니다(여행 전용 장소 행으로만 들어간다, `trip_api.EXTERNAL_PLACE_SOURCES`).
    ★`place_id` 는 받지 않는다(남의 여행 전용 장소 행을 가리킬 수 있다). 관광공사 번호(`content_id`)는 숫자만 — 운영시간 표를 찾는 데만 쓴다."""
    name = str(value.get("name") or "").strip()
    if not 1 <= len(name) <= 80:
        raise IntakeRejected("invalid_value", f"{field_name}: 장소 이름은 1~80자입니다")
    coords = []
    for key in ("latitude", "longitude"):
        number = value.get(key)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or number != number or abs(number) == float("inf"):
            raise IntakeRejected("invalid_value", f"{field_name}: {key} 는 숫자입니다")
        coords.append(float(number))
    if not (SEOUL_LAT[0] <= coords[0] <= SEOUL_LAT[1] and SEOUL_LON[0] <= coords[1] <= SEOUL_LON[1]):
        raise IntakeRejected("place_out_of_seoul", f"{field_name}: 서울 안의 장소만 고를 수 있습니다")
    source = value.get("source", "customer_pick")
    if source not in _PICK_ORIGINS:
        raise IntakeRejected("invalid_value", f"{field_name}: source 는 {', '.join(_PICK_ORIGINS)} 중 하나입니다")
    kind = value.get("kind")
    content_id = value.get("content_id")
    if content_id is not None and not _CONTENT_ID.match(str(content_id)):
        raise IntakeRejected("invalid_value", f"{field_name}: content_id 는 숫자입니다")
    provider_ref = str(value.get("provider_ref") or "").strip()
    if provider_ref and not re.fullmatch(r"(?:kakao|tour):[0-9]{1,30}", provider_ref):
        raise IntakeRejected("invalid_value", f"{field_name}: provider_ref 형식을 확인해 주세요")
    category = str(value.get("category") or "").strip()[:60] or None
    return {"name": name, "kind": kind if kind in ("activity", "dining") else None, "latitude": coords[0],
            "longitude": coords[1], "place_id": None, "content_id": str(content_id) if content_id else None,
            "content_type_id": None, "category": category, "provider_ref": provider_ref or None, "source": "customer_pick",
            "origin": source if source != "customer_pick" else str(value.get("origin") or "search")
            if str(value.get("origin") or "search") in _PICK_ORIGINS else "search"}


def _iso_date(field_name: str, value: Any) -> None:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        raise IntakeRejected("invalid_value", f"{field_name}: 날짜는 YYYY-MM-DD 입니다") from None


def _item_kind(cur, tenant_id: str, intake_id: UUID, revision: int, source_id: str, place_field: str,
               edits: list[dict[str, Any]]) -> str | None:
    """장소를 고치는 항목의 종류 — 같은 요청에서 함께 고친 값이 먼저, 없으면 지금 판의 값. 식사면 요식 원장부터 찾는다."""
    kind_field = place_field[:-len("place")] + "kind"
    for entry in edits:
        if str(entry.get("source_id") or "") == source_id and entry.get("field") == kind_field:
            return entry.get("value")
    cur.execute("SELECT value_json FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=%s "
                "AND source_id=%s AND field=%s ORDER BY created_at DESC LIMIT 1",
                (tenant_id, intake_id, revision, source_id, kind_field))
    row = cur.fetchone()
    return row[0] if row and isinstance(row[0], str) else None


def _edit_place_anchor(cur, tenant, intake_id, revision, source_id, field):
    cur.execute("SELECT value_json FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=%s "
                "AND source_id=%s AND field=%s ORDER BY created_at DESC LIMIT 1",
                (tenant, intake_id, revision, source_id, field))
    row = cur.fetchone()
    value = row[0] if row and isinstance(row[0], dict) else {}
    return ((value["latitude"], value["longitude"]) if value.get("latitude") is not None
            and value.get("longitude") is not None else None)


def _typed_place(value: dict[str, Any], our_places, tour, kakao, dining=None, kind_hint: str | None = None, near=None, conn=None):
    """고객이 적은 장소 이름 → 다시 찾아 **하나**. 못 찾으면 받지 않는다(지어내지 않는다)."""
    from .places import resolve

    name = str(value["name"]).strip()[:80]
    if "near" in value:
        anchor = value["near"]
        if (not isinstance(anchor, (list, tuple)) or len(anchor) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in anchor)
                or not SEOUL_LAT[0] <= anchor[0] <= SEOUL_LAT[1] or not SEOUL_LON[0] <= anchor[1] <= SEOUL_LON[1]):
            raise IntakeRejected("invalid_value", "검색 기준 위치는 서울 안의 위도·경도 숫자여야 해요")
        near = tuple(anchor)
    found = resolve(name, our_places=our_places, tour=tour, kakao=kakao, dining=dining, kind_hint=kind_hint, near=near, choose_near=True,
                    conn=conn)
    if found.status != "resolved":
        raise IntakeRejected("place_not_found", f"「{name}」: {found.note}")
    resolved = {"name": found.name, "kind": found.kind, "latitude": found.latitude, "longitude": found.longitude,
                "place_id": found.place_id, "content_id": found.content_id,
                "content_type_id": found.content_type_id, "source": found.evidence()["source"],
                **({"dining_place_uid": found.dining_place_uid} if found.dining_place_uid else {})}
    return resolved, {**found.evidence(), "typed": name}, found.note


# ── 한 원본 읽기: 규칙 → 남은 줄 → 날짜 → 장소 ─────────────────────
READING_STREAM_KEYS = ("first_token_seconds", "stall_seconds", "max_seconds", "progress_seconds", "output_tokens_base",
                       "output_tokens_per_line", "output_tokens_per_char")

#: 남은 줄 모델이 끝내 답하지 못했을 때 고객에게 보이는 말(접수 `fatal_detail`) — 무엇이 안 됐고 무엇을 하면 되는지. 기술 사유는 로그에 남긴다
READING_FAILED_TEXT = "계획을 읽는 모델이 지금 답하지 않아 계획을 다 읽지 못했어요. 잠시 뒤 같은 계획을 다시 보내 주세요."


def _model_side_failure(exc: BaseException) -> bool:
    """에이전트 실패가 **모델 쪽**(로컬 · 유료 모두 답하지 못함 — 연결 · 시간 초과 · 조각 끊김)인가. `[2026-10-16 2회차 합의 ②]`
    답 내용 쪽(모양 · 스키마 · 인용 검사 — `OllamaContentError` · `ValueError` · 넘김 장치가 모든 경로에서 「모양」 이유로 실패)이면 False — 줄 읽기로 한 번 더 읽는다."""
    from app.infrastructure.llm_failover import current_path
    from app.infrastructure.ollama_chat import OllamaContentError, OllamaError

    if isinstance(exc, OllamaContentError):
        return False
    if not isinstance(exc, (OllamaError, TimeoutError, ConnectionError)):
        return False
    reasons = [reason for _, reason in ((current_path() or {}).get("reasons") or [])]
    return not (reasons and all(reason == "content" for reason in reasons))


def _reading_stream(given: dict[str, Any] | None) -> dict[str, Any]:
    """남은 줄 모델 호출의 조금씩 받기 설정 — 넘겨받은 값이 없으면 가드레일 `travel.intake_reading.*`(근거는 그 설정의 주석)."""
    if given is not None:
        return given
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    return {key: guard.get(f"travel.intake_reading.{key}") for key in READING_STREAM_KEYS}



def _lookup_title(title: str, aliases: dict[str, str] | None) -> str:
    """장소를 찾을 말 — 체크인 · 체크아웃 동작 말을 뺀다(`line_parts.lookup_title`). 고객이 이 글을 다른 이름으로 고친 적이 있으면(별칭) 옛 길이 원문으로 찾아야 하므로 그대로 둔다."""
    from .places import normalize

    return title if normalize(title) in (aliases or {}) else lookup_title(title)


def read_source(text: str, *, chat: Any = None, tour: Any = None, kakao: Any = None,
                our_places: list[dict[str, Any]] | None = None, today: date, now: datetime | None = None,
                aliases: dict[str, str] | None = None, areas: Any = None, dining: Any = None,
                on_rows: Callable[[list[dict[str, Any]]], None] | None = None,
                on_progress: Callable[[str, int, int, int, str | None], None] | None = None,
                differs: dict[int, dict[str, Any]] | None = None, agent: Any = None, agent_mode: str = "off",
                position: int = 0, agent_num_predict: int = 3072, agent_chunk_chars: int | None = None,
                reading_stream: dict[str, Any] | None = None,
                on_reading: Callable[[dict[str, Any]], None] | None = None,
                connect: Callable[[], Any] | None = None) -> list[dict[str, Any]]:
    """읽은 값 줄들(`intake_claims` 한 행 = 한 dict). ★값마다 방법(rule·llm_span·llm_agent·lookup)과 근거가 붙는다.

    `agent` · `agent_mode` `[2026-10-16 사용자 지시]` — 읽기 에이전트(`agent_read.py`, 가르친 모델 한 번 호출). `on` 이면 에이전트가 먼저 읽고
    (시각이 적힌 줄을 에이전트가 빠뜨렸으면 규칙이 읽은 그 줄로 채운다), 에이전트가 실패하거나 아무것도 못 읽었는데 규칙은 읽었으면 지금까지처럼 규칙이 읽는다.
    `shadow` 는 규칙 결과를 쓰고 에이전트 결과는 `reading.agent` 값 줄에 남기기만 한다. `position` 은 이 원본의 접수 안 순서(이동 수단 값 줄의 구간 id).

    `on_rows` — 값 줄이 **생길 때마다 묶음으로** 알려 준다(규칙으로 읽은 줄 → 모델이 가리킨 줄 → 날짜 → 장소가 하나씩 찾아질 때마다).
    실시간 진행이 읽은 줄 · 일정 · 장소를 그때그때 보이게 하려는 것이다. 돌려주는 목록은 전과 같다(알린 줄을 두 번 알리지 않는다).

    `on_progress(phase, done, total, index, title)` `[2026-10-03 ui 세션 요청서 2번]` — **장소 찾기가 한 일정씩 끝날 때마다** 「장소 n/m」을 알린다(`phase` 는 늘 `places`, `index` 는 항목 번호, `title` 은 원문 조각).
    ★찾았든 못 찾았든 **그 일정의 장소 값이 정해지면** 센다 — 이름이 특정된 것은 찾는 즉시, 모호한 것은 앞뒤가 다 찾아진 뒤 가까운 곳을 고른 때.

    `areas` `[2026-10-03 ui 세션 요청서 「장소 해석 개선」]` — 지명 사전(`areas.py`). 이름 없이 **종류 + 지역만** 적은 줄(「성수 예약 식당」)을 알아보는 데 쓴다(`line_parts.py`) —
    그런 줄은 가게 이름으로 **찾지 않는다**(없는 가게를 찾아 글자를 줄여 가던 것이 틀린 장소와 엉뚱한 후보의 뿌리였다). 사전이 없으면(None) 지역 말은 이름 조각으로 남고 종류 · 끼니만 있는 줄만 알아본다.

    `differs` `[2026-10-06 사용자 지시 — 값 변조 줄이기]` — 사진 · 스캔 받아쓰기가 같은 줄을 **두 번 다르게 읽은 곳**(`sources.differing_lines`). 그 줄에서 읽은 제목 · 예약번호는 「확인 필요」로 표시한다 —
    고객이 확인하기 전에는 확정 값으로 쓰지 않는다(`flag_differing`).

    `reading_stream` · `on_reading` `[2026-10-16 2회차 합의 · 사용자 승인]` — 남은 줄을 모델에 **한 번에** 보내고 답을 **조금씩 받는다**(`llm_spans.label_lines`).
    비우면(None) 가드레일 `travel.intake_reading.*`(첫 조각 · 조각 사이 · 맨 위 상한 · 진행 알림 간격 · 답 토큰 상한)를 읽는다.
    `on_reading({phase: reading|reading_api, done, total})` — 원문 검사를 통과한 줄 수 / 보낸 줄 수(`progress_seconds` 마다 · 유료로 바뀌면 곧바로).
    ★모델이 로컬 · 유료 모두 답하지 못하면 `IntakeRejected("reading_model_failed")` — 접수가 「읽기 실패」가 되고 고객은 다시 보낼 수 있다(조용히 남은 줄로 두지 않는다).

    `dining` `[2026-10-05]` — 요식 원장 이름 조회(`dining/place_lookup.py`, 관광공사 자리와 같은 계약 `find` + `misses`). 식사 항목은 이것이 먼저, 그 밖의 항목은 관광공사 자리 뒤다(`places.resolve`). 없으면(None) 건너뛴다."""
    from .dates import resolve_dates
    from .line_parts import parse as parse_line
    from .landmarks import read_move
    from .llm_spans import ReadingFailed, label_lines
    from .places import _kind_hits, nearest, normalize, resolve

    read = read_plan(text)
    copied_cards = schedule_cards.cards(read)
    schedule_cards.restore(read, copied_cards)
    agent_out, agent_error = None, None
    if agent is not None and agent_mode in ("on", "shadow"):
        try:
            # ★`[2026-10-16 2회차 합의]` 조금씩 받기 + 멈춤 감시(`travel.intake_reading`) — 진행 알림은 에이전트 결과를 쓰는 `on` 일 때만(그림자는 규칙 경로가 알린다)
            agent_out = agent_module.read(text, read.lines, agent, today=today, num_predict=agent_num_predict,
                                          chunk_chars=agent_chunk_chars or agent_module.fragments_module.CHUNK_CHARS,
                                          stream=_reading_stream(reading_stream), on_progress=on_reading if agent_mode == "on" else None,
                                          now=now)
        except Exception as exc:                      # noqa: BLE001 — 갈래를 나눈다(아래)
            agent_error = f"{type(exc).__name__}: {exc}"[:200]
            # ★`[2026-10-16 2회차 합의 ②]` 버리는 줄 없음 — 실패 이유로 갈래를 나눈다
            #   · 모델 쪽(로컬 · 유료 모두 답 못 함 — 연결 · 시간 초과 · 멈춤): 같은 모델을 또 부르지 않고 곧바로 「읽기 실패」(유료를 두 번 태우지 않는다)
            #   · 답 내용 쪽(스키마 · 모양 · 인용 검사 — 모델은 답했다): 아래에서 줄 읽기(`label_lines`)로 한 번 더 읽고, 그것도 실패하면 「읽기 실패」
            #   ☆전에는(D-025 첫 판) 어느 쪽이든 「규칙 미리보기 + 못 읽은 줄」로 끝냈다 — 못 읽은 줄이 조용히 남았다
            if agent_mode == "on" and _model_side_failure(exc):
                log.warning("intake reading outcome=failed by=agent_model error=%s", agent_error)
                raise IntakeRejected("reading_model_failed", READING_FAILED_TEXT) from exc
            log.warning("intake agent read failed (answer side — reading lines instead): %s", agent_error)
    use_agent = agent_mode == "on" and agent_out is not None and (bool(agent_out.items) or not read.items)
    #: 어느 길로 읽었나 — `reading.agent` 값 줄과 로그에 남긴다(화면 · 관리 콘솔에서 본다). 줄 읽기가 실패하면 `failed` 로 로그만 남고 접수가 「읽기 실패」가 된다
    outcome = "agent" if use_agent else ("lines_instead" if agent_mode == "on" else "lines")
    rows = [claim.as_dict() for claim in read.claims] if not use_agent else []
    sent: set[int] = set()
    flushed = 0

    def send(batch: list[dict[str, Any]]) -> None:
        batch = [r for r in batch if id(r) not in sent]
        sent.update(id(r) for r in batch)
        flag_differing(batch, differs)
        if on_rows is not None and batch:
            on_rows(batch)

    def flush() -> None:
        nonlocal flushed
        send(rows[flushed:])
        flushed = len(rows)

    if use_agent:
        rows, items, dated, ask = _agent_rows(read, agent_out, position=position, today=today, copied_cards=copied_cards)
        flush()
    else:
        flush()                                       # 규칙으로 읽은 줄 — 이 순간 「읽은 줄」이 생긴다
        marks = [(c.span.line, c.value if c.field.endswith(".heading") else None,
                  c.value if c.field.endswith(".date") else None) for c in read.claims if c.field.startswith("days[")]
        items: list[dict[str, Any]] = []
        for item in read.items:
            items.append({"line": (item.title or item.booking_no).line if (item.title or item.booking_no) else 0,
                          "day": item.day, "date": item.date, "title": item.title.text if item.title else None,
                          "meal": any(r["field"] == f"items[{len(items)}].kind" for r in rows), "booked": item.booked})

        # 남은 줄 — 모델은 가리키기만. ★`[2026-10-16 2회차 합의]` 로컬 · 유료 모두 실패하면 접수를 「읽기 실패」로 드러낸다(전에는 이 단계만 건너뛰었다)
        # ★`[2026-10-16 2회차 합의 ②]` 에이전트가 **답 내용 쪽**으로 실패했거나 항목을 못 냈으면 여기서 줄 읽기로 한 번 더 읽는다.
        #   모델 쪽 실패는 위에서 이미 「읽기 실패」로 끝났다(같은 모델을 또 부르지 않는다)
        if chat is not None and read.unread_lines:
            try:
                _, span_items, report = label_lines(read.lines, read.unread_lines, chat, now=now,
                                                    stream=_reading_stream(reading_stream), on_progress=on_reading)
            except ReadingFailed as exc:
                log.warning("intake reading outcome=failed by=lines after=%s lines=%d: %s", outcome, len(read.unread_lines), exc)
                raise IntakeRejected("reading_model_failed", READING_FAILED_TEXT) from exc
            rows.append({"field": "reading.llm", "value": report, "method": "llm_span",
                         "evidence": {"source": "model", "lines": read.unread_lines}, "needs_review": False,
                         "note": "남은 줄에 모델이 가리킨 결과(원문에 없는 인용은 버렸다)"})
            for span_item in span_items:
                index = len(items)
                day, date_mark = _mark_for(span_item.line, marks)
                rows.append({"field": f"items[{index}].title", "value": span_item.title.text, "method": "llm_span",
                             "evidence": {"source": "text", **span_item.title.as_dict(),
                                          "segment": span_item.segment.as_dict()}, "needs_review": True,
                             "note": "모델이 가리킨 원문 조각"})
                time_claim = span_item.time_claim          # ★한 줄에 장소가 여럿이면 시각도 장소마다 다르다(`llm_spans`)
                if time_claim is not None:
                    rows.append({**time_claim.as_dict(), "field": f"items[{index}].starts_at"})
                if span_item.meal:
                    rows.append({"field": f"items[{index}].kind", "value": "dining", "method": "llm_span",
                                 "evidence": {"source": "text", "line": span_item.line}, "needs_review": False,
                                 "note": f"끼니 말({span_item.meal})"})
                items.append({"line": span_item.line, "day": day, "date": span_item.date or date_mark,
                              "title": span_item.title.text, "meal": bool(span_item.meal), "booked": None,
                              "segment": span_item.segment.as_dict()})
            if report.get("plan_request"):
                rows.append({"field": "trip.plan_request", "value": True, "method": "llm_span",
                             "evidence": {"source": "text"}, "needs_review": False,
                             "note": "「일정 짜 줘」— 확인 화면에서 일정 생성기로 넘긴다"})

        flush()
        # 「일정 짜 줘」 — 모델이 못 가리켜도 규칙으로 잡는다(모델이 꺼져 있어도 요청을 놓치지 않게)
        if not any(r["field"] == "trip.plan_request" for r in rows):
            for number, line in enumerate(read.lines, start=1):
                asked = PLAN_ASK.search(line)
                if asked:
                    rows.append({"field": "trip.plan_request", "value": True, "method": "rule",
                                 "evidence": {"source": "text", "line": number, "start": asked.start(),
                                              "end": asked.end(), "text": asked.group(0)},
                                 "needs_review": False, "note": "「일정 짜 줘」 — 확인 화면에서 일정 생성기로 넘긴다"})
                    break

        # 날짜 — 우선순위대로. 다 없으면 첫날을 묻는다
        dated, ask = resolve_dates(items, today=today, lines=read.lines)
        for index, day_date in enumerate(dated):
            rows.append({"field": f"items[{index}].date", "value": day_date.value, "method": "rule",
                         "evidence": {"source": "rule", "how": day_date.how, "line": items[index]["line"]},
                         "needs_review": day_date.needs_review, "note": day_date.note})
        if ask:
            rows.append({"field": "trip.ask_first_day", "value": True, "method": "rule",
                         "evidence": {"source": "rule"}, "needs_review": True,
                         "note": "날짜가 적혀 있지 않다 — 첫날 날짜 하나만 묻는다"})
        flush()
    if agent is not None and agent_mode in ("on", "shadow"):
        # 에이전트가 읽은 것 중 화면 칸이 없는 것(이동 · 조건 · 성향 · 요청 · 빠진 값)과 실패 · 그림자 결과를 남긴다
        rows.append({"field": "reading.agent", "method": "llm_agent", "evidence": {"source": "model"}, "needs_review": False,
                     "value": ({**agent_module.report_value(agent_out), "used": use_agent, "outcome": outcome} if agent_out is not None
                               else {"error": agent_error, "used": False, "outcome": outcome}),
                     "note": "읽기 에이전트 결과(원문에 글자 그대로 없는 조각은 버렸다)"})
        flush()
    log.info("intake reading outcome=%s agent_mode=%s agent_error=%s", outcome, agent_mode, agent_error or "-")

    # 장소 — 항목마다 하나(원문이 가리킨 만큼만)
    resolved: dict[int, Any] = {}
    early: dict[int, list[dict[str, Any]]] = {}
    nameless: set[int] = set()
    move_lines: dict[int, Any] = {}             # 이동 말 줄(「택시로 이동」) — 장소 대신 앞 · 뒤 일정 사이 구간의 수단이 된다(`_move_segments`)
    titled, placed = sum(1 for item in items if item["title"]), 0
    for index, item in enumerate(items):
        if item["title"]:
            # ★이름 없는 줄(종류 + 지역만) — 가게 이름으로 찾지 않는다. 고객이 앞서 이 글을 다른 이름으로 고친 적이 있으면(별칭) 그 이름으로 다시 찾는 옛 길이 먼저다
            # ★`[2026-10-15 숙박예약 점검 LB-01]` 장소는 체크인 · 체크아웃 말을 뺀 말로 찾는다(숙소 줄) — 고객이 이 글을 다른 이름으로 고친 적이 있으면(별칭) 원문 그대로
            query = _lookup_title(item["title"], aliases)
            # ★`[2026-10-19 진단 포인트 2]` 이동을 적은 말(「택시로 이동」 · 「공항철도 타고 인천공항」)은 방문할 장소가 아니다 — 장소를 찾지 않는다.
            #   ☆「택시로 이동」이 택시 회사 본사가 됐다. 「따릉이 타고 한강」처럼 끝점이 공항 · 역 · 터미널이 아니면 수단 말만 떼고 목적지를 찾는다
            move = read_move(query) if normalize(item["title"]) not in (aliases or {}) else None
            if move is not None and move.is_move:
                early[index] = _move_rows(index, move, item)
                send(early[index])
                nameless.add(index)
                move_lines[index] = move
                placed += 1
                if on_progress is not None:
                    on_progress("places", placed, titled, index, item["title"])
                continue
            if move is not None and move.destination:
                query = move.destination
            parts = parse_line(query, areas=areas, kind_hint="dining" if item["meal"] else None)
            meal_reference = item["meal"] and re.fullmatch(r"(?:(?:거기|여기|그곳|이곳)(?:서|에서)?\s*(?:식사|밥)?|식사|밥)", query.strip())
            if parts.nameless and not meal_reference and normalize(item["title"]) not in (aliases or {}):
                nameless.add(index)
                early[index] = _nameless_rows(index, parts, item, rows)
                send(early[index])
                placed += 1
                if on_progress is not None:
                    on_progress("places", placed, titled, index, item["title"])
                continue
            resolved[index] = resolve(query, our_places=our_places or [], tour=tour, kakao=kakao,
                                      kind_hint=_place_kind_hint(item), aliases=aliases, dining=dining,
                                      near=_near_hint(index, items, resolved, dated), at=_visit_at(index, rows, dated),
                                      conn=connect)       # 공용 별칭의 DB 표 — 연결을 잡지 않고 여는 함수로(`place_by_name.alias_target`)
            if resolved[index].status == "resolved":
                # 이름이 특정된 곳은 앞뒤 일정을 볼 필요가 없다 — 찾은 즉시 알린다(실시간 진행에서 한 곳씩 나타난다)
                early[index] = _place_rows(index, resolved[index], items=items, resolved=resolved, dated=dated, rows=rows,
                                           kakao=kakao, nearest=nearest, kind_hits=_kind_hits)
                send(early[index])
                placed += 1
                if on_progress is not None:
                    on_progress("places", placed, titled, index, item["title"])
    # ★`[2026-10-07 팀]` 체인인데 기준 위치(지점명 · 앞뒤 일정)가 없어 미룬 항목(`chain_deferred`)은 다른 장소가 정해진 뒤 한 번 더 찾는다
    for index, found in list(resolved.items()):
        if getattr(found, "chain_deferred", False) and index not in early:
            point = _near_hint(index, items, resolved, dated)
            if point is not None:
                resolved[index] = resolve(_lookup_title(items[index]["title"], aliases), our_places=our_places or [], tour=tour, kakao=kakao,
                                          kind_hint=_place_kind_hint(items[index]), aliases=aliases,
                                          dining=dining, near=point, conn=connect)
    for index in sorted(set(resolved) | nameless):
        if index in early:
            rows.extend(early[index])
            continue
        found = resolved[index]
        new = _place_rows(index, found, items=items, resolved=resolved, dated=dated, rows=rows, kakao=kakao,
                          nearest=nearest, kind_hits=_kind_hits)
        rows.extend(new)
        send(new)
        placed += 1
        if on_progress is not None:
            on_progress("places", placed, titled, index, items[index]["title"])
    if move_lines:
        new = _move_segments(move_lines, items, dated, position)
        rows.extend(new)
        send(new)
    flush()
    return rows


def flag_differing(rows: list[dict[str, Any]], differs: dict[int, dict[str, Any]] | None) -> None:
    """읽은 값 줄(제목 · 예약번호) 가운데 **받아쓰기가 두 번 다르게 읽은 줄**에서 나온 것을 「확인 필요」로 고친다(제자리). 근거에 두 읽기를 남긴다.

    ★값은 바꾸지 않는다 — 어느 쪽이 맞는지 서버는 모른다. 확인 화면이 두 읽기를 보이고 고객이 고른다."""
    if not differs:
        return
    for row in rows:
        field = str(row.get("field") or "")
        if not (field.endswith(".title") or field.endswith(".booking_no")):
            continue
        evidence = row.get("evidence") or {}
        unlike = differs.get(evidence.get("line"))
        if unlike is None:
            continue
        row["needs_review"] = True
        # ★`[2026-10-07 uiux 요청]` `other_value` — 반쪽 받아쓰기에서는 **이 값이 무엇으로 읽혔나**(줄 전체가 아니라 값만). 화면이 「지금 값 / 다른 읽기」 단추를 그리고 고른 값을 보낸다. 못 정하면 `None`
        row["evidence"] = {**evidence, "transcription_differs": {"text": unlike.get("text"), "other": unlike.get("other"), "ratio": unlike.get("ratio"),
                                                                  "other_value": other_reading(str(row.get("value") or ""), str(unlike.get("text") or ""),
                                                                                               str(unlike.get("other") or ""))}}
        note = f"사진에서 이 줄을 두 가지로 읽었어요 — 「{unlike.get('text')}」 / 「{unlike.get('other')}」 · 원본과 맞는 쪽을 골라 주세요"
        row["note"] = f"{row['note']} · {note}" if row.get("note") else note


def _place_kind_hint(item: dict[str, Any]) -> str | None:
    """장소를 찾을 종류 단서 — 활동 표현은 같은 줄 전체가 아닌 이 항목의 원문에서만 본다.

    ★`[2026-10-19 진단 포인트 2]` **숙소가 먼저다** — 에이전트가 숙소라고 읽었거나(`lodging`) 이 항목의 원문에 숙소 말(호텔 · 숙소 · 체크인 · ○○스테이 …)이
      있으면 끼니 말이 있어도(「호텔 조식」 · 「롯데호텔 서울 조식」) 장소는 숙소 자료에서만 찾는다. 항목이 식사인지는 따로 남는다(종류 값 줄).
      ★찾을 말(`lookup_title`)은 체크인 말을 뗀 것이라 여기서는 **원문 제목**을 본다(「노스텔지어 더블재 체크인」).
      줄 전체(`segment`)는 보지 않는다 — 「체크인 후 경복궁」의 경복궁까지 숙소가 된다."""
    from .landmarks import is_lodging_text

    if item.get("lodging") or is_lodging_text(item.get("title")):
        return "lodging"
    if item["meal"]:
        return "dining"
    text = (item.get("segment") or {}).get("text") or item.get("title") or ""
    return "activity" if re.search(r"산책|걷|관람|둘러보|구경|견학|탐방|관광|나들이", text) else None


def _place_rows(index: int, found: Any, *, items: list[dict[str, Any]], resolved: dict[int, Any], dated: Any,
                rows: list[dict[str, Any]], kakao: Any, nearest: Any, kind_hits: Any) -> list[dict[str, Any]]:
    """찾은 결과 하나 → 그 항목의 장소 값 줄(+ 종류 줄). 이름이 특정하지 않으면 종류가 맞는 후보 중 앞뒤 일정에 가장 가까운 곳을 고른다."""
    out: list[dict[str, Any]] = []
    evidence = found.evidence()
    value = None
    note, review = found.note, found.needs_review
    if found.status == "resolved":
        value = {"name": found.name, "kind": found.kind, "latitude": found.latitude,
                 "longitude": found.longitude, "place_id": found.place_id, "content_id": found.content_id,
                 "content_type_id": found.content_type_id,
                 "source": evidence["source"],
                 **({"dining_place_uid": found.dining_place_uid} if found.dining_place_uid else {})}
    elif found.candidates:
        # ★설계서 §4-2 — 이름이 특정하지 않으면 종류가 맞는 후보 중 **같은 날 앞뒤 일정에 가장 가까운 곳** 하나.
        #   선택지를 나열하지 않는다. 고른 이유(거리)를 근거에 남기고 확인을 받는다
        near = _neighbours(index, items, resolved, dated)
        pool = list(found.candidates)
        if near and kakao is not None:
            # 앞뒤 일정 가운데에서 **거리순**으로 한 번 더 찾는다 — 서울 전역 상위 5곳만으로는 14km 밖을 골랐다(실측)
            mid = (sum(p[0] for p in near) / len(near), sum(p[1] for p in near) / len(near))
            query = lookup_title(items[index]["title"])
            around = kakao.search(query, near=mid) or []
            seen = {c["name"] for c in pool}
            pool += [h for h in kind_hits(query, around) if h["name"] not in seen]
        pool = _fitting(pool, items[index]["title"], meal=bool(items[index]["meal"]),
                        activity=_place_kind_hint(items[index]) == "activity")
        review = True
        if pool:
            pick, metres = nearest(pool, near)
            value = {"name": pick["name"], "kind": "dining" if pick.get("category_group") in ("FD6", "CE7")
                     else (found.kind or "activity"), "latitude": pick["latitude"], "longitude": pick["longitude"],
                     "place_id": None, "content_id": None, "source": "kakao"}
            evidence = {**evidence, "source": "kakao", "method": "kakao_nearest", "name": pick["name"],
                        "chosen_from": [c["name"] for c in pool],
                        "neighbours": len(near), "mean_distance_m": round(metres) if metres is not None else None}
            note = (f"이름이 특정하지 않아 종류가 맞는 {len(pool)}곳 중 "
                    + (f"앞뒤 일정에 가장 가까운 「{pick['name']}」(평균 {round(metres):,}m)을 골랐다"
                       if metres is not None else f"앞뒤 일정 좌표가 없어 카카오 첫 후보 「{pick['name']}」을 골랐다")
                    + " — 이 여행에만 싣는다. 다르면 고쳐 주세요")
        else:
            evidence = {**evidence, "chosen_from": []}
            note = "항목에 맞는 후보가 없어 장소를 정하지 못했다 — 장소를 확인하고 고쳐 주세요"
    out.append({"field": f"items[{index}].place", "value": value, "method": "lookup",
                "evidence": evidence, "needs_review": review, "note": note})
    if found.item_kind and not any(r["field"] == f"items[{index}].kind" for r in rows):
        # 「광장시장 빈대떡」 — 장소는 광장시장, 항목은 식사(설계서 §4-2). 근거는 원문 전체로 찾은 카카오 결과의 종류
        out.append({"field": f"items[{index}].kind", "value": found.item_kind, "method": "lookup",
                    "evidence": {"source": "kakao", "rule": "food_hint", "line": items[index]["line"]},
                    "needs_review": False, "note": "뗀 말로 찾은 곳이 대부분 음식점이라 식사 일정으로 본다"})
    return out


def _fitting(pool: list[dict[str, Any]], title: str, *, meal: bool, activity: bool = False) -> list[dict[str, Any]]:
    """이름이 특정하지 않은 항목의 후보를 **그 항목에 맞는 것**으로 좁힌다(남는 것이 없으면 빈 목록).

    ★`[2026-10-14 테스트 서버 접수 cbd50b1d]` 「오후엔 서촌 골목 좀 걷다가」가 후보 10곳 중 앞뒤 일정에 가장 가까운 「서촌닭갈비 광화문본점」이 됐다 —
      찾은 곳이 식당이라 항목이 식사가 되고 18:00 에 놓였다. 이제
        1 식사가 아닌 항목은 이름이 다른 음식점 · 카페를 빼고, 식사 항목은 음식점 · 카페만 본다
        2 그중 이름이 원문과 **정확히 같은** 후보(「서촌」 — 동네 자체)가 있으면 그것들 중에서 고른다.
          ☆지점 표시까지 비교한다(`normalize_full`) — 떼면 「올리브영 광화문점」이 「올리브영」과 같아져 체인 지점 후보가 하나로 줄었다"""
    from .places import _fits_item_kind, normalize_full

    pool = [c for c in pool if _fits_item_kind(c, title, meal=meal, activity=activity)]
    key = normalize_full(title)
    same = [c for c in pool if normalize_full(c["name"]) == key]
    return same or pool


def _move_rows(index: int, move: Any, item: dict[str, Any]) -> list[dict[str, Any]]:
    """이동을 적은 줄(「택시로 이동」 · 「공항철도 타고 인천공항」)의 값 줄 — 장소 값은 비워 두고(찾지 않았다) 수단 · 목적지 원문을 근거에 남긴다. `[2026-10-19]`
    확인 화면은 「장소 없이 둔」 줄로 보인다(`review.place_state`). 앞뒤 일정 사이 이동 수단으로 옮기는 일은 아직 하지 않는다(에이전트가 읽으면 이동 값 줄로 따로 온다)."""
    return [{"field": f"items[{index}].place", "value": None, "method": "lookup",
             "evidence": {"source": "rule", "method": "move_phrase", "line": item["line"], "query": item["title"],
                          "mode": move.mode, "destination": move.destination},
             "needs_review": False,
             "note": f"이동을 적은 말(「{item['title']}」)이라 장소로 찾지 않았다"
                     + (f" — 끝점 「{move.destination}」은 이동의 도착지로 둔다" if move.destination else "")}]


def _around_quote(quote: Any, lines: list[str], items: list[dict[str, Any]], dated: Any) -> tuple[int | None, int | None]:
    """원문 조각(「택시로 이동」)이 적힌 자리의 바로 앞 일정과 바로 뒤 일정(같은 날). 자리를 못 찾거나 앞뒤 날이 다르면 (None, None)."""
    text = str(quote or "").strip()
    spot = next(((n, line.find(text)) for n, line in enumerate(lines, start=1) if text and text in line), None)
    if spot is None:
        return None, None

    def at(i: int) -> tuple[int, int]:
        line = items[i].get("line") or 0
        column = lines[line - 1].find(items[i].get("title") or "") if 0 < line <= len(lines) else -1
        return line, column

    named = [i for i in range(len(items)) if items[i].get("title")]
    before = [i for i in named if at(i) < spot]
    after = [i for i in named if at(i) > spot]
    a = max(before, key=at) if before else None
    b = min(after, key=at) if after else None
    if a is None or b is None or a >= len(dated) or b >= len(dated) or dated[a].value != dated[b].value:
        return None, None
    return a, b


def _stops_around(index: int, items: list[dict[str, Any]], dated: Any, skip: set[int]) -> tuple[int | None, int | None]:
    """원문에서 `index` 줄 바로 앞 일정과 바로 뒤 일정(같은 날 · 원문 줄 순서 · 이동 말 줄은 빼고). 날짜를 모르면 같은 원본 안 줄 순서."""
    day = dated[index].value if index < len(dated) else None
    same = [i for i in range(len(items)) if i != index and i not in skip and items[i].get("title")
            and (i < len(dated) and dated[i].value == day)]
    key = lambda i: (items[i].get("line") or 0, i)       # noqa: E731 — 같은 줄의 여러 항목은 읽은 순서
    before = [i for i in same if key(i) < key(index)]
    after = [i for i in same if key(i) > key(index)]
    return (max(before, key=key) if before else None), (min(after, key=key) if after else None)


def _move_segments(move_lines: dict[int, Any], items: list[dict[str, Any]], dated: Any, position: int) -> list[dict[str, Any]]:
    """이동 말 줄 → 일정에서 빼고(`items[n].removed`) 바로 앞 · 뒤 일정 사이 구간의 수단(`moves[앞~뒤].mode`, 방법 `rule`). `[2026-10-19 사용자 지시]`

    ☆전에는 「11:30 택시로 이동」이 장소 없는 일정 한 줄로 남고 경복궁 → 광장시장 구간은 추천 수단으로 계산됐다(고객이 적은 택시가 사라졌다).
    ★앞이나 뒤 일정이 없으면(마지막 날 「공항철도 타고 인천공항」) 빼지 않는다 — 그 시각의 「장소 없이 둔 출발」로 남긴다.
    ★확인 화면이 고를 수 없는 수단(자전거 · 렌터카 · 기차)은 구간에 넣지 않고 근거에만 남긴다(줄은 뺀다 — 일정이 아니다)."""
    from .landmarks import move_mode

    out: list[dict[str, Any]] = []
    skip = set(move_lines)
    for index, move in sorted(move_lines.items()):
        before, after = _stops_around(index, items, dated, skip)
        if before is None or after is None:
            continue
        mode = move_mode(move.mode)
        out.append({"field": f"items[{index}].removed", "value": True, "method": "rule",
                    "evidence": {"source": "rule", "method": "move_phrase", "line": items[index]["line"], "mode": move.mode,
                                 "segment": [before, after]},
                    "needs_review": False,
                    "note": f"「{items[index]['title']}」은 일정이 아니라 앞 · 뒤 일정 사이의 이동이라 일정에서 뺐다"})
        if mode is not None:
            out.append({"field": f"moves[{position}-{before}~{position}-{after}].mode", "value": mode, "method": "rule",
                        "evidence": {"source": "text", "text": items[index]["title"], "line": items[index]["line"]},
                        "needs_review": False, "note": f"계획서의 「{items[index]['title']}」 — 이 구간을 이 수단으로 봤어요"})
    return out


def _nameless_rows(index: int, parts: Any, item: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """이름 없는 줄(종류 + 지역만)의 값 줄 — **장소 값은 비워 두고**(없는 가게를 지어내지 않는다) 뜻의 조각을 근거에 남긴다. 고르는 것은 고객(또는 전체 자동 추천)이다.

    ★예약: 줄이 「예약 있음」이면(칸 또는 줄 글자의 「예약한」) 후보를 권하지 않고 이름만 묻는 길이다(`needs_name`). 예약을 모르면 후보를 보이며 「이미 예약하셨나요?」를 묻는다.
    ★일정 종류(`kind`)도 여기서 정한다 — 식당 · 끼니 말이면 식사다(「성수 예약 식당」이 활동으로 읽혀 활동 후보가 권해졌다). 규칙이 이미 정한 종류는 덮지 않는다."""
    booked = item.get("booked") if item.get("booked") is not None else parts.booked
    public = parts.public()
    where = f"{public['area']['name']} 지역의 " if public["area"] else ""
    evidence = {"source": "line_parts", "method": "nameless", "line": item["line"], "query": item["title"], "parts": public,
                "booked": booked}
    out = [{"field": f"items[{index}].place", "value": None, "method": "lookup", "evidence": evidence, "needs_review": True,
            "note": f"이름이 아닌 말(「{item['title']}」)이라 가게를 찾지 않았다 — {where}{public['label']}을 고르게 한다"
                    + (" · 예약이 있다고 적혀 있어 이름을 묻는다" if booked is True else "")}]
    if public["kind"] and not any(r["field"] == f"items[{index}].kind" for r in rows):
        out.append({"field": f"items[{index}].kind", "value": public["kind"], "method": "lookup",
                    "evidence": {"source": "rule", "rule": "line_parts", "line": item["line"]}, "needs_review": False,
                    "note": (f"「{public['label']}」에서 하는 {public['meal'] or '끼니'} 말이 있어 식사 일정으로 본다" if public.get("lodging_meal")
                             else f"「{public['label']}」을 뜻하는 말이라 {'식사' if public['kind'] == 'dining' else '활동'} 일정으로 본다")})
    return out


def _neighbours(index: int, items: list[dict[str, Any]], resolved: dict[int, Any], dated) -> list[tuple[float, float]]:
    """같은 날(날짜를 모르면 같은 원본)의 바로 앞·뒤 항목 중 좌표를 아는 것."""
    day = dated[index].value if index < len(dated) else None
    same = [i for i in range(len(items)) if i != index and (day is None or (i < len(dated) and dated[i].value == day))]
    near = []
    for pick in (max([i for i in same if i < index and _coords(resolved.get(i))], default=None),
                 min([i for i in same if i > index and _coords(resolved.get(i))], default=None)):
        if pick is not None:
            near.append(_coords(resolved[pick]))
    return near


def _cluster_centre(found) -> tuple[float, float] | None:
    """정하지 못했지만 후보가 서로 붙어 있으면(홍대입구역 출구들) 그 가운데 — 어느 후보든 위치가 거의 같다. `[2026-10-07 팀]`
    ☆전에는 「홍대입구역 → 교촌치킨」의 홍대입구역이 기준이 되지 못해 종로 지점을 골랐다(5.7km)."""
    from .chain_pick import CLUSTER_M, centre, spread_m

    if found is None or found.status == "resolved" or not getattr(found, "candidates", None):
        return None
    points = [(float(c["latitude"]), float(c["longitude"])) for c in found.candidates
              if c.get("latitude") is not None and c.get("longitude") is not None]
    # 관련도 1위 후보에서 CLUSTER_M 안에 절반 이상이 모였나 — 「홍대입구역 사거리」 하나가 섞여 서로 가장 먼 거리는 555m 였다
    tight = [point for point in points if spread_m([points[0], point]) <= CLUSTER_M] if points else []
    return centre(tight) if tight and len(tight) * 2 >= len(points) else None


def _visit_at(index: int, rows: list[dict[str, Any]], dated) -> datetime | None:
    """이 항목의 방문 시각(서울) — 날짜(`dated`)와 읽은 시작 시각(값 줄 `items[i].starts_at`)이 다 있을 때만. 하나라도 모르면 None.
    `[2026-10-19 사용자 지시]` 「광장시장 점심」의 근처 식당을 고를 때 그 시각에 확실히 닫힌 가게를 건너뛰는 데 쓴다(`places.resolve(at=)`)."""
    day = dated[index].value if index < len(dated) else None
    start = next((r["value"] for r in reversed(rows) if r.get("field") == f"items[{index}].starts_at" and r.get("value")), None)
    if not day or not isinstance(start, str):
        return None
    try:
        return datetime.fromisoformat(f"{day}T{start}").replace(tzinfo=KST)
    except ValueError:
        return None


def _near_hint(index: int, items: list[dict[str, Any]], resolved: dict[int, Any], dated) -> tuple[float, float] | None:
    """체인 지점 · 같은 이름 여럿을 고르는 **기준 좌표** — 같은 날(날짜를 모르면 같은 원본) 가장 가까운 앞 항목, 없으면 뒤 항목의
    좌표(정하지 못한 항목은 후보가 붙어 있을 때 그 가운데). 없으면 None — 부르는 쪽이 고르지 않고 「어느 곳인가요?」로 둔다. `[2026-10-07 팀 포팅]`"""
    day = dated[index].value if index < len(dated) else None
    same = [i for i in range(len(items)) if i != index and (day is None or (i < len(dated) and dated[i].value == day))]
    for i in sorted([i for i in same if i < index], reverse=True) + sorted(i for i in same if i > index):
        found = resolved.get(i)
        point = _coords(found) or _cluster_centre(found)
        if point is not None:
            return point
    return None


def _coords(found) -> tuple[float, float] | None:
    if found is None or found.status != "resolved" or found.latitude is None or found.longitude is None:
        return None
    return float(found.latitude), float(found.longitude)


#: 이동 수단 값 줄로 확인 화면에 싣는 수단(`review.MOVE_MODES`) — 에이전트의 「대중교통」은 지하철로, 나머지(자동차 · 자전거 · 케이블카)는 화면 칸이 없어 기록만 한다
_AGENT_MODE = {"taxi": "taxi", "subway": "subway", "bus": "bus", "walk": "walk", "transit": "subway"}


def _agent_booking_rows(read: Any, item: Any, index: int) -> list[dict[str, Any]]:
    """원문에서 같은 장소에 붙은 예약 값만 보존한다. 여러 장소에 걸친 인용은 추측하지 않는다."""
    matches = [i for i, original in enumerate(read.items)
               if original.title is not None and original.title.line == item.title.line
               and max(original.title.start, item.title.start) < min(original.title.end, item.title.end)]
    if len(matches) != 1:
        return []
    prefix = f"items[{matches[0]}]"
    rows = []
    for claim in read.claims:
        if claim.field not in (f"{prefix}.booked", f"{prefix}.booking_no"):
            continue
        row = claim.as_dict()
        row["field"] = f"items[{index}]" + claim.field[len(prefix):]
        rows.append(row)
    return rows


def _agent_rows(read: Any, out: Any, *, position: int, today: date,
                copied_cards: list[Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Any, bool]:
    """읽기 에이전트 결과 → (값 줄, 항목, 날짜, 첫날 묻기). `[2026-10-16]`

    ★에이전트가 시각이 적힌 줄을 통째로 빠뜨리면(실제 접수 시험에서 둘째 날 다섯 줄) 규칙이 그 줄에서 읽은 항목을 붙인다 —
      단 그 줄이 에이전트가 이동 · 조건 · 성향으로 읽은 줄이거나(「택시로 이동」) 고객이 메시지 안에서 고친 경우(정정)는 붙이지 않는다.
    ★날짜는 에이전트 값이 먼저, 없으면 규칙의 날짜 해석(`resolve_dates`)."""
    from .dates import DayDate, resolve_dates
    from .places import normalize

    lines = read.lines
    cards_by_line = {card.title.line: card for card in copied_cards or []}
    rows: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    guessed_dates: set[int] = set()
    by_line: dict[int, list[Any]] = {}
    for it in out.items:
        by_line.setdefault(it.title.line, []).append(it)

    from .span_segments import split_segments

    segments: dict[tuple[int, int, int], dict[str, Any]] = {}

    def build_segments() -> None:
        # 제목은 아래에서 앞 카드 원문으로 바뀔 수 있다 — 바뀐 뒤의 범위로 처음 부를 때 만든다
        by_line_now: dict[int, list[Any]] = {}
        for item in out.items:
            by_line_now.setdefault(item.title.line, []).append(item)
        for line_no, line_items in by_line_now.items():
            line = lines[line_no - 1]
            ordered = sorted(line_items, key=lambda item: item.title.start)
            bounds = split_segments(line, [(item.title.start, item.title.end) for item in ordered])
            for item, (start, end) in zip(ordered, bounds):
                segments[(line_no, item.title.start, item.title.end)] = {
                    "line": line_no, "start": start, "end": end, "text": line[start:end]}

    def segment(it: Any) -> dict[str, Any]:
        # 다음 장소 앞의 「저녁」·시각은 그 장소 몫이다. 조립과 같은 경계를 저장한다.
        if not segments:
            build_segments()
        return segments[(it.title.line, it.title.start, it.title.end)]

    # ★`[2026-10-16 D-025 사실 검사]` 같은 줄에 규칙이 읽은 시각 — 에이전트가 항목은 읽고 시각을 비웠거나(실제 접수 R08: 9곳) 시각 근거를 **다른 줄**에서
    #   가져왔으면(R19: 경복궁 10:00 → 12:00) 그 줄의 원문 시각을 쓴다. 같은 줄 근거로 오후를 판단한 값(「1시 점심」→13:00)은 그대로 둔다.
    #   그 줄에 규칙 항목이 하나일 때만(한 줄에 장소가 여럿이면 어느 시각인지 규칙도 모른다)
    rule_clock: dict[int, Any] = {}
    for rule_item in read.items:
        if rule_item.title is not None and rule_item.start:
            rule_clock.setdefault(rule_item.title.line, []).append(rule_item)
    line_counts = {}
    for it in out.items:
        line_counts[it.title.line] = line_counts.get(it.title.line, 0) + 1
    for it in out.items:
        card = cards_by_line.get(it.title.line)
        if card is not None:
            it.title = agent_module.Quote(**card.title.as_dict())
            it.start, it.end, it.time_guessed = card.start.value, card.end.value, False
            it.time_from_rule = True
            continue
        same = rule_clock.get(it.title.line) or []
        if len(same) != 1 or line_counts[it.title.line] > 1:
            continue
        quote_line = it.time_quote.line if it.time_quote is not None else None
        if it.start is None or (quote_line is not None and quote_line != it.title.line and same[0].start != it.start):
            it.start, it.end, it.time_quote, it.time_guessed = same[0].start, it.end or same[0].end, None, False
            it.time_from_rule = True                                          # 근거 표시용 — 아래 값 줄의 방법이 규칙이 된다

    for it in out.items:
        index = len(items)
        booking_rows = _agent_booking_rows(read, it, index)
        rows.extend(booking_rows)
        booked = next((r["value"] for r in booking_rows if r["field"].endswith(".booked")),
                      True if any(r["field"].endswith(".booking_no") for r in booking_rows) else None)
        rows.append({"field": f"items[{index}].title", "value": it.title.text, "method": "llm_agent",
                     "evidence": {"source": "text", **it.title.as_dict(), "segment": segment(it)}, "needs_review": False,
                     "note": "읽기 에이전트가 가리킨 원문 조각"})
        if getattr(it, "time_from_rule", False):
            card = cards_by_line.get(it.title.line)
            rows.append({"field": f"items[{index}].starts_at", "value": it.start, "method": "rule",
                         "evidence": {"source": "text", **card.start.span.as_dict()} if card else {"source": "text", "line": it.title.line}, "needs_review": False,
                         "note": "앞 카드 시각줄의 원문 시각으로 맞췄어요" if card else "같은 줄의 원문 시각(규칙)으로 맞췄어요"})
        for name, value in (("starts_at", None if getattr(it, "time_from_rule", False) else it.start), ("ends_at", it.end)):
            if value:
                card = cards_by_line.get(it.title.line)
                rows.append({"field": f"items[{index}].{name}", "value": value, "method": "rule" if card else "llm_agent",
                             "evidence": {"source": "text", **card.end.span.as_dict()} if card else
                                         {"source": "text", **it.time_quote.as_dict()} if it.time_quote else {"source": "model"},
                             "needs_review": it.time_guessed,
                             "note": (f"「{it.time_quote.text}」을 오후로 봤어요 — 다르면 고쳐 주세요" if it.time_guessed and it.time_quote
                                      else "읽기 에이전트가 읽은 시각")})
        if it.kind == "dining":
            rows.append({"field": f"items[{index}].kind", "value": "dining", "method": "llm_agent",
                         "evidence": {"source": "text", "line": it.title.line}, "needs_review": False, "note": "읽기 에이전트 — 식사"})
        if it.role == "origin":
            rows.append({"field": f"items[{index}].role", "value": "origin", "method": "llm_agent",
                         "evidence": it.title.as_dict(), "needs_review": False, "note": "고객이 말한 출발 위치 — 체류 없음"})
        if it.date_guessed:
            guessed_dates.add(index)
        # ★`[2026-10-19 진단 포인트 2]` 에이전트가 「숙소」라고 읽은 항목은 장소를 숙소 자료에서만 찾는다(`_place_kind_hint`) — 전에는 식사만 넘기고 숙소를 버렸다
        items.append({"line": it.title.line, "day": it.day, "date": it.date, "title": it.title.text,
                      "meal": it.kind == "dining", "lodging": it.kind == "lodging", "booked": booked, "segment": segment(it),
                      "start": it.start})
    agent_count = len(items)

    # 규칙이 읽은 시각 있는 줄 중 에이전트가 빠뜨린 줄
    covered = {it.title.line for it in out.items}
    noted: set[int] = set()
    for quote in [m.get("quote") for m in out.moves] + [c.get("quote") for c in out.conditions] + [p.get("quote") for p in out.preferences]:
        noted |= {n for n, line in enumerate(lines, start=1) if quote and quote in line}
    # ★`[2026-10-20 사용자 지시]` 에이전트가 일정이 아니라 빈 시간 · 추천 요청 · 질문 · 잡담으로 읽은 줄 — 규칙 일정은 **뺀 채로** 두고 묻는다(`interpretations.py`).
    #   ☆전에는 「오후 13시~16시 정도」(에이전트: 빈 시간)를 빠뜨린 줄로 보고 규칙 일정 「정도」를 넣어 오타 고침 「정돈 대학로본점」이 됐다
    from . import interpretations

    contested = interpretations.contested_lines(lines, out)
    if "correction" not in out.requests or copied_cards:
        claims_by_item: dict[int, list[Any]] = {}
        for claim in read.claims:
            if claim.field.startswith("items["):
                claims_by_item.setdefault(int(claim.field[6:claim.field.index("]")]), []).append(claim)
        for k, rule_item in enumerate(read.items):
            line = rule_item.title.line if rule_item.title else None
            if line is None or not rule_item.start or line in covered or line in noted:
                continue
            if "correction" in out.requests:
                card = cards_by_line.get(line)
                if card is None or not schedule_cards.may_restore(card, out.requests, out.pieces):
                    continue
            index = len(items)
            reading = contested.get(line)
            for claim in claims_by_item.get(k, []):
                row = claim.as_dict()
                row["field"] = f"items[{index}]" + claim.field[claim.field.index("]") + 1:]
                row["note"] = ((row.get("note") or "") + (" · 규칙이 읽은 일정 — 읽기 에이전트는 이 줄을 다르게 읽었다" if reading
                                                          else " · 읽기 에이전트가 빠뜨린 줄이라 규칙으로 읽었다")).lstrip(" ·")
                rows.append(row)
            if reading is not None:
                rows.extend(interpretations.question_rows(index=index, position=position, line=line, line_text=lines[line - 1],
                                                          reading=reading, rule_title=rule_item.title.text, rule_start=rule_item.start))
            items.append({"line": line, "day": rule_item.day, "date": rule_item.date, "title": rule_item.title.text,
                          "meal": any(c.field == f"items[{k}].kind" for c in claims_by_item.get(k, [])), "booked": rule_item.booked,
                          "start": rule_item.start})
    # 일차 머리줄 · 여행 전체(규칙이 원문에서 잡은 것)는 근거가 원문 위치라 그대로 싣는다 — 「읽은 줄」 표시와 일차 묶음에 쓰인다
    rule_trip: set[str] = set()
    for claim in read.claims:
        if claim.field.startswith("days[") or claim.field.startswith("trip."):
            rows.append(claim.as_dict())
            rule_trip.add(claim.field)
    for key, value in out.trip.items():
        if f"trip.{key}" not in rule_trip and value:
            rows.append({"field": f"trip.{key}", "value": value, "method": "llm_agent", "evidence": {"source": "model"},
                         "needs_review": True, "note": "읽기 에이전트가 읽은 값 — 다르면 고쳐 주세요"})
    if "plan_ask" in out.requests:
        rows.append({"field": "trip.plan_request", "value": True, "method": "llm_agent", "evidence": {"source": "model"},
                     "needs_review": False, "note": "「일정 짜 줘」— 확인 화면에서 일정 생성기로 넘긴다"})

    dated, ask = resolve_dates(items, today=today, lines=lines)
    for index, day_date in enumerate(dated):
        if index in guessed_dates and day_date.value:
            dated[index] = DayDate(day_date.value, "agent_relative", True, "읽기 에이전트가 오늘 기준으로 정한 날짜 — 다르면 고쳐 주세요")
    for index, day_date in enumerate(dated):
        rows.append({"field": f"items[{index}].date", "value": day_date.value, "method": "llm_agent" if index < agent_count else "rule",
                     "evidence": {"source": "rule", "how": day_date.how, "line": items[index]["line"]},
                     "needs_review": day_date.needs_review, "note": day_date.note})
    if ask or (not items and "first_day_date" in out.missing):
        rows.append({"field": "trip.ask_first_day", "value": True, "method": "rule" if ask else "llm_agent",
                     "evidence": {"source": "rule"}, "needs_review": True, "note": "날짜가 적혀 있지 않다 — 첫날 날짜 하나만 묻는다"})

    # 이동 수단 — 확인 화면의 구간 수단 값 줄(`moves[{앞}~{뒤}].mode`, `review.picked_modes`). 구간은 같은 날 시각 순서로 이웃한 두 항목
    order = sorted(range(len(items)), key=lambda i: (dated[i].value or "", items[i].get("start") or "99:99", i))
    pairs = [(a, b) for a, b in zip(order, order[1:]) if dated[a].value == dated[b].value]

    def find(quote: Any) -> int | None:
        key = normalize(quote or "")
        return next((i for i, item in enumerate(items)
                     if key and (key in normalize(item["title"] or "") or normalize(item["title"] or "") in key)), None)

    picked: dict[tuple[int, int], tuple[str, str]] = {}
    for move in out.moves:
        mode = _AGENT_MODE.get(move.get("mode"))
        if mode is None:
            continue
        if move.get("scope") == "segment":
            a, b = find(move.get("from")), find(move.get("to"))
            if a is None and b is None:
                # ★`[2026-10-19 사용자 지시]` 에이전트가 앞뒤 장소를 비웠다 — 수단 말이 적힌 원문 자리의 바로 앞 · 뒤 일정 사이로 본다(규칙 길 `_move_segments` 와 같다).
                #   ☆전에는 어느 구간에도 붙지 않아 고객이 적은 수단이 사라졌다
                a, b = _around_quote(move.get("quote"), lines, items, dated)
            if b is not None:
                chosen = [(x, y) for x, y in pairs if y == b and (a is None or x == a)]
            else:
                chosen = [(x, y) for x, y in pairs if a is not None and x == a]
        else:
            day_value = None
            if move.get("scope") == "day" and move.get("day"):
                day_items = [i for i in order if items[i].get("day") == move["day"]]
                day_value = dated[day_items[0]].value if day_items else None
            chosen = [(x, y) for x, y in pairs if day_value is None or dated[x].value == day_value]
        for pair in chosen:
            picked[pair] = (mode, move.get("quote") or "")
    for (a, b), (mode, quote) in picked.items():
        rows.append({"field": f"moves[{position}-{a}~{position}-{b}].mode", "value": mode, "method": "llm_agent",
                     "evidence": {"source": "text", "text": quote}, "needs_review": False,
                     "note": f"계획서의 「{quote}」 — 이 구간을 이 수단으로 봤어요"})
    return rows, items, dated, ask


def _mark_for(line: int, marks: list[tuple[int, Any, Any]]) -> tuple[int | None, str | None]:
    day = date_value = None
    for mark_line, mark_day, mark_date in sorted(marks, key=lambda m: m[0]):
        if mark_line > line:
            break
        if mark_day is not None:
            day, date_value = mark_day, None
        if mark_date is not None:
            date_value = mark_date
    return day, date_value


#: 우리가 넣은 기본 별칭 — 옛 이름 · 흔한 줄임말(고객 글 → 다시 찾을 이름). 값은 매번 조회한다
SEED_ALIASES = {"남산타워": "N서울타워", "남산서울타워": "N서울타워", "서울타워": "N서울타워",
                "롯데타워": "롯데월드타워", "동대문디자인플라자": "DDP"}


def load_aliases(conn, tenant_id: str, customer_id: Any) -> dict[str, str]:
    """정규화한 원문 → 다시 찾을 이름. 고객이 고친 것이 기본값을 이긴다.

    ★`[2026-09-30 사용자 확인 「명백한 버그」]` **누구의 별칭인지 가른다.** 기본값(`source='seed'`)만 모든 고객에게 쓰고, 고객이 고친 것은
      **그 고객의 다음 접수에만** 쓴다(마이그레이션 038). ☆전에는 테넌트 전체가 공유해 한 고객의 「이촌동 점심 식당 → 엘 샌드위치」가
      다른 고객의 같은 원문에 자동으로 적용됐다(고른 값은 그 여행에 대한 그 사람의 선택이지 이름 교정이 아니다 — 데이터 격리 문제).
      누가 고쳤는지 모르는 옛 행(`customer_id` 없음)은 아무에게도 쓰지 않는다."""
    from .places import normalize

    out = {normalize(k): v for k, v in SEED_ALIASES.items()}
    with conn.cursor() as cur:
        cur.execute("SELECT phrase_norm, replacement FROM place_aliases WHERE tenant_id=%s AND "
                    "(source='seed' OR (source='customer' AND customer_id = %s)) "
                    "ORDER BY (source='customer')", (tenant_id, customer_id))
        out.update(dict(cur.fetchall()))
    return out


def remember_alias(cur, tenant_id: str, customer_id: Any, phrase: str, replacement: str) -> None:
    """확인 화면에서 고객이 장소 이름을 고치면 (원래 글 → 고친 글)을 **그 고객의 것으로** 쌓는다. ★둘 다 고객 글이다(약관, 030 머리).
    다른 고객에게는 쓰이지 않는다(`load_aliases`)."""
    from .places import normalize

    key = normalize(phrase)
    if not key or key == normalize(replacement):
        return
    cur.execute("INSERT INTO place_aliases (tenant_id, phrase_norm, phrase, replacement, source, customer_id) "
                "VALUES (%s,%s,%s,%s,'customer',%s) "
                "ON CONFLICT (tenant_id, phrase_norm, (COALESCE(customer_id, '00000000-0000-0000-0000-000000000000'::uuid))) "
                "DO UPDATE SET replacement=EXCLUDED.replacement, source='customer', uses=place_aliases.uses + 1, "
                "updated_at=now()",
                (tenant_id, key, phrase[:120], replacement[:120], customer_id))


def _our_places(conn, tenant_id: str, *, trip_id=None) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT place_id, name, kind, latitude, longitude FROM places WHERE tenant_id=%s "
                    "AND (trip_scope IS NULL OR trip_scope=%s) ORDER BY trip_scope NULLS FIRST,place_id",
                    (tenant_id, trip_id))  # Only the verified current trip may add its private picks.
        return [dict(zip(("place_id", "name", "kind", "latitude", "longitude"), r)) for r in cur.fetchall()]


# ── 부품 ─────────────────────────────────────────────────────────
def _items(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`items[n].필드` 줄들을 항목으로 묶는다. 각 값은 근거를 같이 들고 간다."""
    items: dict[int, dict[str, Any]] = {}
    for claim in claims:
        field = claim["field"]
        if not field.startswith("items["):
            continue
        index = int(field[6:field.index("]")])
        name = field[field.index("]") + 2:]
        entry = items.setdefault(index, {"index": index, "fields": {}})
        entry["fields"][name] = {"value": claim["value"], "method": claim["method"],
                                 "evidence": claim["evidence"], "needs_review": claim["needs_review"],
                                 "note": claim["note"]}
    days = _day_dates(claims)
    for entry in items.values():
        line = min((f["evidence"].get("line") or 0 for f in entry["fields"].values()
                    if f["evidence"].get("line")), default=0)
        entry["line"] = line
        entry["day"], entry["date"] = _day_for(line, days)
        if "date" in entry["fields"] and entry["fields"]["date"]["value"]:
            entry["date"] = entry["fields"]["date"]["value"]        # ★날짜 해석이 정한 값이 이긴다
    return [items[k] for k in sorted(items)]


def _day_dates(claims: list[dict[str, Any]]) -> list[tuple[int, int | None, str | None]]:
    """(줄, 몇째 날, 날짜) — 일차 머리줄·날짜 줄의 위치."""
    marks: dict[int, list] = {}
    for claim in claims:
        field, line = claim["field"], claim["evidence"].get("line", 0)
        if field.startswith("days[") and field.endswith(".heading"):
            marks.setdefault(line, [None, None])[0] = claim["value"]
        elif field.startswith("days[") and field.endswith(".date"):
            marks.setdefault(line, [None, None])[1] = claim["value"]
    return [(line, day, date) for line, (day, date) in sorted(marks.items())]


def _day_for(line: int, marks: list[tuple[int, int | None, str | None]]) -> tuple[int | None, str | None]:
    day = date = None
    for mark_line, mark_day, mark_date in marks:
        if mark_line > line:
            break
        if mark_day is not None:
            day, date = mark_day, mark_date
        elif mark_date is not None:
            date = mark_date
    return day, date


def _trip_fields(claims: list[dict[str, Any]]) -> dict[str, Any]:
    return {c["field"][5:]: {"value": c["value"], "evidence": c["evidence"]}
            for c in claims if c["field"].startswith("trip.")}


def _sources(conn, tenant_id: str, intake_id: UUID) -> list[dict[str, Any]]:
    columns = ("source_id", "position", "kind", "filename", "transcript", "transcribed", "missing_json", "seconds")
    with conn.cursor() as cur:
        try:
            with conn.transaction():                              # ★마이그레이션 055(`differs_json`)가 안 올라간 DB 에서도 읽는다 — 그때는 「다르게 읽은 줄」이 없는 것으로 본다
                cur.execute(f"SELECT {', '.join(columns)}, differs_json FROM intake_sources WHERE tenant_id=%s AND intake_id=%s "
                            "ORDER BY position", (tenant_id, intake_id))
                return [dict(zip((*columns, "differs_json"), r)) for r in cur.fetchall()]
        except Exception as exc:                                  # noqa: BLE001 — 칸이 없을 때만 물러난다
            if type(exc).__name__ != "UndefinedColumn":
                raise
            log.warning("intake_sources.differs_json missing — reading without it (migration 055?)")
        cur.execute(f"SELECT {', '.join(columns)} FROM intake_sources WHERE tenant_id=%s AND intake_id=%s "
                    "ORDER BY position", (tenant_id, intake_id))
        return [dict(zip(columns, r)) for r in cur.fetchall()]


def _store_transcript(conn, cur, source_id: Any, tenant_id: str, result: Any) -> None:
    """받아쓴 글 · 빠진 줄 · 다르게 읽은 줄을 저장한다. 055 가 안 올라간 DB 에서는 다르게 읽은 줄만 빼고 저장한다(경고)."""
    base = (result.text, bool(result.transcribed_pages) or result.kind == "image", json.dumps(result.missing, ensure_ascii=False), result.seconds)
    try:
        with conn.transaction():
            cur.execute("UPDATE intake_sources SET transcript=%s, transcribed=%s, missing_json=%s, seconds=%s, differs_json=%s "
                        "WHERE source_id=%s AND tenant_id=%s", (*base, json.dumps(result.differs, ensure_ascii=False), source_id, tenant_id))
        return
    except Exception as exc:                                      # noqa: BLE001
        if type(exc).__name__ != "UndefinedColumn":
            raise
        log.warning("intake_sources.differs_json missing — transcript saved without it (migration 055?)")
    cur.execute("UPDATE intake_sources SET transcript=%s, transcribed=%s, missing_json=%s, seconds=%s "
                "WHERE source_id=%s AND tenant_id=%s", (*base, source_id, tenant_id))


def differs_by_line(rows: Any) -> dict[int, dict[str, Any]]:
    """저장된 「다르게 읽은 줄」 → {줄 번호: 줄 정보}. 모양이 이상한 줄은 건너뛴다(없는 것으로 본다)."""
    out: dict[int, dict[str, Any]] = {}
    for row in rows or []:
        if isinstance(row, dict) and isinstance(row.get("line"), int):
            out[row["line"]] = row
    return out


def _hold_reading(cur, tenant_id: str, intake_id: UUID) -> None:
    """이 트랜잭션 안에서 접수 행을 **잠그고** 아직 읽는 중인지 본다 — 아니면 `_Abandoned`. 실패 확정(`reap_stalled`)은 같은 행을 갱신하므로
    둘 중 하나가 먼저 끝나야 다른 쪽이 진행한다(일꾼이 실패 확정 뒤에 원본 · 값을 쓰지 못한다)."""
    cur.execute("SELECT 1 FROM trip_intakes WHERE tenant_id=%s AND intake_id=%s AND status='reading' FOR UPDATE", (tenant_id, intake_id))
    if cur.fetchone() is None:
        raise _Abandoned()


def _stage(connect, tenant_id: str, intake_id: UUID, stage: str) -> None:
    """읽는 중일 때만 단계를 바꾼다 — 그 사이 실패로 확정됐으면 `_Abandoned`(되살리지 않는다)."""
    with connect() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("UPDATE trip_intakes SET stage=%s, updated_at=now() WHERE tenant_id=%s AND intake_id=%s AND status='reading'",
                    (stage, tenant_id, intake_id))
        if cur.rowcount == 0:
            raise _Abandoned()


def _fatal(connect, tenant_id: str, intake_id: UUID, code: str, detail: str) -> None:
    with connect() as conn, conn.transaction(), conn.cursor() as cur:
        # 읽는 중인 접수만 실패로 만든다(이미 확인 화면 · 등록 · 실패인 접수는 그대로). 읽다 만 값은 남기지 않는다 — 못 읽은 접수의 확인 화면에
        # 반쯤 읽은 일정이 보이지 않게(전에는 값을 끝에 한꺼번에 적어 이 경우가 없었다)
        cur.execute("UPDATE trip_intakes SET status='fatal', stage='fatal', fatal_code=%s, fatal_detail=%s, "
                    "updated_at=now() WHERE tenant_id=%s AND intake_id=%s "
                    "AND (status='reading' OR (status='review' AND stage='checking'))", (code, detail, tenant_id, intake_id))
        if cur.rowcount:
            cur.execute("DELETE FROM intake_claims WHERE tenant_id=%s AND intake_id=%s AND revision=1 AND method <> 'customer'",
                        (tenant_id, intake_id))


def _claim_sink(connect, tenant_id: str, intake_id: UUID, source_id: Any) -> Callable[[list[dict[str, Any]]], None]:
    """읽는 동안 값 줄을 **바로** 적는 함수 — 한 번 부를 때마다 한 묶음(트랜잭션 하나)이고 접수의 갱신 시각도 올린다
    (뒤에서 읽는 일꾼이 살아 있다는 표시 — 실시간 진행이 「멈춤」으로 오해하지 않게)."""
    def write(batch: list[dict[str, Any]]) -> None:
        with connect() as conn, conn.transaction(), conn.cursor() as cur:
            # 먼저 접수가 아직 읽는 중인지 보고 갱신 시각을 올린다(한 문장) — 실패로 확정된 접수에는 값을 더 적지 않는다
            cur.execute("UPDATE trip_intakes SET updated_at=now() WHERE tenant_id=%s AND intake_id=%s AND status='reading'",
                        (tenant_id, intake_id))
            if cur.rowcount == 0:
                raise _Abandoned()
            for row in batch:
                cur.execute("INSERT INTO intake_claims (intake_id, tenant_id, revision, source_id, field, "
                            "value_json, method, evidence, needs_review, note) "
                            "VALUES (%s,%s,1,%s,%s,%s,%s,%s,%s,%s)",
                            (intake_id, tenant_id, source_id, row["field"],
                             json.dumps(row["value"], ensure_ascii=False), row["method"],
                             json.dumps({**row["evidence"], "source_id": str(source_id)}, ensure_ascii=False, default=str),
                             row["needs_review"], row["note"]))
    return write


def _claims(conn, tenant_id: str, intake_id: UUID, revision: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT source_id, field, value_json, method, evidence, needs_review, note FROM intake_claims "
                    "WHERE tenant_id=%s AND intake_id=%s AND revision=%s ORDER BY created_at, claim_id",
                    (tenant_id, intake_id, revision))
        return [dict(zip(("source_id", "field", "value", "method", "evidence", "needs_review", "note"), r))
                for r in cur.fetchall()]


__all__ = ["IntakeConflict", "IntakeRejected", "MAX_FILES", "MAX_FILE_BYTES", "MAX_TEXT_CHARS", "STAGES", "draft",
           "edit", "mark_confirmed", "open_intake", "process", "view"]
