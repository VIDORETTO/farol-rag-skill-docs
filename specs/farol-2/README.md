# Esforço Farol 2.0

Este diretório é a fonte normativa da evolução de Farol 1.x para um sistema de
conhecimento multi-skill com IR canônica e RAGFlow. Os planos anteriores em
`docs/master-evolution/`, `docs/continuous-knowledge/` e
`docs/main-consolidation/` permanecem evidência histórica do comportamento 1.x;
não definem o escopo 2.0.

## Ordem de leitura

1. [`CONTEXT.md`](../../CONTEXT.md) — vocabulário canônico.
2. [`spec.md`](spec.md) — comportamento e critérios de aceite.
3. [`research.md`](research.md) — comparação verificada dos projetos externos.
4. [`data-model.md`](data-model.md) — identidades e estado alvo.
5. [`plan.md`](plan.md) — arquitetura, seams, migração e verificação.
6. [`backlog.md`](backlog.md) — fases, dependências e gates.
7. [`todo.md`](todo.md) — projeção operacional dos tickets.
8. [`tickets/`](tickets/) — pacotes de execução canônicos.

## Autoridade

- `spec.md` responde **o quê e por quê**.
- `plan.md` responde **como**.
- Cada `tickets/TK-xxx.md` é editável e canônico para sua fatia.
- `todo.md` e `backlog.md` são views; não registrar progresso apenas nelas.
- `state.json` guarda checkpoint do esforço, não substitui tickets.

## Estado atual do esforço

O esforço Farol 2.0 está em preparação de release. A auditoria de prontidão
reabriu TK-020 após encontrar gaps no empacotamento e nos workflows; TK-021
voltou a `verified` após a regressão da wheel passar. Consulte `state.json`,
`backlog.md` e os tickets antes de considerar a release pronta. RAGFlow
`0.27.2`, Docling/RapidOCR, `book-to-skill`, dual-run e contração do legado
possuem evidência histórica redigida em `evidence/`.

O gate full de 20 de setembro de 2026 passou `25/25` etapas, com `1045 passed`,
`12 skipped` explícitos e zero falhas, bloqueios ou etapas `not_run` no commit
de implementação `93bb8894d816aad3c3b3682ccec317db1da39d45`. Esse resultado não
valida o commit de preparação `be40e16f09153cfc12e3ea389302793f920c40b2` nem
as alterações locais atuais. O perfil `core` foi executado na árvore local da
RC em 25 de setembro de 2026 UTC e passou 22/22 etapas (`1050 passed`, `12
skipped`, zero falhas/bloqueios/not_run); esse worktree tinha 33 entradas
alteradas ao iniciar o gate. A integração/full gate continua bloqueada sem os
inputs RAGFlow. Não há tag ou GitHub Release `v2.0.0-rc.1`; os scripts
continuam sem publicar artefatos, e a promoção para GA exige nova evidência e
autorização humana.
