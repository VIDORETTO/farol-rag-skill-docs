# Farol 2.0.0rc1 — candidata local, ainda não publicada

> Versão-alvo: `v2.0.0-rc.1` · pacote: `2.0.0rc1` · sem tag ou GitHub Release

## Objetivo

Esta release candidate consolida a migração de Farol 1.x para uma arquitetura
de conhecimento para agentes com IR canônica, skills, roteador global e
RAGFlow externo opcional. Ela é destinada a validação de integração antes de
uma eventual release estável 2.0.0.

## Destaques

- IR canônica, locators estáveis, extractors governados e proveniência de
  lineage para fatos e skills derivados.
- Taxonomia aprovada, síntese multi-skill e roteamento global com budgets e
  falhas fail-closed.
- RAGFlow `0.27.2` externo, opt-in e autenticado, com lifecycle, mapping,
  retrieval, rebuild, rollback e cleanup implementados; a validação real do
  serviço segue como gate externo.
- OCR real com Docling `2.129.0`, ONNX Runtime `1.30.0` e RapidOCR no perfil
  Python 3.13.
- Proveniência de release, bundle candidate, wheel reproduzível, SBOM,
  checksums, auditoria de supply chain e clean clone multiplataforma.
- Compatibilidade do nome técnico `consulta-documentacao` e dos comandos
  `docops`; o launcher `farol` fica disponível como marca principal.

## Verificação e distribuição

O gate full `25/25` foi executado no commit de implementação
`93bb8894d816aad3c3b3682ccec317db1da39d45`; esse resultado não é evidência do
commit de preparação da RC nem desta árvore de trabalho. O estado atual dos
gates e das limitações está em [`specs/farol-2/state.json`](../specs/farol-2/state.json).

O perfil `core` da árvore local baseada em `be40e16f09153cfc12e3ea389302793f920c40b2`
passou em 25 de setembro de 2026 UTC: 22/22 etapas, `1050 passed`, `12 skipped`
e zero falhas/bloqueios/not_run. A árvore tinha 33 entradas alteradas quando o
gate capturou sua identidade; esse resultado não é full gate e não valida
RAGFlow. A RC segue sem publicação autorizada.

Não há wheel, checksums ou release para baixar neste momento. Não instale um
nome de artefato presumido; aguarde a publicação autorizada e confira os
digests na release correspondente.

## Limites da prévia

Esta não é uma garantia de compatibilidade final. RAGFlow, OCR e qualquer
fonte adquirida exigem ambiente, direitos, credenciais e revisão próprios.
Transporte HTTP/SSE exige bearer token; `stdio` local é o padrão seguro.
Não distribua documentos privados, corpus adquirido, índices, modelos,
credenciais ou artefatos de execução.

Falhas de segurança devem ser reportadas pelo fluxo privado descrito em
[`SECURITY.md`](../SECURITY.md).
