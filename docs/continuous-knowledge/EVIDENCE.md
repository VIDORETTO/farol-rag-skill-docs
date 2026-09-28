# Evidências e limites da análise

[Índice](README.md) · [Especificação](SPEC.md)

Baseline: `566ac3b8d16e3e65785859ba46c35fe0212c87c1` em 2026-09-04.
Os caminhos abaixo são relativos a este documento; os símbolos identificam a
região observada sem depender apenas de linhas que podem mudar.

## Inventário de fatos

| ID | Fato observado | Fonte e localização |
|---|---|---|
| E01 | A interface suportada usa import da raiz, plan/preview/apply/inspect/cleanup; pipeline é compatibilidade | [PYTHON-API](../PYTHON-API.md), [exports](../../docops/__init__.py), [adapter](../../docops/pipeline.py) |
| E02 | Há staging, lease, fingerprints, checkpoints e journal; atomicidade universal de leitura direta não é prometida | [ARCHITECTURE](../ARCHITECTURE.md), [operations](../../docops/operations.py): `apply`, `_promote`, `_recover_interrupted_promotion` |
| E03 | A geração é scaffold de títulos, capítulos e proveniência; não executa LLM | [generation](../../docops/generation.py): `skill_artifacts`, `write_skill` |
| E04 | skill/router/rag/.docops não são copiados como arquivos de usuário; artefatos são gerados novamente no staging | [operations](../../docops/operations.py): `_GENERATED_ROOTS`, `_copy_preserved_user_files`, `_write_artifacts` |
| E05 | O atalho sem mudanças não é usado quando index_rag está ativo | [operations](../../docops/operations.py): `apply` |
| E06 | O estado compara origem canônica + versão e inclui hash na identidade; o conjunto desejado define remoções | [state](../../docops/state.py): `content_identity`, `StateStore.plan` |
| E07 | DOCOPS indexa staging e sync usa force=True por padrão | [operations](../../docops/operations.py): `_write_index`; [rag_sync](../../docops/rag_sync.py): `RagSynchronizer.sync` |
| E08 | O backend possui incremental; force=True encaminha reembedding forçado; a detecção de inalterado usa mtime/tamanho | [server](../../skills/vendor/knowledge-rag/mcp_server/server.py): `start_reindex_background`, `_unchanged_since_last_index` |
| E09 | Há watcher com janela de acumulação; o harness gerado o desativa | [server](../../skills/vendor/knowledge-rag/mcp_server/server.py): `DocumentWatcher`; [harness](../../docops/harness.py): `build_harness_manifest` |
| E10 | O script legado usa mutações individuais e checkpoints; o wrapper de skill chama run e validate | [update_rag](../../scripts/update_rag.py): `apply`; [update_skill](../../scripts/update_skill.ps1) |
| E11 | Enriquecimento registra skill_hash; evidência persistida de avaliação não vincula toda a composição avaliada | [readiness](../../docops/readiness.py): `_enrichment_evidence`, `assess_readiness`; [evaluator](../../docops/evaluator.py): `evaluate_package`, payload `evidence` |
| E12 | Divergência compara principalmente versão textual do manifesto e da skill | [divergence](../../docops/divergence.py): `inspect_package_divergence` |
| E13 | Casos factuais recuperam arquivo esperado; conceituais fazem busca lexical na skill; router usa regra de palavras | [evaluator](../../docops/evaluator.py): `evaluate_package`; [retrieval](../../docops/retrieval.py): `SkillRetrievalAdapter`, `route_query` |
| E14 | Golden gerado vem não revisado; avaliação exige revisão explícita | [evaluator](../../docops/evaluator.py): `generate_golden_candidates`, `_case_payload` |
| E15 | Normalização tem limites e heurísticas de injection; PDF sem texto pede OCR; DOCX extrai parágrafos | [normalizer](../../docops/normalizer.py): `SUPPORTED_SUFFIXES`, `_INJECTION_PATTERNS`, `normalize_file` |
| E16 | Há proteção SSRF, limites de crawl/redirect/payload e regras de robots | [web_acquirer](../../docops/web_acquirer.py): `NetworkPolicy`, `FetchPolicy`, `WebAcquirer.acquire` |
| E17 | compact usa modelo inglês; multilingual existe; o índice DOCOPS preenche profile compact literalmente | [config vendor](../../skills/vendor/knowledge-rag/mcp_server/config.py): `_EMBEDDING_PROFILES`; [operations](../../docops/operations.py): `_write_index` |
| E18 | Backup é removido depois de promoção bem-sucedida | [operations](../../docops/operations.py): `apply`, finalização após validação |
| E19 | Polling encerra ao ficar inativo; smoke registra ok mesmo se result_count for zero | [rag_sync](../../docops/rag_sync.py): `RagSynchronizer.sync` |
| E20 | Campos aditivos são permitidos; mudanças de significado exigem versionamento; schemas têm duas cópias | [SCHEMAS](../SCHEMAS.md), [checker](../../scripts/check_contracts.py) |
| E21 | Novos testes comportamentais devem usar raiz/CLI/artefatos/MCP | [SEAMS](../../tests/SEAMS.md), [test_public_interface](../../tests/test_public_interface.py), [test_promotion_recovery](../../tests/test_promotion_recovery.py) |
| E22 | Direitos de fontes são separados da licença do código; private-only não autoriza publicação | [PUBLISHING-POLICY](../PUBLISHING-POLICY.md) |
| E23 | O contrato de harness é hand-off relativo; não promete comportamento de qualquer modelo | [HARNESSES](../HARNESSES.md), [operator](../../skills/doc-to-rag-operator/SKILL.md) |
| E24 | Fingerprint percorre árvore ativa; .docops é raiz gerada | [operations](../../docops/operations.py): `_tree_snapshot`, `_destination_fingerprint`, `_GENERATED_ROOTS` |
| E25 | Não aceitar documentos resulta em no_accepted_documents; validação exige RAG ready | [operations](../../docops/operations.py): `_collect`; [package_validator](../../docops/package_validator.py): `validate_package` |

## Inferências relevantes

- **I01, E03–E05:** repetir o fluxo atual por agenda pode apagar enriquecimento externo.
  A análise é baseada no caminho do código; não foi criado teste novo para reproduzi-la.
- **I02, E06–E08:** diff incremental no operador não equivale a reaproveitamento do índice.
  Trocar apenas force não resolve staging novo ou caminhos persistidos no backend.
- **I03, E11–E13:** readiness e qualidade precisam de evidências da composição exata;
  recuperar um arquivo não comprova a qualidade da resposta do harness.
- **I04, E18:** recuperação de falha de promoção não equivale a rollback editorial após sucesso.
- **I05, E06/E16:** fontes múltiplas e crawls parciais precisam de contrato de conjunto
  desejado/completude antes de autorizar remoções automaticamente.
- **I06, E24:** fila dentro da árvore ativa pode ser substituída ou invalidar planos
  repetidamente; coordenador deve ter armazenamento operacional separado.

## Verificação executada na análise anterior à criação destes documentos

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_public_interface.py tests/test_public_metrics.py \
  tests/test_public_seams.py tests/test_promotion_recovery.py
```

Resultado: **15 passed in 74.22s**. Trata-se de teste existente em fixtures,
não de teste da funcionalidade proposta. Não foi executado rebuild, benchmark
completo, avaliação do Golden FastAPI ou teste real de enriquecimento.

## Referências técnicas primárias consultadas

- [SQLite WAL](https://www.sqlite.org/wal.html): restrições de filesystem/rede
  relevantes à escolha de fila local. Não justifica fila distribuída.
- [SQLite Backup API](https://www.sqlite.org/backup.html): snapshot consistente
  de SQLite. Não comprova snapshot de todos os arquivos do Chroma.
- [OWASP Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/):
  ataques por conteúdo externo e necessidade de segregação de privilégios.

A [decisão Chroma do projeto](../archive/1.x/CHROMA-RESIDUAL-DECISION.md) permanece um registro
de mitigação delimitada. Esta análise não fez auditoria nova de vulnerabilidades.
