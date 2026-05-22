# Agentic RAG Plan

Sunlight should make the RAG pipeline more agentic by adding a bounded
retrieval controller around the existing deterministic hybrid search path. The
goal is better evidence gathering, not an autonomous agent that invents tools,
loops indefinitely, or chooses citations without retrieval support.

## Current Baseline

The current production path is:

```text
question
  -> Workers AI Qwen embedding
  -> Vectorize semantic candidates
  -> D1 FTS5 BM25 candidates
  -> weighted reciprocal-rank fusion
  -> source-diverse final citations
  -> grounded answer JSON
```

This remains the baseline. The agentic layer is an offline eval experiment until
it beats the current hybrid retriever on the reviewed eval set.

## Agentic Controller

The controller has four bounded steps.

1. Query analysis

   Parse the user question into a small structured plan:

   ```json
   {
     "queryKind": "exact_lookup",
     "sourceFilter": "justice_tenancy",
     "entities": ["172069933"],
     "mustTerms": ["tenancy", "tribunal", "rent", "arrears"],
     "expandedQueries": [
       "172069933 tenancy tribunal rent arrears",
       "172069933 rent arrears"
     ],
     "needsFullDocument": true,
     "abstainIfNoExactEvidence": true
   }
   ```

2. Tool fanout

   Run the normal vector and BM25 tools first. When the query plan says the
   evidence is exact, numeric, or source-specific, keep query expansions ready
   for a second pass.

3. Evidence inspection

   Inspect the first-pass retrieval trace before answering. A second pass is
   allowed only when the first pass has a clear evidence gap, such as:

   * no candidates
   * exact or numeric terms missing from the retrieved evidence
   * lexical evidence missing for an exact lookup

4. Bounded retry

   Run at most one expansion round, capped by `--agentic-max-rounds` and
   `--agentic-expansions`. Merge expanded vector and BM25 candidates back into
   the same hybrid fusion path.

## Guardrails

The agentic controller must stay constrained:

* max two retrieval rounds by default
* no external web access
* no corpus mutation
* no model-generated citation IDs
* deterministic tool list
* full per-question trace output
* production changes only after eval evidence shows a win

## Eval Mode

`scripts/eval_search.py` now supports:

```bash
uv run python scripts/eval_search.py --agentic --no-rerank --device cuda
```

The new mode records:

* `retrieval_policy`
* `agentic_trace.plan`
* `agentic_trace.rounds`
* `agentic_trace.second_pass_reason`
* `timings_ms.agentic_controller`

The report includes an agentic trace summary with second-pass counts and
trigger reasons.

## First Comparison

Use the same reviewed eval manifest and compare:

```bash
uv run python scripts/eval_search.py \
  --no-rerank \
  --output-dir storage/evals/search/hybrid-source-diverse \
  --device cuda

uv run python scripts/eval_search.py \
  --agentic \
  --no-rerank \
  --output-dir storage/evals/search/agentic-source-diverse \
  --device cuda
```

Keep reranking disabled for the first comparison so the retrieval controller is
the only changed variable.

## Tenancy Path

Tenancy decisions are where the agentic layer should matter most. The planner
should route and expand around:

* Tenancy Tribunal order IDs
* application numbers
* rent arrears, bond, damages, repairs, termination, healthy homes, and access
  issues
* city, suburb, and suppressed-address cases
* statute-section and amount-heavy questions
* absent-answer questions where the right answer should be "not enough evidence"

The next ingestion-side improvement is to finish controlled LLM enrichment
batches for summaries, catchwords, legal principles, and generated questions.
Those generated views should become extra retrieval targets once the eval set
can show whether they improve recall without increasing false positives.

## Promotion Criteria

Do not ship the agentic path to production until it improves the reviewed evals
without unacceptable latency:

* final recall@5 improves or stays flat
* final MRR@5 improves or stays flat
* exact/numeric failures decrease
* no-answer behavior does not regress
* second-pass rate is explainable and bounded
* trace output makes regressions easy to debug
