#!/usr/bin/env bash
# Run the hybrid model over one or more suites and write a JSON report.
#
# The Python commands read the process environment, not .env. This wrapper
# loads .env when it exists, checks the provider's variables, and runs
# tools/hybrid_eval.py with the matching provider SDK.
#
#   bash tools/run_model.sh                    # dev suite, Azure OpenAI
#   SUITES="dev synth stress holdout" bash tools/run_model.sh
#   MODEL_PROVIDER=replay MODEL_REPLAY=evals/recordings/gpt-6-luna.jsonl bash tools/run_model.sh
#
# The key belongs in .env or the environment, never in models.toml. .env is
# ignored by git; .env.example lists the names without values.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # Strip CR so an .env saved on Windows still sources. The process
  # substitution is a pipe, not a temporary file that holds the key.
  # shellcheck disable=SC1090
  . <(tr -d '\r' < .env)
  set +a
fi

provider="${MODEL_PROVIDER:-azure_openai}"
model="${MODEL_ID:-gpt-6-luna}"
report="${REPORT:-reports/scored-run-hybrid.json}"
port="${PORT:-8901}"
export MODEL_PROVIDER="$provider"
export MODEL_ID="$model"
export PYTHONUTF8="${PYTHONUTF8:-1}"

suite_args=()
if [ -n "${SUITES:-}" ]; then
  read -r -a suite_args <<< "$SUITES"
else
  suite_args=(dev)
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not on PATH; install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

run_report() {
  exec uv run --locked "$@" python tools/hybrid_eval.py \
    --suites "${suite_args[@]}" --report "$report" --port "$port"
}

require() {
  local name="$1" hint="$2"
  if [ -z "${!name:-}" ]; then
    echo "set $name $hint" >&2
    exit 1
  fi
}

case "$provider" in
  replay)
    require MODEL_REPLAY "to a recording, for example evals/recordings/gpt-6-luna.jsonl"
    if [ ! -f "$MODEL_REPLAY" ]; then
      echo "MODEL_REPLAY does not name a file: $MODEL_REPLAY" >&2
      exit 1
    fi
    echo "model: replay/$model; suites: ${suite_args[*]}; report: $report"
    run_report
    ;;
  azure_openai)
    require AZURE_OPENAI_ENDPOINT "in .env, for example https://RESOURCE.openai.azure.com"
    require AZURE_OPENAI_API_KEY "in .env or the environment"
    echo "model: $provider/$model; suites: ${suite_args[*]}; report: $report"
    run_report --with openai==3.37.0
    ;;
  anthropic_foundry)
    require ANTHROPIC_FOUNDRY_RESOURCE "in .env"
    require ANTHROPIC_FOUNDRY_API_KEY "in .env or the environment"
    echo "model: $provider/$model; suites: ${suite_args[*]}; report: $report"
    run_report --with anthropic==2.1.0
    ;;
  off)
    echo "MODEL_PROVIDER=off; unset it or set azure_openai to run the model" >&2
    exit 1
    ;;
  *)
    echo "unknown MODEL_PROVIDER: $provider (use azure_openai, anthropic_foundry or replay)" >&2
    exit 1
    ;;
esac
