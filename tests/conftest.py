"""Settings shared by every test."""

import pytest

# The hybrid's model settings (ADR-003; see src/model_clients.py). A developer's shell may
# set them for a live run; the suite must still never reach a model it did not name.
_MODEL_SETTINGS = (
    "MODEL_PROVIDER",
    "MODEL_ID",
    "MODEL_REPLAY",
    "MODEL_RECORD",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "ANTHROPIC_FOUNDRY_RESOURCE",
    "ANTHROPIC_FOUNDRY_API_KEY",
)


@pytest.fixture(autouse=True)
def _no_model_settings_from_the_shell(monkeypatch):
    for name in _MODEL_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    # The hybrid is on by default when MODEL_PROVIDER is unset, so the suite turns it off;
    # a test of the default deletes this setting itself.
    monkeypatch.setenv("MODEL_PROVIDER", "off")
