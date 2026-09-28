# Handoff pós-release — Farol 1.1.0

Registro operacional preenchido após a publicação controlada. Não contém
credenciais, corpus adquirido, prompts ou logs privados.

> A release foi publicada antes do rebrand. Por isso, o asset da wheel e o nome
> instalado abaixo preservam o identificador técnico `consulta-documentacao`.

## Identidade da release

| Campo | Registro |
|---|---|
| versão | `1.1.0` |
| tag anotada | [`v1.1.0`](https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.1.0) |
| commit/SHA | `303e995a9cf5c939f11a368865bfb76488e9654d` |
| candidate digest | `bd64da7b769a2fd442abc28e768008fe6a8eccf8ca130906309b2291e88293a2` |
| wheel | [`consulta_documentacao-1.1.0-py3-none-any.whl`](https://github.com/VIDORETTO/agent-knowledge-kit/releases/download/v1.1.0/consulta_documentacao-1.1.0-py3-none-any.whl) |
| wheel SHA-256 | `a6656139143df70974619581129a049b06a9e4511fdb2cf00ff4fd54aa2fc5c1` |
| checksums | [`SHA256SUMS`](https://github.com/VIDORETTO/agent-knowledge-kit/releases/download/v1.1.0/SHA256SUMS) |
| SBOM | [`sbom-1.1.0.spdx.json`](https://github.com/VIDORETTO/agent-knowledge-kit/releases/download/v1.1.0/sbom-1.1.0.spdx.json) |
| provenance | [`supply-chain-1.1.0.json`](https://github.com/VIDORETTO/agent-knowledge-kit/releases/download/v1.1.0/supply-chain-1.1.0.json) |
| GitHub Release | [v1.1.0](https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.1.0), publicado `2026-09-04T20:18:45Z` |
| registry | `none` |

## Gate e canário

- [CI push 33913704577](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33913704577): matriz required completa.
- [Integration 33914255198](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33914255198): RAG/MCP, fixture MIT, Recall@5/MRR@5 `1.0/1.0`.
- [CI release verification 33914405994](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33914405994): candidato e digest no SHA exato.
- [CI acionado pela tag 33915236656](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33915236656): 13 contexts obrigatórios em `success`.
- Canário externo: Linux, Python `3.12.13`, virtualenv temporário fora do
  checkout; download público, checksum, instalação do wheel, `resolve`,
  `run`, `validate`, `evaluate` e `doctor --root` passaram.
- O Golden FastAPI privado não foi baixado nem publicado. A fixture pública
  MIT foi a base do canário e da avaliação anunciada.

## Observação

| início UTC | fim UTC | canal | estado | decisão |
|---|---|---|---|---|
| `2026-09-04T20:18:45Z` | `2026-09-05T20:18:45Z` | GitHub Release controlado | aberta | não ampliar canal |
| `2026-09-04T20:18:45Z` | `2026-09-07T20:18:45Z` | acompanhamento | agendada | revisar issues, CI e segurança |

Até o preenchimento deste registro, não há incidente crítico conhecido. O
proprietário escolheu não fazer divulgação externa em massa nesta versão.

## Risco residual e rollback

- Chroma: decisão `mitigate` registrada em
  [`CHROMA-RESIDUAL-DECISION.md`](CHROMA-RESIDUAL-DECISION.md), com quatro
  advisories explícitos e reavaliação em `2026-10-04` ou se o threat model
  mudar.
- Não mover a tag nem editar os assets publicados. Para defeito, preservar
  `v1.1.0` e publicar uma nova versão de correção.
- Para incidente de segurança, interromper divulgação e usar
  [`SECURITY.md`](../../../SECURITY.md).
