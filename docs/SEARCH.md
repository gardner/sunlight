# Sunlight Search

This document records the public `sunlight.nz/search` design, the current
retrieval path, and the planned BM25/vector hybrid path.

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
  -> Vectorize index: fyi-v2, top 20 candidates
  -> Workers AI reranker: @cf/baai/bge-reranker-base
  -> top 5 reranked citations
  -> Workers AI answer model: @cf/google/gemma-4-26b-a4b-it
  -> JSON answer + citations
```

The route returns both scores when reranking succeeds:

```json
{
  "score": 0.398,
  "rerankScore": 0.398,
  "vectorScore": 0.567
}
```

`score` is the display/sort score for the current stage. After reranking, it is
the reranker score. `vectorScore` preserves the original Vectorize score for
debugging.

## Why Add BM25

Pure vector search is missing some exact-term intent. Recent live tests showed a
query about council leisure-centre contracts retrieving loosely related council
contract material. The reranker improved ordering once a better candidate was in
the Vectorize candidate set, but vector search still has to retrieve that
candidate first.

BM25 should help with:

* exact authority names, request titles, and unusual terms
* acronyms and statute terms
* numeric identifiers, file names, and proper nouns
* queries where dense embeddings overgeneralize

BM25 should not replace semantic search. It should feed a hybrid candidate set
that is then fused and reranked.

## Does BM25 Work With D1?

Yes. Cloudflare D1 supports SQLite FTS5, and SQLite FTS5 includes the `bm25()`
ranking function.

Important D1 constraints:

* D1 paid databases are limited to 10 GB.
* Individual string/BLOB/row values are limited to 2 MB.
* SQL query duration is limited to 30 seconds.
* A D1 database processes queries through a single underlying database instance,
  so slow FTS queries can affect throughput.

For Sunlight, this means D1 is a reasonable lexical sidecar for chunk-level text,
not for storing whole PDF bodies or huge markdown files. Full source artifacts
should stay in R2; D1 should store chunk text and citation metadata needed for
retrieval.

## Proposed D1 FTS Schema

Add a dedicated search database or tables to the public/search database, not the
private operational admin database.

Minimal table shape:

```sql
CREATE TABLE disclosed_chunks (
  chunk_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  source TEXT NOT NULL,
  authority_name TEXT,
  authority_slug TEXT,
  authority_category TEXT,
  request_title TEXT,
  request_url TEXT,
  source_url TEXT,
  original_filename TEXT,
  markdown_r2_key TEXT,
  chunk_index INTEGER NOT NULL,
  chunk_text TEXT NOT NULL,
  text_preview TEXT NOT NULL,
  request_year INTEGER
);

CREATE VIRTUAL TABLE disclosed_chunks_fts USING fts5(
  chunk_id UNINDEXED,
  document_id UNINDEXED,
  authority_name,
  request_title,
  original_filename,
  chunk_text,
  tokenize='unicode61 remove_diacritics 2'
);
```

This intentionally duplicates chunk text into the FTS table. That is simpler and
more explicit than starting with external-content FTS tables. We can optimize
storage later if D1 size or import speed becomes a real problem.

BM25 query shape:

```sql
SELECT
  chunk_id,
  bm25(disclosed_chunks_fts, 1.5, 3.0, 1.0, 1.0) AS bm25_score
FROM disclosed_chunks_fts
WHERE disclosed_chunks_fts MATCH ?
ORDER BY bm25_score
LIMIT 50;
```

SQLite FTS5 returns better BM25 matches as lower numbers, so fusion should use
rank order rather than treating the raw score as "higher is better".

The query string must be sanitized for FTS5 syntax. Do not pass arbitrary user
text directly into `MATCH` without escaping quotes/operators or transforming it
into a safe token expression.

## Hybrid Retrieval Plan

Recommended runtime path:

```text
question
  -> embed question
  -> Vectorize top 50 with metadata
  -> D1 FTS5 BM25 top 50
  -> fuse by chunk_id
  -> BGE rerank top 20 fused candidates
  -> answer from top 5
```

Run Vectorize and D1 in parallel:

```ts
const [vectorMatches, bm25Matches] = await Promise.all([
  env.FYI_VECTORS.query(vector, {
    topK: 50,
    returnMetadata: "all",
  }),
  searchBm25(env.SEARCH_DB, question, 50),
]);
```

Use Reciprocal Rank Fusion first. It is robust because it depends on ranks, not
on incompatible score scales:

```ts
function rrf(rank: number, k = 60) {
  return 1 / (k + rank);
}
```

Initial fusion formula:

```text
fused_score =
  0.55 * rrf(vector_rank)
  + 0.45 * rrf(bm25_rank)
```

Then pass the top 20 fused candidates into `@cf/baai/bge-reranker-base` and keep
the top 5 for generation. The reranker is still useful after hybrid retrieval
because it evaluates query/document relevance directly.

Keep these fields in returned citations for debugging:

```json
{
  "score": 0.72,
  "rerankScore": 0.72,
  "fusedScore": 0.029,
  "vectorScore": 0.58,
  "vectorRank": 4,
  "bm25Score": -8.3,
  "bm25Rank": 1
}
```

## Cloudflare AI Search Alternative

Cloudflare AI Search has a managed hybrid mode that can return vector and
keyword/BM25 scoring details. That is attractive for the R2 markdown pipeline in
`docs/RAG.md`.

However, AI Search is a separate managed index. It does not directly hybridize
against our existing `fyi-v2` Vectorize index. For the current landing search
path, "hybrid search with Vectorize" means implementing the lexical sidecar and
fusion ourselves.

Decision:

* Use D1 FTS5 + Vectorize for the controlled `sunlight.nz/search` path.
* Use AI Search hybrid mode as the managed comparison pipeline once
  `sunlight-corpus` markdown is uploaded to R2.

## Do We Need LlamaIndex?

No, not for the production Worker search path.

Reasons:

* The runtime needs three direct platform calls: Workers AI, Vectorize, and D1.
  A framework would mostly wrap APIs we already need to control.
* LlamaIndex.TS is a general data framework. It is useful for local experiments,
  indexing prototypes, and evaluation harnesses, but it does not remove the need
  for D1 FTS schema/import work.
* Keeping the Worker path direct makes bundle size, edge compatibility, latency,
  and failure modes easier to reason about.

Reasonable LlamaIndex use:

* offline retrieval experiments
* eval harness prototypes
* comparing retriever strategies locally against LanceDB/D1 exports

Avoid using it in the public Worker unless a specific feature proves worth the
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

1. `ai-gateway-provider` for Gateway/unified-provider calls with
   `accountId`, `gateway`, and `apiKey`.
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

## Implementation Steps For BM25 Hybrid

1. Add D1 binding for a public search database.
2. Add a migration for `disclosed_chunks` and `disclosed_chunks_fts`.
3. Export chunk rows from LanceDB into D1 import shards.
4. Import in batches small enough for D1 statement and file limits.
5. Add `searchBm25()` helper with FTS query escaping and unit tests.
6. Add `fuseSearchResults()` helper with RRF and unit tests.
7. Change `/api/search` to run Vectorize and BM25 in parallel.
8. Feed top 20 fused results into BGE reranker.
9. Keep top 5 for generation.
10. Add live log timing for each retrieval stage:
    `embed_ms`, `vector_ms`, `bm25_ms`, `fusion_ms`, `rerank_ms`, `answer_ms`.
11. Build a small eval set before tuning weights.

## Open Questions

* Should the BM25 sidecar live in the existing `sunlight-requests` D1 database
  or a separate `sunlight-search` database? Prefer separate unless operational
  simplicity wins.
* Should BM25 index only `text_preview`, full `chunk_text`, or a windowed chunk
  body from R2 markdown? Prefer full `chunk_text` with a measured D1 size check.
* Should fusion use RRF only, or a weighted normalized score? Start with RRF.
* Should exact metadata filters, such as `authority_slug` or `request_year`, be
  applied before both retrieval branches? Yes, once the UI exposes filters.

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
