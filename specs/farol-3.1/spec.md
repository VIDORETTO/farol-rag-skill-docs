<!-- docs-gate: proposal -->

# Especificação: Farol 3.1 — qualquer conteúdo, consultado com precisão

**Esforço:** `farol-3.1`
**Revisão:** 1
**Estado:** proposta (decisões abertas em [decisions.md](decisions.md))
**Baseline observado:** `6ee4ffe` (`main`, docs: record Farol 3.0.0 release evidence)
**Consome:** `specs/farol-3/` (entregue), `CONTEXT.md`, `docs/COMPATIBILITY.md`, ADR 0001–0004

## Intenção (do mantenedor)

> Juntar o **book-to-skill** e o **RAGFlow** e transformar qualquer conteúdo
> consultável para o agente de IA: um livro inteiro baixado no computador, um
> curso, um vídeo… deve virar skills e a estrutura de consulta RAG da melhor forma.

O 3.0 entregou o circuito (`add → build → task → connect → mcp`). O 3.1 não
reescreve nada: aprofunda o que o usuário sente em uso real — **cursos**,
**livros grandes**, **bibliotecas com muitas fontes** e **perguntas difíceis**.

## Diagnóstico do 3.0.0 (o que preservar e o que falta)

Preservar: IR canônica com locators; validação de citações `[bN]`, cópia e
injeção na síntese; lineage por afirmação; `sync` com capítulos `stale`; índice
local SQLite FTS5 + embeddings com RRF; MCP read-only; superfície pública
versionada (`docs/PUBLIC-SURFACE-3.json`).

| # | Lacuna | Evidência | Impacto |
|---|---|---|---|
| G1 | Curso não existe como conceito: uma fonte = um pacote = uma skill; sem playlist do YouTube; pasta de aulas sem ordem nem módulos. | `docops/journey.py:97` (`add_source`), `docops/journey.py:213` (`_build_one`); `grep playlist docops/` vazio. | Um curso vira dezenas de skills soltas ou uma pasta sem estrutura didática. |
| G2 | Skill temática só nasce de uma fonte; vários livros/cursos sobre o mesmo assunto não formam uma skill. | `CONTEXT.md` (“uma skill pode ser sustentada por várias fontes”) vs. jornada 1:1. | Conhecimento duplicado e fragmentado entre skills. |
| G3 | A destilação é serial e manual: `next_task` entrega uma tarefa por vez; capítulos independentes não podem ser feitos em paralelo; gravação de `plan.json` sem lock. | `docops/agent_tasks.py:513` (`next_task`), `docops/agent_tasks.py:325` (`_save_task` lê-modifica-grava). | Livro de 500 páginas ≈ 37 capítulos + outline + core, um por vez. Paralelizar hoje corromperia o plano. |
| G4 | Orçamento de tarefa fixo (6k tokens de fonte) e sem flag; o outline não recebe o sumário nativo do livro. | `docops/agent_tasks.py:32`; `docops/__main__.py:908` (`task plan` sem `--task-tokens`). | Capítulos do livro fatiados; mais tarefas que o necessário para modelos de contexto longo. |
| G5 | Sem expansão de contexto: `get_document` devolve o documento inteiro (num PDF, o livro todo); hits do MCP não expõem `block_id`. | `docops/backends/local_fts.py:300`; `docops/mcp_server.py:191` (hit sem `block_id`). | Ver “o parágrafo ao redor” custa o livro inteiro em tokens. |
| G6 | Ordem dos hits medíocre (MRR@5 0,54 no HTTPX) e sem reranker. | `specs/farol-3/evidence/TK-111.md` (aceitação publicada). | A resposta certa aparece, mas tarde; o agente lê mais blocos. |
| G7 | Biblioteca multi-pacote ordena por RRF posicional de cada pacote: intercala pacotes em vez de ranquear por relevância. | `docops/mcp_server.py:208` (`hits.sort` por score RRF local). | Com 20 livros, o top 5 mistura pacotes irrelevantes. |
| G8 | Embedding padrão antigo (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dim); fastembed 0.8.1 já oferece alternativas multilíngues permissivas. | `docops/backends/semantic.py:16`; D-05 de `specs/farol-3/decisions.md`. | Teto de qualidade em perguntas parafraseadas e PT→EN. |
| G9 | PDF digital extraído como texto puro (tabelas e layout perdidos); Docling só no OCR e com `do_table_structure=False`; slides de videoaula não são capturados. | `docops/extractors/pdf.py:50`. | Apostilas, papers e slides perdem a parte mais densa. |
| G10 | Ruído e peso: router menciona RAGFlow/lifecycle/generations; um router por fonte é instalado no agente; skills legadas `skills/fastapi*` e `skills/meuframework*` na raiz; caminho do `build` atravessa `master.py` (6k linhas) e `operations.py` (4,1k). | `docops/templates/router.md:3`; `docops/connect.py:134`; `docops/generation.py:221`. | Tokens desperdiçados em toda conversa; manutenção cara. |

Oportunidades sem lacuna direta:

- **O1 — Skill como camada de busca (estilo RAPTOR):** afirmações aceitas da
  skill já têm lineage para blocos, mas não são pesquisáveis.
- **O2 — Autoavaliação por pacote:** a lineage é um golden set gratuito para
  medir recall de qualquer fonte nova do usuário (hoje só o corpus de aceitação é medido).

## Resultado desejado

```text
farol add ./curso-python --as course      # pasta de aulas (vídeo, legenda, PDF) em ordem de módulo
farol add "https://youtube.com/playlist?list=…" --as course
farol add ./livro.pdf
farol skill compose python --from curso-python livro   # uma skill temática sobre várias fontes
farol build
farol task claim --n 4                    # subagentes destilam capítulos em paralelo
farol connect claude-code                 # skills + 1 router enxuto + skill farol-distill
farol eval                                # recall do próprio pacote, sem corpus externo
```

E, no MCP: `search_knowledge` mais preciso (rerank opcional, ranking global
na biblioteca, camada de síntese opcional) e `get_context` para ler só a
vizinhança de um hit.

## Atores

- **Usuário final**, **agente operador** (destila), **agente leitor** (consulta),
  **mantenedor** — os mesmos do 3.0.

## Escopo

### Incluído

- Expansão de contexto e `block_id` nos hits (G5).
- Reranker local opcional, ranking global multi-pacote e avaliação de embedding (G6–G8).
- Destilação paralela com claim/lease, orçamento configurável e outline guiado pelo sumário nativo (G3–G4).
- Skill `farol-distill` instalada por `farol connect` (G3).
- Cursos: pasta ordenada e playlist do YouTube como uma fonte (G1).
- Skill temática composta por várias fontes (G2).
- PDF digital com layout/tabelas via Docling opcional (G9).
- Camada de síntese pesquisável e `farol eval` (O1–O2).
- Router enxuto, router único por projeto, higiene do repositório e mapa do legado (G10).

### Excluído

- LLM embutido / chamada de modelo pelo core (mantém a decisão do 3.0).
- MCP com escrita (D-303 recomenda manter read-only).
- Remoção de superfície pública: só no 4.0 (TK-217, rascunho).
- Interpretação de imagens/diagramas/equações (continua pós-3.x; TK-213 só extrai texto de slides).
- Fontes autenticadas (Notion, Drive, Udemy etc.) e download que viole termos.

## Jornadas e critérios de aceite

### US-201 — Ler só o que importa ao redor de um hit (P1)

- **AC-201** — Todo hit de `search_knowledge` traz `block_id` (campo aditivo).
- **AC-202** — `get_context(block_id, before, after, scope)` devolve os blocos
  vizinhos em ordem, ou a seção inteira (`scope="section"`), cada um com `citation`,
  respeitando `max_tokens`; bloco `high` risk nunca é devolvido.
- **AC-203** — `get_document` aceita `offset`/`limit` (aditivo) e informa
  `total_blocks`/`next_offset`; sem parâmetros o comportamento atual é preservado.

### US-202 — Resposta certa no topo (P1)

- **AC-204** — Com reranker habilitado, MRR@5 sobe ≥ 0,10 absoluto na média do
  corpus de aceitação sem reduzir recall@5 e sem piorar o split de validação nem
  as perguntas em português (critério de D-301).
- **AC-205** — Na biblioteca, hits de pacotes diferentes são comparados por um
  score independente de pacote; um pacote irrelevante não ocupa o top-k só por
  ter hits (fixture de dois pacotes).
- **AC-206** — Um modelo de embedding só vira padrão se cumprir o critério de
  D-302; trocar o modelo reconstrói o índice em `farol build` automaticamente.

### US-203 — Destilar um livro grande rápido (P1)

- **AC-207** — `farol task claim --n N` entrega até N tarefas disponíveis com
  lease; duas sessões nunca recebem a mesma tarefa enquanto o lease vale;
  submissões concorrentes não perdem atualização do plano.
- **AC-208** — `farol task plan --task-tokens T` define o orçamento; o outline
  recebe o sumário nativo (PDF outline/EPUB nav/ordem de módulos) e, no modo
  heurístico, capítulos nativos dentro de [0,5×T, 3×T] viram um capítulo da skill.
- **AC-209** — `farol connect` instala a skill `farol-distill`, que conduz o
  loop (inclusive com subagentes quando o harness suporta) usando só comandos públicos.

### US-204 — Curso vira uma skill (P1)

- **AC-210** — `farol add <pasta> --as course` gera **um** pacote com módulos em
  ordem natural (`2` antes de `10`; prefixos `Aula`, `Módulo`, `Lesson`), cada
  módulo com título e locator do membro (`arquivo` + `HH:MM:SS`/página).
- **AC-211** — `farol add <playlist> --as course` adquire legendas de cada vídeo
  na ordem da playlist, registra licença por vídeo e bloqueia redistribuição
  quando qualquer membro não for redistribuível.
- **AC-212** — O outline do curso parte da ordem dos módulos.

### US-205 — Uma skill sobre várias fontes (P2)

- **AC-213** — `farol skill compose <nome> --from <ids…>` cria uma skill temática
  cujas tarefas citam blocos de várias fontes; a lineage registra `package` +
  `block_id`; `sync` de qualquer membro marca capítulos `stale` da composta.
- **AC-214** — Membros podem pular a skill própria (`--no-skill`) sem perder índice.

### US-206 — PDF com estrutura (P2)

- **AC-215** — Com o extra de layout instalado, PDF digital vira blocos com
  headings e tabelas (`kind: table`, Markdown) e locator de página; sem o extra,
  o caminho pypdf atual é mantido e reportado como `text-fallback`.
- **AC-216** — (P3) Vídeo local com `--slides` extrai texto de quadros-chave como
  blocos `slide` com `(at HH:MM:SS)`.

### US-207 — Perguntas amplas e autoavaliação (P2)

- **AC-217** — `search_knowledge(layer="synthesis"|"both")` pesquisa afirmações
  aceitas da skill e devolve, para cada uma, as citações dos blocos de suporte;
  o padrão continua `evidence`.
- **AC-218** — `farol eval [--package] --json` mede recall@5/MRR@5 do próprio
  pacote a partir da lineage (e de perguntas escritas pelo agente quando houver),
  rotulando o resultado como autoavaliação.

### US-208 — Menos ruído, menos peso (P2)

- **AC-219** — O router gerado tem ≤ 350 tokens, não menciona RAGFlow/lifecycle
  e cita `get_context`; `farol connect` instala **um** router por projeto.
- **AC-220** — Skills legadas e `plan-backlog-todo.md` saem da raiz sem quebrar
  links; um relatório de alcance do caminho `build` lista módulos não usados pela jornada.

### Transversal

- **AC-221** — Toda adição pública entra em `docs/PUBLIC-SURFACE-3.json` e em
  `docs/ERRORS.md`; nenhuma remoção/renomeação (regra de minor de `docs/COMPATIBILITY.md`).
- **AC-222** — Release 3.1 só com SC-201–SC-206 no mesmo SHA.

## Requisitos

- **FR-201** Ferramentas MCP aditivas (`get_context`, parâmetros novos) mantendo read-only.
- **FR-202** Reranker e ranking global atrás de um seam próprio, opcional e medido.
- **FR-203** Perfil de embedding com prefixos de query/passage e rebuild automático.
- **FR-204** Protocolo de tarefas com claim/lease, orçamento e dicas de sumário nativo.
- **FR-205** Fonte `course` (pasta/playlist) e skill composta sobre `farol.json` schema 1 (chaves aditivas).
- **FR-206** Extractor de layout opcional com fidelidade declarada.
- **FR-207** Camada de síntese indexada e `farol eval`.
- **FR-208** Router enxuto, higiene e mapa do legado sem quebra.

## Critérios de sucesso

- **SC-201** MRR@5 médio do corpus de aceitação ≥ 0,70 com rerank (baseline 3.0: HTTPX 0,54, Pro Git 0,64, paper 0,90), recall@5 ≥ 0,90 mantido.
- **SC-202** Livro do corpus (Pro Git) destilado com `claim --n 4` em ≤ 50% do tempo de relógio do loop serial, mesma rubrica e lineage válida.
- **SC-203** Curso de referência (≥ 5 aulas, licença conferida) vira 1 pacote e 1 skill com módulos em ordem; perguntas factuais citam `(at HH:MM:SS)` da aula certa.
- **SC-204** `get_context` reduz em ≥ 80% os tokens lidos para “contexto ao redor de um hit” vs. `get_document` no livro do corpus.
- **SC-205** Router instalado ≤ 350 tokens; um router por projeto.
- **SC-206** Zero regressão: suíte 3.0 e `tests/test_public_contract_v3.py` verdes em Linux/macOS/Windows.

## Decisões abertas

Ver [decisions.md](decisions.md). Bloqueiam: D-301 → TK-204; D-302 → TK-205;
D-303 → TK-208; D-304 → TK-211; D-305 → TK-212; D-306 → TK-213; D-307 → TK-217; D-308 → TK-218.
