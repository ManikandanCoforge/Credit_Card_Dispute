import pytest
from pydantic import ValidationError

from src.api_models import HealthResponse


def test_dev_health_body_parses():
    parsed = HealthResponse.model_validate(
        {
            "status": "ok",
            "dataset": "card-disputes-dev",
            "fictional_training_only": True,
        }
    )
    assert parsed.status == "ok"
    assert parsed.dataset == "card-disputes-dev"
    assert parsed.fictional_training_only is True


def test_parsed_health_body_rejects_mutation():
    parsed = HealthResponse.model_validate(
        {
            "status": "ok",
            "dataset": "card-disputes-dev",
            "fictional_training_only": True,
        }
    )
    with pytest.raises(ValidationError):
        parsed.dataset = "card-disputes-other"


def test_health_body_keeps_an_extra_key():
    parsed = HealthResponse.model_validate(
        {
            "status": "ok",
            "dataset": "card-disputes-dev",
            "fictional_training_only": True,
            "region": "dev",
        }
    )
    assert parsed.model_extra == {"region": "dev"}


def test_health_body_rejects_empty_dataset():
    with pytest.raises(ValidationError):
        HealthResponse.model_validate(
            {"status": "ok", "dataset": "", "fictional_training_only": True}
        )


def test_health_body_rejects_coerced_training_marker():
    with pytest.raises(ValidationError):
        HealthResponse.model_validate(
            {
                "status": "ok",
                "dataset": "card-disputes-dev",
                "fictional_training_only": "true",
            }
        )


def test_health_body_missing_dataset_is_rejected():
    with pytest.raises(ValidationError):
        HealthResponse.model_validate(
            {"status": "ok", "fictional_training_only": True}
        )
