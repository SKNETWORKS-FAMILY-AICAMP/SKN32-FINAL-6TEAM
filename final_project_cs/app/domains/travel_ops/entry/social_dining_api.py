"""고객 제공 SNS 맛집 링크의 웹 경계. 일정 적용은 기존 접수 검증기를 거친다."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.settings import get_guardrails
from app.domains.travel_ops.components.intake.pipeline import IntakeConflict, IntakeRejected


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1)
    note: str = ""
    priority: Literal["must", "if_fits"] = "if_fits"


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    links: list[LinkIn] = Field(min_length=1)


class UpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority: Literal["must", "if_fits"] | None = None
    restaurant_index: int | None = Field(default=None, ge=0)
    selected_ref: str | None = None
    name: str | None = None
    area: str | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("보완하거나 선택할 값을 보내 주세요")
        return self


class PreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    target_item_id: str | None = None


class ApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    proposal_id: str = Field(min_length=1, max_length=128)


def register_routes(router, *, web_customer, count, lazy, chat_factory, kakao_factory,
                    dining_factory, error, service=None, connection_factory=None, sse_response=None):
    """기존 고객 인증·요청 제한·모델/조회 조립을 재사용한다. DB와 서비스는 요청 때 얻는다."""
    prefix = "/v1/web/trip-intakes/{intake_id}/dining-links"

    def invoke(operation, who, intake_id, **kwargs):
        from app.infrastructure.db.session import get_connection

        tenant, customer = who
        api = service
        if api is None:
            from app.domains.travel_ops.components.intake import social_dining
            api = social_dining
        connect = connection_factory or get_connection
        try:
            with connect() as conn:
                return getattr(api, operation)(conn, tenant_id=tenant, customer_id=customer,
                                                intake_id=intake_id, **kwargs)
        except LookupError:
            raise error(404, "not_found", "resource not found") from None
        except IntakeConflict as exc:
            raise error(409, exc.code, exc.message, **exc.detail) from None
        except IntakeRejected as exc:
            raise error(422, exc.code, exc.message) from None
        except ValueError:
            raise error(422, "invalid_dining_link", "맛집 링크와 선택 내용을 확인해 주세요") from None

    def perform(http, who, work):
        if "text/event-stream" in http.headers.get("accept", "").lower() and sse_response is not None:
            return sse_response(*who, op="intake", http=http,
                                work=lambda progress, defer: work(progress.stage))
        return work(None)

    @router.get(prefix)
    def list_dining_links(intake_id: UUID, who=Depends(web_customer)):
        return invoke("list_links", who, intake_id)

    @router.post(prefix)
    def resolve_dining_links(intake_id: UUID, request: ResolveIn, http: Request, who=Depends(web_customer)):
        cfg = get_guardrails().get("travel.social_dining")
        if len(request.links) > int(cfg["max_links"]):
            raise error(422, "too_many_links", f"한 번에 링크 {cfg['max_links']}개까지 보내 주세요")
        if any(len(link.url) > int(cfg["max_url_chars"]) or len(link.note) > int(cfg["max_metadata_chars"])
               for link in request.links):
            raise error(422, "dining_link_too_long", "링크나 보완 내용이 너무 길어요")
        count("place_search", *who, http)

        def work(progress):
            return invoke("resolve", who, intake_id, entries=[x.model_dump() for x in request.links],
                          chat=lazy("chat", chat_factory), progress=progress)

        return perform(http, who, work)

    @router.patch(prefix + "/{key}")
    def update_dining_link(intake_id: UUID, key: str, request: UpdateIn, http: Request, who=Depends(web_customer)):
        cfg = get_guardrails().get("travel.social_dining")
        if any(isinstance(value, str) and len(value) > int(cfg["max_metadata_chars"])
               for value in request.model_dump(exclude_unset=True).values()):
            raise error(422, "dining_link_too_long", "보완 내용이 너무 길어요")
        count("place_search", *who, http)
        return invoke("update", who, intake_id, key=key, **request.model_dump(exclude_unset=True))

    @router.post(prefix + "/preview")
    def preview_dining_links(intake_id: UUID, request: PreviewIn, http: Request, who=Depends(web_customer)):
        count("place_search", *who, http)

        def work(progress):
            if progress is not None:
                progress("checking")
            return invoke("preview", who, intake_id, revision=request.revision,
                          target_item_id=request.target_item_id, chat=lazy("chat", chat_factory),
                          kakao=lazy("kakao", kakao_factory))

        return perform(http, who, work)

    @router.post(prefix + "/apply")
    def apply_dining_links(intake_id: UUID, request: ApplyIn, http: Request, who=Depends(web_customer)):
        count("place_search", *who, http)

        # [2026-10-15 브라우저 실측] 적용은 전체 일정을 다시 검사해 1분을 넘길 수 있다 — 미리보기처럼 진행 상태(SSE)로도 답한다.
        def work(progress):
            if progress is not None:
                progress("checking")
            return invoke("apply", who, intake_id, revision=request.revision, proposal_id=request.proposal_id,
                          kakao=lazy("kakao", kakao_factory),
                          dining=lazy("social_dining_ledger", dining_factory))

        return perform(http, who, work)
