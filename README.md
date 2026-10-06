<div align="center">

<img src="assets/farol-logo-horizontal.png" alt="Farol logo: a yellow lighthouse on a navy background" width="420">

# Farol

**Turn documentation, books, papers, videos and repositories into knowledge your AI can use — with citations.**

<a href="https://github.com/VIDORETTO/farol-rag-skill-docs/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/VIDORETTO/farol-rag-skill-docs/actions/workflows/ci.yml/badge.svg?branch=main"></a>
<img alt="Python 3.11–3.13" src="https://img.shields.io/badge/Python-3.11--3.13-3776AB?logo=python&logoColor=white">
<a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/github/license/VIDORETTO/farol-rag-skill-docs"></a>
<img alt="Works with any MCP client" src="https://img.shields.io/badge/MCP-Claude%20Code%20%7C%20Codex%20%7C%20Cursor%20%7C%20OpenCode-0f766e">

**Version:** `3.0.0` ([changelog](CHANGELOG.md))

</div>

Farol gives your AI agent two things for every source you add:

- **A skill** — a compact guide to the subject (mental models, decision rules,
  pitfalls, chapters on demand), in the spirit of
  [book-to-skill](https://github.com/virgiliojr94/book-to-skill). Your own AI
  writes it, task by task; Farol plans the work and rejects answers without
  citations, with copied text or with injected instructions.
- **Cited evidence** — a local search index over the original text. Every fact
  comes back with a verifiable locator: `file:line`, page, or video timestamp.

Both are served to **any MCP-capable agent** (Claude Code, Codex, Cursor,
OpenCode…). Everything runs locally: no API key, no server, no Docker.

## See it working

Real session: a project built from the HTTPX documentation, connected to
Claude Code, asked a question.

```text
> What is the default timeout in HTTPX, which timeout types exist,
  and what is raised when the connection pool is exhausted?

1. Default timeout: 5 seconds of network inactivity.
   "The default behavior is to raise a TimeoutException after 5 seconds of
   network inactivity." (rag/documents/advanced-timeouts.md:3)
2. Four timeout types: connect, read, write and pool.
   (rag/documents/advanced-timeouts.md:45)
3. Pool exhausted: httpx.PoolTimeout.
   (rag/documents/advanced-timeouts.md:58, rag/documents/exceptions.md:63)
```

## Quick start

Requires Python 3.11–3.13.

```bash
pipx install "farol-kit[semantic] @ git+https://github.com/VIDORETTO/farol-rag-skill-docs@v3.0.0"

mkdir my-knowledge && cd my-knowledge
farol add ./path/to/docs --license MIT
farol add arXiv:2404.16130v2
farol build
farol connect claude-code --target ~/my-repo
```

`farol add` accepts a folder (including a cloned repository), file, URL,
`arXiv:<id>` or a YouTube link; `farol connect` also supports `codex`, `cursor`, `opencode` and
`generic`. Then ask your agent to write the skill:

> Run `farol task next` in `~/my-knowledge`, do the task, submit it with
> `farol task submit`, and repeat until there are no tasks left.

Check progress any time with `farol status`. Keep sources fresh with
`farol sync` (or print a daily schedule with `farol sync --schedule cron`).
The [getting-started guide](docs/GETTING-STARTED.md) covers installation
options, every agent and troubleshooting.

## What you can add

| Source | How | Evidence locator |
|---|---|---|
| Markdown, HTML, reStructuredText, AsciiDoc, text | folder or file | `file:line`, section |
| Documentation websites | URL (robots.txt, sitemaps and limits respected) | `file:line` |
| Code repositories | local clone (docs and source files) | `file:line` |
| PDF books and papers | file, or `arXiv:<id>` | `file:line (page N)`, outline sections |
| DOCX, EPUB, notebooks, spreadsheets, slides | file | `file:line`, sheet, slide |
| Subtitles (WebVTT, SRT) | file | `(at HH:MM:SS)` |
| YouTube videos | URL — needs `[media]` | `(at HH:MM:SS)`, chapters |
| Audio and video files | file — local speech recognition, needs `[media]` | `(at HH:MM:SS)` |
| Scanned PDFs | file — needs `[ocr]` | page, confidence |
| Courses (folder of lessons, YouTube playlist) | `--as course` — one package and one skill, lessons in order | lesson file, `(at HH:MM:SS)` |

Optional extras: `semantic` (multilingual hybrid search, recommended),
`media` (YouTube and speech recognition), `ocr` (scanned documents) and
`ragflow` (use an external [RAGFlow](https://github.com/infiniflow/ragflow)
server as the search backend).

## Use cases

Farol is for any situation where you want your AI to **know a body of text
well and prove what it says**. Each case below uses the same three steps:
`farol add`, `farol build`, `farol connect`.

| You want to… | Add | What your agent gains |
|---|---|---|
| **Code against a library or API** your model doesn't know (new, niche, internal or post-cutoff) | the docs site or `docs/` folder, the changelog | Current usage patterns and pitfalls as a skill; exact signatures, defaults and error types with `file:line` citations instead of guesses. |
| **Onboard onto a codebase** | a local clone of the repository (docs and source) | Architecture notes, conventions and "where is X defined" answers pointing at `file:line`. |
| **Learn from a book** | the PDF or EPUB | A book-to-skill distillation (mental models, decision rules, chapters) plus page-cited quotes when you need the exact wording. |
| **Keep up with research** | `arXiv:<id>` papers | Method, results and limits per paper; answers cite page and section, so claims about numbers can be checked. |
| **Use talks, courses and meetings** | YouTube links, lecture recordings, subtitles | Searchable transcripts with `(at HH:MM:SS)` citations, so you can jump to the moment something was said. |
| **Answer from internal knowledge** (runbooks, policies, specs, wikis) | local folders, DOCX, spreadsheets, slides | A private assistant that stays on your machine — no upload, no API key — and says "not in the sources" instead of inventing. |
| **Support and consulting** | product manuals, release notes, FAQs | Answers with a citation you can paste back to the customer; `farol sync` refreshes when a new version ships. |
| **Build a personal library** | everything above, across projects | `farol library` serves all your packages through **one** MCP server, each source kept separate and citable. |

When it is **not** the right tool: very small texts that fit comfortably in
the prompt (just paste them), questions that need live data or web search, and
images or equations (text only for now).

## How it works

```text
source ─► extraction ─► canonical blocks with locators ─┬─► local index (BM25 + embeddings)
                                                         │
                                                         └─► skill tasks ─► your AI ─► validated skill

farol mcp (read-only)
  ├─ list_skills / get_skill            concepts and decisions
  ├─ search_knowledge                  cited facts
  └─ get_context / get_document        the text around a fact
```

- **One source, one package, one skill** — the way a book becomes one skill.
- **The skill never invents facts**: every factual sentence must cite source
  blocks; the lineage is stored and checked.
- **Updates are safe**: `farol sync` refreshes facts without touching the skill
  and reopens only the chapters whose cited text changed.
- **Sources are data, not instructions**: text that tries to steer the AI is
  flagged or excluded ([details](SECURITY.md)).

## Quality, measured

Farol is measured on a real, licensed corpus (downloaded by hash, never shipped
with the project) with reviewed questions, including Portuguese questions about
English sources. Hybrid search, top 5:

| Source | Questions | Answer found | Citations with locator |
|---|---|---|---|
| HTTPX documentation (21 pages) | 13 | 92% | 100% |
| *Pro Git* book (~500 pages) | 13 | 92% | 100% |
| GraphRAG paper (arXiv) | 5 | 100% | 100% |
| Spoken article (audio, local speech recognition) | 3 | 100% | 100% |

Every measured source is also distilled into a skill that passes the quality
rubric with valid lineage (the book: 22 chapters). A separate validation split
of questions, never used to tune retrieval, scores 85% on the HTTPX docs.

In a [value benchmark](docs/BENCHMARK.md) with Claude Haiku, answers with Farol
were 89% correct (83% with a verifiable citation) using 1.4k prompt tokens,
versus 22% correct without context and 100% correct but uncitable and ~20× more
tokens when pasting the whole source.

Reproduce with `python scripts/acceptance_real.py --json` from a clone. On a
2-vCPU, 4 GB machine a 500-page book builds in 10 s (BM25) or 75 s (hybrid);
see [performance and scale](docs/SCALE.md).

## Commands

| Command | What it does |
|---|---|
| `farol add <source>` | Register a source in the project (`farol.json`). |
| `farol build` | Build or refresh every source and plan its skill. |
| `farol sync` | Refresh sources, report changes and stale skill chapters. |
| `farol status` | Show each source's state and the next step. |
| `farol task next` / `farol task submit` | The skill-writing loop for your AI. |
| `farol connect <agent>` | Install skills and the MCP server for your agent. |
| `farol mcp --project .` | Serve skills and evidence over MCP (stdio). |
| `farol library add` / `farol mcp --library` | One MCP server for all your projects. |
| `farol eval` | Measure how well search finds what your skills cite (self-assessment). |
| `farol doctor` | Check the installation and project; `--fix` repairs indexes. |
| `farol advanced` | Lifecycle, governance and compatibility commands. |

Every error prints what to do next; see the [error reference](docs/ERRORS.md).

## Project status

Farol 3.0 is the first release built for everyday use by anyone, with any AI
agent. Every claim above is backed by tests or by the measured acceptance
corpus, and the public CLI, MCP tools and package layout follow
[semantic versioning](docs/COMPATIBILITY.md). Known limits:

- YouTube may require browser cookies from servers or VPNs
  (`FAROL_YTDLP_COOKIES`); local subtitle and audio files always work.
- Questions phrased very differently from the source are harder to answer;
  the `semantic` extra reduces this gap.
- Images, diagrams and equations are not interpreted yet.
- One writer per project at a time; Farol is not a multi-user server.

The plan, decisions and evidence live in [specs/farol-3](specs/farol-3/README.md).

## Security, privacy and rights

- Nothing leaves your machine unless you add a URL or enable an external backend.
- You declare each source's license; Farol records it, warns about restricted
  licenses and never redistributes acquired content.
- The MCP server is read-only, and retrieved text is always marked as untrusted.

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Learn more

- [Getting started](docs/GETTING-STARTED.md) (Portuguese) — install, agents and troubleshooting
- [Connecting agents](docs/HARNESSES.md) and [architecture](docs/ARCHITECTURE.md)
- [Supported platforms and extras](docs/SUPPORT-MATRIX.json) and [release process](docs/RELEASE.md)
- [Contributing](CONTRIBUTING.md) — TDD, fixtures and checks; [community and governance](community/)

Farol is MIT licensed. Respecting the license of each source you add is up to you.
