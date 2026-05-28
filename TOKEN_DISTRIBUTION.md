# Token Distribution For vLLM Tribunal Requests

This note is for vLLM server tuning. It describes the token shapes we are
actually sending for the tribunal extraction workload in this repo.

Source of truth in code:

- `vllm/tribunal_eval_runner.py`
- `vllm/tribunal_process_docling.py`

## Mental Model

Our extractor uses `POST /v1/chat/completions/batch`.

Each batch request contains many independent conversations:

- one tribunal markdown document per conversation
- one shared model / temperature / `max_tokens` / schema for the whole batch
- one choice back per conversation

This is not one giant merged prompt.

If a batch has `96` cases, that means:

- `96` separate per-sequence contexts inside one HTTP request
- aggregate prompt and completion usage reported at the batch level

## The Three Token Numbers That Matter

### 1. Per-item prompt tokens

For each case we build one user message from:

- the extraction instructions
- the tribunal markdown body

Locally we store an approximate prompt size as:

- `approximate_token_count(build_prompt_content(case.markdown_text))`

This is a planning estimate, not the final server-reported token count.

### 2. Per-item generation budget

The request also carries:

- `max_tokens`

This is the total output budget for that one conversation.

If thinking is enabled, we may also send:

- `thinking_token_budget`

Important:

- `thinking_token_budget` is inside `max_tokens`
- it is not added on top of `max_tokens`

So the true per-item context bound is:

- `prompt_tokens + max_tokens`

Not:

- `prompt_tokens + thinking_token_budget + max_tokens`

### 3. Batch-level aggregate usage

The API response reports:

- `usage.prompt_tokens`
- `usage.completion_tokens`
- `usage.total_tokens`

These are sums across the whole batch request.

## What The Repo Currently Uses For Batch Planning

For `--target-batch-tokens`, current selection logic uses a conservative reserve:

- `reserved_case_tokens = approximate_prompt_tokens + thinking_token_budget`

That is used only as a packing heuristic for deciding how many cases to put in a
batch.

It is not the true context formula.

In code:

- `vllm/tribunal_eval_runner.py:218`

So there are two separate concepts:

- true per-item context fit: `prompt + max_tokens`
- current batch packing heuristic: `approximate_prompt + thinking_budget`

## Full Corpus Per-Item Prompt Distribution

Computed across all `43,854` Docling tribunal markdown files in:

- `storage/justice/tenancy/markdown_docling`

These are the repo's local approximate prompt-token counts per case:

| Metric | Approx prompt tokens per case |
| --- | ---: |
| count | 43,854 |
| min | 301 |
| p50 | 1,245 |
| p75 | 2,055 |
| p90 | 3,513 |
| p95 | 4,949 |
| p99 | 9,362 |
| max | 58,448 |
| mean | 1,836.9 |

Interpretation:

- most cases are short
- the long tail is real
- a few outliers are very large, but still nowhere near a `250k` per-sequence
  context limit even with generous output budgets

For example, with `max_tokens=4096`, the heaviest observed approximate per-item
context would be about:

- `58,448 + 4,096 = 62,544`

before chat-template overhead.

## Full Corpus Batch Distribution

The completed run was:

- `vllm/results/tribunal_docling_full_20260527_225730`

Run shape:

- `43,854` cases
- `483` main batches
- defaults:
  - `max_cases_per_batch=96`
  - `target_batch_tokens=180000`
  - `max_tokens=320`
  - no thinking

### Cases per main batch

| Metric | Cases |
| --- | ---: |
| min | 44 |
| p50 | 96 |
| p90 | 96 |
| p95 | 96 |
| p99 | 96 |
| max | 96 |
| mean | 90.8 |

### Approximate prompt tokens per main batch

| Metric | Approx prompt tokens |
| --- | ---: |
| min | 122,696 |
| p50 | 173,708 |
| p90 | 179,576 |
| p95 | 179,770 |
| p99 | 179,930 |
| max | 179,990 |
| mean | 166,779.3 |

### Actual prompt tokens per main batch

From API `usage.prompt_tokens`:

| Metric | Actual prompt tokens |
| --- | ---: |
| min | 140,191 |
| p50 | 192,248 |
| p90 | 199,400 |
| p95 | 200,076 |
| p99 | 201,626 |
| max | 202,247 |
| mean | 185,628.9 |

Observed mean uplift from local approximation to actual API prompt usage:

- about `+11.3%`

That uplift is from the real chat-template / schema / wrapper overhead that our
local prompt estimator does not fully capture.

### Completion tokens per main batch

From API `usage.completion_tokens`:

| Metric | Completion tokens |
| --- | ---: |
| min | 9,238 |
| p50 | 20,578 |
| p90 | 21,422 |
| p95 | 21,516 |
| p99 | 21,618 |
| max | 21,664 |
| mean | 19,738.6 |

### Full-corpus totals

Across the finished no-thinking run:

- prompt tokens total: `89,658,770`
- completion tokens total: `9,533,738`
- mean actual prompt tokens per case: `2,044.5`
- mean completion tokens per case: `217.4`

## 96-Case Benchmark Runs

These are useful because they held the same `96` real cases constant while we
changed only the thinking budget.

### No thinking baseline

From `vllm/results/tribunal_big_96_v2_summary.json`:

- cases: `96`
- elapsed: `21.695s`
- prompt tokens: `215,596`
- completion tokens: `20,544`
- total tokens: `236,140`
- mean prompt tokens per case: `2,245.8`
- mean completion tokens per case: `214.0`
- local approximate prompt tokens: `194,384`
- actual vs approximate prompt uplift: `+10.9%`

### Thinking-budget sweeps on the same 96 cases

| Run | Thinking budget | Prompt tokens | Completion tokens | Mean completion / case | Elapsed |
| --- | ---: | ---: | ---: | ---: | ---: |
| no thinking | - | 215,596 | 20,544 | 214.0 | 21.695s |
| think-256 | 256 | 215,404 | 46,934 | 488.9 | 42.178s |
| think-512 | 512 | 215,404 | 69,586 | 724.9 | 56.447s |
| think-1024 | 1,024 | 215,404 | 118,782 | 1,237.3 | 90.950s |
| think-2048 | 2,048 | 215,404 | 217,040 | 2,260.8 | 162.359s |
| think-4096 | 4,096 | 215,404 | 302,887 | 3,155.1 | 240.633s |

What this shows:

- prompt load stayed almost flat because the documents were the same
- completion load grew sharply with thinking budget
- the thinking budget affected latency mostly through completion growth

## What Matters For vLLM Tuning

For this workload, the useful numbers for the sysadmin are:

- per-sequence approximate prompt p50/p95/p99/max:
  - `1,245 / 4,949 / 9,362 / 58,448`
- main-batch actual prompt p50/p95/p99/max:
  - `192,248 / 200,076 / 201,626 / 202,247`
- main-batch completion p50/p95/p99/max in no-thinking extraction:
  - `20,578 / 21,516 / 21,618 / 21,664`
- typical main batch width:
  - `96` sequences
- actual prompt overhead above local estimate:
  - about `11%`

Operationally:

- no-thinking extraction is prompt-heavy and stable
- thinking-heavy extraction mostly increases completion-side pressure
- per-item context safety should be evaluated with `prompt + max_tokens`
- batch packing in the repo is currently more conservative than that, because it
  reserves `approximate_prompt + thinking_budget`

## Practical Guidance

If the sysadmin is tuning scheduler settings, the most relevant takeaways are:

- Expect around `90-96` concurrent sequences per request for the main corpus run.
- Expect about `185k-200k` actual prompt tokens per main batch on the current
  no-thinking configuration, even though the local planner aims for about
  `180k` approximate prompt tokens.
- Expect around `20k-22k` completion tokens per main batch in the current
  no-thinking extraction path.
- If thinking is enabled, prompt load stays about the same but completion load
  rises quickly with budget.
- The longest individual sequence in the corpus is about `58k` approximate
  prompt tokens, so per-sequence context is not the bottleneck on a `~250k`
  context model; scheduler behavior is more likely to matter.
