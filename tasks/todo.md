# Checkpoint Farol 2.0 — 2026-09-20

## Estado atual

- Branch `farol-v2`, candidato `93bb8894d816aad3c3b3682ccec317db1da39d45`;
  `origin/farol-v2` aponta para o mesmo SHA. Worktree dirty, sem commit/push
  autorizado.
- Gate full final no `.venv-rag` Python 3.13.12: `25/25` estágios, `1045 passed`,
  `12 skipped`, `0 failed`, `0 blocked`, `0 not_run`. O relatório é
  `artifacts/release-gates-full-20260920-final7/release-gates.json`, SHA-256
  `EFFE3B18D009CC659326C3F58F7B43FCABBC75540945F7F55B23EEBD0FD29824`.
- A suíte principal passou `474 passed, 6 skipped`; clean clone `474 passed,
  6 skipped`; crash matrix `17 passed`; revogação `25 passed`. Os skips são
  integrações externas opt-in/symlink indisponível e estão explicitamente registrados.
- Acceptance matrix atualizada: `verified=33`, `in_progress=0`, `blocked=0`; TK-021 agora
  cobre AC-031 com teste explícito do bundle privado/provenance. Contratos: 77
  schemas, sem findings; documentação: 164 Markdown, sem findings; superfície editorial: 337
  arquivos, sem findings; superfície `legacy/all`: 0 findings.

## Entregas confirmadas

- TK-001/TK-004/TK-013/TK-014: RAGFlow v0.27.2 real passou health, dataset,
  upload, parse, chunks/locators, retrieval, mapping canônico, query,
  snapshot, rebuild e cleanup; adapter corrigido para o limite real de 100
  chunks por página.
- TK-007: Docling 2.129.0 + ONNX Runtime 1.30.0 + RapidOCR processaram PDF
  escaneado de duas páginas com texto, page/bbox e confiança reais.

- TK-017: contração editorial concluída e auditada; legado `knowledge-rag`/
  Chroma não foi removido porque isso pertence a TK-019.
- TK-018: runner dual e recibo `cutover-decision` provider-free fail-closed;
  o dual-run sem braços medidos retorna `not_run`, preserva o legado e não
  fabrica `cutover_approved`.
- TK-020: jornada provider-free, matriz de aceite e pipeline completo
  core/book-to-skill/RAGFlow/OCR/wheel validados. O runner de release agora
  executa Ruff pelo interpretador selecionado, sem depender de `PATH` ativado.
- TK-021: fronteira de originais privados, derivados distribuíveis e
  provenance de release verificada no bundle candidate.

## Pendências e bloqueios reais

- TK-011.3 foi concluído: o harness real `book-to-skill` gerou duas skills
  PT-BR a partir de uma projeção IR temporária; validação, scan, budgets e
  lineage passaram. Evidência: `specs/farol-2/evidence/TK-011.md`.
- TK-018 foi concluído com dois braços medidos e receipt atual
  `cutover_approved`; TK-019 foi concluído em lotes controlados e sua superfície
  final está limpa.

## Próximo passo

O release gate completo passou e TK-020 está fechado. Publicação, tag, release,
commit e push continuam fora desta execução.

## Histórico preservado

- [`tasks/archive/todo-history-2026-09-13.md`](archive/todo-history-2026-09-13.md)
- [`tasks/archive/AGENTS-2026-09-13.md`](archive/AGENTS-2026-09-13.md)
