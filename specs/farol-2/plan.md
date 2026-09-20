# Plano técnico: Farol 2.0

**Revisão:** 1
**Consome:** `spec.md` revisão 1
**Baseline:** `81d5dcb2e189d00406cdd9b9e671d94e3f23cd58`
**Perfil:** expandido; migração ampla e contrato público

## Abordagem escolhida

Evoluir por expand–contract, preservando os seams públicos atuais enquanto os
novos contratos 2.0 ganham implementação e evidência. O pipeline passa a ser
composto por Modules profundos: projeto, aquisição, extração/IR, síntese,
composição e backend de conhecimento. Callers conhecem poucos resultados
versionados; detalhes de RAGFlow, parsers e armazenamento ficam nos adapters.

O `knowledge-rag` atual é primeiro encapsulado sem mudar comportamento. RAGFlow
é adicionado e exercitado em candidatas isoladas. Depois da paridade, novos
projetos deixam de selecionar o legado; a contração final remove vendor, Chroma,
configuração e contratos específicos.

## Alternativas consideradas

- **Substituição direta:** rejeitada; não oferece rollback ou oráculo de paridade.
- **Dois backends permanentes:** rejeitada; duplica claims, testes e suporte.
- **RAGFlow como autoridade:** rejeitada; enfraquece portabilidade e lineage.
- **Markdown como IR:** rejeitada; perde layout, tabela, OCR e coordenadas.
- **Reimplementar book-to-skill:** rejeitada; mistura harness/modelo com core.

## Arquitetura alvo

```text
Conversa / CLI / Python
          |
 KnowledgeProject Module
          |
      operation plan
    ______|____________________________
   |             |                     |
Acquisition   Extraction/IR        Policy/Governance
 Module          Module                 Module
                   |
              IR Revision
              /         \
    Conceptual Synthesis   Knowledge Backend
          Module                Module
             |                     |
 taxonomy + skills          RAGFlow Adapter
             \                     /
              Composition Module
                       |
               router + candidate
                       |
              readers / agent harness
```

## Mapa de Modules e Interfaces

| Module | Interface proposta | Implementação existente a evoluir | Consumidores |
|---|---|---|---|
| KnowledgeProject | `start/inspect/answer/plan/apply` com resultados v2 | `docops/master.py`, `docops/operations.py`, `docops/__init__.py`, CLI | agente operador |
| Acquisition | `resolve` e `acquire` → artefatos imutáveis | `source_resolver.py`, `repository_acquirer.py`, `web_acquirer.py` | Extraction |
| Extraction/IR | `extract(artifact, policy)` → `IRDocument + receipt` | decompor `normalizer.py::normalize_file` | Synthesis, Backend |
| Extractor Registry | `capabilities/choose` com policy | novo; adapters internos/entry points autorizados | doctor, Extraction |
| Conceptual Synthesis | `prepare/submit/inspect` → candidata vinculada | generalizar enrichment em `master.py`; adapter book-to-skill | Composition |
| Taxonomy | `propose/approve/diff` | novo sobre graph/revision existentes | Synthesis, Router |
| Composition | `prepare/evaluate/promote/rollback` | `operations.py`, activation/recovery em `master.py` | readers |
| Knowledge Backend | lifecycle pequeno abaixo | extrair `RagSynchronizer` e `McpRetrievalAdapter` | Composition, Reader |
| Router | `route(query, project_revision)` → plano de consulta | substituir `retrieval.py::route_query` e template | agente leitor |
| Migration | `inspect/plan/apply/rollback` 1.x→2.0 | evoluir `adopt_project_package` | operador |

### Interface `KnowledgeBackend`

A Interface externa deve expor somente:

```text
probe(config) -> capabilities/health
prepare(project_revision, ir_revision) -> backend_candidate
apply(backend_candidate) -> index_revision
query(index_revision, query_request) -> evidence_result
snapshot(index_revision) -> snapshot_identity
discard(backend_candidate) -> receipt
close() -> receipt
```

Provisionamento, upload, polling, delete, retry e mapeamento de IDs ficam dentro
do Module. Adapters reais: `KnowledgeRagLegacyAdapter` e `RagFlowAdapter`; testes
usam um adapter controlado somente para falhas/tempo e contract fixtures.

### Interface `Extractor`

```text
describe() -> capabilities + permissions + dependency status
extract(artifact_ref, policy, budget) -> IRDocument + ExtractionReceipt
```

O registry escolhe apenas adapters autorizados capazes de atingir a fidelidade
requerida. Fallback muda o resultado de fidelidade e precisa ser observável.
Plugins de terceiros não recebem artefatos antes de opt-in persistido.

## Estrutura de pacote 2.0

```text
<project>/
├── manifest.json
├── project.json
├── taxonomy.json
├── sources/                 # metadados; originais privados fora do release
├── knowledge/
│   ├── ir/<revision>/
│   ├── lineage/
│   └── backend-mapping.json
├── skills/<topic-slug>/
│   ├── SKILL.md
│   └── chapters/
├── router/SKILL.md
├── harness.json
└── .docops/                # estado privado/checkpoints/candidatas
```

Schemas canônicos continuam em `schemas/`; `docops/schemas/` é cópia empacotada
gerada. Novos schemas previstos: `ir-document`, `ir-block`, `extraction-receipt`,
`extractor-capability`, `taxonomy`, `skill-lineage`, `backend-config`,
`backend-candidate`, `backend-mapping`, `composition-v2` e `migration-v2`.

## Parsing e IR

1. Aquisição grava artefato imutável no armazenamento privado e metadados
   publicáveis separados.
2. Registry seleciona extractor conforme MIME, assinatura, fidelity requerida,
   permissões e dependências; extensão é apenas indício.
3. Extractor produz blocos ordenados e receipt. Conteúdo suspeito é dado
   `untrusted`; confiança insuficiente vira quarentena.
4. IR validator verifica IDs, ordem, ranges, locators, hashes, direitos e budgets.
5. Revisão de IR imutável alimenta taxonomia, síntese e backend.

O adapter RAGFlow pode enviar original para seu parser quando autorizado e
importar a estrutura resultante para IR. Se um parser local produzir a IR, o
adapter indexa a projeção canônica/chunks controlados. Em ambos os casos, o
receipt registra parser/version/config e o Farol materializa a IR antes de
qualquer composição ativa.

## Taxonomia, síntese e router

- Taxonomia é grafo acíclico hierárquico com refs de cobertura. A proposta é
  revisão isolada; primeira ativação e reorganização exigem aprovação.
- Um concept tem um owner. Dependências são links, não cópias.
- O sintetizador recebe IR selecionada, taxonomia, idioma, budgets e contrato de
  lineage. Saída sem receipt/hash ou com claim sem suporte é rejeitada.
- O router classifica `conceptual|factual|hybrid`; escolhe skills por taxonomia e
  cria `QueryRequest` com projeto, revisão, filtros, as-of, região e top-k.
- Evidência é filtrada por elegibilidade antes do ranking; resultados citam a IR,
  não IDs opacos do backend.

## Integração RAGFlow

- Fixar `v0.27.2` e imagem/SDK por digest no ticket de adapter; atualizar requer
  contract tests e decisão de dependência.
- Usar HTTP autenticado para lifecycle documentado: dataset, documento, parsing,
  chunks e retrieval. MCP pode ser handoff de leitura, não lifecycle.
- Um dataset de candidata é isolado do ativo. Nomes não são identidade; mappings
  guardam IDs, revision/hash e fingerprint.
- Polling tem deadline, backoff limitado e cancelamento. Retry repete operação
  idempotente ou reconcilia por chave canônica.
- Remoto exige HTTPS, salvo loopback explicitamente permitido em desenvolvimento.
  Token vem de env/secret reference e nunca entra em manifest/receipt/log.
- Compose de desenvolvimento fica sob `config/ragflow/` e não é iniciado por
  `import docops`, `plan` ou testes core.

## Migração expand–contract

1. **Expandir contratos:** adicionar schemas/DTOs v2 sem alterar leitura 1.x.
2. **Extrair seams:** encapsular comportamento knowledge-rag atual e preservar
   gates; separar contratos editoriais do lifecycle genérico.
3. **Introduzir IR/extractors:** materializar v2 em paralelo ao corpus legado.
4. **Introduzir multi-skill/router:** gerar apenas candidatas 2.0.
5. **Adicionar RAGFlow:** indexar candidata isolada e comparar com legado.
6. **Migrar consumidores:** CLI, harness, readers, snapshots, validator, release.
7. **Promover 2.0:** novos projetos usam RAGFlow; 1.x permanece migrável/read-only.
8. **Contrair:** remover Mercado Livre/curso/página/oferta, depois knowledge-rag,
   Chroma, vendor e configurações quando seus gates independentes passarem.
9. **Governar a distribuição:** manter originais privados e emitir somente
   derivados allowlisted com provenance verificável (TK-021), sem publicar
   automaticamente.

Nenhum ticket mistura a contração destrutiva com a criação do rollback que a
torna segura.

## Remoção do desvio editorial

Inventário mínimo: `docops/presets/mercado-livre.json`, aliases em
`docops/master.py::load_project_preset`, contratos de course/page/offer em
`master.py`/`contracts.py`/schemas, exports em `__init__.py`, CLI, fixtures,
testes e docs `MASTER-*`/`master-evolution`. Preservar governança, projeto,
fontes, claims, conflitos, candidatas, readers, backup, presets genéricos e
rollback. A prova de extensibilidade de preset deve usar duas fixtures neutras
ou ser removida se a Interface deixar de precisar de preset.

## Verificação e oráculos

Cada ticket segue red → green por Interface pública. Comandos-base, ajustados
quando o ticket adicionar perfis:

```text
python -m pytest -q <teste focal>
python -m pytest -q
python -m ruff check docops tests scripts
python scripts/sync_schemas.py --check
python scripts/check_contracts.py --json
python scripts/check_documentation.py --root . --json
python scripts/check_public_seams.py --tests tests --json
python scripts/run_release_gates.py --profile core --output <tmp>
python scripts/run_release_gates.py --profile ragflow --output <tmp>
```

Oráculos independentes:

- fixtures pequenas com estrutura/locator esperado, não snapshot do parser;
- servidor fake apenas para protocolo/erros e RAGFlow real para contract/integration;
- Golden revisado separado em ajuste/holdout;
- processo reiniciado para crash/recovery;
- auditor de release para proibir corpus, segredos e contratos excluídos;
- pacote 1.x sintético para migração/rollback.
- candidato sintético para auditar a fronteira entre originais privados,
  derivados distribuíveis e provenance (TK-021).

Gates de remoção do legado: Recall@5 ≥ 1,0 nos críticos, MRR@5 ≥ 0,86,
100% de hits factuais com locator verificável, zero claim factual de skill sem
lineage, lifecycle/rebuild/recovery/rollback verdes e nenhuma regressão de
segurança.

## Ambiente e operação

- Core: Python 3.11–3.13 e matriz existente.
- Integração: Docker/Compose compatíveis, RAGFlow fixado, recursos declarados.
- Core não baixa modelo, inicia container nem acessa rede durante testes.
- Perfis de capacidade registram ambiente, corpus, concurrency, latência e
  resultados. Sem benchmark, o claim é `not_measured`.

## Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| API RAGFlow muda | adapter quebra | pin por digest + contract suite |
| Parser RAGFlow não exporta estrutura suficiente | IR incompleta | spike antes do adapter; projeção/local extractor |
| Migração vira rewrite | regressões amplas | expand–contract por consumidor |
| IR cresce sem limite | custo/latência | budgets no plan e streaming/staging |
| Synthesizer inventa lineage | skill não confiável | refs/hashes verificados contra IR |
| Upload remoto indevido | incidente de privacidade | opt-in por fonte, policy, receipt e redaction |
| Dual-run vira dupla autoridade | divergência | somente candidata/CI; IR permanece canônica |
| Remoção editorial quebra dados válidos | perda | reportar excluídos e preservar pacote 1.x |

## Gate G2

G2 passa quando H-001/H-002 têm spikes observados, schemas v2 e seams têm
contract tests planejados, todos os ACs possuem ticket, o grafo é acíclico e
nenhuma contração antecede seu rollback/paridade. Antes disso, tickets de spike
podem ficar `ready`; implementação dependente retorna à planejadora se a hipótese
falhar.
