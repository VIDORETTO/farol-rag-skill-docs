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

O esforço Farol 2.0 está em handoff de entrega. Os 21 tickets (`TK-001` a
`TK-021`) estão `verified` e a matriz possui 33 critérios de aceite
`verified`. RAGFlow `0.27.2`, Docling/RapidOCR, `book-to-skill`, dual-run,
contração do legado, provenance de release e o gate full possuem evidência
redigida em `evidence/`.

O gate full final de 20 de setembro de 2026 passou `25/25` etapas, com `1045
passed`, `12 skipped` explícitos e zero falhas, bloqueios ou etapas `not_run`.
O snapshot versionado foi enviado na branch `farol-v3`. O próximo passo é a
decisão humana sobre tag, release e publicação; nenhuma dessas ações é feita
automaticamente pelos scripts.
