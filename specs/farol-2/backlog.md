# Backlog Farol 2.0

**Gerado a partir de:** spec/plan revisão 1 e tickets revisão 1.
**Baseline:** `81d5dcb2e189d00406cdd9b9e671d94e3f23cd58`
**Snapshot de entrega:** branch `farol-v3`; a árvore candidata foi
versionada e enviada ao GitHub. A evidência full foi capturada em 20/09/2026
contra a mesma árvore de implementação antes do handoff documental.

## Fases e gates

| Fase | Resultado demonstrável | Tickets | Gate |
|---|---|---|---|
| P0 — Risco e contratos | RAGFlow comprovado e contratos v2 expandidos | TK-001–002 | H-001/H-002 respondidas; v1 preservado |
| P1 — Seams e IR | Backend legado encapsulado, IR e registry governado | TK-003–005 | conformance + IR imutável + opt-in |
| P2 — Fidelidade | Formatos iniciais percorrem artefato→IR | TK-006–009 | estrutura, locator, erro e degradação por formato |
| P3 — Conhecimento | Taxonomia, multi-skill, lineage e router global | TK-010–012 | concept owner, budget, claims e rotas validados |
| P4 — RAGFlow e lifecycle | Candidata RAGFlow consultável e composição atômica | TK-013–015 | mapping/citation/recovery/rollback verdes |
| P5 — Migração | Pacotes 1.x migram e desvio editorial sai do 2.0 | TK-016–017 | origem preservada; auditor de superfície limpo (editorial) |
| P6 — Cutover e entrega | RAGFlow aprovado, legado removido, privacidade e wheel 2.0 auditados | TK-018–021 | SC-001–008 no mesmo candidato |

MVP técnico = P0–P4 para corpus sintético autorizado. Farol 2.0 distribuível
= P0–P6, sem publicação remota implícita.

## Ordem topológica

| Ticket | Entrega | Requer | Estado inicial |
|---|---|---|---|
| [TK-001](tickets/TK-001.md) | Spike RAGFlow/DeepDoc | — | verified (RAGFlow/DeepDoc real) |
| [TK-002](tickets/TK-002.md) | Contratos fundamentais v2 | — | verified |
| [TK-003](tickets/TK-003.md) | KnowledgeBackend + adapter legado | TK-002 | verified |
| [TK-004](tickets/TK-004.md) | IR canônica | TK-001, TK-002 | verified |
| [TK-005](tickets/TK-005.md) | Registry de extractors | TK-004 | verified |
| [TK-006](tickets/TK-006.md) | Markdown/HTML estruturados | TK-005 | verified |
| [TK-007](tickets/TK-007.md) | PDF textual/OCR | TK-001, TK-005 | verified (Docling/RapidOCR real) |
| [TK-008](tickets/TK-008.md) | DOCX/EPUB | TK-001, TK-005 | verified |
| [TK-009](tickets/TK-009.md) | Repositório por escopo | TK-005 | verified |
| [TK-010](tickets/TK-010.md) | Taxonomia aprovada | TK-004, TK-006 | verified |
| [TK-011](tickets/TK-011.md) | Síntese multi-skill + lineage | TK-006, TK-010 | verified (book-to-skill real) |
| [TK-012](tickets/TK-012.md) | Router global | TK-003, TK-010, TK-011 | verified |
| [TK-013](tickets/TK-013.md) | Lifecycle RAGFlow | TK-001, TK-003, TK-004 | verified (lifecycle real) |
| [TK-014](tickets/TK-014.md) | Index/mapping/retrieval/citations | TK-012, TK-013 | verified (mapping/retrieval real) |
| [TK-015](tickets/TK-015.md) | Composição/updates/recovery | TK-011, TK-014 | verified |
| [TK-016](tickets/TK-016.md) | Migração 1.x→2.0 | TK-015 | verified |
| [TK-017](tickets/TK-017.md) | Remover Mercado Livre e editorial | TK-002, TK-016 | verified (remoção executada) |
| [TK-021](tickets/TK-021.md) | Originais privados e provenance de release | TK-017 | verified |
| [TK-018](tickets/TK-018.md) | Paridade e autorização de cutover | TK-007–009, TK-015–017 | verified (`cutover_approved`) |
| [TK-019](tickets/TK-019.md) | Contração do backend legado | TK-018 | verified (legacy/vendor/Chroma removidos da superfície) |
| [TK-020](tickets/TK-020.md) | Jornada e release candidate 2.0 | TK-017, TK-019 | verified (full gate e handoff) |

## Grafo

```text
TK-001 ─┬─> TK-004 ─> TK-005 ─┬─> TK-006 ─> TK-010 ─> TK-011 ─> TK-012 ─┐
        │                       ├─> TK-007 ───────────────────────────┤
TK-002 ─┴─> TK-003 ──────────────────────────────────├─> TK-013 ─> TK-014 ─> TK-015 ─> TK-016 ─> TK-017 ─┐
                                ├─> TK-008 ──────────────────────────────────────┤                              │
                                └─> TK-009 ──────────────────────────────────────┴─> TK-018 ─> TK-019 ─> TK-020
                                                                                └─> TK-021
```

TK-006–009 podem ser executados em paralelo depois de TK-005, mas compartilham
fixtures/matriz; cada implementador deve limitar edits ao adapter próprio. TK-003
e TK-004 podem avançar em paralelo após seus blockers. Builds de wheel e uma
instância RAGFlow compartilhada não devem rodar concorrentemente no mesmo checkout.

## Rastreabilidade

- AC-001–003: TK-002/TK-020.
- AC-004–009: TK-004–009/TK-018.
- AC-010–014: TK-010–011/TK-018.
- AC-015–018: TK-012/TK-014/TK-020.
- AC-019–023: TK-001/TK-003/TK-013–014.
- AC-024–026: TK-015/TK-018.
- AC-027–029: TK-016–019.
- AC-030, AC-032–033: TK-005/TK-007/TK-020.
- AC-031: TK-021/TK-020.

## Backlog posterior ao 2.0

Somente após métricas de uso:

- alta fidelidade para XLSX, PPTX, notebooks, OpenAPI, código adicional;
- RTF, ODT/ODS/ODP, MOBI/AZW, e-mail e archives governados;
- ASR nativo para áudio/vídeo e timestamps;
- browser renderizado/autenticação por plugins autorizados;
- figuras/diagramas/equações com compreensão multimodal;
- perfis medidos de capacidade, multi-host ou SaaS.

Cada item exige demanda real, fixture licenciada, locator, lineage, degradação,
segurança e conformance skill+RAG.
