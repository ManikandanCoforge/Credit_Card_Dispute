# Model qualification sets

A model may answer the hybrid's questions (ADR-003) only after it passes `cue_suite.json`
with zero unsafe answers and at least 90% of the cases answered. `tools/qualify_model.py`
runs a suite and scores it with `src/model_registry.py`. Expected answers were fixed
before any model ran and must not be edited in response to a result.

- `cue_suite.json` (66 cases) holds the customer statement lines of the copilot's synthetic,
  stress, held-out and edge cases, as the copilot extracted them, with each case's expected
  classification from its gold answer. The edge suite is not in this repository.
  19 were gap cases for the copilot's rules, where the model's answer decides the route;
  this repository's rules leave a somewhat different set. Cases whose gold is ambiguous
  because customer accounts conflict are left out, because the rules decide a conflict.
  The two vague complaints where abstaining is right, STR-P11 and STR-P12, are kept.
- `heldout_cues.json` (12 cases) was written by hand on 2026-10-22, after prompt cue-v1
  failed on STR-P10 (an overcharge read as a duplicate) and before prompt cue-v2 ran on
  anything. It is the only unbiased check of cue-v2: the 66-case suite was used to find
  that failure, so cue-v2's result on it is optimistic.

Both sets come from the Card Disputes Copilot assessment, with its line ids (for example
`SYN-S01-INTAKE:5`) and line text unchanged.

## Reports

`reports/` holds the per-case results behind each record. All four runs used prompt cue-v2
and schema hash `sha256:cb8b14c6d934704e`, the hash `src/model_cue.py` computes.

| Report | Run | Correct | Cautious | Unsafe | Passed |
|---|---|---|---|---|---|
| `azure_openai__gpt-6-luna__cue_suite.json` | 2026-10-25 | 66 / 66 | 0 | 0 | yes |
| `azure_openai__gpt-6-luna__heldout_cues.json` | 2026-10-25 | 11 / 12 | 1 | 0 | yes |
| `anthropic_foundry__claude-haiku-5-5__cue_suite.json` | 2026-10-24 | 65 / 66 | 1 | 0 | yes |
| `anthropic_foundry__claude-haiku-5-5__heldout_cues.json` | 2026-10-24 | 12 / 12 | 0 | 0 | yes |

GPT-6 Luna's cautious held-out answer is HQ-07, whose call failed on the network after 41
seconds and counted as no answer, the intended behaviour; an earlier run scored 12 of 12.
Claude Haiku 5.5's cautious answer is STR-P12, a vague complaint it read as another kind
of dispute (unsupported) where abstaining was expected. Only GPT-6 Luna is registered in
`models.toml`. Claude Haiku 5.5 passed both sets and is registered once the bank approves
it as the alternate.
