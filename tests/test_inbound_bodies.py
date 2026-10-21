import pytest
from pydantic import ValidationError

from src.api_models import CaseListResponse, HealthResponse


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


def test_case_list_parses_one_dev_case():
    parsed = CaseListResponse.model_validate(
        {
            "cases": [
                {
                    "case_id": "CARD-D01",
                    "intake_source": "CARD-D01-INTAKE",
                    "documents": ["CARD-D01-INTAKE", "CARD-D01-ATTACHMENT"],
                }
            ]
        }
    )
    case = parsed.cases[0]
    assert case.case_id == "CARD-D01"
    assert case.intake_source == "CARD-D01-INTAKE"
    assert case.documents == ["CARD-D01-INTAKE", "CARD-D01-ATTACHMENT"]


def test_case_list_keeps_an_extra_key():
    parsed = CaseListResponse.model_validate(
        {
            "cases": [
                {
                    "case_id": "CARD-D01",
                    "intake_source": "CARD-D01-INTAKE",
                    "documents": ["CARD-D01-INTAKE"],
                }
            ],
            "dataset": "card-disputes-dev",
        }
    )
    assert parsed.model_extra == {"dataset": "card-disputes-dev"}


def test_parsed_case_list_rejects_mutation():
    parsed = CaseListResponse.model_validate(
        {
            "cases": [
                {
                    "case_id": "CARD-D01",
                    "intake_source": "CARD-D01-INTAKE",
                    "documents": ["CARD-D01-INTAKE"],
                }
            ]
        }
    )
    with pytest.raises(ValidationError):
        parsed.cases = []


def test_parsed_case_summary_rejects_mutation():
    parsed = CaseListResponse.model_validate(
        {
            "cases": [
                {
                    "case_id": "CARD-D01",
                    "intake_source": "CARD-D01-INTAKE",
                    "documents": ["CARD-D01-INTAKE"],
                }
            ]
        }
    )
    with pytest.raises(ValidationError):
        parsed.cases[0].case_id = "CARD-D02"


def test_case_summary_keeps_an_extra_key():
    parsed = CaseListResponse.model_validate(
        {
            "cases": [
                {
                    "case_id": "CARD-D01",
                    "intake_source": "CARD-D01-INTAKE",
                    "documents": ["CARD-D01-INTAKE"],
                    "logical_key": "dispute-d01",
                }
            ]
        }
    )
    assert parsed.cases[0].model_extra == {"logical_key": "dispute-d01"}


def test_case_list_rejects_a_case_missing_intake_source():
    with pytest.raises(ValidationError):
        CaseListResponse.model_validate(
            {
                "cases": [
                    {
                        "case_id": "CARD-D01",
                        "documents": ["CARD-D01-INTAKE"],
                    }
                ]
            }
        )


def test_case_list_rejects_a_non_string_document():
    with pytest.raises(ValidationError):
        CaseListResponse.model_validate(
            {
                "cases": [
                    {
                        "case_id": "CARD-D01",
                        "intake_source": "CARD-D01-INTAKE",
                        "documents": [1],
                    }
                ]
            }
        )
