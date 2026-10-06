# Farol 3.1.0

Farol 3.1 makes any content — books, **courses**, videos, papers, docs and
repositories — easier to turn into skills and faster to query precisely. It
only adds to 3.0: every command, MCP tool and package from 3.0 keeps working.

## Highlights

- **Courses as one source**: `farol add ./course --as course --license …` or a
  YouTube playlist URL; lessons in natural order, modules from sub-folders,
  per-video licenses, citations that name the lesson and the moment. Optional
  `--slides` reads the text shown on lecture slides.
- **One skill from several sources**: `farol skill compose python --from book course`.
- **Read around a fact**: hits carry `block_id`; `get_context` returns the
  neighbouring blocks or the section; `get_document` pages long documents.
- **Better ranking across a library** of projects, an optional local
  reranker (`FAROL_RERANKER`) and embedding profiles with query/passage prefixes.
- **Faster skill writing**: `farol task claim` for parallel subagents (with a
  locked plan), `--task-tokens`, chapters that follow the author's own, and the
  `farol-distill` skill installed by `farol connect`.
- **Search the skill itself** (`search_knowledge(layer="synthesis")`) with the
  source blocks behind each statement, and **`farol eval`** to measure any
  package from its own skill.
- **Digital PDFs with layout and tables** (extra `layout`, opt-in).
- **One router per project**, about 260 tokens, instead of one per source.

## Security

- `get_document` no longer returns blocks classified as prompt-injection
  directives (3.0 returned them through this tool only).
- `farol connect` only removes files inside the harness's skills folder, even
  with a tampered `.farol/connect.json`.
- See [SECURITY.md](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/SECURITY.md)
  for supported versions and the threat model.

## Measured

| | 3.0.0 | 3.1.0 |
|---|---|---|
| Library of two sources (BM25, top 5): MRR@5 | 0.378 | **0.481** |
| Library: hits from the wrong package | 40% | **6%** |
| Tokens to read the context of a fact (*Pro Git*) | 218,675 (whole document) | **1,313** (`get_context`) |
| Parallel `task submit` of 16 chapters | up to 4 accepted chapters lost | none lost |

Per-source retrieval is unchanged. Reranker, alternative embeddings and the
layout path stay opt-in until measured on the acceptance corpus.

## Upgrading

`pipx upgrade farol-kit` (or reinstall from the `v3.1.0` tag), then
`farol build` once: routers are refreshed and indexes are kept. Run
`farol connect <agent>` again to switch to the single project router and get
`farol-distill`.

## Known limits

YouTube may require cookies from servers or VPNs; images and equations are not
interpreted; one writer per project (several agents may now share the task
queue with `farol task claim`).
