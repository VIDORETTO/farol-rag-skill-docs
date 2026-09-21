# Pesquisa técnica — backend e síntese

**Data da verificação:** 2026-09-11
**Escopo:** fontes oficiais e snapshot vendorizado; claims promocionais não são
tratados como evidência de qualidade.

## Estado observado do Farol

- `pyproject.toml` fixa `knowledge-rag==4.8.5` como extra opcional.
- `docops/rag_sync.py::RagSynchronizer`, `docops/retrieval.py::McpRetrievalAdapter`,
  `docops/runtime.py` e `docops/harness.py` conhecem diretamente o backend.
- `docops/normalizer.py::SUPPORTED_SUFFIXES` aceita 25 sufixos; parte cai em
  leitura UTF-8 genérica. PDF sem texto retorna `ocr_required`.
- `docops/generation.py::skill_artifacts` produz scaffold e declara o
  enriquecimento externo por `book-to-skill`.
- `docops/master.py` concentra lifecycle genérico e contratos editoriais que
  serão removidos em 2.0.

## RAGFlow escolhido

A release oficial observada é
[`v0.27.2`](https://github.com/infiniflow/ragflow/releases/tag/v0.27.2), Apache-2.0.
O [README oficial](https://github.com/infiniflow/ragflow) descreve OCR/layout,
parsing de formatos heterogêneos, chunking configurável, retrieval híbrido,
reranking e citações. O [DeepDoc](https://github.com/infiniflow/ragflow/tree/main/deepdoc)
expõe OCR, reconhecimento de layout e estrutura de tabelas.

A [referência Python v0.27.2](https://github.com/infiniflow/ragflow-docs/blob/main/website/versioned_docs/version-v0.27.2/references/python_api_reference.md)
documenta criação/listagem/atualização/remoção de datasets, upload/listagem/
remoção de documentos, parsing assíncrono/com espera, chunks e retrieval. A
implementação deve fixar imagem/SDK por digest e provar essas operações em
contract test; documentação não substitui execução.

Custos observados no README: Docker, pelo menos 4 cores, 16 GiB de RAM e 50 GiB
de disco para self-hosting; imagens prontas x86. Portanto RAGFlow não pode ser
dependência em processo do core nem pressuposto silencioso do perfil leve.

## knowledge-rag legado

O snapshot local `skills/vendor/knowledge-rag/PROVENANCE.json` fixa upstream
`lyonzin/knowledge-rag`, `v4.8.5`, commit
`f531148b0d5fe479e7f0a104daf21d8fde7d3189`, licença MIT e um patch downstream.
Ele fornece MCP stdio, híbrido local, reranker e operação simples. Continua útil
como oráculo de regressão durante a migração, não como backend final.

## book-to-skill

O projeto oficial observado é
[`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill), MIT.
Seu README descreve extractor determinístico e gerador executado pelo agente,
`SKILL.md` compacto, capítulos sob demanda, glossário, patterns, cheatsheet e
fold-in. A integração Farol não depende de sua estrutura interna: ela usa um
request/receipt versionado e valida a saída contra taxonomia, budget e lineage.

## Conclusão

RAGFlow é o melhor encaixe para a fidelidade escolhida, desde que a integração
não transforme seu estado em autoridade nem descarte os originais antes do
parsing. O caminho é strangler: interface neutra, adapter legado caracterizado,
adapter RAGFlow, comparação controlada, promoção e remoção do legado.
