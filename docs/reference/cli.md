# CLI reference

Generated from the code by `python scripts/gen_reference.py`. `docops` is an alias of `farol`;
run `farol advanced` for lifecycle and compatibility commands.

## farol add

add a source: folder, file, URL or Git repository

| Argument | Description |
|---|---|
| `<source>` | folder, file, URL, Git repository, arXiv:<id> or YouTube link |
| `--license` | license of the source, e.g. MIT or CC-BY-4.0 |
| `--name` | short id for the source (default: derived from the source) |
| `--redistribution` | how derived content may be shared (one of: private-only, internal, public) |
| `--as` | treat a folder of lessons or a YouTube playlist as one course (one package, one skill) (one of: course) |
| `--max-items` | playlist courses: at most this many videos (default 200) |
| `--project` | project directory (default: current directory) |
| `--json` | print machine-readable JSON |

## farol build

build or refresh every source: facts, index and synthesis tasks

| Argument | Description |
|---|---|
| `<sources>` | only these source ids |
| `--project` | project directory (default: current directory) |
| `--json` | print machine-readable JSON |

## farol sync

refresh sources, report changes and stale skill chapters

| Argument | Description |
|---|---|
| `<sources>` | only these source ids |
| `--project` | project directory (default: current directory) |
| `--schedule` | print a daily schedule (one of: cron, systemd, windows) |
| `--json` | print machine-readable JSON |

## farol status

show each source's state and the next step

| Argument | Description |
|---|---|
| `--project` | project directory (default: current directory) |
| `--json` | print machine-readable JSON |

## farol task



### farol task plan

| Argument | Description |
|---|---|
| `--language` | language of the generated skills, e.g. en or pt-BR |
| `--outline` | who plans the chapters (default: auto) (one of: agent, heuristic) |
| `--refresh` | reopen only chapters made stale by source changes |
| `--questions` | also ask the agent for N evaluation questions per chapter |
| `--task-tokens` | source tokens per chapter task (2000-48000; raise it for long-context models) |
| `--package` | package, or a project directory |
| `--source` | inside a project: the source id to work on |
| `--json` | print machine-readable JSON |

### farol task next

| Argument | Description |
|---|---|
| `--package` | package, or a project directory |
| `--source` | inside a project: the source id to work on |
| `--json` | print machine-readable JSON |

### farol task submit

| Argument | Description |
|---|---|
| `<task_id>` | task id shown by farol task next |
| `<output_dir>` | directory with the answer files |
| `--lease` | lease id from `farol task claim` (optional) |
| `--package` | package, or a project directory |
| `--source` | inside a project: the source id to work on |
| `--json` | print machine-readable JSON |

### farol task claim

| Argument | Description |
|---|---|
| `--n` | how many tasks to reserve |
| `--ttl` | lease lifetime in seconds |
| `--agent` | name of the claiming agent, shown in task status |
| `--package` | package, or a project directory |
| `--source` | inside a project: the source id to work on |
| `--json` | print machine-readable JSON |

### farol task status

| Argument | Description |
|---|---|
| `--package` | package, or a project directory |
| `--source` | inside a project: the source id to work on |
| `--json` | print machine-readable JSON |

## farol connect

connect your AI agent: skills + MCP server

| Argument | Description |
|---|---|
| `<harness>` | the AI agent to configure (one of: claude-code, codex, cursor, opencode, generic) |
| `--project` | project directory (default: current directory) |
| `--target` | repository/workspace to configure (default: project) |
| `--scope` |  (one of: project, user) |
| `--dry-run` | show the changes without writing |
| `--remove` | undo a previous connect |
| `--json` | print machine-readable JSON |

## farol mcp

serve your knowledge to an AI agent over MCP (stdio, read-only)

| Argument | Description |
|---|---|
| `--package` | serve a single package |
| `--project` | serve every package of a project (default: current dir) |
| `--library` | serve every project in your library |

## farol doctor

diagnose an installation or checkout

| Argument | Description |
|---|---|
| `--root` | directory to inspect (default: current directory) |
| `--json` | emit JSON |
| `--probe-ragflow` | check the configured RAGFlow connection |
| `--require-ragflow` | require a healthy RAGFlow connection (also probes) |
| `--fix` | apply safe local repairs (e.g. rebuild a damaged index) |

## farol advanced

list advanced and compatibility commands
