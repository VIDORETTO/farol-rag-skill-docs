# Aceitação por ticket

Para o esforço Farol 2.0, a fonte canônica da aceitação é a matriz derivada em
[`specs/farol-2/acceptance-matrix.md`](../specs/farol-2/acceptance-matrix.md),
atualizada por `scripts/check_acceptance_matrix.py`. Em 20 de setembro de 2026,
os 33 critérios (`AC-001..AC-033`) estavam `verified`.

Este arquivo preserva abaixo o registro histórico da aceitação 1.x e seus
comandos de regressão. Ele não substitui a matriz 2.0 nem autoriza publicação.

| Ticket/gate | Evidência executável |
|---|---|
| DOCOPS-001 | `bootstrap.py`, `docops doctor`, `verify_clean_clone.py`, CI Windows/Ubuntu/macOS |
| DOCOPS-002 | `run_pipeline` + `validate_package`, `tests/test_pipeline.py` |
| DOCOPS-003/004 | `WebAcquirer`, fixtures HTTP, sitemap/robots, SSRF e limites em `tests/test_web_acquirer.py` |
| DOCOPS-005/006 | `RepositoryAcquirer` e `SourceResolver`, testes de tag/árvore/catálogo |
| DOCOPS-007 | `StateStore`, `CheckpointStore`, escritas atômicas e teste de repetição |
| DOCOPS-008 | `evaluate_package`, Golden revisado obrigatório e métricas dinâmicas `Recall@k`/`MRR@k` |
| DOCOPS-009 | `config-audit`, `release_audit`, prompt-injection/SSRF/OCR/auth tests |
| DOCOPS-010 | workflows CI/integration, schemas, tutorial sintético e checklist de release |

## Registro histórico Farol 1.x — comandos locais

```text
python -m pytest -q
python -m ruff check docops tests scripts
python scripts/audit_release.py --tracked-only --json
python scripts/verify_clean_clone.py
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict
```

O último comando cria um diretório temporário fora do checkout, copia somente o
material distribuível e roda doctor, auditoria e testes. Use `--keep` para
inspecionar o clone temporário. A auditoria `--tracked-only` é a forma correta
de auditar o conteúdo publicável enquanto caches e ambientes locais existem no
checkout de trabalho.

## Registro histórico Farol 1.x — integração opcional

Com um ambiente Python 3.13 instalado com `.[dev,formats,ragflow,ocr]`, a
execução de release também deve passar pelo servidor real, pelo perfil de
integração RAGFlow, pelo perfil de lifecycle/recovery e pelo fluxo sintético
`docops run` → `validate` → `evaluate`. Uma execução com rede/configuração de
produção deve também passar `config-audit`; nenhuma etapa publica ou faz
commit automaticamente.

## Harnesses

OpenCode 1.18.25 e Codex CLI 0.151.0 foram exercitados em sessões somente
leitura no host Windows e validaram versão 1.0.0, comando `python -m
mcp_server.server`, transporte `stdio` e o manifesto contra o schema. Claude
Code não está instalado e não é anunciado pela release. Detalhes e limitações
estão em [HARNESSES.md](HARNESSES.md).

Os números e hashes da execução final — incluindo a quantidade exata de testes,
o resultado do CI público, a tag e a release — ficam registrados em
`tasks/todo.md`, que é a checklist operacional da publicação.

## SPEC-002 pós-1.0

O seam normativo da iniciativa é `plan(request)`, `apply(plan)` e
`inspect(package)`. `plan` não escreve no destino; `apply` usa staging no
mesmo volume, valida os contratos e promove uma geração completa. Falhas
preservam a geração ativa e registram uma tentativa redigida.

Os gates executáveis adicionais são:

```text
python scripts/check_support_matrix.py --json
python scripts/check_contracts.py --json
python scripts/verify_wheel.py
python -m docops run documents/fixtures/acme-docs --output artifacts/acme --slug acme --license MIT --index-rag
python -m docops validate artifacts/acme --json
python -m docops evaluate --package artifacts/acme --cases golden-set/test-cases-fixture.json --adapter mcp --runtime-root . --json
```

O adapter lexical é diagnóstico; o gate de qualidade híbrida usa MCP real. A
matriz de suporte publicada, incluindo versões toleradas apenas localmente,
está em `docs/SUPPORT-MATRIX.json`. Esta documentação não autoriza commit,
push, tag ou release automático.

O gate `verify_wheel.py` mantém o operador instalado em alvo temporário e
exercita o perfil MCP do wheel quando o runtime RAG revisado está disponível.
No CI, `DOCOPS_REQUIRE_WHEEL_RAG=1` torna essa parte obrigatória.
