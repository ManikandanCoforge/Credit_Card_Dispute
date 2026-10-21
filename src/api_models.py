from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    status: Literal["ok"]
    dataset: str = Field(min_length=1)
    fictional_training_only: Literal[True]
