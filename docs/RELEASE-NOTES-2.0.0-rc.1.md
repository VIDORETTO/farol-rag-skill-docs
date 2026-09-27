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

Na validação local de 27 de setembro de 2026, o source limpo `8f06ee7` passou o
perfil `core`: 22/22 etapas, `1050 passed`, `12 skipped` explícitos e zero
falhas/bloqueios/not_run. O bundle candidate desse source foi verificado
independentemente, sem erros, com auditoria e supply-chain aprovadas; o
manifesto fixa source e digests. Os resultados e hashes estão em
[`specs/farol-2/state.json`](../specs/farol-2/state.json).

Book-to-skill passou 23/23 etapas e OCR passou 1/1 em execução local com PDF
sintético sem envio remoto no predecessor documental `c0859b6`. Esses perfis
são evidência suplementar e não são apresentados como executados no source
`8f06ee7`.

O perfil `core` e os perfis suplementares não constituem o gate `full`. Na
retomada de 27 de setembro, o RAGFlow local voltou a funcionar e a integração
real passou (2 testes, zero skips). A CI do PR #16 passou no commit `1afd00e`.
As melhorias de instalação e diagnóstico do TK-022 precisam dos gates do novo
candidato. A RC segue sem tag, GitHub Release ou artefatos públicos.

O [guia de instalação](GETTING-STARTED.md) cobre core, OCR, RAGFlow, credenciais
próprias, uso em agentes, problemas comuns e desinstalação. O bootstrap aceita
`--ragflow` e `--ocr`; `doctor --require-ragflow` verifica o serviço configurado.

Não há wheel, checksums ou release públicos para baixar neste momento. O
artefato local auditado não é uma distribuição pública; aguarde a publicação
autorizada e confira os digests no manifesto da release correspondente.

## Limites da prévia

Esta não é uma garantia de compatibilidade final. RAGFlow, OCR e qualquer
fonte adquirida exigem ambiente, direitos, credenciais e revisão próprios.
Transporte HTTP/SSE exige bearer token; `stdio` local é o padrão seguro.
Não distribua documentos privados, corpus adquirido, índices, modelos,
credenciais ou artefatos de execução.

Falhas de segurança devem ser reportadas pelo fluxo privado descrito em
[`SECURITY.md`](../SECURITY.md).
