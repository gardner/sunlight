# NVIDIA NIM Tenancy LLM Notes

This records NVIDIA OpenAI-compatible model probes for Tenancy Tribunal metadata
enrichment. Tests used real Docling markdown excerpts and the same enrichment
message builder as the ingestion pipeline.

## Current Takeaways

Use reasoning when it stays separate from `message.content`. Reasoning appears
helpful for output quality and is safe when the JSON answer still lands in
`message.content`. Do not send a blanket `chat_template_kwargs.enable_thinking`
override across providers: Mistral rejects that parameter, and most models do
not need it for parseable content.

The strongest NVIDIA candidate from this pass is
`meta/llama-4-maverick-17b-128e-instruct`. It returned `10/10` parseable real
Tenancy enrichments with correct document IDs. Nine requests were fast
(`2.44s` to `5.63s`), but one request stalled to `153.48s`, so it needs a
larger serial run and a timeout/tail-latency policy before production use.

`mistralai/mistral-large-3-675b-instruct-2512` follows the schema, but is too
slow for the enrichment backlog at current observed latency. Four real serial
requests all parsed, but took `49.19s` to `83.60s`.

`mistralai/mistral-nemotron` can produce good parseable real enrichments, but
latency was unstable (`3.54s`, `55.14s`, `248.33s`) and the capability probe
also hit a `500` inference connection error on a simple JSON-mode request.

Do not add `stepfun-ai/step-3.5-flash` to the current parser path. With
`response_format={"type":"json_object"}`, it puts the JSON answer in
`reasoning_content` while `message.content` is empty. Nineteen serial real
requests all failed parsing for this reason.

## Probe Artifacts

Raw logs and JSONL:

* `logs/nvidia-model-capabilities-20260526-093156.log`
* `logs/nvidia-model-capabilities-20260526-093156.jsonl`
* `logs/nvidia-model-serial-100-20260526-092729.jsonl`
* `logs/nvidia-candidate-serial-10-20260526-094036.jsonl`
* `logs/nvidia-fast-candidates-serial-10-20260526-094551.jsonl`
* `logs/nvidia-llama-maverick-serial-10-20260526-095249.jsonl`
* `logs/nvidia-llama-maverick-serial-10-20260526-095249.summary.json`

OpenRouter probes:

* `logs/openrouter-deepseek-v4-flash-capabilities-20260526-095918.log`
* `logs/openrouter-deepseek-v4-flash-capabilities-20260526-095918.jsonl`

Reusable harness:

```bash
set -a
. bifrost/.env
set +a

uv run python scripts/probe_nvidia_tenancy_models.py \
  --requests-per-model 10 \
  --output-jsonl logs/nvidia-probe.jsonl \
  --summary-json logs/nvidia-probe.summary.json \
  --models meta/llama-4-maverick-17b-128e-instruct
```

## Model Findings

### OpenRouter Capability Matrix

| Provider | Model | Plain chat content | JSON object content | JSON schema response format | Reasoning behavior | Real Tenancy parse | Latency observed | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenRouter | `deepseek/deepseek-v4-flash` | OK: `message.content="ok"` | OK: simple JSON object parsed from `message.content` | OK: simple JSON schema parsed; real Tenancy schema parsed | Reasoning is separate when enabled and does not interfere with `message.content`; JSON schema calls returned no reasoning tokens | OK with real Tenancy `json_object` and real Tenancy `json_schema`, correct document ID and non-empty fields | Plain `3.19s`; simple `json_object` `6.48s`; simple `json_schema` `1.60s`; Tenancy `json_object` `7.42s`; Tenancy `json_schema` `22.24s` | Strong paid candidate; next step is a serial reliability/rate sample |

OpenRouter `deepseek/deepseek-v4-flash` notes:

* `json_object` mode preserved reasoning separately in the OpenRouter response
  while keeping parseable JSON in `message.content`.
* `json_schema` mode worked for both a trivial schema and the real
  `GeneratedEnrichmentBatch` schema. In these probes, schema mode did not return
  reasoning tokens.
* The real Tenancy `json_object` probe cost about `$0.00050344`; the real
  Tenancy `json_schema` probe cost about `$0.00034888`, as reported by
  OpenRouter usage metadata.
* Both real Tenancy probes returned the exact expected document ID
  `doc_justice_tenancy_172069933` and non-empty retrieval fields.

### NVIDIA Capability Matrix

| Model | Real Tenancy result | Latency observed | Notes |
| --- | --- | --- | --- |
| `meta/llama-4-maverick-17b-128e-instruct` | `10/10` OK in serial sample | min `2.44s`, median about `3.5s`, max `153.48s`, avg `18.66s` | Best current NVIDIA candidate. Reasoning did not interfere with parsing. Needs larger reliability/rate sample. |
| `mistralai/mistral-large-3-675b-instruct-2512` | `4/4` OK in partial serial sample | `49.19s` to `83.60s`, avg `63.38s` | Schema-compatible but too slow for backlog throughput. One successful row had empty retrieval fields. Rejects `chat_template_kwargs.enable_thinking` with HTTP 400. |
| `mistralai/mistral-nemotron` | `3/3` OK in partial serial sample | `3.54s`, `55.14s`, `248.33s` | Output can be good, but latency is unstable. Capability probe also saw HTTP 500: `Inference connection error while making inference request`. |
| `stepfun-ai/step-3.5-flash` | `0/19` parseable in serial sample | avg `7.33s` across parse failures | Plain chat content works. JSON-mode answer goes to `reasoning_content`; `message.content` is empty. Current parser cannot use it safely. |
| `bytedance/seed-oss-36b-instruct` | Capability real parse failed schema | real probe `134.51s` | Simple JSON mode works in `message.content`, but real enrichment emitted `catchwords` as a string instead of a list. |
| `qwen/qwen3-coder-480b-a35b-instruct` | Capability real parse failed schema | real probe `7.39s` | Simple JSON mode works, but real enrichment changed the document ID prefix and emitted `legal_principles` as strings. |
| `nvidia/nemotron-3-super-120b-a12b` | Capability real parse failed schema | real probe `16.62s` | Simple JSON mode works. Real enrichment returned `{"items":[{"":""}]}` in `message.content`; reasoning contained a fuller attempt. |

## Error Details

Observed HTTP/provider errors in this pass:

* `mistralai/mistral-large-3-675b-instruct-2512` with
  `extra_body={"chat_template_kwargs":{"enable_thinking": false}}` returned
  HTTP 400: `chat_template is not supported for Mistral tokenizers`.
* `mistralai/mistral-nemotron` returned HTTP 500 on one simple JSON-mode probe:
  `Inference connection error while making inference request`.

No HTTP 429s were observed in the small serial capability probes. Previous
scheduled-start real-data tests of NVIDIA `minimaxai/minimax-m2.7` did hit 429s
at 40 RPM and 15 RPM, so rate testing still needs to be model-specific.

## Recommendations

1. Run the next NVIDIA rate/reliability sample only on
   `meta/llama-4-maverick-17b-128e-instruct`.
2. Keep reasoning enabled when the model returns parseable JSON in
   `message.content`.
3. Add an explicit request timeout policy before any production canary, because
   both Llama Maverick and Mistral Nemotron showed long-tail stalls.
4. Do not use `chat_template_kwargs.enable_thinking` as a generic NVIDIA option.
5. Do not parse `reasoning_content` in the production pipeline unless a
   model-specific adapter is intentionally added and tested. `stepfun-ai` and
   `nvidia/nemotron-3-super-120b-a12b` showed why this is tempting, but it is a
   different response contract from ordinary OpenAI-compatible content parsing.
