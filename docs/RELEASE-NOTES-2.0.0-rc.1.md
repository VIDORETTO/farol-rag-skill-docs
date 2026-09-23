# Farol 2.0.0rc1 — release candidate

> Tag: `v2.0.0-rc.1` · pacote: `2.0.0rc1` · prévia de Farol 2.0

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
  retrieval, rebuild, rollback e cleanup verificados.
- OCR real com Docling `2.129.0`, ONNX Runtime `1.30.0` e RapidOCR no perfil
  Python 3.13.
- Proveniência de release, bundle candidate, wheel reproduzível, SBOM,
  checksums, auditoria de supply chain e clean clone multiplataforma.
- Compatibilidade do nome técnico `consulta-documentacao` e dos comandos
  `docops`; o launcher `farol` fica disponível como marca principal.

## Verificação

O candidato de implementação passou `25/25` etapas no gate full, com `1045
passed`, `12 skipped` explícitos e zero falhas, bloqueios ou etapas
`not_run`. A evidência redigida e os receipts de integração permanecem no
checkout de desenvolvimento; nenhum corpus privado, cache, token ou
credencial faz parte da release.

Antes de instalar, baixe a wheel e confirme o digest no `SHA256SUMS` da
[release no GitHub](https://github.com/VIDORETTO/farol-rag-skill-docs/releases/tag/v2.0.0-rc.1):

```text
python -m pip install ./consulta_documentacao-2.0.0rc1-py3-none-any.whl
python -m farol --help
```

## Limites da prévia

Esta não é uma garantia de compatibilidade final. RAGFlow, OCR e qualquer
fonte adquirida exigem ambiente, direitos, credenciais e revisão próprios.
Transporte HTTP/SSE exige bearer token; `stdio` local é o padrão seguro.
Não distribua documentos privados, corpus adquirido, índices, modelos,
credenciais ou artefatos de execução.

Falhas de segurança devem ser reportadas pelo fluxo privado descrito em
[`SECURITY.md`](../SECURITY.md).
