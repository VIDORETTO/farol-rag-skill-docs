<!-- docs-gate: proposal -->

# Estratégia TDD: Farol 3.1

**Consome:** [spec.md](spec.md) e [plan.md](plan.md) revisão 1.

## Princípios

1. **RED observado antes do GREEN.** Cada passo `N.x RED` do ticket vira um
   teste que falha pelo motivo certo no baseline `6ee4ffe` (registrar comando e
   saída curta em `evidence/TK-2xx.md`). Teste que passa no baseline não é RED:
   reescreva-o ou documente que o comportamento já existia.
2. **Só seams públicos** (`tests/SEAMS.md`): CLI em subprocesso, `import docops`,
   JSON-RPC do `farol mcp`, artefatos JSON do pacote. Seams S10–S12 permitem
   injeção de falsos apenas onde há dependência pesada (modelo, rede, Docling).
3. **Anti-tautologia:** valores esperados vêm da fixture escrita à mão ou do
   golden revisado; nunca do mesmo código sob teste.
4. **Sem rede e sem modelos na suíte padrão.** Modelos reais, YouTube, Docling e
   ffmpeg só em perfis opt-in (`@pytest.mark.integration` ou scripts), que
   retornam `blocked`/`not_run` quando a dependência falta.
5. **Uma fatia vertical por teste**: do comando público ao artefato/saída.
6. **Não commitar RED em `main`.** O RED vive na branch do ticket até o GREEN
   do mesmo ticket; a CI de `main` nunca fica vermelha por teste planejado.

## Catálogo de fixtures novas

Todas geradas em `tmp_path` por helpers em `tests/fixtures_31.py` (novo, sem
corpus versionado; respeita o invariante de não versionar `documents/` reais).

| ID | Fixture | Conteúdo | Usada por |
|---|---|---|---|
| F1 | `two_package_library` | Projeto `redes` com 6 parágrafos sobre “timeout do pool de conexões”; projeto `culinaria` com 6 parágrafos sobre receitas e **uma** menção a “timeout do forno”. Registrados com `farol library add` sob `FAROL_HOME` temporário. | TK-203, TK-204 |
| F2 | `long_section_book` | Markdown com 1 título, 3 capítulos `#` e 4 seções `##` cada; seção 2.3 com 40 parágrafos numerados (`Parágrafo 2.3.N: …`) para testar vizinhança. | TK-202, TK-207 |
| F3 | `native_outline_book` | Markdown com 3 capítulos nativos de ~10k tokens (gerados por repetição controlada) e um PDF pequeno com outline (reusar o gerador de `tests/test_paper_structure.py`). | TK-207 |
| F4 | `course_folder` | `Aula 1 - Introdução.vtt`, `Aula 2 - Variáveis.vtt`, `Aula 10 - Projeto final.vtt`, `material/slides.md`; legendas curtas com frases únicas por aula (`Na aula dez construímos o projeto final.`). Sem ASR. | TK-210, TK-211 |
| F5 | `fake_playlist_client` | Cliente com 3 entradas (`id`, `title`, `license`, `playlist_index`, legendas VTT) e uma variante em que o 2º vídeo tem licença padrão do YouTube. | TK-210 |
| F6 | `KeywordRanker` | Ranker falso determinístico: score = nº de tokens da consulta presentes no texto ÷ tamanho; permite prever a ordem. | TK-203, TK-204, TK-214 |
| F7 | `ConceptEmbedder` | Reusar o falso de `tests/test_semantic_backend.py`, estendido com `query_prefix`/`passage_prefix` gravados no perfil. | TK-205 |
| F8 | `FakeLayoutConverter` | Devolve itens Docling-like: heading, parágrafo, tabela (3×3) com `page_no`. | TK-212 |
| F9 | `fake_frames` | Lista `(segundo, texto_ocr)` simulando quadros-chave; dispensa ffmpeg. | TK-213 |
| F10 | `distilled_package` | Pacote da F2 com skill destilada por respostas fixas escritas à mão (capítulos com `[bN]` conhecidos), produzidas pelo protocolo público. | TK-214, TK-215 |

## Mapa teste → ticket

Nomes propostos; o executor pode ajustar a redação, não o comportamento.

### TK-201 — régua (`tests/test_acceptance_real.py`)

- `test_report_includes_mrr_context_tokens_and_library_metrics`
- `test_validation_split_and_portuguese_cases_are_reported_separately`
- `test_missing_course_source_is_not_run_not_success`

### TK-202 — contexto (`tests/test_mcp_server.py`, `tests/test_local_fts_backend.py`)

- `test_search_hits_expose_block_id`
- `test_get_context_returns_neighbours_in_order_with_citations` (F2: hit no `Parágrafo 2.3.20` → `before=2, after=2` devolve 18–22)
- `test_get_context_section_scope_respects_max_tokens_and_reports_truncation`
- `test_get_context_never_returns_high_risk_blocks`
- `test_get_document_paginates_and_keeps_the_unpaged_default`
- `test_unknown_block_id_is_a_typed_error` (`block_unknown`)

### TK-203 — biblioteca (`tests/test_library.py`)

- `test_library_ranks_hits_by_package_independent_score` (F1: top 5 de “timeout do pool de conexões” só de `redes`)
- `test_single_package_ordering_is_unchanged_without_a_ranker`
- `test_ranker_failure_degrades_to_previous_order_and_is_reported`

### TK-204 — reranker (`tests/test_rerank.py`, novo)

- `test_reranker_reorders_the_pool_and_reports_retrieval_mode` (F6; `metadata.retrieval_mode == "hybrid+rerank"`)
- `test_reranker_is_opt_in_and_absent_extra_is_declared_degraded`
- `test_reranker_never_admits_ineligible_or_high_risk_blocks`
- Perfil opt-in `scripts/benchmark_rerank.py --json` (integração; `not_run` sem modelo)

### TK-205 — embedding (`tests/test_semantic_backend.py`, `tests/test_journey.py`)

- `test_embedding_profile_records_query_and_passage_prefixes`
- `test_build_rebuilds_the_index_when_the_embedding_model_changes`
- `test_doctor_fix_rebuilds_an_index_with_a_stale_embedding_profile`
- Perfil opt-in `scripts/benchmark_embeddings.py --json`

### TK-206 — claim/lease (`tests/test_agent_tasks.py`)

- `test_claim_returns_up_to_n_independent_tasks_with_leases`
- `test_two_claimers_never_receive_the_same_task_while_the_lease_is_valid` (dois subprocessos)
- `test_expired_lease_returns_the_task_to_the_pool`
- `test_concurrent_submits_keep_every_accepted_task_in_the_plan` (subprocessos em paralelo; nenhum `accepted` perdido)
- `test_core_task_is_not_claimable_until_chapters_are_accepted`

### TK-207 — orçamento e sumário (`tests/test_agent_tasks.py`)

- `test_task_tokens_option_sets_the_chapter_budget`
- `test_native_chapters_within_bounds_become_skill_chapters_in_heuristic_mode` (F3: 3 capítulos com `--task-tokens 12000`)
- `test_outline_task_receives_the_native_table_of_contents`
- `test_oversized_native_chapter_is_split_along_its_sections`

### TK-208 — `farol-distill` (`tests/test_connect.py`)

- `test_connect_installs_the_distill_skill_idempotently_and_removes_it`
- `test_distill_skill_mentions_only_existing_commands` (via `scripts/check_documentation.py`)

### TK-209 — router (`tests/test_connect.py`, `tests/test_package_contract.py`)

- `test_generated_router_is_small_and_backend_neutral` (≤ 350 tokens por `len//4`; sem “RAGFlow”, “lifecycle”, “generation”)
- `test_connect_installs_one_project_router_instead_of_one_per_source`
- `test_build_upgrades_a_3_0_router_and_keeps_revisions_consistent`

### TK-210 — curso (`tests/test_course.py`, novo)

- `test_course_folder_becomes_one_package_with_modules_in_natural_order` (F4: ordem 1, 2, 10)
- `test_course_citations_name_the_lesson_and_timestamp`
- `test_playlist_course_keeps_playlist_order_and_per_video_licenses` (F5)
- `test_non_redistributable_member_blocks_course_redistribution` (F5 variante)
- `test_course_outline_task_lists_modules_in_order`
- `test_course_requires_a_declared_license_for_local_folders` (`license_required`)

### TK-211 — skill composta (`tests/test_composite_skill.py`, novo)

- `test_compose_plans_tasks_citing_blocks_from_every_member`
- `test_composite_lineage_qualifies_blocks_by_package`
- `test_member_change_marks_composite_chapters_stale`
- `test_no_skill_member_keeps_its_index_but_skips_synthesis`
- `test_mcp_lists_the_composite_skill_and_searches_its_members`

### TK-212 — layout (`tests/test_pdf_extractor.py`)

- `test_layout_converter_emits_headings_tables_and_pages` (F8)
- `test_without_the_layout_extra_pdf_stays_text_fallback_and_says_so`
- `test_table_blocks_are_indexed_and_cited_by_page`

### TK-213 — slides (`tests/test_transcripts.py`)

- `test_slide_text_becomes_timestamped_slide_blocks` (F9)
- `test_slides_without_ffmpeg_is_a_typed_error` (`ffmpeg_missing`)

### TK-214 — camada de síntese (`tests/test_mcp_server.py`)

- `test_synthesis_layer_returns_claims_with_supporting_citations` (F10)
- `test_default_layer_is_evidence_only`
- `test_synthesis_index_follows_a_new_skill_installation`
- `test_stale_claims_are_flagged_in_synthesis_hits`

### TK-215 — eval (`tests/test_eval.py`, novo)

- `test_eval_measures_recall_from_lineage_and_labels_it_self_assessment` (F10)
- `test_eval_uses_agent_written_questions_when_present`
- `test_eval_without_a_distilled_skill_is_not_run`

### TK-216 — higiene (`tests/test_reference_docs.py`, `tests/test_contract_doc_drift.py`)

- `test_reachability_report_lists_modules_unused_by_the_journey`
- Gate existente: `python scripts/check_documentation.py` sem `broken_local_link` após mover arquivos.

## Comandos de verificação

```text
python -m pytest tests/test_<alvo>.py -q          # RED/GREEN do ticket
python -m ruff check docops tests scripts
python scripts/check_documentation.py
python -m pytest tests/test_public_contract_v3.py -q   # superfície pública
python -m pytest -q                                # suíte ampla, uma vez por ticket
python scripts/acceptance_real.py --json           # tickets de qualidade (S6)
```

## Ordem RED/GREEN por onda

| Onda | Primeiro RED | Por quê |
|---|---|---|
| A | TK-201 `test_report_includes_mrr_context_tokens_and_library_metrics` | Sem régua não há como provar ganho |
| A | TK-202 `test_search_hits_expose_block_id` | Pré-requisito de `get_context`, TK-214 e TK-215 |
| B | TK-203 `test_library_ranks_hits_by_package_independent_score` | Introduz S10, reusado pelo reranker |
| C | TK-206 `test_concurrent_submits_keep_every_accepted_task_in_the_plan` | Corrige o risco antes de incentivar paralelismo |
| D | TK-210 `test_course_folder_becomes_one_package_with_modules_in_natural_order` | Maior valor de alcance |
| E | TK-214 `test_synthesis_layer_returns_claims_with_supporting_citations` | Base do eval |
