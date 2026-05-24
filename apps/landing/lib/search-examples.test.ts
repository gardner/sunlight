import { describe, expect, it } from "vitest";
import {
  EVAL_EXAMPLE_QUESTIONS,
  selectRandomExampleQuestions,
} from "./search-examples";

describe("selectRandomExampleQuestions", () => {
  it("returns three unique eval-backed questions by default", () => {
    const selected = selectRandomExampleQuestions(EVAL_EXAMPLE_QUESTIONS, () => 0.42);

    expect(selected).toHaveLength(3);
    expect(new Set(selected).size).toBe(3);
    expect(selected.every((question) => EVAL_EXAMPLE_QUESTIONS.includes(question))).toBe(true);
  });

  it("keeps selection bounded when fewer questions are available", () => {
    expect(selectRandomExampleQuestions(["one", "two"], () => 0)).toEqual(["one", "two"]);
  });

  it("is deterministic when the random source is injected", () => {
    const selected = selectRandomExampleQuestions(["a", "b", "c", "d"], () => 0.75);

    expect(selected).toEqual(["d", "c", "b"]);
  });
});
