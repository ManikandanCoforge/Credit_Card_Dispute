"""Provider adapters, recorded answers and the environment switch for the hybrid's model.

No test reaches a provider. The openai and anthropic SDKs are replaced by fakes that
record each request, so the request shape is checked against ADR-003 and the
providers' structured-output contracts, and every failure is shown to become no answer
rather than an exception.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from src.model_clients import (
    AnthropicFoundryClient,
    AzureOpenAIClient,
    ModelSetupError,
    RecordingClient,
    ReplayClient,
    model_from_env,
    model_or_rules,
    request_key,
)
from src.model_cue import (
    CUE_SCHEMA,
    CUE_SYSTEM,
    MULTI_SCHEMA,
    MULTI_SYSTEM,
    SCHEMA_HASH,
    ask_multiple_problems,
    statement_lines,
)

ROOT = Path(__file__).resolve().parents[1]
LUNA_RECORDING = ROOT / "evals" / "recordings" / "gpt-6-luna.jsonl"
USER = "<evidence>\nL1: The shop took my money two times.\n</evidence>"
SECRET = "test-key-not-a-real-secret"


class APITimeoutError(Exception):
    """A provider error, as the SDKs raise one."""


class _AzureSDK:
    """The slice of an openai client the adapter calls. Each request is kept."""

    def __init__(self, response=None, error=None):
        self._response, self._error = response, error
        self.options = []
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **options):
        self.options.append(options)
        return self

    def _create(self, **request):
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._response


class _FoundrySDK:
    """The slice of an anthropic client the adapter calls. Each request is kept."""

    def __init__(self, response=None, error=None):
        self._response, self._error = response, error
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **request):
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return self._response


def _clock(*times):
    values = iter(times)
    return lambda: next(values)


def _azure_response(content, *, finish_reason="stop", refusal=None, usage=(120, 8)):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, refusal=refusal),
                finish_reason=finish_reason,
            )
        ],
        usage=(
            None
            if usage is None
            else SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1])
        ),
    )


def _foundry_response(*blocks, stop_reason="end_turn", usage=(140, 30)):
    return SimpleNamespace(
        content=list(blocks),
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1]),
    )


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _azure(response=None, error=None):
    sdk = _AzureSDK(response, error)
    return AzureOpenAIClient("gpt-6-luna", sdk, (APITimeoutError,), _clock(10.0, 10.75)), sdk


def _foundry(response=None, error=None):
    sdk = _FoundrySDK(response, error)
    client = AnthropicFoundryClient("claude-haiku-5-5", sdk, (APITimeoutError,), _clock(3.0, 4.5))
    return client, sdk


def _call(provider, model, latency_ms, tokens=(None, None), error=None):
    return {
        "purpose": "",
        "provider": provider,
        "model": model,
        "answered": error is None,
        "error": error,
        "latency_ms": latency_ms,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
    }


def test_azure_sends_one_strict_structured_output_request():
    client, sdk = _azure(_azure_response('{"type": "none", "line_id": "L1"}'))

    client.ask(CUE_SYSTEM, USER, CUE_SCHEMA)

    assert sdk.options == [{"timeout": 30.0}]
    assert sdk.requests == [
        {
            "model": "gpt-6-luna",
            "messages": [
                {"role": "system", "content": CUE_SYSTEM},
                {"role": "user", "content": USER},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": CUE_SCHEMA},
            },
            "max_completion_tokens": 400,
        }
    ]


def test_azure_returns_the_parsed_answer_with_its_tokens_and_latency():
    client, _sdk = _azure(_azure_response('{"type": "duplicate_charge", "line_id": "L1"}'))

    answer, call = client.ask(CUE_SYSTEM, USER, CUE_SCHEMA)

    assert answer == {"type": "duplicate_charge", "line_id": "L1"}
    assert call == _call("azure_openai", "gpt-6-luna", 750.0, (120, 8))


@pytest.mark.parametrize(
    "response, tokens, error",
    [
        (SimpleNamespace(choices=[], usage=None), (None, None), "empty"),
        (_azure_response(None, refusal="I can't help with that."), (120, 8), "refusal"),
        (_azure_response('{"type": "no', finish_reason="length"), (120, 8), "max_tokens"),
        (_azure_response("not json"), (120, 8), "invalid_json"),
        (_azure_response('["duplicate_charge", "L1"]'), (120, 8), "invalid_json"),
        (_azure_response(None, usage=None), (None, None), "invalid_json"),
    ],
)
def test_an_azure_answer_that_is_not_one_json_object_is_no_answer(response, tokens, error):
    client, _sdk = _azure(response)

    assert client.ask(CUE_SYSTEM, USER, CUE_SCHEMA) == (
        None,
        _call("azure_openai", "gpt-6-luna", 750.0, tokens, error),
    )


def test_an_azure_provider_error_is_no_answer_named_by_its_class():
    client, _sdk = _azure(error=APITimeoutError(f"timed out for key {SECRET}"))

    answer, call = client.ask(CUE_SYSTEM, USER, CUE_SCHEMA)

    assert answer is None
    assert call == _call("azure_openai", "gpt-6-luna", 750.0, error="APITimeoutError")
    assert SECRET not in json.dumps(call)


def test_an_error_that_is_not_the_providers_is_a_bug_and_is_raised():
    client, _sdk = _azure(error=KeyError("choices"))

    with pytest.raises(KeyError):
        client.ask(CUE_SYSTEM, USER, CUE_SCHEMA)


def test_token_counts_that_are_not_integers_are_not_reported():
    response = _azure_response('{"multiple_problems": true}')
    response.usage = SimpleNamespace(prompt_tokens="120", completion_tokens=None)
    client, _sdk = _azure(response)

    _answer, call = client.ask(MULTI_SYSTEM, USER, MULTI_SCHEMA)

    assert (call["input_tokens"], call["output_tokens"]) == (None, None)


def test_foundry_sends_one_structured_output_request_at_low_effort():
    client, sdk = _foundry(_foundry_response(_text('{"multiple_problems": false}')))

    client.ask(MULTI_SYSTEM, USER, MULTI_SCHEMA)

    assert sdk.requests == [
        {
            "model": "claude-haiku-5-5",
            "max_tokens": 2000,
            "system": MULTI_SYSTEM,
            "messages": [{"role": "user", "content": USER}],
            "output_config": {
                "format": {"type": "json_schema", "schema": MULTI_SCHEMA},
                "effort": "low",
            },
            "timeout": 30.0,
        }
    ]


def test_foundry_reads_the_first_text_block_after_any_thinking():
    thinking = SimpleNamespace(type="thinking", thinking="Two charges are described.")
    client, _sdk = _foundry(_foundry_response(thinking, _text('{"multiple_problems": true}')))

    answer, call = client.ask(MULTI_SYSTEM, USER, MULTI_SCHEMA)

    assert answer == {"multiple_problems": True}
    assert call == _call("anthropic_foundry", "claude-haiku-5-5", 1500.0, (140, 30))


@pytest.mark.parametrize(
    "response, error",
    [
        (_foundry_response(_text("I can't help with that."), stop_reason="refusal"), "refusal"),
        (_foundry_response(_text('{"multiple'), stop_reason="max_tokens"), "max_tokens"),
        (_foundry_response(), "invalid_json"),
        (_foundry_response(_text("yes")), "invalid_json"),
    ],
)
def test_a_foundry_answer_that_is_not_one_json_object_is_no_answer(response, error):
    client, _sdk = _foundry(response)

    assert client.ask(MULTI_SYSTEM, USER, MULTI_SCHEMA) == (
        None,
        _call("anthropic_foundry", "claude-haiku-5-5", 1500.0, (140, 30), error),
    )


def test_a_foundry_provider_error_is_no_answer_named_by_its_class():
    client, _sdk = _foundry(error=APITimeoutError("timed out"))

    assert client.ask(MULTI_SYSTEM, USER, MULTI_SCHEMA) == (
        None,
        _call("anthropic_foundry", "claude-haiku-5-5", 1500.0, error="APITimeoutError"),
    )


def test_a_changed_prompt_line_or_schema_is_a_new_recording_key():
    key = request_key(CUE_SYSTEM, USER, CUE_SCHEMA)

    assert key == request_key(CUE_SYSTEM, USER, dict(reversed(list(CUE_SCHEMA.items()))))
    assert len({
        key,
        request_key(MULTI_SYSTEM, USER, CUE_SCHEMA),
        request_key(CUE_SYSTEM, USER.replace("two times", "twice"), CUE_SCHEMA),
        request_key(CUE_SYSTEM, USER, MULTI_SCHEMA),
    }) == 4


def test_a_recorded_answer_is_replayed_and_anything_else_gets_none(tmp_path):
    recording = tmp_path / "luna-sample.jsonl"
    row = {
        "key": request_key(CUE_SYSTEM, USER, CUE_SCHEMA),
        "answer": {"type": "duplicate_charge", "line_id": "L1"},
        "call": {**_call("azure_openai", "gpt-6-luna", 812.0, (230, 9)), "purpose": "dispute_type"},
    }
    recording.write_text(f"{json.dumps(row)}\n\n", encoding="utf-8")
    replay = ReplayClient(recording)

    assert (replay.provider, replay.model) == ("replay", "luna-sample")
    assert replay.ask(CUE_SYSTEM, USER, CUE_SCHEMA) == (
        {"type": "duplicate_charge", "line_id": "L1"},
        _call("azure_openai", "gpt-6-luna", 812.0, (230, 9)),
    )
    assert replay.ask(CUE_SYSTEM, USER.replace("two times", "twice"), CUE_SCHEMA) == (
        None,
        _call("replay", "luna-sample", 0.0, error="no_recording"),
    )


def test_a_recording_keeps_the_answer_and_call_but_never_the_prompt(tmp_path):
    recording = tmp_path / "recorded.jsonl"
    client, _sdk = _azure(_azure_response('{"type": "duplicate_charge", "line_id": "L1"}'))
    recorder = RecordingClient(client, recording)

    answer, call = recorder.ask(CUE_SYSTEM, USER, CUE_SCHEMA)

    text = recording.read_text(encoding="utf-8")
    assert (recorder.provider, recorder.model) == ("azure_openai", "gpt-6-luna")
    assert json.loads(text) == {
        "key": request_key(CUE_SYSTEM, USER, CUE_SCHEMA),
        "answer": answer,
        "call": call,
    }
    assert "money two times" not in text
    assert "dispute type" not in text
    assert ReplayClient(recording).ask(CUE_SYSTEM, USER, CUE_SCHEMA) == (answer, call)


def test_the_committed_recording_holds_gpt_6_lunas_answers_one_per_question():
    rows = [json.loads(line) for line in LUNA_RECORDING.read_text(encoding="utf-8").splitlines()]
    answers = {}

    assert rows
    for row in rows:
        assert set(row) == {"key", "answer", "call"}
        assert set(row["call"]) == set(_call("", "", 0.0))
        assert (row["call"]["provider"], row["call"]["model"]) == ("azure_openai", "gpt-6-luna")
        # A question asked twice, such as a redelivered complaint's, has one answer.
        assert answers.setdefault(row["key"], row["answer"]) == row["answer"]


def test_the_committed_recording_answers_a_dev_case_as_gpt_6_luna_did():
    intake = (ROOT / "data" / "dev" / "documents" / "CARD-D02-INTAKE.md").read_text(
        encoding="utf-8"
    )
    lines = statement_lines([("CARD-D02-INTAKE", intake)])

    answer, call = ask_multiple_problems(ReplayClient(LUNA_RECORDING), lines)

    assert answer is False
    assert call is not None
    assert (call["provider"], call["model"], call["answered"]) == (
        "azure_openai",
        "gpt-6-luna",
        True,
    )


@pytest.mark.parametrize("provider", [None, "", "  ", "off"])
def test_no_model_is_used_unless_one_is_named(provider):
    env = {} if provider is None else {"MODEL_PROVIDER": provider}

    assert model_from_env(env) is None


def test_replay_reads_a_recording_of_qualified_answers_without_approval(tmp_path):
    # A replay sends nothing anywhere, so it needs qualified answers, not the bank's approval.
    replay = model_from_env(
        {
            "MODEL_PROVIDER": "replay",
            "MODEL_REPLAY": str(LUNA_RECORDING),
            "MODEL_RECORD": str(tmp_path / "again.jsonl"),
        },
        _registry(tmp_path, approved_by=""),
    )

    # Replayed answers are never recorded again.
    assert isinstance(replay, ReplayClient)
    assert replay.model == "gpt-6-luna"
    assert replay.sources == {("azure_openai", "gpt-6-luna")}


def test_replay_refuses_answers_from_a_model_without_a_passed_record(tmp_path):
    recording = tmp_path / "other.jsonl"
    row = {"key": "k", "answer": None, "call": _call("azure_openai", "gpt-7-nova", 1.0)}
    recording.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ModelSetupError) as refused:
        model_from_env(
            {"MODEL_PROVIDER": "replay", "MODEL_REPLAY": str(recording)}, _registry(tmp_path)
        )

    assert str(refused.value) == (
        "MODEL_REPLAY holds answers from azure_openai/gpt-7-nova, which has no passed "
        f"qualification record for {SCHEMA_HASH} in models.toml"
    )


@pytest.mark.parametrize("content", ["not json\n", '["key", "answer"]\n', '{"key": "k"}\n'])
def test_a_file_that_is_not_a_recording_is_refused(tmp_path, content):
    recording = tmp_path / "broken.jsonl"
    recording.write_text(content, encoding="utf-8")

    with pytest.raises(ModelSetupError, match="^MODEL_REPLAY is not a recording of model answers$"):
        model_from_env({"MODEL_PROVIDER": "replay", "MODEL_REPLAY": str(recording)})


@pytest.mark.parametrize(
    "env, message",
    [
        ({"MODEL_PROVIDER": "replay"}, "MODEL_REPLAY is not set"),
        (
            {"MODEL_PROVIDER": "replay", "MODEL_REPLAY": "evals/recordings/none.jsonl"},
            "MODEL_REPLAY does not name a recording file",
        ),
        (
            {"MODEL_PROVIDER": "openai"},
            "MODEL_PROVIDER must be off, azure_openai, anthropic_foundry or replay",
        ),
        ({"MODEL_PROVIDER": "azure_openai"}, "MODEL_ID is not set"),
        (
            {
                "MODEL_PROVIDER": "azure_openai",
                "MODEL_ID": "gpt-6-luna",
                "AZURE_OPENAI_API_KEY": SECRET,
            },
            "AZURE_OPENAI_ENDPOINT is not set",
        ),
        (
            {
                "MODEL_PROVIDER": "azure_openai",
                "MODEL_ID": "gpt-6-luna",
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            },
            "AZURE_OPENAI_API_KEY is not set",
        ),
    ],
)
def test_a_setting_that_cannot_be_used_stops_with_its_name_and_never_its_value(
    env, message, tmp_path, monkeypatch
):
    monkeypatch.setitem(sys.modules, "openai", _fake_openai())

    with pytest.raises(ModelSetupError) as refused:
        model_from_env(env, _registry(tmp_path))

    assert str(refused.value) == message
    assert SECRET not in str(refused.value)


def test_a_live_model_without_a_passed_record_is_refused_before_its_sdk_loads(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    env = {
        "MODEL_PROVIDER": "anthropic_foundry",
        "MODEL_ID": "claude-haiku-5-5",
        "ANTHROPIC_FOUNDRY_RESOURCE": "example-resource",
        "ANTHROPIC_FOUNDRY_API_KEY": SECRET,
    }

    with pytest.raises(ModelSetupError) as refused:
        model_from_env(env, _registry(tmp_path))

    assert str(refused.value) == (
        f"anthropic_foundry/claude-haiku-5-5 has no passed qualification record for "
        f"{SCHEMA_HASH} in models.toml; run tools/qualify_model.py first"
    )


def test_a_qualified_model_whose_use_is_not_approved_is_refused(tmp_path, monkeypatch):
    # A live call sends the customer's redacted lines to the provider: the bank decides.
    monkeypatch.setitem(sys.modules, "openai", None)

    with pytest.raises(ModelSetupError) as refused:
        model_from_env(_LUNA_ENV, _registry(tmp_path, approved_by=""))

    assert str(refused.value) == (
        "azure_openai/gpt-6-luna is qualified but its use is not approved; record "
        "approved_by in models.toml once its use is approved"
    )



def test_the_hybrid_is_on_by_default_with_the_approved_pair(tmp_path, monkeypatch):
    # MODEL_PROVIDER unset means the hybrid's approved default pair, not the rules alone.
    monkeypatch.setitem(sys.modules, "openai", _fake_openai())
    env = {k: v for k, v in _LUNA_ENV.items() if k not in ("MODEL_PROVIDER", "MODEL_ID")}

    model, unused = model_or_rules(env, _registry(tmp_path))

    assert isinstance(model, AzureOpenAIClient)
    assert (model.provider, model.model, unused) == ("azure_openai", "gpt-6-luna", None)


def test_model_provider_off_keeps_the_rules_alone_and_says_nothing(tmp_path):
    assert model_or_rules({"MODEL_PROVIDER": "off"}, _registry(tmp_path)) == (None, None)


@pytest.mark.parametrize(
    ("env", "reason"),
    [
        ({}, "AZURE_OPENAI_ENDPOINT is not set"),
        (
            {"MODEL_PROVIDER": "azure_openai", "MODEL_ID": "gpt-6-luna"},
            "AZURE_OPENAI_ENDPOINT is not set",
        ),
    ],
    ids=["default, no key", "named, no key"],
)
def test_a_model_that_cannot_be_set_up_falls_back_to_the_rules_with_the_reason(
    env, reason, tmp_path, monkeypatch
):
    # An assessor's machine has no provider key: the run falls back, it never stops.
    monkeypatch.setitem(sys.modules, "openai", _fake_openai())

    assert model_or_rules(env, _registry(tmp_path)) == (None, reason)


def test_an_unapproved_default_pair_falls_back_to_the_rules(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", _fake_openai())
    env = {k: v for k, v in _LUNA_ENV.items() if k not in ("MODEL_PROVIDER", "MODEL_ID")}

    model, unused = model_or_rules(env, _registry(tmp_path, approved_by=""))

    assert model is None
    assert unused is not None and "not approved" in unused

def test_azure_builds_a_client_on_the_v1_endpoint_with_one_retry(tmp_path, monkeypatch):
    openai = _fake_openai()
    monkeypatch.setitem(sys.modules, "openai", openai)
    env = {**_LUNA_ENV, "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/"}

    client = model_from_env(env, _registry(tmp_path))

    assert isinstance(client, AzureOpenAIClient)
    assert (client.provider, client.model) == ("azure_openai", "gpt-6-luna")
    assert openai.built == [
        {
            "base_url": "https://example.openai.azure.com/openai/v1/",
            "api_key": SECRET,
            "max_retries": 1,
            "timeout": 30.0,
        }
    ]
    # The fake client raises the SDK's own APIError, which must become no answer.
    answer, call = client.ask(CUE_SYSTEM, USER, CUE_SCHEMA)
    assert (answer, call["answered"], call["error"]) == (None, False, "APIError")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.openai.azure.com",
        "https://example.openai.azure.com/openai/v1",
        "https://example.openai.azure.com/openai/v1/responses",
        "https://example.openai.azure.com/openai/v1/chat/completions",
        "https://example.openai.azure.com/openai",
        "https://example.services.ai.azure.com/openai/v1/responses/",
    ],
    ids=[
        "resource root",
        "v1 base",
        "responses URL",
        "chat completions URL",
        "openai base",
        "Foundry responses URL",
    ],
)
def test_azure_accepts_the_full_responses_url_the_portal_shows(
    endpoint, tmp_path, monkeypatch
):
    # The Azure portal can show the path of one operation as the endpoint. A pasted
    # /openai/v1/responses URL must reach the same resource, not a 404.
    openai = _fake_openai()
    monkeypatch.setitem(sys.modules, "openai", openai)
    env = {**_LUNA_ENV, "AZURE_OPENAI_ENDPOINT": endpoint}

    model_from_env(env, _registry(tmp_path))

    host = urlparse(endpoint)
    assert openai.built[0]["base_url"] == f"{host.scheme}://{host.netloc}/openai/v1/"


def test_a_live_run_appends_every_answer_to_the_named_recording(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", _fake_openai())
    recording = tmp_path / "gpt-6-luna.jsonl"

    client = model_from_env({**_LUNA_ENV, "MODEL_RECORD": str(recording)}, _registry(tmp_path))
    answer, call = client.ask(CUE_SYSTEM, USER, CUE_SCHEMA)

    assert isinstance(client, RecordingClient)
    assert (client.provider, client.model) == ("azure_openai", "gpt-6-luna")
    text = recording.read_text(encoding="utf-8")
    assert json.loads(text) == {
        "key": request_key(CUE_SYSTEM, USER, CUE_SCHEMA),
        "answer": answer,
        "call": call,
    }
    assert SECRET not in text


def test_a_recording_in_a_missing_folder_is_refused_before_any_call(tmp_path, monkeypatch):
    openai = _fake_openai()
    monkeypatch.setitem(sys.modules, "openai", openai)
    env = {**_LUNA_ENV, "MODEL_RECORD": str(tmp_path / "missing" / "gpt-6-luna.jsonl")}

    with pytest.raises(
        ModelSetupError, match="^MODEL_RECORD names a file in a folder that does not exist$"
    ):
        model_from_env(env, _registry(tmp_path))

    assert openai.built == []


def test_foundry_builds_a_client_for_a_qualified_and_approved_model(tmp_path, monkeypatch):
    anthropic = _fake_anthropic()
    monkeypatch.setitem(sys.modules, "anthropic", anthropic)
    env = {
        "MODEL_PROVIDER": "anthropic_foundry",
        "MODEL_ID": "claude-haiku-5-5",
        "ANTHROPIC_FOUNDRY_RESOURCE": "example-resource",
        "ANTHROPIC_FOUNDRY_API_KEY": SECRET,
    }

    client = model_from_env(
        env, _registry(tmp_path, provider="anthropic_foundry", model_id="claude-haiku-5-5")
    )

    assert isinstance(client, AnthropicFoundryClient)
    assert (client.provider, client.model) == ("anthropic_foundry", "claude-haiku-5-5")
    assert anthropic.built == [
        {"resource": "example-resource", "api_key": SECRET, "max_retries": 1, "timeout": 30.0}
    ]
    answer, call = client.ask(MULTI_SYSTEM, USER, MULTI_SCHEMA)
    assert (answer, call["answered"], call["error"]) == (None, False, "APIError")


def test_qualification_builds_a_client_for_a_model_without_a_record(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic())
    env = {
        "MODEL_PROVIDER": "anthropic_foundry",
        "MODEL_ID": "claude-haiku-5-5",
        "ANTHROPIC_FOUNDRY_RESOURCE": "example-resource",
        "ANTHROPIC_FOUNDRY_API_KEY": SECRET,
    }

    client = model_from_env(env, require_qualified=False)

    assert isinstance(client, AnthropicFoundryClient)


def test_a_live_provider_whose_sdk_is_not_installed_says_how_to_add_it(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)

    with pytest.raises(ModelSetupError) as refused:
        model_from_env(_LUNA_ENV, _registry(tmp_path))

    assert str(refused.value) == (
        "the openai package is not installed; see README.md for the live-model command"
    )


_LUNA_ENV = {
    "MODEL_PROVIDER": "azure_openai",
    "MODEL_ID": "gpt-6-luna",
    "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
    "AZURE_OPENAI_API_KEY": SECRET,
}


def _registry(
    tmp_path, provider="azure_openai", model_id="gpt-6-luna", approved_by="Dispute operations"
):
    """A models.toml holding one passed record for the current schema."""
    path = tmp_path / "models.toml"
    path.write_text(
        "[[model]]\n"
        f'provider = "{provider}"\n'
        f'model_id = "{model_id}"\n'
        f'schema_hash = "{SCHEMA_HASH}"\n'
        "passed = true\n"
        f'approved_by = "{approved_by}"\n',
        encoding="utf-8",
    )
    return path


def _fake_openai():
    """An openai module whose client records its settings and fails every call."""
    built = []

    class APIError(Exception):
        pass

    def openai_client(**settings):
        built.append(settings)
        return _AzureSDK(error=APIError("unreachable"))

    return SimpleNamespace(OpenAI=openai_client, APIError=APIError, built=built)


def _fake_anthropic():
    """An anthropic module whose Foundry client records its settings and fails every call."""
    built = []

    class APIError(Exception):
        pass

    def foundry_client(**settings):
        built.append(settings)
        return _FoundrySDK(error=APIError("unreachable"))

    return SimpleNamespace(AnthropicFoundry=foundry_client, APIError=APIError, built=built)
