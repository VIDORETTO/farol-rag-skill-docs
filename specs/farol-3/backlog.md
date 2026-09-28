<!-- docs-gate: proposal -->

# Backlog Farol 3.0

**Gerado a partir de:** spec/plan revisão 1 · **Baseline:** `90c8229`

## Fases e gates

| Fase | Resultado demonstrável | Tickets | Gate |
|---|---|---|---|
| F0 — Régua | Corpus real + métricas baseline (falhando) | TK-101, TK-110 (paralelo) | baseline registrado |
| F1 — Circuito factual | IA consulta fatos sem RAGFlow | TK-103 → TK-104 | MCP responde com locator; recall@5 ≥ 0,9 |
| F2 — Circuito conceitual | Skill destilada pela IA do usuário | TK-105 → TK-106 | rubrica R-01 num livro real |
| F3 — Jornada | `add/build/connect` em máquina limpa | TK-102 → TK-109 | SC-101 ≤ 10 min |
| F4 — Fontes | YouTube/áudio/vídeo e papers | TK-107 ∥ TK-108 | SC-104 |
| F5 — Release | 3.0 publicável | TK-111 | SC-101–105 no mesmo SHA |
| F6 — Robustez | sync, segurança, erros, estabilidade | TK-112, TK-113, TK-117, TK-118 | SC-106, SC-108 |
| F7 — Alcance | semântica, escala, biblioteca | TK-114, TK-115, TK-116 | benchmarks publicados |
| F8 — Confiança pública | prova de valor, docs, distribuição | TK-119, TK-120, TK-121 | SC-107; site e release atestada |
| F9 — Beta | usuários externos | TK-122 | SC-109 = **gate de divulgação** |

MVP “baixar e usar” = F0–F3. F4 amplia a promessa “qualquer fonte”.
Divulgação ampla só após F9 (beta). Parte 2 em [spec-prontidao.md](spec-prontidao.md).

## Ordem topológica

| Ticket | Entrega | Requer | Estado |
|---|---|---|---|
| [TK-101](tickets/TK-101.md) | Corpus real e aceitação | — | ready |
| [TK-110](tickets/TK-110.md) | Dieta de processo/superfície | — | ready |
| [TK-103](tickets/TK-103.md) | Backend local FTS5 | D-01 | blocked (D-01) |
| [TK-104](tickets/TK-104.md) | Servidor MCP stdio | TK-103 | draft |
| [TK-105](tickets/TK-105.md) | Tarefas de síntese para o agente | — | ready |
| [TK-106](tickets/TK-106.md) | Taxonomia pelo agente | TK-105 | draft |
| [TK-102](tickets/TK-102.md) | Jornada add/build/status | TK-103, TK-105 | draft |
| [TK-109](tickets/TK-109.md) | connect + instalação | TK-104 | draft |
| [TK-107](tickets/TK-107.md) | Transcrição YouTube/áudio/vídeo | D-02 | blocked (D-02) |
| [TK-108](tickets/TK-108.md) | Papers | — | ready |
| [TK-111](tickets/TK-111.md) | Release 3.0 | 101–105, 109, 110 | draft |
| [TK-112](tickets/TK-112.md) | `farol sync` | TK-102, TK-105 | draft |
| [TK-113](tickets/TK-113.md) | Defesa contra prompt injection | TK-104, TK-105 | draft |
| [TK-114](tickets/TK-114.md) | Busca híbrida semântica (extra) | TK-103, TK-101, D-05 | blocked (D-05) |
| [TK-115](tickets/TK-115.md) | Escala medida e progresso | TK-102, TK-107, TK-108 | draft |
| [TK-116](tickets/TK-116.md) | Biblioteca e MCP multi-pacote | TK-104 | draft |
| [TK-117](tickets/TK-117.md) | Erros que ensinam, `doctor --fix` | TK-102 | draft |
| [TK-118](tickets/TK-118.md) | Semver e testes de upgrade | TK-102, TK-104, TK-110 | draft |
| [TK-119](tickets/TK-119.md) | Prova de valor com vs. sem | TK-101, TK-104, TK-105 | draft |
| [TK-120](tickets/TK-120.md) | Site de docs e pacotes demo | TK-109, TK-117, D-06, D-07 | blocked |
| [TK-121](tickets/TK-121.md) | Attestation, SBOM, container | TK-111 | draft |
| [TK-122](tickets/TK-122.md) | Beta fechado (gate de divulgação) | TK-111, TK-113, TK-117, TK-120, D-08 | blocked |

## Grafo

```text
TK-101 ───────────────────────────────────────────────┐
TK-110 ───────────────────────────────────────────────┤
D-01 ─> TK-103 ─> TK-104 ─> TK-109 ───────────────────┤
TK-105 ─┬─> TK-106                                    ├─> TK-111
        └─> TK-102 (também requer TK-103) ────────────┤
D-02 ─> TK-107 ─┐                                     │
TK-108 ─────────┴─ (ampliam o corpus de aceitação) ───┘
```

## Rastreabilidade

- AC-101/103: TK-109 · AC-102/104: TK-102/103/105 · AC-105/106: TK-105
- AC-107: TK-106 · AC-108–110: TK-103/104 · AC-111–114: TK-107/108
- AC-115: TK-101 · AC-116/117: TK-110
- AC-118/119: TK-112 · AC-120–122: TK-113 · AC-123/124: TK-114 · AC-125/126: TK-115
- AC-127/128: TK-116 · AC-129/130: TK-117 · AC-131/132: TK-118 · AC-133: TK-119
- AC-134/135: TK-120 · AC-136: TK-121 · AC-137: TK-122

## Pós-3.0 (só com métricas de uso)

Rerank local; XLSX/PPTX/notebooks/OpenAPI; imagens e diagramas;
podcasts por RSS; Notion/Confluence/Drive como fontes; MCP HTTP com bearer; UI.
