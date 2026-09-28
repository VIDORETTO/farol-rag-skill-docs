<!-- docs-gate: proposal -->

# Especificação: Farol 3.0 — qualquer fonte vira conhecimento utilizável por qualquer agente

**Esforço:** `farol-3`
**Revisão:** 1
**Estado:** aceita (decisões em [decisions.md](decisions.md))
**Baseline observado:** `90c8229` (`main`, release: prepare Farol 2.0.0rc1)
**Consome:** `specs/farol-2/` (entregue como fundação), `CONTEXT.md`, ADR 0001–0003

## Intenção original (o espírito do projeto)

> `qualquer fonte → pacote de conhecimento → agente responde com contexto e evidência`

Farol nasceu como a junção de duas ideias:

| Ideia | O que traz | Papel no Farol |
|---|---|---|
| **book-to-skill** | Destila um livro em `SKILL.md` (~4k tokens) + capítulos sob demanda, glossário, padrões e cheatsheet. O agente *entende* o assunto. | Camada **conceitual** (skills temáticas). |
| **RAGFlow** | Parsing profundo (DeepDoc), chunking por template (book, paper, laws, QA…), retrieval híbrido com citação. O agente *confirma* fatos literais. | Camada **factual** (evidência com locator). |

O **router** decide quando usar cada camada. O público-alvo é qualquer pessoa que
baixe o Farol e o conecte à própria IA (Claude Code, Codex, Cursor, Copilot, Amp,
OpenCode ou qualquer cliente MCP), para **qualquer caso de uso**: documentação
técnica, livros, papers, vídeos do YouTube, podcasts, repositórios.

## Diagnóstico do estado atual (2.0.0rc1)

O que está sólido e deve ser **preservado**:

- IR canônica com blocos, relações e locators (`docops/ir/`), registry de
  extractors com fidelidade declarada (MD/HTML, PDF+OCR, DOCX/EPUB, repositório).
- `SynthesisEngine` que valida budgets, owner único, idioma e lineage por bloco.
- `TaxonomyEngine` com proposta/aprovação/CAS.
- Adapter RAGFlow `0.27.2`, staging/promoção atômica, leases, rollback, schemas.
- Postura de segurança (dado ≠ instrução, SSRF, traversal, redaction).

Lacunas que impedem o produto de cumprir a promessa:

| # | Lacuna | Evidência | Impacto |
|---|---|---|---|
| G1 | O caminho principal (`farol run`) gera uma skill **estrutural** (lista de headings), não uma skill destilada. | `docops/generation.py:119-180` (“This structural scaffold contains headings and provenance only”). | O valor “book-to-skill” não chega ao usuário. |
| G2 | A síntese real só existe num script de perfil com fixture e taxonomia **hardcoded** (exige exatamente 2 docs `acme`). | `scripts/run_book_to_skill_profile.py:165-200`. | Não há jornada de síntese para fontes do usuário. |
| G3 | O router e a skill operadora mandam o agente chamar o MCP `search_knowledge`, mas **nenhum servidor MCP é distribuído** desde a remoção do `knowledge-rag`. | `docops/templates/router.md:19-20`; ausência de servidor em `docops/`; `harness.py` só descreve o adapter. | O agente leitor não consegue consultar fatos. |
| G4 | Retrieval factual real só com RAGFlow externo (requisito oficial ≥4 vCPU/16 GB RAM, Docker, token, digest). Sem ele, o pacote é `corpus-ready`, não consultável. | README §Configuração; `retrieval.py` é “diagnóstico/TDD”. | A maioria dos usuários não terá RAGFlow; o produto “não funciona” fora da caixa. |
| G5 | Fontes prometidas na visão não existem: YouTube/áudio/vídeo (transcrição com `timestamp`), papers (seções, abstract, referências, DOI). | `grep youtube/transcri/arxiv` sem extractor; backlog 2.0 adiou “ASR/áudio/vídeo”. | Metade dos casos de uso da visão fica de fora. |
| G6 | Taxonomia proposta por heurística determinística de headings; não entende o conteúdo. | `docops/taxonomy.py` (“Deterministic taxonomy proposals”). | Skills espelham a árvore de arquivos, o que o próprio `CONTEXT.md` manda evitar. |
| G7 | Toda validação de qualidade usou uma fixture sintética de 131 palavras. Nunca houve um livro, paper, site ou vídeo real ponta a ponta. | `specs/farol-2/evidence/TK-011.md`. | Não sabemos se o produto entrega valor real. |
| G8 | O processo pesa mais que o produto: `state.json` com 53 KB de recibos, 165 Markdown em `docs/`+`specs/`, gate de 25 etapas, `master.py` (6k linhas) e `operations.py` (4,1k). | `wc`/`du` no baseline. | Custo alto de manutenção e de onboarding para contribuidores. |
| G9 | Superfície de CLI extensa (`lifecycle`, `init`, `project`, `v2`, `supervisor`…) para o usuário final. | README §Hierarquia canônica. | Primeira experiência confusa. |

**Veredito:** não é caso de refatoração total. A fundação 2.0 (IR, extractors,
lineage, staging, RAGFlow) é exatamente o que um produto maduro precisa. O que
falta é **fechar o circuito do usuário** (G1–G4), **ampliar fontes** (G5–G6),
**provar com corpus real** (G7) e **enxugar processo e superfície** (G8–G9).
São mudanças localizadas de alto efeito, não reescrita.

## Problema e resultado desejado

Hoje um usuário que instala o Farol obtém um pacote validado, mas sua IA não
recebe uma skill útil nem consegue consultar fatos sem montar RAGFlow. Farol 3.0
deve permitir que qualquer usuário, em uma máquina comum e sem serviços externos,
execute:

```text
farol add <fonte>...          # docs, pasta, URL, repo, PDF/EPUB/DOCX, paper, YouTube, áudio
farol build                   # IR → taxonomia → skills destiladas (pela própria IA) → índice
farol connect <harness>       # instala skills + registra MCP no Claude Code/Codex/Cursor/...
```

e, a partir daí, a IA do usuário responde perguntas conceituais pelas skills e
perguntas factuais pelo MCP, com citação verificável, sobre qualquer uma dessas
fontes. RAGFlow continua suportado como backend avançado opt-in.

## Consumidores e atores

- **Usuário final:** instala por `pipx`/`uv`, aponta fontes, conecta sua IA.
- **Agente operador (a IA do usuário):** conduz `add/build`, realiza a destilação
  e a proposta de taxonomia quando o Farol emite pedidos de síntese.
- **Agente leitor:** carrega skills e consulta o MCP `farol`.
- **Mantenedor:** mantém extractors, backends, releases.

## Escopo

### Incluído

- Jornada de 3 comandos (`add`, `build`, `connect`) sobre os Modules 2.0.
- Síntese conceitual no caminho do produto via **protocolo de tarefas para o
  agente** (o core continua sem chamar modelo; a IA do usuário executa).
- Taxonomia proposta pelo agente, validada pelo `TaxonomyEngine`.
- Servidor **MCP stdio** distribuído (`farol mcp`) com `search_knowledge`,
  `get_document`, `list_skills`, `get_skill`.
- Backend factual **local padrão** sem dependências externas (D-01).
- Extractors: **transcrição** (YouTube/legendas, áudio/vídeo local com ASR
  opcional) com locator `timestamp`; **paper** (arXiv/PDF científico) com seções,
  abstract, referências e DOI.
- Instalação `pipx/uv`, `farol doctor`, `farol connect` para os principais harnesses.
- Suíte de aceitação com **corpus real licenciado** (livro CC, paper CC-BY, vídeo
  CC-BY, site de docs open source).
- Dieta de processo: arquivo histórico, estado enxuto, gate de release reduzido.

### Excluído

- LLM embutido, escolha de provedor, armazenamento de chaves de IA no core.
- SaaS, multi-tenant, UI web (poderá vir depois de métricas reais).
- Download de conteúdo que viole termos/direitos: o usuário declara a base
  legal; o Farol registra e bloqueia redistribuição (herdado de AC-031).
- Compreensão multimodal de imagens/diagramas (continua pós-3.0).

## Jornadas e critérios de aceite

### US-101 — Primeiro pacote útil em minutos (P1)

- **AC-101** — Em máquina limpa (Linux/macOS/Windows, Python 3.11–3.13),
  `pipx install farol` (ou `uv tool install`) + `farol doctor` passam sem Docker,
  rede externa obrigatória ou credenciais.
- **AC-102** — `farol add ./docs && farol build` produz pacote válido com índice
  **consultável** pelo backend local.
- **AC-103** — `farol connect claude-code|codex|cursor|opencode|generic` instala
  skills/router e registra o MCP de forma idempotente, com `--dry-run` e remoção.

### US-102 — Skill destilada de verdade (P1)

- **AC-104** — `farol build` sem síntese concluída deixa o pacote `facts-ready`
  e emite **tarefas de síntese** (uma por tópico) com projeção IR, template,
  budget e critérios; nunca publica scaffold como se fosse skill destilada.
- **AC-105** — A IA do usuário conclui as tarefas (`farol synth next/submit`);
  o `SynthesisEngine` aceita somente saídas com lineage válida e budget; rejeições
  retornam motivo acionável para nova tentativa.
- **AC-106** — Para um livro real (≥ 50k tokens), a skill gerada atinge a rubrica
  de qualidade R-01 (frameworks, decisões, anti-padrões, glossário, cheatsheet)
  e `SKILL.md` ≤ budget, com capítulos sob demanda.

### US-103 — Taxonomia que entende o conteúdo (P2)

- **AC-107** — O Farol emite tarefa de proposta de taxonomia; a proposta do
  agente é validada (cobertura, owner único, órfãos) e requer aprovação na
  primeira ativação; o proposer heurístico continua como fallback declarado.

### US-104 — Consultar fatos pela própria IA (P1)

- **AC-108** — `farol mcp` (stdio) expõe `search_knowledge`, `get_document`,
  `list_skills`, `get_skill`; cada hit traz `source`, `revision` e locator
  (`section|line|page|timestamp|…`).
- **AC-109** — Ausência de evidência retorna `insufficient_evidence`; evidência
  revogada nunca aparece (herdado de AC-017).
- **AC-110** — O mesmo servidor atende backend local ou RAGFlow sem mudar o
  contrato das tools.

### US-105 — Qualquer fonte (P1)

- **AC-111** — URL do YouTube com legendas disponíveis gera IR de transcrição
  com blocos por segmento/capítulo e locator `timestamp` (`?t=` clicável);
  sem legendas, ASR local opcional (`faster-whisper`) com fidelidade
  `external-converter`; sem ambos, erro tipado.
- **AC-112** — Áudio/vídeo local (mp3/mp4/wav/m4a/webm) segue o mesmo caminho via ASR opcional.
- **AC-113** — Paper (arXiv ID/URL ou PDF científico) gera IR com título,
  autores, abstract, seções numeradas, referências e DOI/arXiv ID; locator
  `page` + `section`.
- **AC-114** — Toda fonte nova passa pela mesma conformance: conteúdo,
  estrutura, locator, fidelidade, uso por skill e por RAG.

### US-106 — Produto estável e sustentável (P1)

- **AC-115** — A suíte de aceitação real (corpus licenciado fixado por hash)
  roda em CI agendado e mede recall@5, cobertura de citações e rubrica de skill.
- **AC-116** — `docops` e contratos 2.0 continuam funcionando (alias/compat) até
  a remoção anunciada; nenhum schema distribuído quebra sem ticket autorizando.
- **AC-117** — Histórico operacional sai de `state.json`/`docs/` para arquivo;
  `state.json` fica ≤ 10 KB; gate de release principal ≤ 10 etapas.

## Requisitos

- **FR-101** Jornada `add/build/connect` sobre `KnowledgeProject`, sem novo estado paralelo.
- **FR-102** Protocolo de tarefas de agente (síntese e taxonomia) com request/receipt existentes.
- **FR-103** Servidor MCP stdio distribuído no wheel, sem dependência obrigatória nova.
- **FR-104** Backend factual local conforme `KnowledgeBackend` (D-01).
- **FR-105** Extractors de transcrição e paper no registry, com fidelidade honesta.
- **FR-106** `connect` por harness, idempotente e reversível.
- **FR-107** Suíte de aceitação com corpus real licenciado e métricas publicadas.
- **FR-108** Dieta de processo sem perder rastreabilidade.

## Critérios de sucesso

- **SC-101** Instalação limpa → primeira resposta citada da IA do usuário em ≤ 10 min
  (docs pequenas), sem Docker.
- **SC-102** Recall@5 ≥ 0,9 e 100% de hits com locator no corpus real de aceitação (backend local).
- **SC-103** Skill de livro real aprovada na rubrica R-01 por revisão humana.
- **SC-104** YouTube CC-BY e paper CC-BY respondem perguntas factuais com `timestamp`/`page` corretos.
- **SC-105** Zero regressão nos testes 2.0 mantidos; CI verde em Linux/macOS/Windows.

## Decisões abertas (bloqueiam os tickets indicados)

| ID | Decisão | Recomendação | Bloqueia |
|---|---|---|---|
| D-01 | Backend factual local padrão, revendo ADR 0001 (“RAGFlow estratégico, sem dois backends permanentes”). | **Sim:** SQLite FTS5 (stdlib, BM25) como padrão; embeddings locais opcionais; RAGFlow opt-in avançado. ADR 0004 registra a mudança. | TK-103, TK-104 |
| D-02 | Aquisição do YouTube: `yt-dlp` como extra opcional, só legendas/áudio para uso pessoal declarado; redistribuição bloqueada. | **Sim**, extra `media`, com `rights`/`purpose` obrigatórios. | TK-107 |
| D-03 | Nome do pacote no PyPI (`consulta-documentacao` hoje) e comando `farol` como principal. | Publicar como `farol-kit` (ou nome disponível) mantendo alias `docops`. | TK-110 |
| D-04 | Encerrar 2.0 (PR #16) antes de iniciar 3.0 ou seguir em paralelo. | Aprovar/mergear PR #16 e marcar 2.0.0rc1 como base; 3.0 parte de `main`. | início |
