"""Inbound JSON bodies from the local mock."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Health body. Status is ok and the training marker is true."""

    model_config = ConfigDict(extra="allow", frozen=True)

    status: Literal["ok"]
    dataset: str = Field(min_length=1)
    fictional_training_only: Literal[True]


class CaseSummary(BaseModel):
    """One case in the case list: case id, intake source, and document ids."""

    model_config = ConfigDict(extra="allow", frozen=True)

    case_id: str
    intake_source: str
    documents: list[str]


class CaseListResponse(BaseModel):
    """The mock case list."""

    model_config = ConfigDict(extra="allow", frozen=True)

    cases: list[CaseSummary]


class ToolPayload(BaseModel):
    """A transaction or merchant tool body. Fixture fields besides source id are kept."""

    model_config = ConfigDict(extra="allow", frozen=True)

    source_id: str = Field(min_length=1)


class ErrorBody(BaseModel):
    """An error body. The error code is an open string."""

    model_config = ConfigDict(extra="allow", strict=True, frozen=True)

    error: str = Field(min_length=1)
    retryable: bool | None = None
    message: str | None = None
    existing_record_id: str | None = None


class ReviewCreated(BaseModel):
    """The body returned when a review is submitted. Status is pending."""

    model_config = ConfigDict(extra="allow", frozen=True)

    review_id: str
    status: Literal["pending"]
    draft_hash: str


class ReviewRow(BaseModel):
    """A fetched review. The draft stays the stored string, and reviewer may be null."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    case_id: str
    draft: str
    hash: str
    status: str
    reviewer: str | None


class RecordCreated(BaseModel):
    """The body returned when a record is created. Status is created."""

    model_config = ConfigDict(extra="allow", frozen=True)

    record_id: str
    case_id: str
    status: Literal["created"]
    review_id: str


class RecordRow(BaseModel):
    """A fetched record. The draft stays the stored string."""

    model_config = ConfigDict(extra="allow", frozen=True)

    id: str
    case_id: str
    draft: str
    review_id: str
