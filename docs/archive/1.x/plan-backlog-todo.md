# De Documentação Técnica a Skill Inteligente com RAG Híbrido
## Especificação de Projeto — Contexto, Objetivo, Arquitetura, Ticket e Plano de Execução

| Campo | Valor |
|---|---|
| **Documento** | SPEC-001 — Doc-to-Skill + RAG Híbrido (MCP) |
| **Status** | Release pública 1.0.0 implementada, auditada e publicada; perfil RAG segue opt-in |
| **Versão** | 1.0 |
| **Última atualização** | 2026-08-29 |
| **Autor** | Assistente, a pedido do usuário |

---

## 1. Sumário Executivo

O objetivo é transformar a documentação de um framework, pipeline ou aplicação (site de docs, pasta de markdown, PDFs, OpenAPI/Swagger, changelogs, etc.) em uma **skill inteligente para agentes de IA** usada pelo harness do usuário que:

1. Carrega **mental models, convenções e fluxos de decisão** do framework sob demanda, com baixo custo de tokens (via `SKILL.md` + arquivos por tópico) — resolvido pela ferramenta **`book-to-skill`**;
2. Consegue responder perguntas pontuais e literais sobre **qualquer trecho da documentação**, mesmo em corpora grandes, versionados e que mudam com frequência (algo que uma skill estática sozinha não cobre bem) — resolvido por um **servidor MCP de RAG híbrido** (`knowledge-rag`), que expõe busca semântica + lexical (BM25) com reranking;
3. Combina as duas camadas via um **skill "roteador"** que decide quando usar o mental model já carregado versus quando ir buscar o trecho exato na base RAG.

A pesquisa confirma que essa combinação (**skill estruturada + RAG híbrido + MCP**) é a abordagem recomendada pela comunidade e por trabalhos recentes de context engineering, porque cada camada resolve um problema diferente: skill = comportamento/procedimento; RAG = grounding factual em conteúdo grande e vivo; MCP = protocolo padrão de conexão entre o agente e a base de conhecimento.

---

## 2. Contexto e Motivação

### 2.1 O problema

Frameworks, SDKs e pipelines internos têm documentação que:

- É grande demais para caber no contexto do agente a cada pergunta (dumping bruto = "discovery loop tax": o agente reprocessa o índice/TOC a cada turno);
- Muda com frequência (releases, deprecations, breaking changes) — uma skill estática vira "notas desatualizadas" se não houver atualização incremental;
- Tem dois tipos de necessidade de consulta muito diferentes:
  - **"Como esse framework pensa?"** → mental models, convenções, arquitetura, anti-patterns, decisões de design (uso repetido, cabe em poucos milhares de tokens, é estável).
  - **"Qual é a assinatura exata dessa função/endpoint na versão X?"** → fato pontual, texto literal, precisa de recall alto sobre um corpus grande, muda a cada release.

Nenhuma ferramenta isolada resolve bem os dois casos:

- **Uma skill estática (só `book-to-skill`)** é ótima para o primeiro caso (structure, not summary) mas não escala para documentação de milhares de páginas que muda toda semana — o "fold-in" manual não é RAG, é uma atualização incremental orientada por agente.
- **Um RAG puro (só vetor/embeddings)** é ótimo para recall factual em corpora grandes, mas não carrega comportamento, convenções ou "como aplicar isso enquanto eu trabalho" — ele devolve trechos, não know-how estruturado.

### 2.2 A resposta da comunidade: camadas complementares

Um paper recente de context engineering (arXiv 2604.23674) descreve exatamente esse racional:

> RAG grounds model outputs in retrieved documents ... but lacks reasoning and the ability to execute actions. MCP provides a standardized interface ... but specifies only how to connect, not what domain knowledge to apply. Skills occupy a distinct layer: they encode behavioral expertise ... A well-designed [...] skill may internally orchestrate MCP-style tool calls and RAG-style retrieval, then synthesize results using domain-specific reasoning present only in the skill specification itself.

Ou seja: **Skill = cérebro procedural, RAG = memória factual, MCP = fio que conecta os dois ao agente.** Essa é a mesma lógica por trás de "book-to-skill + RAG híbrido MCP".

### 2.3 As ferramentas identificadas na pesquisa

| Camada | Ferramenta escolhida | Por quê |
|---|---|---|
| **Extração → Skill estruturada** | [`virgiliojr94/book-to-skill`](https://github.com/virgiliojr94/book-to-skill) (MIT, ~26k★) | Converte qualquer prosa estruturada (não só livros: `docs/` inteiro, RFCs, specs, changelogs) em `SKILL.md` + capítulos sob demanda + `glossary.md` + `patterns.md` + `cheatsheet.md`. Suporta atualização incremental ("fold-in") quando a doc-fonte muda. Padrão aberto Agent Skills para harnesses compatíveis. |
| **RAG híbrido via MCP** | [`lyonzin/knowledge-rag`](https://github.com/lyonzin/knowledge-rag) (MIT, ativo, v4.8.x) | Busca híbrida semântica (FastEmbed ONNX, embeddings 384D) + lexical (BM25 com índice invertido, 128× mais rápido que baseline) fundidas por Reciprocal Rank Fusion, com **reranking por cross-encoder**. 13 tools MCP (`search_knowledge`, `get_document`, `search_similar`, `add_from_url`, `reindex_documents`, etc.). 20 formatos de arquivo nativos (md, pdf, docx, código-fonte, etc.). 100% local (zero cloud, zero custo de API), roda via stdio ou SSE/HTTP conforme o perfil. Inclui 10 skills prontas (`rag-check-first`, `rag-cite-sources`, `rag-deep-dive`...) que ensinam o agente a *usar* o RAG antes de responder. |

**Alternativas avaliadas e descartadas (ou mantidas como plano B):**

| Alternativa | Observação |
|---|---|
| `rag-cli` (ItMeDiaTech) | ChromaDB + orquestração multi-agente (MAF); mais pesado/opinativo, bom se já quiser roteamento multi-agente embutido. |
| `CodeRAG` (Simona Barankova, artigo) | Prova de conceito para busca semântica em código interno via LanceDB; bom conceito de arquitetura, não é um produto pronto para instalar. |
| `mcp-rag-server` (0xrdan) | Depende de ChromaDB externo já populado; menos "zero-config" que `knowledge-rag`. |
| RAG "cru" via LangChain/LlamaIndex custom | Mais flexível, mas exige construir o servidor MCP, o pipeline de chunking e a busca híbrida do zero — sem necessidade quando `knowledge-rag` já entrega isso pronto e testado (700+ testes, benchmarks públicos). |

**Veredito da análise:** sim, `book-to-skill` sozinho **não** entrega RAG — ele entrega uma skill estruturada com carregamento progressivo, que é uma forma de "retrieval" por navegação de arquivos, não por embeddings. Para ter RAG de verdade (recall semântico + lexical sobre um corpus grande e vivo), a combinação com um MCP de RAG híbrido dedicado é a escolha correta e é exatamente o padrão que aparece na comunidade. A dupla `book-to-skill` + `knowledge-rag` é a implementação concreta mais recomendável hoje para esse padrão.

---

## 3. Objetivo do Projeto

**Objetivo geral:** transformar a documentação de um framework/pipeline/app-alvo em um pacote de conhecimento para agentes de IA composto por (a) uma skill estruturada de mental models e (b) uma base RAG híbrida pesquisável via MCP, com um mecanismo de roteamento entre as duas e um processo de atualização incremental.

**Objetivos específicos (SMART):**

1. Gerar uma skill (`SKILL.md` + arquivos por capítulo/tópico) a partir da documentação-alvo, com custo de carregamento ≤ ~4.000 tokens no core e arquivos sob demanda ≤ ~1.500 tokens cada.
2. Indexar 100% da documentação-alvo (incluindo API reference, changelogs e exemplos de código) em um servidor MCP de RAG híbrido, com latência p95 de busca < 500ms local.
3. Produzir uma skill "roteador" que decide automaticamente entre resposta pela skill estática, busca no RAG, ou ambos, com citação de fonte (`arquivo:linha` ou URL) em toda resposta factual.
4. Estabelecer um processo de atualização (fold-in da skill + reindex incremental do RAG) disparável manualmente ou por CI quando a documentação-fonte mudar.
5. Validar com um conjunto de perguntas de teste (golden set) cobrindo os dois tipos de consulta (conceitual e factual/literal), medindo recall e precisão da camada RAG (MRR@5, Recall@5).

---

## 4. Escopo

### 4.1 Dentro do escopo

- Definição do "framework-alvo" (a documentação a ser processada) e coleta/preparação das fontes.
- Instalação e execução de `book-to-skill` sobre a fonte, geração da skill e validação com `tools/validate_skill.py`.
- Instalação e configuração de `knowledge-rag` como servidor MCP, com preset adequado (`developer.yaml` como ponto de partida), ingestão do corpus completo.
- Criação da skill roteadora (comportamento: quando usar skill vs. RAG vs. ambos, formato de citação).
- Definição de golden set de perguntas e avaliação inicial de qualidade (`evaluate_retrieval`).
- Processo de atualização incremental (fold-in + reindex) documentado e testado uma vez.
- Documentação de uso para o time (como instalar, como consultar, como atualizar).

### 4.2 Fora do escopo (nesta primeira iteração)

- Deploy multi-usuário via SSE/HTTP com autenticação corporativa (bearer token, rate limiting) — fica como *fast follow* se o uso for além de uma máquina/indivíduo.
- Fine-tuning de modelo de embeddings customizado para o domínio.
- Integração com pipelines de CI/CD para reindexação automática a cada commit da documentação-fonte (planejado como Fase 5, opcional).
- Publicação/distribuição pública da skill gerada (respeitar direitos autorais da documentação-fonte, conforme aviso do próprio `book-to-skill`).

---

## 5. Arquitetura Proposta

```
                         ┌───────────────────────────────────────────┐
                         │        DOCUMENTAÇÃO-ALVO (fonte)           │
                         │  site de docs / pasta docs/ / PDFs /       │
                         │  OpenAPI / changelogs / exemplos de código │
                         └───────────────┬─────────────────────────┬─┘
                                         │                          │
                     ┌───────────────────▼──────────┐   ┌───────────▼────────────────────┐
                     │   PIPELINE A — book-to-skill   │   │   PIPELINE B — knowledge-rag     │
                     │   (extração + estruturação)    │   │   (ingestão + indexação híbrida) │
                     │                                │   │                                  │
                     │  extractor → full_text +       │   │  documents/ → 20 parsers →       │
                     │  metadata → agente gera:        │   │  chunker (md-aware/code-aware) → │
                     │   • SKILL.md (core)             │   │  FastEmbed ONNX (embeddings) +   │
                     │   • chapters/*.md (sob demanda) │   │  BM25 (índice invertido) →       │
                     │   • glossary.md                 │   │  ChromaDB (vetores) + SQLite     │
                     │   • patterns.md                 │   │  FTS5 (lexical)                  │
                     │   • cheatsheet.md               │   │                                  │
                     └───────────────┬────────────────┘   └────────────────┬─────────────────┘
                                     │                                      │
                                     │            ~/.claude/skills/         │  MCP server
                                     │            <slug>/                   │  (stdio ou SSE)
                                     ▼                                      ▼
                     ┌─────────────────────────────────────────────────────────────────┐
                     │                SKILL ROTEADORA ("<slug>-router")                  │
                     │  Decide: pergunta conceitual → skill estática                     │
                     │          pergunta factual/literal → search_knowledge (MCP)        │
                     │          pergunta ambígua → skill primeiro, RAG para confirmar     │
                     │  Sempre cita fonte (arquivo:linha / URL) em respostas factuais     │
                     └───────────────────────────┬─────────────────────────────────────┘
                                                  │
                                                  ▼
                     ┌─────────────────────────────────────────────────────────────────┐
                     │             AGENTE (harness externo compatível)                 │
                     │             Usuário faz a pergunta em linguagem natural            │
                     └─────────────────────────────────────────────────────────────────┘
```

**Fluxo de atualização (quando a doc-fonte muda):**

```
doc-fonte muda ──► book-to-skill (modo update/fold-in) ──► SKILL.md + capítulos atualizados
              └──► knowledge-rag: add_from_url / update_document / reindex_documents (async, zero-downtime)
```

---

## 6. Especificação Técnica Detalhada

### 6.1 Pipeline A — Geração da Skill (`book-to-skill`)

**Entrada:** arquivo único, pasta ou glob (ex.: `./docs/**/*.md`, PDF do manual, export do site de docs).

**Passos (conforme `docs/how-it-works.md` do projeto, Steps 0–10):**

1. **Step 0** — checagem de escopo (é conteúdo válido para virar skill?).
2. **Step 1 / 1.5** — validação de entrada e classificação do tipo de conteúdo: *técnico* (tabelas, código, fórmulas → usa Docling) vs. *texto corrido* (prosa → usa pdftotext/pypdf/pdfminer).
3. **Step 2 / 2.5** — extração real (`scripts/extract.py`), estimativa de custo em tokens, confirmação.
4. **Step 2.6** — para fontes muito grandes, probing estilo REPL (grep/sed) em vez de releitura completa.
5. **Step 3** — análise de estrutura (título, capítulos/seções, ToC).
6. **Step 4** — define profundidade (referência rápida vs. estudo aprofundado) conforme o uso pretendido.
7. **Step 7** — gera resumo estruturado por capítulo/seção (budget de tokens por tipo de conteúdo).
8. **Step 8** — gera `glossary.md`, `patterns.md`, `cheatsheet.md` (camada de decisão rápida).
9. **Step 9 / 9.5** — monta `SKILL.md` (core + índice) e os arquivos de capítulo.

**Saída** (instalada no diretório de skills do harness, por exemplo `<slug>/`):

| Arquivo | Papel | Custo aprox. |
|---|---|---|
| `SKILL.md` | Mental models centrais + índice de capítulos | ~4.000 tokens |
| `chapters/<n>-*.md` | Um por seção/capítulo, carregado só quando referenciado | ~1.000 tokens cada |
| `glossary.md` | Termos-chave, ordem alfabética, com referência ao capítulo | ~1.500 tokens |
| `patterns.md` | Técnicas, padrões de design, anti-patterns | ~2.000 tokens |
| `cheatsheet.md` | Tabelas de decisão e regras rápidas | ~1.000 tokens |

**Modo de atualização:** ao apontar `book-to-skill` para as mesmas fontes revisadas (ou fontes novas) e indicar que já existe uma skill para aquele slug, ele roda o *Update / Fold-in Workflow*: reextrai, mescla no `SKILL.md`/capítulos existentes em vez de recriar do zero.

**Validação:** `tools/validate_skill.py --lens claude` garante conformidade com as regras do host antes de considerar a skill pronta.

### 6.2 Pipeline B — RAG Híbrido (`knowledge-rag` via MCP)

**Instalação:**
```bash
pip install knowledge-rag
knowledge-rag init          # cria config.yaml + documents/
```

**Ingestão:** copiar/symlink a documentação-alvo completa (a mesma pasta `docs/`, exports de OpenAPI convertidos para markdown/JSON, changelogs, exemplos de código) para dentro de `documents/`. O watchdog interno reindexará automaticamente (debounce de 10s).

**Configuração recomendada** (`config.yaml`), partindo do preset `developer.yaml`:

```yaml
paths:
  documents_dir: "./documents"
  data_dir: "./data"

models:
  embedding:
    profile: "compact"      # trocar para "multilingual" se a doc tiver PT+EN
    gpu: "auto"
  reranker:
    enabled: false  # piloto FastAPI: RRF superou o cross-encoder no Golden

search:
  default_results: 5
  max_results: 100

query_expansions:
  # aliases específicos do vocabulário FastAPI para a perna BM25
  oauth2: ["oauth2-jwt", "jwt", "password bearer"]
  basesettings: ["pydantic-settings", "environment variables", "settings"]
  docker: ["dockerfile", "container image", "fastapi run"]
  testclient: ["testing fastapi applications", "httpx", "pytest"]
  middleware: ["middleware stack", "outermost", "innermost"]

server:
  transport: "stdio"        # uso individual via MCP local
```

> Se mais de uma pessoa do time vai consultar a mesma base, usar o perfil de
> rede opt-in em `config/network.example.yaml`, substituir o token e executar o
> auditor — ver Fase 6. O padrão individual continua `stdio`.

**Registro como MCP no cliente:** adicionar o servidor na configuração MCP do
harness escolhido conforme a documentação da versão instalada.

**Tools MCP relevantes para este projeto:**

| Tool | Uso no projeto |
|---|---|
| `search_knowledge` | Busca híbrida principal (semântica + BM25 + rerank) |
| `get_document` | Recuperar um documento inteiro quando o trecho não é suficiente |
| `search_similar` | Encontrar páginas de doc relacionadas a uma já encontrada |
| `add_from_url` | Indexar páginas do site de docs oficial diretamente por URL |
| `reindex_documents` / `get_reindex_status` | Reindexação incremental sem downtime, após atualização da doc-fonte |
| `evaluate_retrieval` | Medir MRR@5 / Recall@5 / Precision@5 no golden set |
| `list_categories` / `get_index_stats` | Sanity check da cobertura do corpus indexado |

**Skills comportamentais complementares** (instalar do próprio `knowledge-rag/skills/`): `rag-check-first` (buscar antes de responder qualquer claim técnica), `rag-cite-sources` (toda claim vem com citação `path:line`), `rag-deep-dive` (fluxo `search → fetch → find similar`).

### 6.3 Camada de Orquestração — Skill Roteadora

Criar uma skill leve (`<slug>-router/SKILL.md`) com a lógica:

- **Pergunta conceitual/comportamental** ("como esse framework lida com retries?", "qual o padrão recomendado para X?") → responder primeiro com a skill gerada pelo `book-to-skill` (mental models, `patterns.md`, `cheatsheet.md`).
- **Pergunta factual/literal** ("qual a assinatura exata de `Client.request()` na v3.2?", "o que mudou no changelog da última release?") → chamar `search_knowledge` via MCP, citar fonte.
- **Pergunta ambígua ou de alto risco** (decisão de arquitetura, breaking change) → usar a skill para o racional + RAG para confirmar o detalhe literal atual, e declarar explicitamente quando as duas fontes divergirem (skill desatualizada vs. doc atual).
- **Regra de citação obrigatória:** toda resposta que se apoie no RAG deve incluir a fonte (arquivo/URL + trecho), seguindo o padrão do skill `rag-cite-sources`.

### 6.4 Processo de Atualização Incremental

| Gatilho | Ação na Skill | Ação no RAG |
|---|---|---|
| Nova versão da documentação lançada | Rodar `book-to-skill` em modo update/fold-in apontando para as fontes revisadas | `add_from_url` para páginas novas; `update_document` para páginas alteradas |
| Página removida/depreciada | Fold-in reflete a remoção nos capítulos afetados | `remove_document` |
| Reorganização grande da doc-fonte | Reavaliar geração completa da skill (não só fold-in) | `reindex_documents` (nuclear rebuild, zero-downtime) |

---

## 7. Ticket Principal

```
TICKET: DOCKB-001
Título: Transformar documentação de [FRAMEWORK-ALVO] em skill inteligente com RAG híbrido (MCP)
Tipo: Épico
Prioridade: Alta
Responsável: [a definir]
Sprint alvo: [a definir]

Descrição:
Como desenvolvedor(a) que usa [FRAMEWORK-ALVO] no dia a dia dentro de agentes de IA
(um harness externo compatível), quero que o agente tenha acesso tanto aos mental
models e convenções do framework quanto à capacidade de buscar qualquer trecho
literal e atualizado da documentação, para que eu não precise abrir o navegador
nem colar documentação manualmente no contexto.

Critérios de aceite (alto nível):
[x] Skill FastAPI gerada/validada e carregando corretamente
[x] Servidor MCP knowledge-rag rodando e retornando resultados relevantes
[x] Retrieval supera 90% de cobertura no Golden (Recall@5 = 1,0)
[x] Skill roteadora exige citação em toda resposta factual
[x] Processo de atualização testado de ponta a ponta com checkpoints

Subtarefas: ver Seção 9 (Fases e Tarefas)
```

### Subtickets

| ID | Título | Depende de |
|---|---|---|
| DOCKB-002 | Levantar e preparar as fontes de documentação | — |
| DOCKB-003 | Instalar e rodar `book-to-skill` sobre a fonte | DOCKB-002 |
| DOCKB-004 | Instalar e configurar `knowledge-rag` (MCP) | DOCKB-002 |
| DOCKB-005 | Ingerir e indexar corpus completo no RAG | DOCKB-004 |
| DOCKB-006 | Criar skill roteadora | DOCKB-003, DOCKB-005 |
| DOCKB-007 | Montar golden set e avaliar qualidade (retrieval) | DOCKB-005 |
| DOCKB-008 | Testar e documentar processo de atualização incremental | DOCKB-003, DOCKB-005 |
| DOCKB-009 | Documentação de uso para o time | DOCKB-006 |
| DOCKB-010 (opcional) | Deploy multi-usuário (SSE/HTTP + auth) | DOCKB-009 |

---

## 8. Fases e Cronograma

| Fase | Nome | Duração estimada | Entregável |
|---|---|---|---|
| **Fase 0** | Preparação e decisão de escopo | 0,5 dia | Framework-alvo definido, fontes localizadas, acesso confirmado |
| **Fase 1** | Geração da Skill (`book-to-skill`) | 1 dia | Skill instalada e validada em `~/.claude/skills/<slug>/` |
| **Fase 2** | RAG Híbrido (`knowledge-rag`) | 1 dia | MCP configurado, corpus indexado, `search_knowledge` funcionando |
| **Fase 3** | Orquestração (skill roteadora) | 0,5–1 dia | Skill roteadora funcional com regra de citação |
| **Fase 4** | Avaliação e ajuste | 1 dia | Golden set + métricas (MRR@5, Recall@5) + ajustes de config |
| **Fase 5** | Atualização incremental e documentação | 0,5 dia | Processo de fold-in/reindex testado; guia de uso do time |
| **Fase 6 (opcional)** | Escala multi-usuário | 1 dia | SSE/HTTP, auth, rate limit, métricas Prometheus |

**Estimativa total (Fases 0–5):** ~4,5 a 5,5 dias úteis para uma pessoa técnica, assumindo documentação-alvo de porte médio (algumas centenas a poucos milhares de páginas equivalentes).

---

## 9. Tarefas Detalhadas por Fase

### Fase 0 — Preparação
- [x] Definir claramente o framework-alvo — **FastAPI** (piloto; estado em `docs/FRAMEWORK-TARGET.md`)
- [x] Levantar as fontes — snapshot `github.com/fastapi/fastapi/docs/en/docs` em `documents/fastapi-docs/` (157 arquivos suportados)
- [x] Confirmar licença/direitos — documentação FastAPI sob MIT; corpus local não é versionado
- [x] Definir `slug` (nome curto) — `fastapi` (`skills/fastapi/`, `skills/fastapi-router/`)
- [x] Escolher idioma dos embeddings — `compact` (bge-small-en 384D) decidido; roteiro para PT/EN em `config.yaml` + `docs/USE.md` §6 (`multilingual` + full rebuild)

### Fase 1 — Geração da Skill
- [x] Checar dependências: `python3 scripts/extract.py --check` — pypdf/pdfminer/ebooklib/python-docx/trafilatura/striprtf instalados; docling "fallback available" (opcional, `--mode technical`); Calibre (MOBI) ausente (fora do escopo)
- [x] Instalar: git clone do `book-to-skill` em `~/.agents/skills/book-to-skill` (padrão Agent Skills; alternativas em `docs/install.md` do repo)
- [x] Rodar/estabelecer a skill sobre a fonte real — `skills/fastapi/SKILL.md` + 7 capítulos, com mapa de decisão, glossário e anti-patterns
- [x] Classificar o formato — Markdown/prosa técnica processado em modo `text`; código permanece como contexto dos capítulos
- [x] Escolher profundidade (referência rápida vs. estudo aprofundado) de acordo com o uso pretendido — "referência rápida" com capítulos sob demanda (registro em `docs/FRAMEWORK-TARGET.md` §3)
- [x] Validar saída com `tools/validate_skill.py --lens claude` — `skills/fastapi/SKILL.md` e `skills/fastapi-router/SKILL.md` sem warnings
- [x] Revisar `glossary.md`, `patterns.md`, `cheatsheet.md` — no piloto, mapa de decisão/glossário/anti-patterns estão no core e os capítulos ficam sob demanda

### Fase 2 — RAG Híbrido
- [x] `pip install knowledge-rag` (v4.8.5) e `knowledge-rag init` — venv `.venv-rag/`, `presets/` + `config.example.yaml` gerados (config.yaml existente preservado)
- [x] Copiar/symlinkar a documentação completa para `documents/` — 157 arquivos FastAPI + 3 auxiliares + 3 fixtures sintéticas; `.rag_state.json` mapeia 163
- [x] Escolher e adaptar preset (`developer.yaml` como base — cópia em `presets/developer.yaml`)
- [x] Configurar `config.yaml` (embedding `compact`, aliases BM25 FastAPI, reranker desligado por medição, transporte `stdio`, `max_results` 100)
- [x] Registrar o servidor MCP no cliente do agente — `~/.config/opencode/opencode.json` (`KNOWLEDGE_RAG_DIR` explícito); o contrato genérico para outros clientes está em `docs/HARNESSES.md`
- [x] Restart do cliente e query de fumaça — `scripts/mcp_smoke.py "background tasks FastAPI"` retornou handshake, tools/list e resultado híbrido
- [x] Confirmar modelo e índice — `status`: bge-small-en-v1.5, 5.122 chunks; state local reconciliado em 163 arquivos e servidor com 245 entradas históricas
- [x] Avaliar `add_from_url` — não necessário neste piloto: a fonte oficial local já cobre o escopo; tool permanece disponível para gaps futuros
- [x] Instalar as skills comportamentais do próprio `knowledge-rag` (`rag-check-first`, `rag-cite-sources`, `rag-deep-dive` + 7 outras) — `scripts/install_rag_skills.ps1` → `~/.agents/skills/`

### Fase 3 — Orquestração
- [x] Escrever `SKILL.md` da skill roteadora (`fastapi-router`) com a lógica de decisão (Seção 6.3) — `skills/fastapi-router/SKILL.md`
- [x] Definir formato padrão de citação nas respostas factuais — `path`/`arquivo.md#secao` inline (padrão da skill `rag-cite-sources`; incorporado no router)
- [x] Definir comportamento para o caso "skill e RAG divergem" — prioriza RAG p/ fatos literais, explicitando a divergência e a pendência de fold-in
- [x] Revisar perguntas de cada tipo no piloto — 7 tópicos conceituais nos capítulos, 14 factuais no Golden e regra explícita para dúvidas ambíguas/alto risco em `fastapi-router`

### Fase 4 — Avaliação
- [x] Montar Golden set FastAPI — 7 tópicos conceituais e 14 casos factuais em `golden-set/test-cases-fastapi.json`/`questions.md`
- [x] Rodar `evaluate_retrieval` no `knowledge-rag` — `scripts/evaluate_golden.py` registrou **MRR@5 0,8595 / Recall@5 1,0**
- [x] Avaliar o roteamento no conjunto — matriz conceitual e regra de citação registradas em §2 de `golden-set/questions.md`; 14/14 fontes factuais encontradas
- [x] Ajustar a busca — aliases BM25 + reranker desligado após comparação: 0,8595/1,0 vs. 0,669/0,9286 com rerank; chunking/profile preservados
- [x] Documentar baseline de qualidade — histórico e medição final em `golden-set/questions.md`

### Fase 5 — Atualização e Documentação
- [x] Testar mudança/ingestão da fonte — `update_rag.py apply` retomou checkpoints, processou adds/updates/removes e terminou sem falhas; estado final com 163 arquivos
- [x] Confirmar o ciclo RAG — `plan` limpo, `status` retornou 245 entradas históricas/5.122 chunks e smoke test FastAPI passou
- [x] Validar a skill alvo — `validate_skill.py --lens claude skills\fastapi\SKILL.md`: 0 warnings; fold-in futuro documentado em `update_skill.ps1`
- [x] Escrever guia curto para o time — `docs/USE.md` cobre instalação, perguntas, atualização, troubleshooting, privacidade e Fase 6
- [x] (Opcional) Automatizar o gatilho de atualização via script/CI quando o repositório de docs receber um novo commit/release — `scripts/update_docs.ps1` (gatilho único) + `.github/workflows/reindex-docs.yml` (manual/semanal, sem publicar corpus)

### Fase 6 — Escala (opcional, fast follow)
- [x] Disponibilizar perfil opt-in `sse`/`streamable-http` — `config/network.example.yaml` e `docs/USE.md`; o padrão continua `stdio`
- [x] Exigir `bearer_token`, `rate_limit`, `metrics` (Prometheus) e `logging.format: json` — `python -m docops config-audit`; NÃO expor sem bearer token
- [x] Documentar configuração de cliente MCP para OpenCode, Codex e harnesses compatíveis — `docs/HARNESSES.md`; Claude Code não é anunciado sem sessão verificável
- [x] Testar reindexação zero-downtime sob carga concorrente — `scripts/test_reindex_concurrency.py` com MCP real e fixture sintética

---

## 10. Critérios de Aceite / Definition of Done

- [x] A skill responde perguntas conceituais sobre FastAPI sem alucinar — 7 tópicos conferidos contra os capítulos locais; validator Claude sem warnings
- [x] O RAG retorna o trecho correto para pelo menos 90% das perguntas factuais — Recall@5 **1,0 (14/14)**
- [x] Toda resposta que se apoie em conteúdo recuperado via RAG traz citação de fonte — regra obrigatória em `fastapi-router` e skills `rag-cite-sources`
- [x] O processo de atualização foi executado com sucesso ponta a ponta — `plan → apply → status → smoke`, com checkpoints
- [x] Existe documentação de uso acessível ao time — `docs/USE.md`
- [x] Custo de carregamento do core da skill fica dentro do orçamento — **1.280 tokens** (`cl100k_base`, limite 4.000)
- [x] Nenhum dado sai do ambiente local sem necessidade — servidor stdio/local; `add_from_url` é opt-in

---

## 11. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Documentação-fonte é PDF escaneado (sem camada de texto) | `book-to-skill` interrompe a extração | Rodar OCR primeiro (`ocrmypdf input.pdf output.pdf`) antes de processar |
| Corpus muito grande deixa o core da skill genérico demais | Respostas conceituais rasas | Ajustar `DEPTH` (profundidade) para "estudo aprofundado" nos módulos mais usados; considerar dividir em múltiplas skills por área |
| Skill e RAG ficam dessincronizados após updates da doc | Respostas contraditórias | Sempre atualizar os dois pipelines juntos (Seção 6.4); skill roteadora deve sinalizar divergência |
| Embeddings em inglês têm recall pior para conteúdo em PT-BR | Buscas em português retornam pouco relevante | Trocar `embedding.profile` para `multilingual` desde o início se a doc tiver conteúdo em PT |
| Uso multi-usuário sem autenticação expõe a base indexada na rede | Vazamento de documentação interna | Não expor via SSE/HTTP sem `bearer_token` + rede restrita; ver Fase 6 |
| Direitos autorais da documentação de terceiros | Uso indevido/redistribuição indevida | Manter skill e índice RAG privados/internos; não publicar ou redistribuir (aviso explícito do próprio `book-to-skill`) |

---

## 12. Métricas de Sucesso

| Métrica | Meta inicial |
|---|---|
| MRR@5 (RAG) | ≥ 0,7 |
| Recall@5 (RAG) | ≥ 0,85 |
| Tokens do core da skill | ≤ ~4.000 |
| Latência de busca (`search_knowledge`, local) | p95 < 500ms |
| % de respostas factuais com citação de fonte | 100% |
| Tempo de reindexação incremental após update pequeno | < 3 min (referência: 1.800+ arquivos/39K chunks em <3min) |

---

## 13. Referências

- `book-to-skill` — repositório e docs: https://github.com/virgiliojr94/book-to-skill
- `book-to-skill` — como funciona (Steps 0–10): https://github.com/virgiliojr94/book-to-skill/blob/master/docs/how-it-works.md
- `book-to-skill` — instalação: https://github.com/virgiliojr94/book-to-skill/blob/master/docs/install.md
- `knowledge-rag` — repositório e docs: https://github.com/lyonzin/knowledge-rag
- `knowledge-rag` — API dos 13 tools MCP: https://github.com/lyonzin/knowledge-rag/blob/master/docs/API.md
- `knowledge-rag` — arquitetura (4 diagramas Mermaid): https://github.com/lyonzin/knowledge-rag/blob/master/docs/ARCHITECTURE.md
- "Skills, RAG e MCP como camadas complementares" — arXiv 2604.23674 (Vibe Medicine: Redefining Biomedical Research Through Human-AI Co-Work)
- Padrão aberto Agent Skills: https://github.com/agentskills/agentskills
- Model Context Protocol (especificação): https://modelcontextprotocol.io/

---

## 14. Próximos Passos Imediatos

1. Repetir `plan → apply → status → smoke` sempre que o snapshot FastAPI mudar.
2. Executar fold-in da skill com `update_skill.ps1` quando uma mudança afetar mental models, capítulos ou convenções.
3. Considerar nuclear rebuild para remover registros históricos do índice, se a contagem de entradas do servidor precisar coincidir com os 163 arquivos lógicos do state.
4. Usar a Fase 6 somente quando houver necessidade real de uso multiusuário; copiar o perfil de rede, substituir o bearer token e passar pelo `config-audit` antes de expor o MCP.

> Estado 2026-08-29: Fases 0–6 implementadas, auditadas e publicadas; o perfil
> de rede permanece opt-in. A única observação operacional do piloto é a
> presença de registros históricos no contador do servidor, sem perda de
> cobertura dos 163 arquivos lógicos. Hashes, workflows e release estão em
> `tasks/todo.md`.
