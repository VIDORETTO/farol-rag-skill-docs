# Farol 1.1.0 — release notes

> Esta versão é distribuída exclusivamente pelo GitHub Release. Review these
> notes against the final tag, wheel, checksums, SBOM and provenance.

## What this release is for

**Farol** turns a documentation source into an agent-usable
package containing a structured skill, a query router, a local RAG corpus and
machine-readable provenance. The core operator is usable without an LLM,
provider, hosted service or API key.

## Highlights

- Explicit `resolve`, `plan`, `run`, `validate` and `evaluate` flows with
  relative paths, terminal outcomes and resumable checkpoints.
- Optional local `knowledge-rag`/MCP indexing with redacted diagnostics,
  factual-query evaluation and source-aware result handling.
- Candidate identity, release audit, wheel verification, SBOM, checksums and
  vendor/model provenance suitable for an independently reviewed release.
- Cross-platform bootstrap and support evidence for Python 3.11–3.13 on
  Ubuntu, Windows and macOS; Python 3.14 remains tolerated only.
- No acquired corpus, index, model cache, token, user log or private path is
  part of this release.

## Installation after publication

This version is distributed only through its GitHub Release. After the release
is public, download the exact wheel asset and verify its checksum before use:

```text
python -m pip install ./consulta_documentacao-1.1.0-py3-none-any.whl
python -m docops run <fonte> --output ./artifacts/<slug> --license <id>
python -m docops validate ./artifacts/<slug> --json
```

The wheel filename and the `docops` module name are legacy technical
identifiers retained for compatibility with this published release.

`doctor` verifica um checkout de projeto (metadata, lock e skill do operador),
não uma pasta que contenha somente o wheel. Para diagnosticar um checkout
público, use `python -m docops doctor --root <checkout> --json`.

The RAG profile is optional and must be installed only when the selected
channel, recorded dependency decision and local threat model have been
reviewed.

## Minimal flow

```text
python -m docops resolve ./documents/fixtures/acme-docs --json
python -m docops run ./documents/fixtures/acme-docs --output ./artifacts/acme --slug acme --license MIT
python -m docops validate ./artifacts/acme --json
```

## Limits and security

This package does not execute a model, choose a provider, host an HTTP service
or guarantee compatibility with every agent harness. Acquired documentation
may be copyrighted and requires an explicit license/redistribution decision.
The optional RAG dependency currently has four documented ChromaDB advisories;
the raw audit remains visible and the recorded scope-limited decision is in
[`CHROMA-RESIDUAL-DECISION.md`](CHROMA-RESIDUAL-DECISION.md). Report security
issues privately according to [`SECURITY.md`](../../../SECURITY.md).

## Support

The normative support matrix is
[`SUPPORT-MATRIX.json`](../../SUPPORT-MATRIX.json). Public claims must be limited to
the platforms, Python versions and profiles verified by the release and its
canary.
