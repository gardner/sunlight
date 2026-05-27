# vLLM Batch Requests and Output Steering

This repo has tested the vLLM OpenAI-compatible batch chat endpoint against:

- Server: `http://192.168.88.96:8001`
- Endpoint: `POST /v1/chat/completions/batch`
- Model: `RedHatAI/Qwen3.6-35B-A3B-NVFP4`
- Tokenizer override at serve time: `Qwen/Qwen3.6-35B-A3B`

## What the Batch Endpoint Does

`/v1/chat/completions/batch` sends many independent chat conversations in one HTTP request.

The key shape difference from `/v1/chat/completions` is `messages`:

- Normal chat: `messages` is one conversation.
- Batch chat: `messages` is a list of conversations.

Each conversation is still a normal list of chat messages:

```json
[
  [{"role": "user", "content": "First request"}],
  [{"role": "user", "content": "Second request"}]
]
```

The response returns one choice per input conversation. Use `choice.index` to map each answer back to the input conversation.

Important: a batch request does not merge all documents into one shared context window. If the batch contains 100k tokens across 45 markdown files, that is 45 independent requests with about 100k aggregate prompt tokens. For a single question over one combined 250k-token corpus, use `/v1/chat/completions` with one large conversation instead.

## Minimal Batch Request

Use the host-level base URL, not a `/v1` base URL:

```bash
curl -sS http://192.168.88.96:8001/v1/chat/completions/batch \
  -H 'Content-Type: application/json' \
  -d @- <<'JSON'
{
  "model": "RedHatAI/Qwen3.6-35B-A3B-NVFP4",
  "messages": [
    [
      {
        "role": "user",
        "content": "Case: The plaintiff prevailed. Who won? Plaintiff, defendant, or tie? Answer with one word:"
      }
    ],
    [
      {
        "role": "user",
        "content": "Case: The tribunal dismissed all claims. Who won? Plaintiff, defendant, or tie? Answer with one word:"
      }
    ]
  ],
  "temperature": 0,
  "max_tokens": 4,
  "chat_template_kwargs": {
    "enable_thinking": false
  }
}
JSON
```

The same generation parameters apply to every conversation in the request. If different conversations need different schemas, temperatures, or token limits, split them into separate batch calls.

## Tribunal Classifier Request

For the tribunal markdown classifier, use `structured_outputs.choice`. This is stricter than prompting for “one word” and prevents out-of-set labels such as `Landlord` or `Tenant`.

```json
{
  "model": "RedHatAI/Qwen3.6-35B-A3B-NVFP4",
  "messages": [
    [
      {
        "role": "user",
        "content": "Read the following tribunal markdown and answer the question.\n\n--- FILE: case-001.md ---\n...\n\nWho won? Plaintiff, defendant, or tie? Answer with one word:"
      }
    ]
  ],
  "temperature": 0,
  "max_tokens": 4,
  "chat_template_kwargs": {
    "enable_thinking": false
  },
  "structured_outputs": {
    "choice": ["plaintiff", "defendant", "tie"]
  }
}
```

Observed live result: the batch endpoint accepted `structured_outputs.choice` and returned only the allowed labels.

## Running the Repo Script

Use `uv run scripts/run_big_batch.py` for the batch script:

```bash
HF_HOME=/tmp/codex-hf-cache \
  uv run scripts/run_big_batch.py \
    --target-document-tokens 100000 \
    --run-name big_batch_100k_structured
```

Use `--dry-run` to build and save metadata without sending the request:

```bash
HF_HOME=/tmp/codex-hf-cache \
  uv run scripts/run_big_batch.py \
    --target-document-tokens 1000 \
    --dry-run \
    --run-name docs_validation_structured_choice
```

The explicit `HF_HOME` avoids the current shared Hugging Face cache permission issue caused by root-owned Docker cache lock files.

## Python Shape

`scripts/run_big_batch.py` builds this same request shape. The important part is:

```python
payload = {
    "model": "RedHatAI/Qwen3.6-35B-A3B-NVFP4",
    "messages": conversations,
    "temperature": 0,
    "max_tokens": 4,
    "chat_template_kwargs": {"enable_thinking": False},
    "structured_outputs": {"choice": ["plaintiff", "defendant", "tie"]},
}
```

Where `conversations` is:

```python
[
    [{"role": "user", "content": prompt_for_first_file}],
    [{"role": "user", "content": prompt_for_second_file}],
]
```

Parsing the response:

```python
for choice in response["choices"]:
    input_index = choice["index"]
    answer = choice["message"]["content"]
```

The response-level `usage` aggregates prompt and completion tokens across the whole batch.

## Output Steering Modes

vLLM supports OpenAI-compatible structured output controls plus vLLM-specific `structured_outputs`.

These modes were live-tested on the current container on 2026-05-27:

- `structured_outputs.choice`
- `structured_outputs.regex`
- `structured_outputs.json`
- `structured_outputs.grammar`
- OpenAI-compatible `response_format` with `type: "json_schema"`
- Batch endpoint with `structured_outputs.choice`

### Choice

Use this for a closed label set:

```json
"structured_outputs": {
  "choice": ["plaintiff", "defendant", "tie"]
}
```

This is the best fit for the current “Who won?” classifier because it returns one of the allowed strings directly.

### Regex

Use this for compact text constraints:

```json
"structured_outputs": {
  "regex": "(plaintiff|defendant|tie)"
}
```

Regex is useful when the output is still plain text but must match a pattern. For enums, `choice` is clearer.

### vLLM JSON Schema

Use `structured_outputs.json` when the output should be valid JSON with a schema:

```json
"structured_outputs": {
  "json": {
    "type": "object",
    "properties": {
      "winner": {
        "type": "string",
        "enum": ["plaintiff", "defendant", "tie"]
      }
    },
    "required": ["winner"],
    "additionalProperties": false
  }
}
```

The model returns JSON text in `message.content`; the caller should parse and validate it.

### OpenAI-Compatible JSON Schema

Use `response_format` for OpenAI-compatible JSON schema requests:

```json
"response_format": {
  "type": "json_schema",
  "json_schema": {
    "name": "winner_result",
    "schema": {
      "type": "object",
      "properties": {
        "winner": {
          "type": "string",
          "enum": ["plaintiff", "defendant", "tie"]
        }
      },
      "required": ["winner"],
      "additionalProperties": false
    }
  }
}
```

This is more portable across OpenAI-compatible clients than `structured_outputs.json`.

### Grammar

Use `structured_outputs.grammar` for grammar-constrained generation:

```json
"structured_outputs": {
  "grammar": "root ::= \"plaintiff\" | \"defendant\" | \"tie\""
}
```

This was live-tested successfully for a small request. For simple label classification, prefer `choice`; grammar is useful when output structure is more complex than a small enum.

## Current Batch Findings

The first unconstrained tribunal batch test used `scripts/run_big_batch.py` against `testdata/big`:

- Target document tokens: `100,000`
- Selected files: `45`
- Actual document tokens: `100,650`
- API prompt tokens: `103,104`
- Completion tokens: `161`
- Elapsed time: about `4.8s`

That run returned HTTP 200, but some answers were not in the requested label set. The fix is to add output steering:

```json
"structured_outputs": {
  "choice": ["plaintiff", "defendant", "tie"]
}
```

With `--max-num-seqs 8`, later batch tests completed faster:

- 100k aggregate document-token target: about `4.1s`
- 200k aggregate document-token target: about `5.8s`

vLLM logs expose server-side throughput while requests run, including average prompt throughput, average generation throughput, running/waiting request counts, KV cache usage, and prefix cache hit rate.

## Operational Notes

- `--max-num-seqs` controls how many sequences vLLM can admit concurrently. Higher values let the batch endpoint run more conversations in parallel, bounded by memory and `--max-num-batched-tokens`.
- `--max-num-batched-tokens` controls the scheduler token budget per iteration. Long prompts can still leave requests waiting if this budget is too low.
- Prefix caching can make repeated prompts or shared prefixes dramatically faster. The exact repeat of the 250k-token single-prompt test returned in about `1s`.
- Use `temperature: 0` for classifier-style runs.
- Use `chat_template_kwargs.enable_thinking=false` for this Qwen model when you want direct answers instead of reasoning-style text.
- The vLLM batch example documents that streaming, tools, beam search, and `n > 1` are not supported by the batch endpoint.

## Real Tribunal Extraction Eval

`vllm/tribunal_batch_eval.py` is the direct structured-extraction harness for
real Tenancy Tribunal cases. It intentionally does not use the repo's
`scripts/` ingestion pipeline.

Inputs:

- markdown from `storage/justice/tenancy/markdown_docling`
- Justice sidecars from `justice/data/tenancy/pdfs`

The harness:

- pairs real cases by `order_id`
- derives gold header/order fields from the markdown itself
- reads MiniMax `tenancy-llm-v2` frontmatter as teacher labels for generated
  retrieval fields when present
- applies local post-hoc JSON-schema validation to every parsed response
- sends one JSON-schema extraction request per case through
  `/v1/chat/completions/batch`
- writes manifest, payload, response, and scored summary files to `vllm/results`

Non-LLM generated-field eval:

- `case_summary`, `applicant_story`, `respondent_story`, and
  `neutral_fact_pattern` use lexical token precision/recall/F1.
- `catchwords`, `questions_answered`, `claims_made`, `remedies_sought`, and
  `legal_principles` use greedy item-level precision/recall/F1 over normalized
  text, so wording changes are tolerated better than exact string matching.
- These teacher metrics are currently preparatory for richer schemas. The
  header/order extraction schema does not yet ask vLLM to emit those fields.

Schema validation and batch reserves:

- The harness now reports local `json_parse_success` and `schema_valid` rates,
  plus counts for missing required fields, type violations, enum violations,
  and extra properties.
- Saved 96-case runs `tribunal_big_96_v2`, `tribunal_big_96_think_2048`, and
  `tribunal_big_96_think_4096` all re-scored at `96/96` parseable and
  `96/96` schema-valid.
- When `--target-batch-tokens` is used with thinking enabled, selection now
  reserves `approximate_prompt_tokens + thinking_token_budget` per case rather
  than packing batches by prompt length alone.

Run the current balanced eval:

```bash
uv run python vllm/tribunal_batch_eval.py \
  --case-count 96 \
  --run-name tribunal_big_96_v2
```

Latest real-case run on 2026-05-27:

- 96 cases
- 48 redacted and 48 non-redacted
- 215,596 prompt tokens
- 20,544 completion tokens
- 21.695 seconds elapsed
- 0.9472 aggregate scored-field accuracy
- 0.5000 exact-case accuracy

Strong fields in that run:

- citation
- application_number
- decision_date
- adjudicator
- applicant/respondent roles
- payable_to
- redaction booleans

Current weak fields:

- tribunal_location
- applicant_name
- payable_by
- total_award_nzd
- respondent_name

## Full Docling Run

`vllm/tribunal_process_docling.py` runs the same structured extractor across
all Docling markdown files, even when no Justice sidecar is present.

It writes a dedicated folder containing:

- `run_config.json`
- `progress.json`
- `aggregate_summary.json`
- per-batch `*_cases.json`, `*_payload.json`, `*_response.json`,
  and `*_summary.json`
- append-only `extractions.jsonl`

The runner uses token-bounded shard planning and automatically retries
schema-invalid cases one by one with larger `max_tokens`, which repaired the
known long-party-name truncation for order `172070039` at `640` tokens.
It also supports concurrent HTTP dispatch; with two vLLM instances behind the
load balancer, `--max-concurrent-batches 2` kept two batch requests in flight
and roughly doubled the corpus-run throughput without degrading schema-valid
rates in the first resumed batches.

Launch the full corpus run:

```bash
uv run python vllm/tribunal_process_docling.py \
  --output-dir vllm/results/tribunal_docling_full_YYYYMMDD_HHMMSS \
  --max-concurrent-batches 2
```

Monitor it with:

```bash
cat vllm/results/tribunal_docling_full_YYYYMMDD_HHMMSS/progress.json
tail -f vllm/results/tribunal_docling_full_YYYYMMDD_HHMMSS/run.log
```

## References

- vLLM batched chat completions example: https://docs.vllm.ai/en/latest/examples/generate/batched_chat_completions_online/
- vLLM structured outputs: https://docs.vllm.ai/en/latest/features/structured_outputs.html
- vLLM OpenAI-compatible server: https://docs.vllm.ai/en/latest/serving/openai_compatible_server/
