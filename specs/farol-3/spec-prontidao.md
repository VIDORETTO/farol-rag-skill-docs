<!-- docs-gate: proposal -->

# Especificação — Parte 2: prontidão pública do Farol 3.0

**Esforço:** `farol-3` · **Revisão:** 1 · **Estado:** proposta
**Complementa:** `spec.md` (Parte 1: circuito do produto, TK-101–TK-111)

## Por que a Parte 1 não basta para divulgar

A Parte 1 fecha o circuito `fonte → skill + evidência → IA do usuário`. Um
produto divulgado para qualquer pessoa, em qualquer caso de uso, ainda
precisa responder:

| # | Pergunta de quem adota | Lacuna após a Parte 1 |
|---|---|---|
| L1 | “Minhas fontes mudam; o conhecimento acompanha?” | `reconcile` 2.0 existe, mas fora da jornada; não há `sync` agendável. |
| L2 | “Um documento malicioso pode sequestrar minha IA?” | Dado ≠ instrução está só em texto de skill; nada detecta/sinaliza injeção nos hits do MCP nem nas skills geradas. |
| L3 | “Pergunto em PT sobre docs em EN, funciona?” | FTS5/BM25 é lexical; consultas cross-lingual e paráfrases falham. |
| L4 | “Aguenta um livro de 1.000 páginas, 5 mil páginas de docs ou um vídeo de 3 h?” | Sem benchmark, progresso ou budget de memória medidos (AC-033 2.0 exige claim medido). |
| L5 | “Tenho vários projetos de conhecimento.” | MCP e router atendem um pacote; não há biblioteca local nem roteamento entre pacotes. |
| L6 | “Quando algo falha, sei o que fazer?” | Erros tipados existem, mas mensagens/ações para humanos e progresso não são contrato. |
| L7 | “Se eu atualizar o Farol, meus pacotes quebram?” | Sem política semver/deprecação 3.x nem testes de upgrade entre versões. |
| L8 | “Vale a pena? Quanto melhora minha IA?” | Nenhuma medição “com vs. sem Farol” (acerto, citações, tokens). |
| L9 | “Onde aprendo e vejo exemplos?” | Sem site de docs, galeria de exemplos, pacotes demo, GIF/vídeo. |
| L10 | “Posso confiar no binário?” | Attestation/assinatura `not-configured`; sem SBOM publicado nem imagem container. |
| L11 | “Alguém além do autor já usou?” | Zero usuários externos; maturidade exige beta com feedback real. |

## Jornadas e critérios de aceite

### US-107 — Conhecimento que acompanha a fonte (P1)
- **AC-118** — `farol sync` detecta mudança (hash/ETag/commit/data do vídeo) e
  reprocessa só o afetado; mudança factual ativa sozinha após gates; mudança
  conceitual gera tarefa de síntese só para skills alcançadas pelo lineage.
- **AC-119** — `farol sync --schedule` imprime/instala agendamento (cron,
  systemd timer, Task Scheduler) sem daemon próprio; `--dry-run` obrigatório no primeiro uso.

### US-108 — Segurança contra conteúdo hostil (P1)
- **AC-120** — Extração marca blocos com padrões de injeção (instruções ao
  agente, exfiltração, ferramentas, texto oculto/zero-width, HTML oculto) com
  `risk` no bloco; hits do MCP vêm delimitados como dado não confiável e com `risk`.
- **AC-121** — Skills submetidas pelo agente passam por scanner (instruções
  imperativas vindas da fonte, links/comandos suspeitos); finding bloqueia aceite.
- **AC-122** — Suíte adversarial (fixtures de injeção conhecidas) roda no gate.

### US-109 — Busca que entende o significado (P2)
- **AC-123** — Extra `semantic` (modelo de embedding multilíngue ONNX pequeno,
  CPU, sem API) habilita busca híbrida BM25 + vetor com fusão RRF.
- **AC-124** — Ganho medido no corpus TK-101 (incluindo perguntas PT sobre fonte
  EN); se não superar BM25 por margem declarada, não vira padrão.

### US-110 — Escala honesta (P1)
- **AC-125** — Benchmarks reproduzíveis (livro ~1.000 p., site ~5.000 páginas,
  vídeo 3 h, repositório médio) publicam tempo, pico de RAM, disco e tamanho do
  índice por perfil de máquina; README só afirma o que foi medido.
- **AC-126** — `build` mostra progresso, respeita `--max-memory`/`--workers`,
  é interrompível e retomável sem refazer extrações concluídas.

### US-111 — Biblioteca de conhecimento (P2)
- **AC-127** — `farol library` lista pacotes do usuário; um único `farol mcp
  --library` atende vários pacotes com `package` como filtro e router global
  escolhendo pacote/skill.
- **AC-128** — Isolamento: filtros e direitos de um pacote nunca vazam para outro.

### US-112 — Erros que ensinam (P1)
- **AC-129** — Todo erro público tem `code`, mensagem humana, causa provável e
  `next_action` executável; catálogo em `docs/ERRORS.md` validado contra o código.
- **AC-130** — `farol doctor --fix` corrige o que é seguro (extras ausentes,
  índice corrompido reconstruível, config de harness) e explica o resto.

### US-113 — Estabilidade entre versões (P1)
- **AC-131** — Política semver pública: CLI `--json`, tools MCP, layout do
  pacote e API Python são contrato; deprecação dura ≥ 1 minor com aviso.
- **AC-132** — Teste de upgrade: pacote gerado pela versão N é lido/servido pela
  N+1; pacotes 2.0 migram via `farol migrate` com relatório.

### US-114 — Prova de valor (P1)
- **AC-133** — Benchmark “com vs. sem Farol”: mesmas perguntas do golden,
  mesmo modelo/harness, medindo acerto, citações verificáveis, alucinações e
  tokens de contexto; resultado e método publicados e reproduzíveis.

### US-115 — Documentação e exemplos (P1)
- **AC-134** — Site de docs (MkDocs Material, GitHub Pages) com: quickstart
  por harness, receitas por fonte (docs, livro, paper, YouTube, repo), conceitos,
  referência CLI/MCP gerada do código, troubleshooting, FAQ de direitos.
- **AC-135** — Galeria de 3–5 pacotes demo gerados de fontes com licença que
  permite redistribuição, reproduzíveis por um comando; GIF/vídeo curto no README.

### US-116 — Distribuição confiável (P1)
- **AC-136** — Release com attestation de proveniência (GitHub/Sigstore), SBOM
  CycloneDX e checksums; imagem container opcional para `farol mcp`.

### US-117 — Beta antes da divulgação ampla (P1)
- **AC-137** — Beta fechado com ≥ 5 usuários externos em ≥ 3 harnesses e ≥ 4
  tipos de fonte; feedback triado em issues; critério de saída: zero bug
  bloqueador aberto e SC-101 cumprido por usuários (não pelo autor).

## Critérios de sucesso adicionais

- **SC-106** Nenhum hit do MCP sem delimitação de dado não confiável; suíte adversarial 100%.
- **SC-107** Benchmark “com vs. sem” publicado com ganho mensurável em acerto citado.
- **SC-108** Upgrade N→N+1 verde em CI; política semver publicada.
- **SC-109** Beta concluído pelo critério de saída do AC-137.

## Decisões abertas

| ID | Decisão | Recomendação |
|---|---|---|
| D-05 | Modelo de embedding do extra `semantic`. | Multilíngue pequeno em ONNX (ex.: família `multilingual-e5-small`), fixado por hash; escolher pelo benchmark AC-124. |
| D-06 | Hospedagem de docs e domínio. | GitHub Pages no próprio repo; domínio próprio opcional. |
| D-07 | Pacotes demo: quais fontes. | Documentação OSS com licença permissiva + 1 livro CC-BY + 1 paper CC-BY + 1 vídeo CC-BY. |
| D-08 | Beta: recrutamento e canal. | GitHub Discussions + issues rotuladas `beta`. |
