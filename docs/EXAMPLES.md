# Recipes

Each recipe is runnable with the synthetic fixtures in this repository
(`python scripts/run_examples.py --json` runs them all, offline) and works the
same way with your own sources.

## Documentation folder

```bash
farol add documents/fixtures/acme-docs --license MIT
farol build
farol task next
```

## Book or paper (PDF)

```bash
farol add ./book.pdf --license CC-BY-4.0
farol add arXiv:2404.16130v2
farol build
```

PDF outlines become chapters' sections and every hit cites its page. For
arXiv papers the declared license is detected automatically.

## Video or lecture with subtitles

```bash
farol add ./lecture.vtt --license CC-BY-4.0
farol build
```

Evidence cites the moment in the video, e.g. `(at 00:01:02)`. With the `media`
extra, `farol add` also accepts YouTube links and audio or video files, which
are transcribed locally.

## Several sources, one agent

```bash
farol add ./api-docs --license MIT
farol add ./team-handbook --license MIT
farol build
farol connect codex --target ~/my-repo
```

Every source becomes its own skill; `search_knowledge` searches all of them and
tells you which package each hit came from.

## One server for all your projects

```bash
farol library add ~/knowledge/work
farol library add ~/knowledge/studies
farol mcp --library
```
