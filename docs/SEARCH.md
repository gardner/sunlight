# Sunlight Search

This document records the public `sunlight.nz/search` retrieval path, the D1
BM25 sidecar, and the planned comparison work against Cloudflare AI Search.

## Current State

The live search UI is in the landing app:

```text
apps/landing/app/search/page.tsx
apps/landing/app/search/SearchClient.tsx
apps/landing/app/api/search/route.ts
apps/landing/lib/search.ts
```

The deployed Worker route is:

```text
POST https://sunlight.nz/api/search
```

Current retrieval pipeline:

```text
user question
  -> Workers AI embedding: @cf/qwen/qwen3-embedding-0.6b
  -> Vectorize index: fyi-v2, top 50 semantic candidates
  -> D1 FTS5 sidecar: sunlight-search, top 50 BM25 candidates
  -> reciprocal-rank fusion by chunk_id, top 20 fused candidates
  -> Workers AI reranker: @cf/baai/bge-reranker-base
  -> top 5 reranked citations by default, max 10
  -> Workers AI answer model: @cf/google/gemma-4-26b-a4b-it
  -> JSON answer + citations
```

The route returns score fields that identify each retrieval stage:

```json
{
  "score": 0.398,
  "rerankScore": 0.398,
  "fusedScore": 0.016,
  "vectorScore": 0.567,
  "vectorRank": 3,
  "bm25Score": -8.346,
  "bm25Rank": 1
}
```

`score` is the display/sort score for the latest completed stage. After
reranking, it is the reranker score. `vectorScore`, `bm25Score`, and
`fusedScore` preserve earlier retrieval evidence for debugging and future evals.

## Why BM25

Pure vector search missed some exact-term intent. A query about council
leisure-centre contracts retrieved loosely related council contract material
unless the relevant candidate was already in the Vectorize candidate set.

BM25 helps with:

* exact authority names, request titles, and unusual terms
* acronyms and statute terms
* numeric identifiers, file names, and proper nouns
* queries where dense embeddings overgeneralize

BM25 does not replace semantic search. It feeds a hybrid candidate set that is
then fused and reranked.

## D1 BM25 Sidecar

Cloudflare D1 supports SQLite FTS5, and SQLite FTS5 includes the `bm25()`
ranking function. Sunlight uses a separate public search database rather than
the operational admin database:

```text
D1 database: sunlight-search
D1 database id: be61ceef-eed3-43cd-95d2-cd762f5fd59f
Wrangler binding: SEARCH_DB
Migration directory: cloudflare/search-migrations
```

The migration is:

```text
cloudflare/search-migrations/0001_disclosed_chunks_fts.sql
```

It creates:

* `disclosed_chunks` for citation metadata and capped chunk text
* `disclosed_chunks_fts` as an FTS5 virtual table
* insert, update, and delete triggers to keep the FTS table synchronized

The indexed FTS columns are:

```sql
authority_name,
request_title,
original_filename,
chunk_text
```

The runtime BM25 query weights these fields as:

```sql
bm25(disclosed_chunks_fts, 0.0, 0.0, 2.0, 3.0, 1.0, 1.0)
```

That means unindexed metadata columns have zero weight, request titles get the
highest lexical weight, authority names get the next highest weight, and file
names/body text remain useful but less dominant.

SQLite FTS5 returns better BM25 matches as lower numbers. The production search
path therefore uses BM25 rank order for fusion rather than treating the raw
negative score as "higher is better".

## Import Pipeline

BM25 rows are generated from FYI markdown frontmatter and body text:

```text
fyi/markdown/*.md
  -> scripts/export_bm25_to_d1.py
  -> storage/d1_bm25_import/bm25_*.sql
  -> D1 sunlight-search
```

The exporter uses the same chunker defaults as the Vectorize pipeline:

```text
chunk size: 8192
chunk overlap: 128
```

Chunk IDs are deterministic:

```text
chunk_{document_id}_{chunk_index:04d}_{sha1(original_chunk_text)[:12]}
```

The D1 sidecar stores capped, normalized text for FTS:

```text
default max chunk text chars: 12000
default text preview chars: 800
```

The cap keeps each SQL statement below D1 statement limits while preserving
enough body text for lexical retrieval. Source artifacts remain outside D1.

Generate import shards:

```bash
uv run python scripts/export_bm25_to_d1.py \
  --output-dir storage/d1_bm25_import \
  --rows-per-file 500 \
  --reset
```

Apply generated shards to remote D1:

```bash
uv run python scripts/export_bm25_to_d1.py \
  --output-dir storage/d1_bm25_import \
  --apply-existing \
  --remote
```

Apply selected shards after regenerating a subset:

```bash
uv run python scripts/export_bm25_to_d1.py \
  --output-dir storage/d1_bm25_import \
  --apply-existing \
  --remote \
  --shard 101 \
  --shard 111
```

The current remote import has:

```text
disclosed_chunks rows: 160,479
D1 size after import: about 774 MB
```

Smoke-check row count:

```bash
pnpm dlx wrangler@latest d1 execute sunlight-search \
  --remote \
  --config apps/landing/wrangler.jsonc \
  --command "SELECT count(*) AS rows FROM disclosed_chunks;" \
  --json
```

Smoke-check BM25:

```bash
pnpm dlx wrangler@latest d1 execute sunlight-search \
  --remote \
  --config apps/landing/wrangler.jsonc \
  --command "SELECT c.request_title, c.authority_name, bm25(disclosed_chunks_fts, 0.0, 0.0, 2.0, 3.0, 1.0, 1.0) AS score, c.text_preview FROM disclosed_chunks_fts JOIN disclosed_chunks c ON c.chunk_id = disclosed_chunks_fts.chunk_id WHERE disclosed_chunks_fts MATCH '\"leisure\" OR \"centre\" OR \"contracts\"' ORDER BY score LIMIT 5;" \
  --json
```

## Hybrid Fusion

The Worker runs BM25 and Vectorize retrieval in parallel where possible:

```ts
const bm25Promise = searchBm25Candidates(question, 50);
const embedding = await env.AI.run(EMBEDDING_MODEL, { text: [question] });
const vector = coerceEmbeddingVector(embedding);
const [vectorMatches, bm25Matches] = await Promise.all([
  env.FYI_VECTORS.query(vector, { topK: 50, returnMetadata: "all" }),
  bm25Promise,
]);
```

Candidate fusion uses weighted Reciprocal Rank Fusion:

```text
rrf(rank) = 1 / (60 + rank)
fused_score = 0.55 * rrf(vector_rank) + 0.45 * rrf(bm25_rank)
```

The initial weights intentionally keep semantic retrieval slightly dominant
while giving exact-term matches enough influence to enter the reranker window.

The route sends the top 20 fused candidates to `@cf/baai/bge-reranker-base` and
uses the top 5 reranked citations for answer generation by default.

If BM25 fails, the route logs a warning and falls back to Vectorize-only
retrieval. If reranking fails, the route falls back to fused order.

## FTS Query Sanitization

User text is not passed directly into `MATCH`. The runtime transforms questions
into a safe quoted OR expression:

```text
Council "leisure" OR NEAR(contracts) -x
  -> "council" OR "leisure" OR "contracts"
```

Rules:

* lowercase with `en-NZ`
* keep Unicode letters, numbers, and underscores
* drop one-character terms
* drop a small set of English and release-archive stopwords, such as `what`,
  `information`, `released`, `request`, `or`, and `near`
* de-duplicate terms in original order
* limit to 12 terms
* quote every term for FTS5

This preserves useful lexical recall while avoiding raw FTS operators from user
input.

## Cloudflare AI Search Alternative

Cloudflare AI Search has managed hybrid search that can combine vector and
keyword scoring. That is the planned comparison pipeline once
`sunlight-corpus` markdown is uploaded to R2.

AI Search is a separate managed index. It does not directly hybridize against
the existing `fyi-v2` Vectorize index. For the current landing search path,
"hybrid search with Vectorize" means using this D1 FTS5 sidecar and local fusion.

Decision:

* Use D1 FTS5 + Vectorize for the controlled `sunlight.nz/search` path.
* Add AI Search hybrid mode later as the managed comparison pipeline.
* Run RAG evaluations against both before declaring either "better".

## Do We Need LlamaIndex?

No, not for the production Worker search path.

Reasons:

* The runtime needs direct platform calls to Workers AI, Vectorize, and D1.
* A framework does not remove the need for D1 FTS schema/import work.
* Keeping the Worker path direct keeps bundle size, edge compatibility, latency,
  and failure modes easier to reason about.

Reasonable LlamaIndex use:

* offline retrieval experiments
* eval harness prototypes
* comparing retriever strategies locally against LanceDB/D1 exports

Avoid adding it to the public Worker unless a specific feature proves worth the
extra dependency and runtime surface.

## AI SDK And AI Gateway

The Vercel AI SDK is useful if we want a streaming chat UI. Its `useChat` hook
still talks to an HTTP route; it replaces hand-written client `fetch` and stream
parsing, not the need for a server endpoint.

For our app, that would mean moving from:

```text
SearchClient -> fetch("/api/search") -> JSON response
```

to:

```text
SearchClient -> useChat/sendMessage -> /api/search/chat -> UI message stream
```

The route would return `result.toUIMessageStreamResponse()` from `streamText`.
Retrieval would still happen before generation:

```text
route receives UI messages
  -> normalize latest user message
  -> Vectorize + D1 + reranker
  -> streamText with retrieved citations in the prompt
  -> stream answer and citation metadata
```

Cloudflare AI Gateway can be used with the AI SDK in two distinct ways:

1. `ai-gateway-provider` for Gateway/unified-provider calls with `accountId`,
   `gateway`, and `apiKey`.
2. `workers-ai-provider` with the Worker `AI` binding and a `gateway` option.

For now, keep direct `env.AI.run` for embeddings and reranking. The AI SDK
reranking docs currently focus on providers such as Cohere, Bedrock, and
Together.ai, while Cloudflare's BGE reranker is directly available through the
Workers AI binding.

Recommended AI SDK migration:

1. Keep `/api/search` JSON until hybrid retrieval quality is acceptable.
2. Add `/api/search/chat` as a streaming route rather than replacing the JSON
   route immediately.
3. Install only the needed packages:

   ```bash
   pnpm add ai @ai-sdk/react workers-ai-provider
   ```

4. Stream the answer text, and include citations as structured stream data or
   final message metadata.
5. Route answer-generation calls through AI Gateway once the gateway name and
   observability requirements are settled.

## Evaluation Plan

The next retrieval-quality decision should be eval-driven.

Build a small labeled set first:

* exact-term requests, such as authority names, legislation, and file names
* semantic requests, such as "contracts for running council pools"
* numeric identifier requests
* failure cases from live logs
* queries where the right answer is absent

Measure at least:

* retrieval recall at 5, 10, 20, and 50 before generation
* reranked citation relevance at 5
* grounded answer quality
* citation faithfulness
* latency by stage

Compare:

* Vectorize only
* Vectorize + D1 BM25 + RRF + BGE reranker
* Cloudflare AI Search hybrid mode

Use the same answer model and prompt while comparing retrievers.

## References

* Cloudflare D1 supported SQL extensions:
  https://developers.cloudflare.com/d1/sql-api/sql-statements/
* Cloudflare D1 limits:
  https://developers.cloudflare.com/d1/platform/limits/
* SQLite FTS5 and BM25:
  https://www.sqlite.org/fts5.html
* Cloudflare Vectorize Worker API:
  https://developers.cloudflare.com/vectorize/reference/client-api/
* Cloudflare AI Search hybrid search:
  https://developers.cloudflare.com/ai-search/configuration/indexing/hybrid-search/
* Cloudflare Workers AI BGE reranker:
  https://developers.cloudflare.com/workers-ai/models/bge-reranker-base/
* Cloudflare AI Gateway with Vercel AI SDK:
  https://developers.cloudflare.com/ai-gateway/integrations/vercel-ai-sdk/
* Vercel AI SDK overview:
  https://ai-sdk.dev/docs/introduction
* Vercel AI SDK App Router quickstart:
  https://ai-sdk.dev/docs/getting-started/nextjs-app-router
* Vercel AI SDK reranking:
  https://ai-sdk.dev/docs/ai-sdk-core/reranking
