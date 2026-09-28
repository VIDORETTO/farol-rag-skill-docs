# Value benchmark: the same AI with and without Farol

Measured on 2026-09-28 with `scripts/benchmark_value.py`.

## Method

- **Agent**: Claude Code 2.1.283, model Haiku, in non-interactive mode with every
  tool disabled (no web, no files) in an empty directory, so answers come only
  from the prompt.
- **Questions**: 18 reviewed factual questions about the HTTPX documentation
  (13, including 3 in Portuguese) and the GraphRAG paper (5), from the licensed
  acceptance corpus. An answer is correct when it contains every answer key
  (for example `5`/`five` and `second`); a citation counts only if it resolves to
  an indexed block that contains the expected evidence.
- **Arms**, same prompt instructions:
  - *no context*: only the question;
  - *raw corpus*: the whole source pasted into the prompt (it fits here: ~27k tokens);
  - *Farol*: the top 5 evidence blocks with citations plus the source skill.
- Input tokens include Claude Code's own ~13k-token system prompt in every arm;
  the prompt column below is the part each arm adds.

## Results

| Arm | Correct | Correct with a verifiable citation | Mean prompt added | Mean input tokens | Total cost |
|---|---|---|---|---|---|
| No context | 22% | 0% | 59 | 13,118 | $0.19 |
| Raw corpus | 100% | 0% | 27,330 | 44,464 | $1.31 |
| **Farol** | **89%** | **83%** | **1,385** | **14,640** | **$0.24** |

## Reading the results

- Without context the model mostly guesses (22%).
- Pasting the whole source works when it fits in the context window, but costs
  about 20 times more prompt tokens and 5.4 times more money per question, and
  produces no verifiable citation. It does not scale to large corpora: a
  500-page book is ~220k tokens.
- Farol keeps the prompt ~20 times smaller than the raw source and nearly
  matches its accuracy, with citations the reader can check. Its two misses are
  retrieval misses already visible in the acceptance corpus.

## Limits

- One model and 18 questions; results vary with model, questions and sources.
- The raw-corpus arm has no line markers, so it cannot cite `file:line`.
- The Farol arm here injects evidence into the prompt; in daily use the agent
  calls the MCP tools itself (verified separately with Claude Code).

Reproduce (uses your own agent and account):

```text
python scripts/benchmark_value.py --project <project> --cases <cases.json> --harness "claude -p --output-format json" --json
```
