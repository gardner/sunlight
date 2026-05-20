import { describe, expect, it } from "vitest";
import {
  type SearchCitation,
  buildAnswerPrompt,
  buildFtsMatchQuery,
  buildRerankContexts,
  coerceEmbeddingVector,
  extractAnswerText,
  fuseSearchCandidates,
  mapBm25RowToCitation,
  mapVectorizeMatchToCitation,
  normalizeSearchQuestion,
  rerankCitations,
  selectFinalCitations,
} from "./search";

function citation(
  chunkId: string,
  title: string,
  overrides: Partial<SearchCitation> = {},
): SearchCitation {
  return {
    chunkId,
    label: "Source 1",
    score: 0,
    snippet: `${title} snippet`,
    title,
    ...overrides,
  };
}

describe("normalizeSearchQuestion", () => {
  it("trims useful questions", () => {
    expect(normalizeSearchQuestion("  What did Auckland Council release?  ")).toBe(
      "What did Auckland Council release?",
    );
  });

  it("rejects very short questions", () => {
    expect(() => normalizeSearchQuestion("OIA")).toThrow("at least 4 characters");
  });

  it("rejects overlong questions", () => {
    expect(() => normalizeSearchQuestion("x".repeat(701))).toThrow("700 characters");
  });
});

describe("coerceEmbeddingVector", () => {
  it("reads the first Workers AI embedding vector", () => {
    expect(coerceEmbeddingVector({ data: [[0.1, 0.2, 0.3]] })).toEqual([0.1, 0.2, 0.3]);
  });

  it("rejects missing vectors", () => {
    expect(() => coerceEmbeddingVector({ data: [] })).toThrow("embedding vector");
  });
});

describe("mapVectorizeMatchToCitation", () => {
  it("normalizes citation metadata from Vectorize matches", () => {
    const citation = mapVectorizeMatchToCitation(
      {
        id: "chunk_123",
        score: 0.81234,
        metadata: {
          authority_name: "Auckland Council",
          chunk_index: 4,
          document_id: "doc_123",
          original_filename: "response.pdf",
          request_title: "Council leisure centre contracts",
          request_url: "https://fyi.org.nz/request/123",
          source_url: "https://fyi.org.nz/request/123/response/456/attach/1/response.pdf",
          text_preview: "The attached document describes the contract value.",
        },
      },
      0,
    );

    expect(citation).toMatchObject({
      authorityName: "Auckland Council",
      chunkId: "chunk_123",
      chunkIndex: 4,
      documentId: "doc_123",
      label: "Source 1",
      score: 0.812,
      title: "Council leisure centre contracts",
      vectorRank: 1,
      vectorScore: 0.812,
    });
    expect(citation.requestUrl).toBe("https://fyi.org.nz/request/123");
    expect(citation.sourceUrl).toContain("/attach/1/");
  });

  it("falls back to filename and match id when richer metadata is absent", () => {
    expect(
      mapVectorizeMatchToCitation(
        {
          id: "chunk_456",
          score: 0.4,
          metadata: {
            original_filename: "release-letter.pdf",
            text_preview: "Released in part.",
          },
        },
        1,
      ),
    ).toMatchObject({
      chunkId: "chunk_456",
      label: "Source 2",
      title: "release-letter.pdf",
    });
  });
});

describe("mapBm25RowToCitation", () => {
  it("normalizes citation metadata from D1 BM25 rows", () => {
    expect(
      mapBm25RowToCitation(
        {
          authority_name: "Auckland Council",
          bm25_score: -8.3456,
          chunk_id: "chunk_bm25",
          chunk_index: 2,
          document_id: "doc_bm25",
          request_title: "Leisure centre contracts",
          request_url: "https://fyi.org.nz/request/29087",
          text_preview: "The document names the supplier.",
        },
        0,
      ),
    ).toMatchObject({
      authorityName: "Auckland Council",
      bm25Rank: 1,
      bm25Score: -8.346,
      chunkId: "chunk_bm25",
      documentId: "doc_bm25",
      label: "Source 1",
      score: 0,
      snippet: "The document names the supplier.",
      title: "Leisure centre contracts",
    });
  });
});

describe("buildAnswerPrompt", () => {
  it("numbers citations and includes snippets", () => {
    const prompt = buildAnswerPrompt("What contracts were released?", [
      {
        chunkId: "chunk_1",
        label: "Source 1",
        score: 0.9,
        snippet: "The council released two contracts.",
        title: "Contract release",
      },
    ]);

    expect(prompt).toContain("Question: What contracts were released?");
    expect(prompt).toContain("[1] Contract release");
    expect(prompt).toContain("The council released two contracts.");
  });
});

describe("buildFtsMatchQuery", () => {
  it("turns user text into a safe OR expression", () => {
    expect(buildFtsMatchQuery('Council "leisure" OR NEAR(contracts) -x')).toBe(
      '"council" OR "leisure" OR "contracts"',
    );
  });

  it("deduplicates and limits terms", () => {
    expect(buildFtsMatchQuery("ACC acc a b c")).toBe('"acc"');
  });
});

describe("fuseSearchCandidates", () => {
  it("combines Vectorize and BM25 candidates with reciprocal rank fusion", () => {
    expect(
      fuseSearchCandidates(
        [
          {
            chunkId: "shared",
            label: "Source 1",
            score: 0.9,
            snippet: "Vector snippet",
            title: "Shared vector",
            vectorRank: 1,
            vectorScore: 0.9,
          },
          {
            chunkId: "vector_only",
            label: "Source 2",
            score: 0.8,
            snippet: "Vector only",
            title: "Vector only",
            vectorRank: 2,
            vectorScore: 0.8,
          },
        ],
        [
          {
            bm25Rank: 1,
            bm25Score: -9,
            chunkId: "shared",
            label: "Source 1",
            score: 0,
            snippet: "BM25 snippet",
            title: "Shared BM25",
          },
          {
            bm25Rank: 2,
            bm25Score: -7,
            chunkId: "bm25_only",
            label: "Source 2",
            score: 0,
            snippet: "BM25 only",
            title: "BM25 only",
          },
        ],
        3,
      ),
    ).toEqual([
      {
        bm25Rank: 1,
        bm25Score: -9,
        chunkId: "shared",
        fusedScore: 0.016,
        label: "Source 1",
        score: 0.016,
        snippet: "Vector snippet",
        title: "Shared vector",
        vectorRank: 1,
        vectorScore: 0.9,
      },
      {
        chunkId: "vector_only",
        fusedScore: 0.009,
        label: "Source 2",
        score: 0.009,
        snippet: "Vector only",
        title: "Vector only",
        vectorRank: 2,
        vectorScore: 0.8,
      },
      {
        bm25Rank: 2,
        bm25Score: -7,
        chunkId: "bm25_only",
        fusedScore: 0.007,
        label: "Source 3",
        score: 0.007,
        snippet: "BM25 only",
        title: "BM25 only",
      },
    ]);
  });
});

describe("selectFinalCitations", () => {
  it("reserves room for strong BM25 hits before filling from fused order", () => {
    const vector = [
      citation("vector_1", "Vector 1", { documentId: "doc-v1", vectorRank: 1 }),
      citation("vector_2", "Vector 2", { documentId: "doc-v2", vectorRank: 2 }),
      citation("vector_3", "Vector 3", { documentId: "doc-v3", vectorRank: 3 }),
    ];
    const bm25 = [
      citation("bm25_1", "BM25 1", { bm25Rank: 1, documentId: "doc-b1" }),
      citation("bm25_2", "BM25 2", { bm25Rank: 2, documentId: "doc-b2" }),
    ];
    const fused = [
      citation("vector_1", "Vector 1", { documentId: "doc-v1", fusedScore: 0.009 }),
      citation("vector_2", "Vector 2", { documentId: "doc-v2", fusedScore: 0.008 }),
      citation("vector_3", "Vector 3", { documentId: "doc-v3", fusedScore: 0.007 }),
      citation("bm25_1", "BM25 1", { bm25Rank: 1, documentId: "doc-b1", fusedScore: 0.006 }),
      citation("bm25_2", "BM25 2", { bm25Rank: 2, documentId: "doc-b2", fusedScore: 0.005 }),
    ];

    expect(selectFinalCitations(fused, vector, bm25, 5).map((item) => item.chunkId)).toEqual([
      "vector_1",
      "bm25_1",
      "bm25_2",
      "vector_2",
      "vector_3",
    ]);
  });

  it("deduplicates selected citations by document id", () => {
    const vector = [
      citation("vector_1", "Vector 1", { documentId: "doc-shared", vectorRank: 1 }),
    ];
    const bm25 = [
      citation("bm25_1", "BM25 duplicate", { bm25Rank: 1, documentId: "doc-shared" }),
      citation("bm25_2", "BM25 2", { bm25Rank: 2, documentId: "doc-b2" }),
    ];

    expect(selectFinalCitations([], vector, bm25, 5).map((item) => item.chunkId)).toEqual([
      "vector_1",
      "bm25_2",
    ]);
  });
});

describe("buildRerankContexts", () => {
  it("builds compact context text for the reranker", () => {
    expect(
      buildRerankContexts([
        {
          authorityName: "Auckland Council",
          chunkId: "chunk_1",
          label: "Source 1",
          score: 0.5,
          snippet: "Contract details were released.",
          title: "Leisure contracts",
        },
      ]),
    ).toEqual([
      {
        text: "Title: Leisure contracts\nAuthority: Auckland Council\nSnippet: Contract details were released.",
      },
    ]);
  });
});

describe("rerankCitations", () => {
  const citations = [
    {
      chunkId: "chunk_a",
      label: "Source 1",
      score: 0.62,
      snippet: "Weak candidate.",
      title: "A",
      vectorScore: 0.62,
    },
    {
      chunkId: "chunk_b",
      label: "Source 2",
      score: 0.58,
      snippet: "Strong candidate.",
      title: "B",
      vectorScore: 0.58,
    },
    {
      chunkId: "chunk_c",
      label: "Source 3",
      score: 0.55,
      snippet: "Middle candidate.",
      title: "C",
      vectorScore: 0.55,
    },
  ];

  it("orders citations by reranker score and relabels sources", () => {
    expect(
      rerankCitations(citations, {
        response: [
          { id: 1, score: 0.91 },
          { id: 2, score: 0.77 },
          { id: 0, score: 0.1 },
        ],
      }, 2),
    ).toEqual([
      {
        chunkId: "chunk_b",
        label: "Source 1",
        rerankScore: 0.91,
        score: 0.91,
        snippet: "Strong candidate.",
        title: "B",
        vectorScore: 0.58,
      },
      {
        chunkId: "chunk_c",
        label: "Source 2",
        rerankScore: 0.77,
        score: 0.77,
        snippet: "Middle candidate.",
        title: "C",
        vectorScore: 0.55,
      },
    ]);
  });

  it("falls back to vector order when reranker output is empty", () => {
    expect(rerankCitations(citations, { response: [] }, 2)).toEqual([
      {
        ...citations[0],
        label: "Source 1",
      },
      {
        ...citations[1],
        label: "Source 2",
      },
    ]);
  });

  it("does not invent vector scores for BM25-only candidates", () => {
    expect(
      rerankCitations(
        [
          {
            bm25Rank: 1,
            bm25Score: -8,
            chunkId: "chunk_bm25",
            fusedScore: 0.007,
            label: "Source 1",
            score: 0.007,
            snippet: "Lexical-only candidate.",
            title: "BM25",
          },
        ],
        { response: [{ id: 0, score: 0.82 }] },
        1,
      ),
    ).toEqual([
      {
        bm25Rank: 1,
        bm25Score: -8,
        chunkId: "chunk_bm25",
        fusedScore: 0.007,
        label: "Source 1",
        rerankScore: 0.82,
        score: 0.82,
        snippet: "Lexical-only candidate.",
        title: "BM25",
      },
    ]);
  });
});

describe("extractAnswerText", () => {
  it("supports OpenAI-compatible chat responses", () => {
    expect(
      extractAnswerText({
        choices: [{ message: { content: "Use Source 1." } }],
      }),
    ).toBe("Use Source 1.");
  });

  it("supports older Workers AI response shapes", () => {
    expect(extractAnswerText({ response: "Older response." })).toBe("Older response.");
  });
});
