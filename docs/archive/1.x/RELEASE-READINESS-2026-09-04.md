# Registro de prontidão — 2026-09-04

**Estado:** `production-ready-publicity-ready` com observação pós-release aberta
**Escopo:** release pública `1.1.0` do produto **Farol** (distribuição técnica
legada `consulta-documentacao`)
**Canal:** somente GitHub Release; nenhum registry ou anúncio externo
**Release:** [v1.1.0](https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.1.0)
**Publicado em:** `2026-09-04T20:18:45Z`

Este registro é o handoff operacional da publicação. A tag é imutável e o
candidate usado no Release foi preservado como evidência do CI; alterações
posteriores na documentação de `main` não alteram a identidade publicada.

## Identidade imutável

| Campo | Valor | Evidência |
|---|---|---|
| versão | `1.1.0` | `pyproject.toml`, wheel e Release |
| tag anotada | `v1.1.0` | [tag pública](https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.1.0) |
| commit da tag | `303e995a9cf5c939f11a368865bfb76488e9654d` | `refs/tags/v1.1.0^{}` |
| candidate digest | `bd64da7b769a2fd442abc28e768008fe6a8eccf8ca130906309b2291e88293a2` | `candidate-manifest.json` e `candidate-identity.json` |
| wheel SHA-256 | `a6656139143df70974619581129a049b06a9e4511fdb2cf00ff4fd54aa2fc5c1` | asset público e reconstrução em clone limpo |
| Release | [GitHub Release v1.1.0](https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.1.0) | não-draft, não-prerelease |
| registry | `none` | PyPI e outros registries fora do escopo |

## Gates executados

- O commit `303e995` foi enviado para `main` com autorização explícita. O
  [CI push 33913704577](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33913704577)
  passou os 13 contexts obrigatórios: nove combinações de Python 3.11–3.13
  em Ubuntu/Windows/macOS, três clean clones e o job de wheel.
- O [Integration 33914255198](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33914255198)
  passou o perfil RAG/MCP com a fixture MIT revisada: `2` documentos, `4`
  chunks, Recall@5/MRR@5 `1.0/1.0`, smoke MCP e concorrência de reindex.
- A [verificação manual de release 33914405994](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33914405994)
  observou o digest e o commit exatos; `verify_candidate.py --release` passou.
- A execução adicional acionada pela tag, [CI 33915236656](https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33915236656),
  também terminou com os 13 contexts obrigatórios em `success`.
- A suíte local do commit publicado terminou com `234 passed`; o wheel foi
  reconstruído em clone limpo, com Python 3.12.13 e `SOURCE_DATE_EPOCH=315532800`,
  reproduzindo byte a byte o SHA público.
- O candidato baixado do CI passou `sha256sum -c SHA256SUMS`, verificação de
  supply chain e verificação independente no clone da tag. O Release publica
  wheel, manifesto, identidade, auditoria, SBOM SPDX, locks, requirements e
  `SHA256SUMS`; não publica corpus, índices, cache ou token.

## Segurança e escopo

- A decisão [Chroma residual](CHROMA-RESIDUAL-DECISION.md) foi registrada como
  `mitigate` pelo administrador autenticado `VIDORETTO`, em `2026-09-04`, para
  `chromadb==1.5.9`/`knowledge-rag==4.8.5`. O `pip-audit` cru continua
  reportando exatamente quatro advisories: `CVE-2026-45829`,
  `CVE-2026-45830`, `CVE-2026-45831` e `CVE-2026-45833`.
- A mitigação é limitada ao `PersistentClient` local e MCP `stdio`; não há
  `HttpClient`, HTTP Chroma, `trust_remote_code` nem repositório remoto de
  modelo. Reavaliar em `2026-10-04` ou antes se esse threat model mudar.
- A revisão autenticada dos settings GitHub está em
  [`community/GITHUB-SETTINGS-CHECKLIST.md`](../../../community/GITHUB-SETTINGS-CHECKLIST.md):
  branch protection, 13 required checks, CODEOWNERS, Dependabot, secret
  scanning, push protection e Actions com SHA pinning.
- O Golden FastAPI não foi fabricado nem baixado: os 14 arquivos do corpus
  privado não estão disponíveis/licenciados neste checkout. Ele está fora da
  release; o Golden público é a fixture sintética MIT revisada.

## Canário externo

Executado em `2026-09-04` fora do checkout do autor, em Linux com Python
`3.12.13`, instalando o wheel diretamente da URL pública e sem `--editable`:

1. Baixar `consulta_documentacao-1.1.0-py3-none-any.whl` e `SHA256SUMS` do
   GitHub Release; checksum passou.
2. Instalar o wheel em um virtualenv temporário sem dependências locais.
3. Rodar `resolve`, `run`, `validate` e `evaluate --adapter lexical` usando a
   fixture MIT pública copiada para uma pasta temporária.
4. Rodar `doctor --root <checkout-público> --json` contra um clone público da
   tag; o resultado foi `ok=true`.

Resultados: todos os comandos passaram; avaliação Recall@5/MRR@5 `1.0/1.0`;
`pip show` confirmou `consulta-documentacao 1.1.0` no virtualenv temporário.
O perfil RAG não é requisito da instalação core; seu fluxo real foi coberto
separadamente pelo Integration CI, com cache/modelo externo permitido.

Links públicos testados com resposta HTTP válida: Release, wheel, checksums,
README da tag, release notes da tag, `docs/USE.md` e `SECURITY.md`.

## Observação pós-release

A divulgação controlada começou no próprio GitHub Release. Nenhum canal externo
foi acionado por escolha explícita do proprietário.

| janela | início UTC | fim UTC | estado |
|---|---|---|---|
| 24h | `2026-09-04T20:18:45Z` | `2026-09-05T20:18:45Z` | aberta; requer acompanhamento |
| 72h | `2026-09-04T20:18:45Z` | `2026-09-07T20:18:45Z` | agendada; não iniciar divulgação externa |

Até a execução deste handoff não há incidente crítico conhecido. Registrar
issues, falhas de instalação ou alertas no handoff pós-release sem copiar
credenciais, corpus, prompts ou logs privados.

## Contenção e rollback

- Não mover `v1.1.0` nem substituir seus assets/checksums.
- Se surgir defeito no pacote, preservar esta release e publicar uma versão de
  correção com nova tag; não editar a evidência histórica.
- Se surgir incidente de segurança, interromper a divulgação, usar o canal
  privado descrito em `SECURITY.md` e publicar apenas a informação necessária.
- O plano e os contatos operacionais estão em
  [`PRODUCTION-PUBLICITY-PLAN.md`](PRODUCTION-PUBLICITY-PLAN.md).
