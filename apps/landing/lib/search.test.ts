import { describe, expect, it } from "vitest";
import {
  buildAnswerPrompt,
  buildRerankContexts,
  coerceEmbeddingVector,
  extractAnswerText,
  mapVectorizeMatchToCitation,
  normalizeSearchQuestion,
  rerankCitations,
} from "./search";

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
    },
    {
      chunkId: "chunk_b",
      label: "Source 2",
      score: 0.58,
      snippet: "Strong candidate.",
      title: "B",
    },
    {
      chunkId: "chunk_c",
      label: "Source 3",
      score: 0.55,
      snippet: "Middle candidate.",
      title: "C",
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
