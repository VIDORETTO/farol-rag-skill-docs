# FRAMEWORK-TARGET — piloto FastAPI e contrato genérico

Este arquivo mantém a decisão histórica do piloto FastAPI. O produto não fica
preso a esse framework: uma execução de `docops` registra a fonte, versão,
idioma, licença e escopo no próprio `manifest.json`.

| Campo | Valor |
|---|---|
| Framework/pipeline do piloto | FastAPI — documentação pública MIT |
| Slug do piloto | `fastapi` |
| Corpus derivado | `documents/fastapi-docs/` (privado/ignorado) |
| Transporte padrão | MCP stdio local |
| Estado do produto | protocolo Farol 2.0 implementado; release candidate `v2.0.0-rc.1` no GitHub, com FastAPI preservado apenas como piloto histórico |

## Decisões preservadas

- O operador aceita nome, URL, URL de repositório, pasta ou arquivo.
- Nomes usam candidatos oficiais com confiança/evidência; empates pedem
  decisão explícita.
- Fontes web são limitadas por páginas, profundidade, host, tipo, tamanho,
  timeout e retries; sitemap e fallback interno são adaptativos.
- Repositórios registram commit, tag/versão, árvore de documentação e licença
  declarada.
- Markdown/HTML/JSON/YAML/OpenAPI, PDF textual e DOCX são normalizados; OCR,
  browser e autenticação retornam ação necessária quando não estão disponíveis.
- A skill é conceitual; o router encaminha fatos literais ao
  `search_knowledge` e exige citação `path#secao`/`path:linha`.
- Perfil de embedding é por corpus. Alterá-lo exige
  `reindex_documents(full_rebuild=True)`.

## Evidência do piloto legado

O snapshot FastAPI anterior foi indexado localmente com 160 fontes lógicas e
Golden de Recall@5 1,0/MRR@5 0,8595. Esses números pertencem ao corpus privado
do piloto e não são uma promessa para outras fontes; cada corpus precisa de um
Golden revisado próprio.

## Fonte de verdade operacional

Use [ROADMAP-GITHUB-PRODUTO.md](ROADMAP-GITHUB-PRODUTO.md) para a ordem dos
tickets, [ARCHITECTURE.md](ARCHITECTURE.md) para o contrato de artefatos e
[PUBLISHING-POLICY.md](PUBLISHING-POLICY.md) para licença e dados.
