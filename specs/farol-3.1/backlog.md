<!-- docs-gate: proposal -->

# Backlog Farol 3.1

**Gerado a partir de:** spec/plan revisão 1 · **Baseline:** `6ee4ffe`

## Fases e gates

| Fase | Resultado demonstrável | Tickets | Gate |
|---|---|---|---|
| F0 — Régua | MRR, tokens de contexto, biblioteca e casos amplos medidos (baseline) | TK-201 | baseline em `evidence/TK-201.md` |
| F1 — Ganhos baratos | `block_id`, `get_context`, router enxuto, repositório limpo | TK-202, TK-209, TK-216 | SC-204, SC-205 |
| F2 — Precisão | ranking global; reranker e embedding decididos por medição | TK-203, TK-204, TK-205 | SC-201 (ou decisão registrada) |
| F3 — Destilação | claim/lease, orçamento, sumário nativo, `farol-distill` | TK-206, TK-207, TK-208 | SC-202 |
| F4 — Alcance | cursos, skill composta, PDF com layout, slides | TK-210, TK-211, TK-212, TK-213 | SC-203 |
| F5 — Síntese e avaliação | camada de síntese e `farol eval` | TK-214, TK-215 | casos `broad` medidos |
| F6 — Release | 3.1.0 | TK-218 | SC-206 no mesmo SHA |
| 4.0 | contração do legado | TK-217 | D-307 |

## Ordem topológica

| Ticket | Entrega | Requer | Estado |
|---|---|---|---|
| [TK-201](tickets/TK-201.md) | Régua 3.1 | — | implemented |
| [TK-202](tickets/TK-202.md) | `block_id`, `get_context`, `get_document` paginado | — | implemented |
| [TK-209](tickets/TK-209.md) | Router enxuto e único | TK-202 | implemented |
| [TK-216](tickets/TK-216.md) | Higiene e mapa do legado | — | implemented |
| [TK-203](tickets/TK-203.md) | Ranking global na biblioteca | TK-202 | implemented |
| [TK-204](tickets/TK-204.md) | Reranker local opcional | TK-201, TK-203, D-301 | implemented |
| [TK-205](tickets/TK-205.md) | Embedding com prefixos e troca medida | TK-201, D-302 | blocked (D-302) |
| [TK-206](tickets/TK-206.md) | Claim/lease e lock do plano | — | ready |
| [TK-207](tickets/TK-207.md) | Orçamento e sumário nativo | TK-206 | ready |
| [TK-208](tickets/TK-208.md) | Skill `farol-distill` | TK-206, D-303 | blocked (D-303) |
| [TK-210](tickets/TK-210.md) | Curso (pasta e playlist) | TK-207 | ready |
| [TK-211](tickets/TK-211.md) | Skill composta multi-fonte | TK-206, TK-207, D-304 | blocked (D-304) |
| [TK-212](tickets/TK-212.md) | PDF com layout | TK-201, D-305 | blocked (D-305) |
| [TK-213](tickets/TK-213.md) | Slides de videoaula | TK-210, D-306 | draft |
| [TK-214](tickets/TK-214.md) | Camada de síntese pesquisável | TK-202 | ready |
| [TK-215](tickets/TK-215.md) | `farol eval` | TK-202, TK-214 | ready |
| [TK-218](tickets/TK-218.md) | Release 3.1.0 | núcleo + D-308 | blocked (D-308) |
| [TK-217](tickets/TK-217.md) | Pipeline enxuto e contração 4.0 | TK-216, D-307 | draft |

## Grafo

```text
TK-201 ──┬─> TK-204 (D-301) ─┐
         ├─> TK-205 (D-302) ─┤
         └─> TK-212 (D-305) ─┤
TK-202 ──┬─> TK-203 ─> TK-204 │
         ├─> TK-209           ├─> TK-218 (D-308)
         └─> TK-214 ─> TK-215 │
TK-206 ──┬─> TK-207 ─┬─> TK-210 ─> TK-213 (D-306)
         ├─> TK-208 (D-303)  │
         └─> TK-211 (D-304) <┘
TK-216 ─> TK-217 (D-307, 4.0)
```

## Rastreabilidade

- AC-201–203, SC-204: TK-202 · AC-204, SC-201: TK-204 (TK-201 mede) · AC-205: TK-203
- AC-206: TK-205 · AC-207, SC-202: TK-206 · AC-208, AC-212: TK-207 (+TK-210)
- AC-209: TK-208 · AC-210–212, SC-203: TK-210 · AC-213–214: TK-211
- AC-215: TK-212 · AC-216: TK-213 · AC-217: TK-214 · AC-218: TK-215
- AC-219, SC-205: TK-209 · AC-220: TK-216 · AC-221: todos (superfície) + TK-217
- AC-222, SC-206: TK-218

## Pós-3.1 (com métricas de uso)

Taxonomia global entre pacotes; perguntas de avaliação revisadas por humano no
`farol eval`; imagens/diagramas; fontes autenticadas; MCP HTTP com bearer.
