# Farol 3.0.0

Farol turns documentation, books, papers, videos and repositories into
knowledge any AI agent can use: **skills** written by your own AI and validated
by Farol, and **cited evidence** served over MCP. Everything runs locally.

## Highlights

- Everyday journey: `farol add`, `farol build`, `farol sync`, `farol status`,
  `farol connect` (Claude Code, Codex, Cursor, OpenCode, any MCP client) and
  `farol library`.
- Skills written by your agent through validated tasks (outline, chapters,
  core) with source citations and lineage; only stale chapters are reopened
  after source changes.
- Local search with citations (`file:line`, page, timestamp); optional
  multilingual hybrid search.
- New sources: PDF outlines and pages, arXiv papers, WebVTT/SRT, YouTube and
  local audio/video with on-device speech recognition.
- Prompt-injection defence at block level, error catalog with next steps,
  `farol doctor --fix`, recorded public surface and semver policy.

## Measured

| | Result |
|---|---|
| Acceptance corpus (hybrid, top 5) | HTTPX docs 92% (validation split 85%), *Pro Git* 92%, GraphRAG paper 100%, spoken article 100%; 100% of hits with locators; every measured source distilled (rubric and lineage pass) |
| Value benchmark (Claude Haiku, 18 questions) | Farol 89% correct, 83% with verifiable citation, 1.4k prompt tokens; raw corpus 100% / 0% / 27k tokens; no context 22% |
| 500-page book on 2 vCPU / 4 GB | 10 s build (BM25) or 75 s (hybrid) |

Details: [benchmark](BENCHMARK.md), [performance](SCALE.md).

## Upgrading from 2.0

Install `farol-kit` (the old distribution name is still recognised). Existing
packages upgrade in place with `farol build` or `farol index <package>`;
`docops` remains an alias and `farol advanced` lists every 2.0 command.

## Known limits

YouTube may require cookies from servers or VPNs; images and equations are not
interpreted; one writer per project.
