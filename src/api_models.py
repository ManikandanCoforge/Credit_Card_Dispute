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
