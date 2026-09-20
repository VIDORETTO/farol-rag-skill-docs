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

## Estado inicial do esforço

Na abertura do esforço, a fronteira executável era TK-001 e TK-002 e nenhuma
implementação havia sido iniciada. Esse registro é histórico; o estado atual
fica nos tickets e em `state.json`. RAGFlow e OCR real já possuem execução
fixada e evidência redigida; `book-to-skill` real continua sendo integração de
harness e precisa registrar `executed` ou `not_run`. Ausência nunca é contada
como aprovação.
