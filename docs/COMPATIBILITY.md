# Compatibility and versioning policy

Farol follows [semantic versioning](https://semver.org/) from 3.0.0 on.

## What is public

The public surface is recorded in [PUBLIC-SURFACE-3.json](PUBLIC-SURFACE-3.json)
and checked by the test suite:

- **CLI**: every command and option, and the JSON printed with `--json`
  (`farol add`, `farol build`, `farol sync`, `farol status`, `farol task`,
  `farol connect`, `farol mcp`, `farol library`, `farol doctor` and the advanced
  commands listed by `farol advanced`). The `docops` command is a permanent alias.
- **MCP tools**: tool names, parameters and search hit fields.
- **Package layout**: `manifest.json`, `harness.json`, `skill/`, `router/`,
  `rag/documents/`, `rag/local-index/ACTIVE.json` and the synthesis lineage.
- **Project file**: the keys of `farol.json` (`schema_version` 1).
- **Python API**: the names exported by `import docops`.
- **Schemas** in `schemas/`, under the expand–contract rules of
  [CONTRACT-COMPATIBILITY.md](CONTRACT-COMPATIBILITY.md).

Error codes are public too; their catalog is [ERRORS.md](ERRORS.md).

## Rules

| Change | Allowed in |
|---|---|
| Add a command, option, tool, parameter, field or error code | minor release |
| Fix behaviour that contradicts the documentation | patch release |
| Remove or rename anything public | major release, after at least one minor release with a deprecation entry and a warning |
| Change an index or embedding format | any release, only if `farol build` rebuilds it automatically |

Removing an item requires a `deprecations` entry in `PUBLIC-SURFACE-3.json`
(kind, name, replacement, release) and a warning when the item is used.

## Upgrades

- Packages built by Farol 2.0 keep working: `farol build` (or `farol index`)
  adds the local index and the synthesis plan in place.
- A `farol.json` written by a newer Farol is rejected with
  `project_version_unsupported` instead of being misread.
- Changing the embedding model requires a rebuild; Farol detects it
  (`embedding_profile_changed`).

## Supported Python

Python 3.11, 3.12 and 3.13 on Linux, macOS and Windows. A Python version leaves
support only in a major release.
