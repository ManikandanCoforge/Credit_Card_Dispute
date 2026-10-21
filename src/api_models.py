from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    status: Literal["ok"]
    dataset: str = Field(min_length=1)
    fictional_training_only: Literal[True]


class CaseSummary(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    case_id: str
    intake_source: str
    documents: list[str]


class CaseListResponse(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    cases: list[CaseSummary]


class ToolPayload(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    source_id: str = Field(min_length=1)


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True, frozen=True)

    error: str = Field(min_length=1)
    retryable: bool | None = None
    message: str | None = None
    existing_record_id: str | None = None


class ReviewCreated(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    review_id: str
    status: Literal["pending"]
    draft_hash: str


class ReviewRow(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    case_id: str
    draft: str
    hash: str
    status: str
    reviewer: str | None
