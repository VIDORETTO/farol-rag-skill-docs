# Performance and scale (measured)

Measured on 2026-09-28 on a shared VPS: 2 vCPU, 3.8 GiB RAM, Linux, Python
3.13.13, Farol at the Farol 3.0 development branch. Numbers are wall-clock
time and peak resident memory of the whole command (`/usr/bin/time`). They are
a floor for small machines, not a promise for every corpus.

## Build (`farol build`)

| Source | Size | Search | Cold build | Peak memory |
|---|---|---|---|---|
| *Pro Git* book (PDF) | 500 pages, 18 MB, ~1.9k blocks | BM25 only (no extra) | 9.7 s | 0.12 GB |
| *Pro Git* book (PDF) | same | hybrid (`semantic` extra) | 75 s | 0.97 GB |
| HTTPX documentation | 21 Markdown pages, ~890 blocks | hybrid | ~25 s (acceptance run, four sources) | 1.2 GB |
| Spoken article (MP3) | 1.8 MB, ~2 min | local ASR (`media` extra, `base` model) | 18.7 s | 0.6 GB |

The first hybrid build downloads the embedding model (~220 MB) once to
`~/.cache/farol/models`.

## Updates (`farol sync`)

| Situation | Time | Peak memory |
|---|---|---|
| *Pro Git*, nothing changed | 11 s | 0.75 GB |

Vectors are cached per model in `~/.cache/farol/vectors`, so only text that
changed is embedded again.

## Queries (`farol mcp`)

| Situation | Time | Peak memory |
|---|---|---|
| First hybrid query (loads the model) | 1.9 s | 0.68 GB |
| Later queries | interactive (index in memory, brute-force cosine) | — |

## Limits and guidance

- Machines with 2 GB of RAM or less: skip the `semantic` extra (BM25 only).
- Very large corpora (tens of thousands of pages) have not been measured yet;
  split them into several sources so each builds and syncs independently.
- Speech recognition time grows with audio length; the `base` model runs near
  real time on 2 CPU cores. Set `FAROL_ASR_MODEL=tiny` for speed or `small` for
  accuracy.

Reproduce: `python scripts/acceptance_real.py --json` and the commands above.
