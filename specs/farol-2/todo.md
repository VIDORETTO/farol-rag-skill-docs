# Todo Farol 2.0

View derivada dos tickets. Atualize estado e tarefas no ticket canônico, depois
regenere esta projeção.

## Estado de entrega

- [x] [TK-001](tickets/TK-001.md) — API/parsing/locators RAGFlow v0.27.2, adapter real e cleanup comprovados.
- [x] [TK-002](tickets/TK-002.md) — expandir contratos fundamentais v2.
- [x] [TK-017](tickets/TK-017.md) — remover Mercado Livre/curso/página/oferta; auditor editorial limpo.

## Estado de prontidão — 2026-09-25

- `TK-020` permanece `in_progress`; `TK-021` foi revalidado e voltou a
  `verified`: a wheel reconstruída localmente
  continha três módulos de `build/lib/`; a CI também usava o extra inexistente
  `rag`, e havia referências a uma release RC ainda não publicada.
- O build foi isolado dos artefatos ignorados; verificador e workflows foram
  endurecidos. Regressões passaram; o core gate da árvore local passou 22/22
  etapas (`1050 passed`, `12 skipped`, zero falhas/bloqueios/not_run). O bundle
  de fechamento em `artifacts/farol-2.0.0-rc.1-clean-commit-audit-20260925`
  passou verificação independente; segue como artefato local de um commit não enviado.
- A claim de suporte Python do README foi alinhada à matriz oficial 3.11–3.13;
  a revisão manual Standards/Spec não deixou findings locais abertos.
- Não há tag/release GitHub da RC.1. Full gate no commit final: `not_run`; gate
  RAGFlow: `blocked` pela falta de serviço e dos quatro inputs externos.
- Private vulnerability reporting foi habilitado e confirmado por API em
  2026-09-25; resta o gate RAGFlow externo e CI no SHA remoto final.
- `main` segue protegido por 13 checks e uma aprovação de code owner; a branch
  RC não tem proteção nem ruleset. Usar `main` por PR ou decidir proteção da
  branch RC antes de usá-la como fonte de publicação.
- O estado dos 21 tickets coincide com `state.json`; os 33 AC do contrato
  coincidem com a matriz e suas referências de evidência existem. A auditoria
  `requirements.lock`/ambiente local passou sem findings nesta data.

## Snapshot de verificação — 2026-09-20 (full final + TK-017–TK-021)

- Branch de entrega: `main`; a release candidate `v2.0.0-rc.1` é derivada da
  integração Farol 2.0. A evidência full foi capturada na árvore candidata
  baseada em `93bb8894d816aad3c3b3682ccec317db1da39d45` e depois versionada no
  GitHub. O worktree atual está limpo antes da preparação da RC.
- Full final histórico (core, book-to-skill, RAGFlow, OCR, wheel, candidate e oráculos):
  `25/25` etapas, `0 failed`, `0 blocked` e `0 not_run`; agregado idempotente
  `1045 passed` e `12 skipped`; pytest `474 passed, 6 skipped`; clone limpo
  `474 passed, 6 skipped`; crash matrix `17`; revogação `25`. Report SHA-256
  `EFFE3B18D009CC659326C3F58F7B43FCABBC75540945F7F55B23EEBD0FD29824`.
  (temporário, não versionado). Executado com `--timeout 3600` porque a suíte
  excede o default de `1800s` por comando neste venv.
- A suíte completa no gate terminal (matriz de aceite, rastreabilidade,
  oráculos de documentação/contrato/superfície) registrou `542 passed,
  5 skipped`.
- TK-018 provider-free: `scripts/run_cutover_dual.py`, `cutover_metrics_from_arms()`
  e `build_cutover_receipt()` validam um recibo `cutover-decision` fail-closed;
  sem braço RAGFlow `passed` → `not_run`, legado preservado.
- TK-020/TK-021 provider-free: `specs/farol-2/acceptance-matrix.md` derivada
  por `scripts/check_acceptance_matrix.py` (`verified=33`, `in_progress=0`,
  `blocked=0`); TK-021 cobre AC-031 e a rastreabilidade do backlog passou.
- Documentação: `check_documentation.py --root . --json` com 164 Markdown,
  `findings=[]` e `ok=true`; `check_contracts.py --json` `ok=true` (77 schemas);
  `sync_schemas.py --check` `ok=true` (`count=77`).
- Auditoria de superfície editorial: `ok=true`, `0` findings em arquivos
  git-tracked e `0` findings no wheel recém-construído.
- RAGFlow, OCR e `book-to-skill` reais passaram em 2026-09-20; evidências
  redigidas estão em `ragflow-spike.md`, `TK-007.md` e `TK-011.md`.

Esses tickets são independentes. TK-001 não altera produção; TK-002 não remove
contratos 1.x.

## Dependências encerradas

### P1 — Seams e IR

- [x] TK-003 — KnowledgeBackend + adapter legado.
- [x] TK-004 — IR canônica, ranges/parent graph e observação de locators RAGFlow verificadas.
- [x] TK-005 — registry governado implementado e verificado; tickets RAGFlow dependentes permanecem condicionados ao spike.

### P2 — Fidelidade

- [x] TK-006 — Markdown/HTML estruturado implementado; regressão local verde.
- [x] TK-007 — PDF textual/quarentena/OCR Docling/RapidOCR real verificados.
- [x] TK-008 — DOCX/EPUB estruturados implementados; regressão local verde.
- [x] TK-009 — repositório por escopo implementado; regressão Git/symlink/budgets verde.

### P3 — Conhecimento

- [x] TK-010 — taxonomia versionada/aprovável implementada; regressão local verde.
- [x] TK-011 — multi-skill/lineage e adapter real book-to-skill verificados.
- [x] TK-012 — router global e citações canônicas implementados; regressão local verde.

### P4 — RAGFlow e lifecycle

- [x] TK-013 — lifecycle RAGFlow fake + real verificado.
- [x] TK-014 — mapping/retrieval/citations fake + real verificados.
- [x] TK-015 — composição/updates/recovery implementados e testados localmente.

### P5 — Migração e foco

- [x] TK-016 — migração 1.x resumível implementada; promoção final permanece condicionada ao cutover.
- [x] TK-017 — desvio editorial removido do contrato 2.0; auditor de superfície limpo.

### P6 — Cutover e entrega

- [x] TK-018 — dual-run comparativo real e receipt `cutover_approved` verificados.
- [x] TK-019 — contração de legado executada após receipt aprovado; surface/wheel/supply-chain verificados.
- [ ] TK-020 — core e bundle locais verificados; private reporting habilitado; full gate bloqueado por RAGFlow.
- [x] TK-021 — wheel builder/verifier isolados; regressões focadas passaram (`9 passed`).

## Checklist por ticket — template para novos esforços

- [ ] Ler spec/plan e paths na ordem do ticket.
- [ ] Confirmar baseline e preservar trabalho do usuário.
- [ ] Executar um caso RED por comportamento ausente.
- [ ] Implementar o mínimo GREEN e refatorar com testes verdes.
- [ ] Executar validação focal e regressão proporcional.
- [ ] Registrar ambiente, SHA, comandos, resultados e skips.
- [ ] Não marcar `done` sem aceites passados e revisão exigida.
