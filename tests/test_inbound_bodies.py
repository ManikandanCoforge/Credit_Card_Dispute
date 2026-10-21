import pytest
from pydantic import ValidationError

from src.api_models import (
    CaseListResponse,
    ErrorBody,
    HealthResponse,
    RecordCreated,
    RecordRow,
    ReviewCreated,
    ReviewRow,
    ToolPayload,
)


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


def test_tool_payload_rejects_a_non_string_source_id():
    with pytest.raises(ValidationError):
        ToolPayload.model_validate({"source_id": 1})


def test_parsed_tool_payload_rejects_mutation():
    parsed = ToolPayload.model_validate({"source_id": "CARD-D01-TRANSACTIONS"})
    with pytest.raises(ValidationError):
        parsed.source_id = "CARD-D01-MERCHANT"


def test_tool_payload_keeps_transaction_fields():
    parsed = ToolPayload.model_validate(
        {
            "source_id": "CARD-D01-TRANSACTIONS",
            "transactions": [{"transaction_id": "TX-D01", "amount": 117}],
        }
    )
    assert parsed.model_extra == {
        "transactions": [{"transaction_id": "TX-D01", "amount": 117}]
    }


def test_tool_payload_rejects_a_missing_source_id():
    with pytest.raises(ValidationError):
        ToolPayload.model_validate({})


def test_tool_payload_rejects_an_empty_source_id():
    with pytest.raises(ValidationError):
        ToolPayload.model_validate({"source_id": ""})


def test_tool_payload_parses_a_source_id():
    parsed = ToolPayload.model_validate({"source_id": "CARD-D01-TRANSACTIONS"})
    assert parsed.source_id == "CARD-D01-TRANSACTIONS"


def test_error_body_keeps_an_extra_key():
    parsed = ErrorBody.model_validate({"error": "not_found", "attempt": 2})
    assert parsed.model_extra == {"attempt": 2}


def test_parsed_error_body_rejects_mutation():
    parsed = ErrorBody.model_validate({"error": "not_found"})
    with pytest.raises(ValidationError):
        parsed.error = "upstream_timeout"


def test_error_body_rejects_a_coerced_retryable_flag():
    with pytest.raises(ValidationError):
        ErrorBody.model_validate({"error": "upstream_timeout", "retryable": "true"})


def test_error_body_rejects_a_missing_code():
    with pytest.raises(ValidationError):
        ErrorBody.model_validate({})


def test_error_body_rejects_an_empty_code():
    with pytest.raises(ValidationError):
        ErrorBody.model_validate({"error": ""})


def test_error_body_parses_an_unknown_code():
    parsed = ErrorBody.model_validate({"error": "new_simulator_code"})
    assert parsed.error == "new_simulator_code"


def test_error_body_parses_a_duplicate_case():
    parsed = ErrorBody.model_validate(
        {"error": "duplicate_case", "existing_record_id": "dispute-d01"}
    )
    assert parsed.error == "duplicate_case"
    assert parsed.existing_record_id == "dispute-d01"
    assert parsed.retryable is None


def test_error_body_parses_an_upstream_timeout():
    parsed = ErrorBody.model_validate(
        {
            "error": "upstream_timeout",
            "retryable": True,
            "message": "Simulated upstream timeout; never treat as no results.",
        }
    )
    assert parsed.error == "upstream_timeout"
    assert parsed.retryable is True
    assert parsed.message == "Simulated upstream timeout; never treat as no results."
    assert parsed.existing_record_id is None


def test_review_submission_rejects_a_missing_draft_hash():
    with pytest.raises(ValidationError):
        ReviewCreated.model_validate({"review_id": "rev_abc", "status": "pending"})


def test_review_submission_rejects_a_decided_status():
    with pytest.raises(ValidationError):
        ReviewCreated.model_validate(
            {"review_id": "rev_abc", "status": "approved", "draft_hash": "abc123"}
        )


def test_review_submission_parses_pending():
    parsed = ReviewCreated.model_validate(
        {"review_id": "rev_abc", "status": "pending", "draft_hash": "abc123"}
    )
    assert parsed.review_id == "rev_abc"
    assert parsed.status == "pending"
    assert parsed.draft_hash == "abc123"


def test_fetched_review_keeps_an_extra_key():
    parsed = ReviewRow.model_validate(
        {
            "id": "rev_abc",
            "case_id": "CARD-D01",
            "draft": '{"case_id":"CARD-D01"}',
            "hash": "abc123",
            "status": "pending",
            "reviewer": None,
            "attempt": 1,
        }
    )
    assert parsed.model_extra == {"attempt": 1}


def test_review_submission_keeps_an_extra_key():
    parsed = ReviewCreated.model_validate(
        {
            "review_id": "rev_abc",
            "status": "pending",
            "draft_hash": "abc123",
            "case_id": "CARD-D01",
        }
    )
    assert parsed.model_extra == {"case_id": "CARD-D01"}


def test_parsed_review_row_rejects_mutation():
    parsed = ReviewRow.model_validate(
        {
            "id": "rev_abc",
            "case_id": "CARD-D01",
            "draft": '{"case_id":"CARD-D01"}',
            "hash": "abc123",
            "status": "pending",
            "reviewer": None,
        }
    )
    with pytest.raises(ValidationError):
        parsed.draft = "{}"


def test_parsed_review_submission_rejects_mutation():
    parsed = ReviewCreated.model_validate(
        {"review_id": "rev_abc", "status": "pending", "draft_hash": "abc123"}
    )
    with pytest.raises(ValidationError):
        parsed.draft_hash = "def456"


def test_fetched_review_accepts_stored_statuses():
    for status in ("pending", "approved", "rejected"):
        parsed = ReviewRow.model_validate(
            {
                "id": "rev_abc",
                "case_id": "CARD-D01",
                "draft": '{"case_id":"CARD-D01"}',
                "hash": "abc123",
                "status": status,
                "reviewer": "reviewer-name",
            }
        )
        assert parsed.status == status


def test_fetched_review_rejects_a_missing_reviewer():
    with pytest.raises(ValidationError):
        ReviewRow.model_validate(
            {
                "id": "rev_abc",
                "case_id": "CARD-D01",
                "draft": '{"case_id":"CARD-D01"}',
                "hash": "abc123",
                "status": "pending",
            }
        )


def test_fetched_review_parses_with_a_null_reviewer():
    parsed = ReviewRow.model_validate(
        {
            "id": "rev_abc",
            "case_id": "CARD-D01",
            "draft": '{"case_id":"CARD-D01"}',
            "hash": "abc123",
            "status": "pending",
            "reviewer": None,
        }
    )
    assert parsed.reviewer is None
    assert parsed.draft == '{"case_id":"CARD-D01"}'


def test_record_creation_rejects_a_missing_review_id():
    with pytest.raises(ValidationError):
        RecordCreated.model_validate(
            {
                "record_id": "dispute-d01",
                "case_id": "CARD-D01",
                "status": "created",
            }
        )


def test_record_creation_rejects_a_status_other_than_created():
    with pytest.raises(ValidationError):
        RecordCreated.model_validate(
            {
                "record_id": "dispute-d01",
                "case_id": "CARD-D01",
                "status": "pending",
                "review_id": "rev_abc",
            }
        )


def test_record_creation_parses_created():
    parsed = RecordCreated.model_validate(
        {
            "record_id": "dispute-d01",
            "case_id": "CARD-D01",
            "status": "created",
            "review_id": "rev_abc",
        }
    )
    assert parsed.record_id == "dispute-d01"
    assert parsed.case_id == "CARD-D01"
    assert parsed.status == "created"
    assert parsed.review_id == "rev_abc"


def test_fetched_record_keeps_an_extra_key():
    parsed = RecordRow.model_validate(
        {
            "id": "dispute-d01",
            "case_id": "CARD-D01",
            "draft": '{"case_id":"CARD-D01"}',
            "review_id": "rev_abc",
            "status": "created",
        }
    )
    assert parsed.model_extra == {"status": "created"}


def test_record_creation_keeps_an_extra_key():
    parsed = RecordCreated.model_validate(
        {
            "record_id": "dispute-d01",
            "case_id": "CARD-D01",
            "status": "created",
            "review_id": "rev_abc",
            "draft_hash": "abc123",
        }
    )
    assert parsed.model_extra == {"draft_hash": "abc123"}


def test_parsed_record_row_rejects_mutation():
    parsed = RecordRow.model_validate(
        {
            "id": "dispute-d01",
            "case_id": "CARD-D01",
            "draft": '{"case_id":"CARD-D01"}',
            "review_id": "rev_abc",
        }
    )
    with pytest.raises(ValidationError):
        parsed.draft = "{}"


def test_parsed_record_creation_rejects_mutation():
    parsed = RecordCreated.model_validate(
        {
            "record_id": "dispute-d01",
            "case_id": "CARD-D01",
            "status": "created",
            "review_id": "rev_abc",
        }
    )
    with pytest.raises(ValidationError):
        parsed.review_id = "rev_other"


def test_fetched_record_rejects_a_missing_review_id():
    with pytest.raises(ValidationError):
        RecordRow.model_validate(
            {
                "id": "dispute-d01",
                "case_id": "CARD-D01",
                "draft": '{"case_id":"CARD-D01"}',
            }
        )


def test_fetched_record_keeps_the_draft_string():
    parsed = RecordRow.model_validate(
        {
            "id": "dispute-d01",
            "case_id": "CARD-D01",
            "draft": '{"case_id":"CARD-D01"}',
            "review_id": "rev_abc",
        }
    )
    assert parsed.id == "dispute-d01"
    assert parsed.case_id == "CARD-D01"
    assert parsed.draft == '{"case_id":"CARD-D01"}'
    assert parsed.review_id == "rev_abc"
