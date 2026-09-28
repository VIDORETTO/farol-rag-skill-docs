# Farol

![Farol logo](farol-logo.png){ width="360" }

**Turn documentation, books, papers, videos and repositories into knowledge
your AI can use — with citations.**

For every source you add, Farol gives your AI agent:

- **a skill** — mental models, decision rules and pitfalls, written by your own
  AI task by task and validated by Farol (every fact must cite the source);
- **cited evidence** — a local search index that returns the original text with
  `file:line`, page or video timestamp.

Both are served over **MCP** to Claude Code, Codex, Cursor, OpenCode or any MCP
client. Everything runs locally: no API key, no server, no Docker.

```bash
pipx install "farol-kit[semantic] @ git+https://github.com/VIDORETTO/farol-rag-skill-docs"
mkdir my-knowledge && cd my-knowledge
farol add ./path/to/docs --license MIT
farol build
farol connect claude-code --target ~/my-repo
```

Then ask your agent to run `farol task next` and submit each task until none
are left.

## Where to go next

- [Getting started](GETTING-STARTED.md) — install, sources, agents, troubleshooting (Portuguese)
- [Recipes](EXAMPLES.md) — documentation site, book, paper, video, audio
- [Connecting agents](HARNESSES.md) and the [MCP tools](reference/mcp.md)
- [CLI reference](reference/cli.md) and [error reference](ERRORS.md)
- [Performance](SCALE.md), [compatibility](COMPATIBILITY.md) and [architecture](ARCHITECTURE.md)
