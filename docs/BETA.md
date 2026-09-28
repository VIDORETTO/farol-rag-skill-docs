# Farol 3 beta programme

The beta validates Farol with people who did not build it, before the public
announcement.

## Who

At least five testers, covering at least three AI agents (Claude Code, Codex,
Cursor, OpenCode or another MCP client) and four kinds of sources
(documentation, repository, PDF book or paper, video or audio).

## Script (one week)

1. Install following the [getting-started guide](GETTING-STARTED.md), without help.
2. Build one project from your own sources (`farol add`, `farol build`).
3. Let your agent write the skills (`farol task next` loop).
4. Connect your agent (`farol connect`) and use it for real work for a week.
5. Run `farol sync` at least once after a source changes.
6. Open a **Beta feedback** issue (GitHub → Issues → New → Beta feedback), and
   separate bug reports for anything that failed.

## What we measure

Time from installation to the first cited answer, installation and build
success without help, bugs by severity, recommendation score (0–10), and
sources or agents that did not work.

## Exit criteria (announcement gate)

- No open blocking bug.
- At least four of five testers reach a cited answer in their agent within
  ten minutes of installing (success criterion SC-101).
- Every recurring failure has a ticket with a failing test before its fix, and
  the fixes ship in a 3.0.x release that passes the release gate.

## Channels

Feedback and questions go to GitHub issues labelled `beta` and to GitHub
Discussions. Security issues follow [SECURITY.md](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/SECURITY.md).
