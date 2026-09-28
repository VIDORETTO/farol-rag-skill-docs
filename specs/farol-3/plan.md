<!-- docs-gate: proposal -->

# Plano técnico: Farol 3.0

**Revisão:** 1
**Consome:** `spec.md` revisão 1
**Baseline:** `90c8229`
**Perfil:** evolutivo; sem reescrita; expand–contract sobre os Modules 2.0

## Abordagem escolhida

Fechar o circuito do usuário sobre a fundação 2.0, na ordem que destrava valor:

1. **Provar antes de construir:** criar a suíte de aceitação com corpus real
   (TK-101) — ela falha hoje e passa a ser o norte de todos os tickets.
2. **Circuito mínimo funcionando:** backend local + MCP (TK-103/104) para que o
   agente consiga consultar fatos sem RAGFlow.
3. **Valor conceitual:** tarefas de síntese/taxonomia executadas pela IA do
   usuário (TK-105/106), substituindo o scaffold estrutural.
4. **Experiência:** `add/build/connect` (TK-102, TK-109).
5. **Mais fontes:** transcrição e paper (TK-107/108).
6. **Sustentabilidade:** dieta de processo e release 3.0 (TK-110/111).

## Alternativas consideradas

- **Reescrita total:** rejeitada. IR, lineage, staging e extractors estão
  corretos; o problema é de integração e de jornada, não de fundação.
- **LLM embutido no core (API key):** rejeitada. Quebra “provider-free”, cria
  custo e credenciais; a IA do usuário já é o LLM — o Farol só precisa pedir
  tarefas bem especificadas e validar a resposta.
- **Só RAGFlow:** rejeitada para o padrão (D-01). Exige 16 GB/Docker; inviável
  como experiência de primeiro uso. Mantido como backend avançado.
- **Vector DB embutido (Chroma/LanceDB) como padrão:** adiado. FTS5/BM25 cobre
  o caso factual literal com zero dependência; embeddings locais entram como
  extra opcional medido contra o corpus de aceitação.
- **Portar o book-to-skill para dentro do core:** rejeitada. O template e as
  regras de qualidade (MIT, com atribuição) viram o **prompt da tarefa** de
  síntese; a execução continua no harness.

## Arquitetura alvo (delta sobre 2.0)

```text
farol add ──> Acquisition ──> Extractors (+ transcript, + paper) ──> IR revision
                                                                      │
farol build ─┬─> TaxonomyTask ──(IA do usuário)──> TaxonomyEngine.validate/approve
             ├─> SynthesisTask ─(IA do usuário)──> SynthesisEngine.accept (lineage)
             └─> KnowledgeBackend.apply ─┬─ LocalFtsBackend (padrão, SQLite FTS5)
                                         └─ RagFlowAdapter (opt-in)
                                                  │
farol connect ──> skills + router + MCP registration por harness
                                                  │
farol mcp (stdio) ──> search_knowledge / get_document / list_skills / get_skill
```

**Protocolo de tarefa de agente (novo seam, TK-105):** o Farol grava
`.farol/tasks/<id>.json` (tipo, instruções, projeção IR com block ids, template,
budget, critérios de aceite, schema de saída). O agente obtém com
`farol task next --json` ou pela tool MCP `next_task`, escreve a saída e envia
com `farol task submit <id> <dir>`. O Farol valida pelo engine existente e
responde `accepted` ou `rejected{reasons}`. Idempotência via request hash (já
existente em `SynthesisRequest`).

## Seams de teste propostos (confirmar antes do RED)

| Seam | Interface pública | Tickets |
|---|---|---|
| S1 CLI JSON | `farol add/build/connect/task/doctor --json` | 102, 105, 106, 109 |
| S2 MCP stdio | JSON-RPC sobre stdin/stdout de `farol mcp` | 104 |
| S3 KnowledgeBackend | contrato de `docops/backends/base.py` (conformance compartilhada local/RAGFlow) | 103 |
| S4 Extractor | `ExtractorRegistry.extract(artifact, policy) → ExtractionResult` | 107, 108 |
| S5 SynthesisEngine/TaxonomyEngine | `accept`/`validate` com saída de agente em disco | 105, 106 |
| S6 Aceitação real | `scripts/acceptance_real.py --json` sobre corpus fixado por hash | 101, 111 |

Regra: um teste por fatia vertical; valores esperados vêm do corpus/golden
revisado, nunca recalculados pelo código (anti-tautologia).

## Matriz de roteamento (SDD)

| ID | Ticket | Nível | Modelo | Lote | Motivo |
|---|---|---|---|---|---|
| TK-101 | Corpus real + suíte de aceitação | 🟡 | intermediário | — | Curadoria de licença + harness de métricas; decide o norte |
| TK-102 | Jornada `add/build` | 🔴 | forte | TK-105 | Toca `master.py`/`operations.py`/CLI; contrato público |
| TK-103 | Backend local FTS5 | 🟡 | intermediário | TK-104 | Adapter novo atrás de seam existente |
| TK-104 | Servidor MCP stdio | 🟡 | intermediário | TK-103 | Protocolo novo, isolado; depende de TK-103 |
| TK-105 | Tarefas de síntese para o agente | 🔴 | forte | TK-102 | Novo seam de protocolo + generalizar script hardcoded |
| TK-106 | Taxonomia proposta pelo agente | 🟡 | intermediário | — | Reusa protocolo de TK-105 |
| TK-107 | Extractor de transcrição (YouTube/áudio/vídeo) | 🟡 | intermediário | TK-108 | Adapter isolado + extra opcional |
| TK-108 | Extractor de paper | 🟡 | intermediário | TK-107 | Adapter isolado sobre PDF/Docling |
| TK-109 | `farol connect` + instalação pipx/uv | 🟡 | intermediário | — | Vários harnesses, arquivos de config de terceiros |
| TK-110 | Dieta de processo e superfície | 🟢→🟡 | menor | — | Mover/arquivar docs e recibos; baixo risco se só docs |
| TK-111 | Release 3.0 | 🟡 | intermediário | — | Gates, notas, publicação autorizada |

## Sequência de maior ROI

1. **TK-101** — sem régua real, qualquer melhoria é opinião. Deve falhar hoje (RED global).
2. **TK-103 → TK-104** — destrava consulta factual para todo usuário; maior efeito com menor risco.
3. **TK-105** — entrega o valor book-to-skill no caminho do produto.
4. **TK-102** — amarra 2–3 numa jornada curta (depois dos seams existirem, para não desenhar no vazio).
5. **TK-109** — distribuição e conexão com as IAs; aqui o produto vira “baixar e usar”.
6. **TK-106** — melhora a qualidade das skills em corpus multi-assunto.
7. **TK-107, TK-108** — amplia fontes, em paralelo (adapters isolados).
8. **TK-110** — pode rodar em paralelo desde o início (só docs/estado), fechar antes da release.
9. **TK-111** — release quando SC-101–105 passarem.

## Parte 2 — prontidão pública (spec-prontidao.md)

| ID | Ticket | Nível | Modelo | Lote | Motivo |
|---|---|---|---|---|---|
| TK-112 | `farol sync` | 🔴 | forte | — | Lineage + invalidação seletiva + agendadores de 3 SOs |
| TK-113 | Prompt injection | 🔴 | forte | — | Segurança transversal (extração, MCP, síntese) |
| TK-114 | Semântica opcional | 🟡 | intermediário | — | Adapter atrás do seam S3, decidido por benchmark |
| TK-115 | Escala e progresso | 🟡 | intermediário | TK-117 | Observabilidade da jornada |
| TK-116 | Biblioteca multi-pacote | 🟡 | intermediário | — | Extensão do MCP; isolamento de direitos |
| TK-117 | Erros e `doctor --fix` | 🟡 | intermediário | TK-115 | Catálogo transversal, baixo risco |
| TK-118 | Semver e upgrade | 🟡 | intermediário | — | Testes de contrato + CI cross-version |
| TK-119 | Prova de valor | 🟡 | intermediário | — | Script opt-in com harness externo |
| TK-120 | Site e exemplos | 🟢 | menor | — | Docs geradas + CI estrito |
| TK-121 | Distribuição confiável | 🟡 | intermediário | — | Workflows de release/segurança |
| TK-122 | Beta | — | humano | — | Recrutamento e triagem; não é código |

### Sequência completa em ondas

Não execute tudo ao mesmo tempo: cada onda termina com gate verde antes da próxima.

1. **Onda A — régua e base:** TK-101, TK-110, TK-103, TK-104.
2. **Onda B — valor:** TK-105, TK-102, TK-106, TK-113 (segurança entra junto com a síntese, não depois).
3. **Onda C — uso real:** TK-109, TK-117, TK-112, TK-108, TK-107.
4. **Onda D — alcance e estabilidade:** TK-114, TK-115, TK-116, TK-118.
5. **Onda E — confiança pública:** TK-119, TK-111, TK-121, TK-120.
6. **Onda F — beta:** TK-122 → correções 3.0.x → **divulgação**.

Seams adicionais a confirmar: S7 agendador do SO (TK-112, via `--dry-run`),
S8 envelope `untrusted_content` do MCP (TK-113), S9 runner de benchmark com
harness fake (TK-119).

## Riscos

| Risco | Mitigação |
|---|---|
| Qualidade da skill varia por modelo do usuário | Rubrica R-01 no validador + rejeição com motivo; golden de perguntas conceituais |
| Termos do YouTube / direitos | D-02; `rights`+`purpose` obrigatórios; nada adquirido é distribuído |
| Quebra de usuários 2.0 | Aliases `docops`, schemas 2.0 lidos; migração explícita |
| Escopo espalhando em `master.py` | TK-102 extrai só o necessário para a jornada; parar e replanejar se diff > previsto |
| Memória da VPS (3,8 GB) nos testes | ASR e Docling só em perfis opt-in; nunca deixar processos rodando |

## Regras para a IA executora

1. Leia `spec.md`, este plano e o ticket inteiro antes de editar.
2. Um ticket por vez; RED observado antes do GREEN; registre o RED na evidência.
3. Não altere contratos 2.0 sem o ticket autorizar; preserve aliases.
4. Se o diff sair dos `owned_areas`, pare e retorne à planejadora.
5. Evidência curta em `evidence/TK-1xx.md`; nada de histórico em `AGENTS.md`/`tasks/todo.md`.
