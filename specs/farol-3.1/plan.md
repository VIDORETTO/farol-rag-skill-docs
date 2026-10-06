<!-- docs-gate: proposal -->

# Plano técnico: Farol 3.1

**Revisão:** 1
**Consome:** `spec.md` revisão 1
**Baseline:** `6ee4ffe`
**Perfil:** evolutivo, só adições (minor); expand antes de qualquer contract

## Abordagem escolhida

Medir primeiro, depois ganhar precisão barata, depois velocidade de destilação,
depois alcance (cursos, multi-fonte, layout), e só então enxugar:

1. **Régua (TK-201):** ampliar a aceitação para medir o que o 3.1 promete
   (MRR, tokens de contexto, biblioteca, curso, perguntas amplas). Falha hoje.
2. **Precisão barata (TK-202, TK-203, TK-209):** `block_id`, `get_context`,
   ranking global e router enxuto — pouco código, efeito em toda conversa.
3. **Precisão medida (TK-204, TK-205):** reranker e embedding, decididos por benchmark.
4. **Velocidade de destilação (TK-206, TK-207, TK-208):** claim/lease,
   orçamento, sumário nativo e skill `farol-distill`.
5. **Alcance (TK-210, TK-211, TK-212, TK-213):** cursos, skill composta, layout, slides.
6. **Síntese como busca e autoavaliação (TK-214, TK-215).**
7. **Sustentabilidade (TK-216 → TK-217) e release (TK-218).**

## Alternativas consideradas

- **Trocar o backend por um vector DB (LanceDB/Chroma/Qdrant embutido):**
  rejeitada para 3.1. O gargalo medido é ordenação (MRR), não escala; numpy em
  memória cobre bibliotecas pessoais. Reavaliar com `docs/SCALE.md` se uma
  biblioteca real passar de ~2M de janelas.
- **Voltar o RAGFlow para o padrão:** rejeitada (D-01 do 3.0). O que vale do
  RAGFlow é trazido sem o servidor: parsing com layout (TK-212), chunking por
  tipo (curso/transcrição, TK-210) e resumos hierárquicos (TK-214).
- **Tools de escrita no MCP para a destilação:** rejeitada (D-303).
- **Reranker como LLM do usuário (o agente reordena):** já possível hoje com
  `top_k` maior; não substitui um reranker local determinístico e barato.
- **Uma skill por aula do curso:** rejeitada; contraria o modelo book-to-skill
  (uma obra → uma skill com capítulos).
- **Gerar perguntas de avaliação no core:** rejeitada (core não chama modelo);
  TK-215 usa lineage e, opcionalmente, uma tarefa `questions` para o agente.

## Arquitetura alvo (delta sobre 3.0)

```text
farol add <pasta|playlist> --as course ─> CourseAcquirer (ordem natural, módulos, licença por membro)
farol skill compose <nome> --from a b ──> packages/@<nome>/ (kind: composite, sem índice próprio)
                                               │
farol build ─┬─> IR (+ extractor de layout opcional, + slides opcionais)
             ├─> índice local (perfil de embedding com prefixos; rebuild automático)
             ├─> índice de síntese (afirmações aceitas → blocos de suporte)
             └─> plano de tarefas (orçamento T, dicas de sumário nativo)
farol task claim/next/submit ─> leases por tarefa + lock do plano
farol connect ─> skills + 1 router do projeto + skill farol-distill
farol mcp ─> search_knowledge(+block_id, +layer) ─> pool por pacote ─> Ranker global (rerank opcional)
          ├─> get_context(block_id, before, after, scope, max_tokens)
          └─> get_document(+offset, +limit)
farol eval ─> lineage + perguntas do agente ─> recall@5/MRR@5 do próprio pacote
```

## Seams de teste

Reuso de S1–S9 do 3.0 (`specs/farol-3/plan.md`). Novos (confirmar antes do RED):

| Seam | Interface pública | Tickets |
|---|---|---|
| S1 CLI JSON | `farol add/build/task/skill/connect/eval/doctor --json` | 206, 207, 208, 210, 211, 215, 216 |
| S2 MCP stdio | JSON-RPC de `farol mcp` (projeto e `--library`) | 202, 203, 204, 214 |
| S3 KnowledgeBackend | `docops/backends/base.py` (conformance) | 202, 205, 214 |
| S4 Extractor | `ExtractorRegistry.extract` | 212, 213 |
| S6 Aceitação real | `scripts/acceptance_real.py --json` | 201, 204, 205, 212, 218 |
| **S10 Ranker** | protocolo `Ranker.rank(query, candidates) -> scores` injetável no servidor MCP; reranker falso determinístico nos testes | 203, 204 |
| **S11 Aquisição de curso** | cliente de playlist injetável (mesmo padrão do `yt_dlp` falso dos testes de transcrição) | 210 |
| **S12 Conversor de layout** | conversor Docling injetável (mesmo padrão de `run_ocr_profile`) | 212 |

Regra herdada: testes de comportamento novo entram por seam público
(`tests/SEAMS.md`); valores esperados vêm de fixture/golden revisado, nunca
recalculados pelo código sob teste. Detalhes em [tdd.md](tdd.md).

## Matriz de roteamento (SDD)

| ID | Ticket | Nível | Modelo | Lote | Motivo |
|---|---|---|---|---|---|
| TK-201 | Régua 3.1 | 🟡 | intermediário | — | Métricas novas e casos; define o norte |
| TK-202 | `block_id` + `get_context` + `get_document` paginado | 🟢 | menor | TK-209 | Adição isolada no MCP/backend |
| TK-203 | Ranking global na biblioteca | 🟡 | intermediário | TK-204 | Seam S10 novo |
| TK-204 | Reranker local opcional | 🟡 | intermediário | TK-203 | Dependência opcional + medição |
| TK-205 | Avaliação/troca de embedding | 🟡 | intermediário | — | Rebuild automático + benchmark |
| TK-206 | Claim/lease e lock do plano | 🔴 | forte | TK-207 | Concorrência em arquivos; corromper plano é perda de trabalho |
| TK-207 | Orçamento e sumário nativo | 🟡 | intermediário | TK-206 | Planejador de tarefas |
| TK-208 | Skill `farol-distill` | 🟢 | menor | — | Texto + instalação por `connect` |
| TK-209 | Router enxuto e único | 🟡 | intermediário | TK-202 | Revisões do manifesto e migração |
| TK-210 | Curso (pasta e playlist) | 🔴 | forte | — | Aquisição, direitos, ordem e locators |
| TK-211 | Skill composta multi-fonte | 🔴 | forte | — | Lineage entre pacotes + sync |
| TK-212 | PDF com layout | 🟡 | intermediário | — | Extractor opcional atrás de S12 |
| TK-213 | Slides de videoaula | 🟡 | intermediário | — | P3, opt-in, ffmpeg |
| TK-214 | Camada de síntese pesquisável | 🟡 | intermediário | TK-215 | Índice derivado da lineage |
| TK-215 | `farol eval` | 🟡 | intermediário | TK-214 | Métrica sobre lineage |
| TK-216 | Higiene e mapa do legado | 🟢 | menor | — | Docs + script de alcance |
| TK-217 | Contração 4.0 | 🔴 | forte | — | Remoção pública; só com D-307 |
| TK-218 | Release 3.1 | 🟡 | intermediário | — | Gates e publicação autorizada |

## Ondas

Cada onda termina com gate verde antes da próxima.

1. **Onda A — régua e ganhos baratos:** TK-201, TK-202, TK-209, TK-216.
2. **Onda B — precisão:** TK-203, TK-204, TK-205.
3. **Onda C — destilação:** TK-206, TK-207, TK-208.
4. **Onda D — alcance:** TK-210, TK-212, TK-211, (TK-213 se D-306 aprovada).
5. **Onda E — síntese e avaliação:** TK-214, TK-215.
6. **Onda F — release:** TK-218. TK-217 só no ciclo 4.0.

## Riscos

| Risco | Mitigação |
|---|---|
| Reranker pesa (1 GB) e é lento em CPU | Opt-in; rerank só do pool (≤ 50); medir latência p95 no corpus; cache de modelo compartilhado com embeddings |
| Reranker inglês piora perguntas em português | Critério de D-301 inclui as perguntas PT; NC proibido como padrão |
| Troca de embedding invalida índices de usuários | Rebuild automático no `build` e `doctor --fix`; mensagem `embedding_profile_changed` continua para leitores |
| Concorrência em `plan.json` corrompe trabalho aceito | Lock de arquivo com `docops/lease.py`; teste com processos reais; escrita atômica já existente |
| Playlist do YouTube bloqueada por bot (já visto no 3.0) | Cliente falso nos testes; aceitação real `not_run` sem cookies, nunca sucesso |
| Direitos de curso pago | `--license` obrigatório para curso local; redistribuição `private-only` por padrão; nada adquirido é distribuído |
| Router novo muda `router_revision` de pacotes existentes | `farol build` regenera router e revisões juntos; teste de upgrade 3.0 → 3.1 |
| Escopo vazando para `master.py`/`operations.py` | Tickets 3.1 não tocam esses arquivos, salvo TK-210/211 via adaptador; parar e replanejar se o diff sair dos `owned_areas` |

## Regras para a IA executora

1. Leia `spec.md`, este plano, [tdd.md](tdd.md) e o ticket inteiro antes de editar.
2. Um ticket por vez; RED observado antes do GREEN; registre o RED em `evidence/TK-2xx.md`.
3. Toda adição pública atualiza `docs/PUBLIC-SURFACE-3.json`, `docs/ERRORS.md` e a doc de usuário no mesmo ticket.
4. Ausência de modelo, extra, ffmpeg, cookies ou harness é `blocked`/`not_run`, nunca sucesso.
5. Se o diff sair dos `owned_areas`, pare e volte à planejadora.
6. Nada de histórico em `AGENTS.md`/`tasks/todo.md`.
