"""Model clients for the hybrid (ADR-003): GPT-6 Luna on Azure OpenAI, Claude Haiku 5.5 on
Microsoft Foundry, and recorded answers for CI and evaluation runs.

Each client turns one closed question from src/model_cue.py into its provider's
structured-output request, and returns the parsed JSON object, or None, with a
ModelCall. A provider failure never reaches the rules as an exception: no answer means
the rules decide alone.

The provider SDKs (openai and anthropic) are not project dependencies. They are imported
only when a live client is built, so the rules-only path, CI and uv.lock need neither;
a drafting command without the SDK falls back to rules with a printed reason. README.md
gives the command that adds them for a live run. Credentials come only from the
environment, and no error message repeats one.
"""

import hashlib
import importlib
import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from src.model_cue import SCHEMA_HASH, ModelCall, ModelClient, canonical
from src.model_registry import find_qualified, load_registry

REGISTRY = Path(__file__).resolve().parents[1] / "models.toml"
LIVE_PROVIDERS = ("azure_openai", "anthropic_foundry")
# The approved pair the hybrid uses when MODEL_PROVIDER is not set (ADR-003). The route is
# on by default; MODEL_PROVIDER=off turns it off.
DEFAULT_PROVIDER = "azure_openai"
DEFAULT_MODEL_ID = "gpt-6-luna"
_TIMEOUT_S = 30.0
# GPT-6 Luna is a reasoning deployment: its reasoning counts against this limit.
_AZURE_MAX_COMPLETION_TOKENS = 400
# Claude's thinking counts against max_tokens, so the budget is wide and effort is low.
_FOUNDRY_MAX_TOKENS = 2000
_FOUNDRY_EFFORT = "low"


class ModelSetupError(Exception):
    """The environment names a model that cannot be used. The message names settings, not values."""


class AzureOpenAIClient:
    """An Azure OpenAI deployment, such as GPT-6 Luna, through the openai SDK's v1 endpoint."""

    provider = "azure_openai"

    def __init__(
        self,
        model: str,
        client: Any,
        errors: tuple[type[Exception], ...],
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.model = model
        self._client, self._errors, self._clock = client, errors, clock

    def ask(
        self, system: str, user: str, schema: dict[str, object]
    ) -> tuple[dict[str, object] | None, ModelCall]:
        started = self._clock()
        try:
            response = self._client.with_options(timeout=_TIMEOUT_S).chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "answer", "strict": True, "schema": schema},
                },
                max_completion_tokens=_AZURE_MAX_COMPLETION_TOKENS,
            )
        except self._errors as error:
            return None, _call(self, started, self._clock, error=type(error).__name__)
        usage = getattr(response, "usage", None)
        tokens = (getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None))
        choice = response.choices[0] if response.choices else None
        if choice is None:
            return None, _call(self, started, self._clock, tokens, error="empty")
        if getattr(choice.message, "refusal", None):
            return None, _call(self, started, self._clock, tokens, error="refusal")
        if choice.finish_reason == "length":
            return None, _call(self, started, self._clock, tokens, error="max_tokens")
        return _answer(self, started, self._clock, tokens, choice.message.content)


class AnthropicFoundryClient:
    """A Claude model on Microsoft Foundry, such as Claude Haiku 5.5, through the anthropic SDK."""

    provider = "anthropic_foundry"

    def __init__(
        self,
        model: str,
        client: Any,
        errors: tuple[type[Exception], ...],
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.model = model
        self._client, self._errors, self._clock = client, errors, clock

    def ask(
        self, system: str, user: str, schema: dict[str, object]
    ) -> tuple[dict[str, object] | None, ModelCall]:
        started = self._clock()
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=_FOUNDRY_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "format": {"type": "json_schema", "schema": schema},
                    "effort": _FOUNDRY_EFFORT,
                },
                timeout=_TIMEOUT_S,
            )
        except self._errors as error:
            return None, _call(self, started, self._clock, error=type(error).__name__)
        usage = getattr(response, "usage", None)
        tokens = (getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None))
        if response.stop_reason in ("refusal", "max_tokens"):
            return None, _call(self, started, self._clock, tokens, error=response.stop_reason)
        # A thinking block may come first; the answer is the first text block.
        text = next(
            (block.text for block in response.content if getattr(block, "type", None) == "text"),
            None,
        )
        return _answer(self, started, self._clock, tokens, text)


def request_key(system: str, user: str, schema: dict[str, object]) -> str:
    """The recording key of one question. A changed prompt, line or schema is a new key."""
    return hashlib.sha256(
        canonical({"system": system, "user": user, "schema": schema}).encode("utf-8")
    ).hexdigest()


class ReplayClient:
    """Recorded answers, for CI and evaluation runs with no network and no credentials.

    Each JSONL line is {"key", "answer", "call"}. A question with no recording gets no
    answer, so a prompt or line change can never silently reuse an old one. A replayed
    call reports the recorded provider, model, latency and token counts.
    """

    provider = "replay"

    def __init__(self, path: Path) -> None:
        self.model = path.stem
        self._records: dict[str, dict[str, Any]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                self._records[row["key"]] = row
        # The provider and model pairs whose answers the recording holds.
        self.sources = {
            (str(row["call"]["provider"]), str(row["call"]["model"]))
            for row in self._records.values()
        }

    def ask(
        self, system: str, user: str, schema: dict[str, object]
    ) -> tuple[dict[str, object] | None, ModelCall]:
        row = self._records.get(request_key(system, user, schema))
        if row is None:
            return None, {
                "purpose": "",
                "provider": self.provider,
                "model": self.model,
                "answered": False,
                "error": "no_recording",
                "latency_ms": 0.0,
                "input_tokens": None,
                "output_tokens": None,
            }
        recorded = row["call"]
        call: ModelCall = {
            "purpose": "",
            "provider": str(recorded["provider"]),
            "model": str(recorded["model"]),
            "answered": bool(recorded["answered"]),
            "error": recorded["error"],
            "latency_ms": float(recorded["latency_ms"]),
            "input_tokens": recorded["input_tokens"],
            "output_tokens": recorded["output_tokens"],
        }
        return row["answer"], call


class RecordingClient:
    """A live client whose every call is appended to a JSONL recording for ReplayClient.

    A line holds the request key, the answer (a type and a line label, or a yes or no)
    and the call. It never holds the prompt, the customer's lines or a credential.
    """

    def __init__(self, inner: ModelClient, path: Path) -> None:
        self.provider, self.model = inner.provider, inner.model
        self._inner, self._path = inner, path

    def ask(
        self, system: str, user: str, schema: dict[str, object]
    ) -> tuple[dict[str, object] | None, ModelCall]:
        answer, call = self._inner.ask(system, user, schema)
        row = {"key": request_key(system, user, schema), "answer": answer, "call": call}
        with self._path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        return answer, call


def model_from_env(
    env: Mapping[str, str], registry: Path = REGISTRY, *, require_qualified: bool = True
) -> ModelClient | None:
    """The model the environment names, or None when MODEL_PROVIDER is unset or "off".

    MODEL_PROVIDER is off, azure_openai, anthropic_foundry or replay. Unset means off
    here; model_or_rules supplies the approved default (azure_openai/gpt-6-luna) for the
    drafting commands. MODEL_ID names the deployment or model. A live model must have a
    passed record in models.toml for the current SCHEMA_HASH, and its use must be approved there
    (approved_by), because a live call sends the customer's redacted lines to the
    provider. Only tools/qualify_model.py, which makes those records, builds a client
    without them. AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY, or
    ANTHROPIC_FOUNDRY_RESOURCE and ANTHROPIC_FOUNDRY_API_KEY, give the credentials.

    MODEL_REPLAY names the recording the replay provider reads; every model whose
    answers it holds must be qualified. MODEL_RECORD, for a live provider, names a JSONL
    file each answer is appended to, so the run can be replayed later.
    """
    provider = env.get("MODEL_PROVIDER", "").strip() or "off"
    if provider == "off":
        return None
    if provider == "replay":
        return _replay(env, registry, require_qualified)
    if provider not in LIVE_PROVIDERS:
        raise ModelSetupError(
            "MODEL_PROVIDER must be off, azure_openai, anthropic_foundry or replay"
        )
    model_id = _required(env, "MODEL_ID")
    if require_qualified:
        entry = find_qualified(load_registry(registry), provider, model_id)
        if entry is None:
            raise ModelSetupError(
                f"{provider}/{model_id} has no passed qualification record for {SCHEMA_HASH} "
                "in models.toml; run tools/qualify_model.py first"
            )
        if not str(entry.get("approved_by", "")).strip():
            raise ModelSetupError(
                f"{provider}/{model_id} is qualified but its use is not approved; record "
                "approved_by in models.toml once its use is approved"
            )
    record = env.get("MODEL_RECORD", "").strip()
    if record and not Path(record).parent.is_dir():
        raise ModelSetupError("MODEL_RECORD names a file in a folder that does not exist")
    live = _live_client(env, provider, model_id)
    return RecordingClient(live, Path(record)) if record else live


def model_or_rules(
    env: Mapping[str, str], registry: Path = REGISTRY
) -> tuple[ModelClient | None, str | None]:
    """The model a drafting run uses, or None and the reason the rules decide alone.

    The hybrid is on by default: with MODEL_PROVIDER unset, the approved default pair
    (DEFAULT_PROVIDER, DEFAULT_MODEL_ID) is used, and MODEL_PROVIDER=off turns it off.
    A model that cannot be set up, for want of credentials, the provider's SDK or an
    approval, never stops the run: the rules draft every case alone, and what they
    cannot type goes to a person. So a machine without the provider's key or network
    still produces a full submission. A model that is set up but fails on a call gives
    no answer for that case, and the case is drafted the same way (src/contract.py).
    """
    settings = dict(env)
    if not settings.get("MODEL_PROVIDER", "").strip():
        settings["MODEL_PROVIDER"] = DEFAULT_PROVIDER
        settings.setdefault("MODEL_ID", DEFAULT_MODEL_ID)
    try:
        return model_from_env(settings, registry), None
    except ModelSetupError as error:
        return None, str(error)


def _replay(env: Mapping[str, str], registry: Path, require_qualified: bool) -> ReplayClient:
    recording = Path(_required(env, "MODEL_REPLAY"))
    if not recording.is_file():
        raise ModelSetupError("MODEL_REPLAY does not name a recording file")
    try:
        replay = ReplayClient(recording)
    except (ValueError, KeyError, TypeError):
        raise ModelSetupError("MODEL_REPLAY is not a recording of model answers") from None
    if require_qualified:
        entries = load_registry(registry)
        for source_provider, source_model in sorted(replay.sources):
            if find_qualified(entries, source_provider, source_model) is None:
                raise ModelSetupError(
                    f"MODEL_REPLAY holds answers from {source_provider}/{source_model}, which "
                    f"has no passed qualification record for {SCHEMA_HASH} in models.toml"
                )
    return replay


_AZURE_OPERATION_SUFFIXES = (
    "/openai/v1/responses",
    "/openai/v1/chat/completions",
    "/openai/v1",
    "/openai",
)


def _azure_base_url(endpoint: str) -> str:
    """The v1 base URL for a resource endpoint or an operation URL from the portal."""
    base = endpoint.strip().rstrip("/")
    for suffix in _AZURE_OPERATION_SUFFIXES:
        if base.endswith(suffix):
            base = base[: -len(suffix)].rstrip("/")
            break
    return f"{base}/openai/v1/"


def _live_client(env: Mapping[str, str], provider: str, model_id: str) -> ModelClient:
    if provider == "azure_openai":
        openai = _sdk("openai")
        client = openai.OpenAI(
            base_url=_azure_base_url(_required(env, "AZURE_OPENAI_ENDPOINT")),
            api_key=_required(env, "AZURE_OPENAI_API_KEY"),
            max_retries=1,
            timeout=_TIMEOUT_S,
        )
        return AzureOpenAIClient(model_id, client, (openai.APIError,))
    anthropic = _sdk("anthropic")
    client = anthropic.AnthropicFoundry(
        resource=_required(env, "ANTHROPIC_FOUNDRY_RESOURCE"),
        api_key=_required(env, "ANTHROPIC_FOUNDRY_API_KEY"),
        max_retries=1,
        timeout=_TIMEOUT_S,
    )
    return AnthropicFoundryClient(model_id, client, (anthropic.APIError,))


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ModelSetupError(f"{name} is not set")
    return value


def _sdk(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        raise ModelSetupError(
            f"the {name} package is not installed; see README.md for the live-model command"
        ) from None


def _call(
    client: AzureOpenAIClient | AnthropicFoundryClient,
    started: float,
    clock: Callable[[], float],
    tokens: tuple[Any, Any] = (None, None),
    *,
    error: str | None = None,
) -> ModelCall:
    return {
        "purpose": "",
        "provider": client.provider,
        "model": client.model,
        "answered": error is None,
        "error": error,
        "latency_ms": round((clock() - started) * 1000, 3),
        "input_tokens": tokens[0] if isinstance(tokens[0], int) else None,
        "output_tokens": tokens[1] if isinstance(tokens[1], int) else None,
    }


def _answer(
    client: AzureOpenAIClient | AnthropicFoundryClient,
    started: float,
    clock: Callable[[], float],
    tokens: tuple[Any, Any],
    text: object,
) -> tuple[dict[str, object] | None, ModelCall]:
    """One JSON object from the answer text, or no answer when the text is anything else."""
    try:
        value = json.loads(text) if isinstance(text, str) else None
    except json.JSONDecodeError:
        value = None
    if not isinstance(value, dict):
        return None, _call(client, started, clock, tokens, error="invalid_json")
    return value, _call(client, started, clock, tokens)
