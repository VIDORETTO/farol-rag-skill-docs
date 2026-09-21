
<div align="center">

# Farol

<p>
  <img src="assets/farol-logo-horizontal.png" alt="Farol" width="780">
</p>

## Documentação confiável para agentes de IA

Transforme uma fonte de documentação em um pacote portátil, versionado e
consultável — com **IR canônica**, **skills**, **roteador**, RAGFlow opcional e
evidências verificáveis.

<p>
  <a href="https://github.com/VIDORETTO/farol-rag-skill-docs/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/VIDORETTO/farol-rag-skill-docs/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/VIDORETTO/farol-rag-skill-docs/releases"><img alt="Release mais recente" src="https://img.shields.io/github/v/release/VIDORETTO/farol-rag-skill-docs?display_name=tag&sort=semver"></a>
  <img alt="Python 3.11 ou superior" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <a href="https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/LICENSE"><img alt="Licença MIT" src="https://img.shields.io/github/license/VIDORETTO/farol-rag-skill-docs"></a>
  <img alt="RAGFlow externo" src="https://img.shields.io/badge/RAGFlow-external%20%7C%20opt--in-0f766e">
</p>

**Estado atual:** snapshot Farol 2.0 na branch `farol-v3`; a última release pública do pacote continua sendo [v1.1.0](https://github.com/VIDORETTO/farol-rag-skill-docs/releases/tag/v1.1.0).

</div>

> **Em uma linha:** <code>fonte → pacote de conhecimento → agente capaz de responder com contexto e evidência</code>.

## Navegação

**Começar:** [instalação](#instalacao) · [primeiro pacote](#primeiro-pacote) · [desenvolvimento](#desenvolvimento)

**Entender:** [arquitetura](#arquitetura) · [segurança](#seguranca-e-limites) · [estrutura do repositório](#estrutura-do-repositorio)

**Aprofundar:** [documentação](#documentacao) · [estado Farol 2.0](#estado-farol-20) · [contribuição](CONTRIBUTING.md)

**Comunidade:** [governança](community/GOVERNANCE.md) · [suporte](community/SUPPORT.md)

## O que é

O <code>Farol</code> é um operador determinístico para construir
bases de conhecimento para agentes. Ele recebe uma fonte — pasta, arquivo, URL,
repositório Git ou nome de catálogo — e produz um pacote com:

| Camada | Papel |
| --- | --- |
| <code>skill/</code> | Conceitos, padrões, glossário e orientação de alto nível. |
| <code>router/</code> | Decide quando usar a skill e quando buscar evidência literal. |
| <code>rag/</code> | Corpus normalizado, proveniência e estado para indexação externa no RAGFlow. |
| <code>manifest.json</code> | Identidade, licença, hashes, estado, métricas e checkpoints. |
| <code>harness.json</code> | Instruções de integração com OpenCode, Codex ou outro harness compatível. |

O projeto não é um chatbot, não executa modelos, não escolhe provedor e não
exige chave de API. O harness externo continua responsável por carregar o
contexto, consultar o MCP quando necessário e produzir a resposta final.

### O que torna o pacote confiável

- **Separação clara:** entendimento conceitual nas skills; fatos literais no RAGFlow.
- **IR canônica:** extractors preservam blocos, relações e locators antes da síntese ou indexação.
- **Rastreabilidade:** respostas factuais apontam para <code>path#seção</code> ou <code>path:linha</code>.
- **Fail-closed:** ambiguidade, licença desconhecida, revogação e evidência ausente bloqueiam o avanço.
- **Recuperação:** staging, leases, checkpoints, journal, backup e rollback preservam a geração ativa.
- **Portabilidade:** o núcleo funciona localmente, sem modelo, banco ou serviço obrigatório; RAGFlow e OCR são perfis opt-in.

## Visão rápida

| Item | Estado |
| --- | --- |
| Entrada | Nome, URL, repositório Git, pasta ou arquivo local |
| Saída | Pacote autocontido com skill, router, corpus, manifesto e harness |
| Runtime | Python 3.11+ |
| RAG | Backend externo RAGFlow `0.27.2`; integração opt-in com endpoint, token e imagem fixados por digest |
| OCR | Docling `2.129.0` + ONNX Runtime `1.30.0` + RapidOCR no perfil Python 3.13 |
| Distribuição | Release pública v1.1.0; o snapshot Farol 2.0 ainda exige handoff e publicação manual |
| Exemplos públicos | Fixtures sintéticas em <code>documents/fixtures/</code> |

## Instalação

### Usar a release pública

> O produto se chama **Farol**. A wheel da release pública `v1.1.0` ainda usa o
> identificador técnico `consulta-documentacao` para preservar compatibilidade
> com a distribuição já publicada.

A distribuição pública é feita pelo [GitHub Release v1.1.0](https://github.com/VIDORETTO/farol-rag-skill-docs/releases/tag/v1.1.0).
Baixe a wheel e instale-a em um ambiente virtual:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install ./consulta_documentacao-1.1.0-py3-none-any.whl
python -m docops --help
~~~

No Windows PowerShell:

~~~powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install .\\consulta_documentacao-1.1.0-py3-none-any.whl
python -m docops --help
~~~

O núcleo não tem dependências obrigatórias além do Python. Para conferir a
integridade do download, compare o hash da wheel com <code>SHA256SUMS</code>
publicado na release.

### Trabalhar a partir do código-fonte

~~~bash
git clone https://github.com/VIDORETTO/farol-rag-skill-docs.git
cd farol-rag-skill-docs
python scripts/bootstrap.py --dev
python -m docops doctor --json
~~~

O bootstrap cria o ambiente e instala o perfil de desenvolvimento em modo
editável. Para executar os perfis externos de RAGFlow e OCR, use um
interpretador Python 3.13 e instale os extras fixados:

~~~bash
python -m pip install --editable ".[dev,formats,ragflow,ocr]"
~~~

Há wrappers equivalentes em <code>scripts/bootstrap.sh</code> e
<code>scripts/bootstrap.ps1</code>.

## Primeiro pacote

O fluxo abaixo usa apenas a fixture sintética pública <code>acme-docs</code>. Ela
não contém documentação de terceiros e é segura para reproduzir o caminho completo.

### 1. Resolver a fonte

~~~bash
python -m docops resolve ./documents/fixtures/acme-docs --json
~~~

Somente leitura: identifica a fonte sem gerar artefatos.

### 2. Inspecionar o plano

~~~bash
python -m docops plan ./documents/fixtures/acme-docs --output ./artifacts/acme --slug acme --license MIT --redistribution private-only --json
~~~

O plano mostra mudanças, políticas e bloqueios antes de qualquer promoção.

### 3. Gerar e validar

~~~bash
python -m docops run ./documents/fixtures/acme-docs --output ./artifacts/acme --slug acme --license MIT --redistribution private-only
python -m docops validate ./artifacts/acme --json
~~~

O <code>run</code> escreve em staging, valida o resultado e só então promove a
composição. Uma falha não substitui a geração ativa por um pacote incompleto.

### 4. Preparar avaliação

~~~bash
python -m docops golden-candidates ./artifacts/acme --json
~~~

As perguntas geradas são candidatas. Um Golden Set oficial precisa de revisão
humana antes de virar critério de publicação.

### 5. Habilitar a integração RAGFlow quando necessário

Configure o perfil externo com credenciais fora do repositório. Em Bash:

~~~bash
export DOCOPS_RAGFLOW_ENDPOINT=https://...
export DOCOPS_RAGFLOW_TOKEN=<secret>
export DOCOPS_RAGFLOW_IMAGE_DIGEST=<repository>@sha256:<64-hex>
export DOCOPS_RAGFLOW_SDK_VERSION=0.27.2
python scripts/run_release_gates.py --profile ragflow --json
~~~

No Windows PowerShell, use `$env:DOCOPS_RAGFLOW_*` com os mesmos valores.

O core não inicia containers nem faz rede. Sem os inputs externos, o perfil
falha fechado como `blocked`/`not_run`.

### Escolha da rota no agente

| Pergunta | Rota |
| --- | --- |
| “Qual padrão devo usar para fazer X?” | <code>skill/</code>, para raciocínio e orientação. |
| “Qual é o default, assinatura ou versão?” | <code>rag/</code>, para o trecho literal com fonte. |
| “A evidência é ambígua ou sensível?” | Skill para interpretar + RAG para confirmar. |

## O pacote gerado

~~~text
artifacts/acme/
├── manifest.json          # identidade, licença, hashes e estado terminal
├── config.yaml            # configuração relativa do pacote
├── harness.json           # hand-off para o harness externo
├── skill/
│   ├── SKILL.md           # conhecimento conceitual principal
│   └── ...                # capítulos, glossário e auxiliares
├── router/
│   └── SKILL.md           # regra skill versus RAG
├── rag/
│   ├── documents/         # documentos normalizados
│   ├── sources.json       # proveniência
│   ├── index.json         # estado e métricas do índice
│   └── data/              # dados locais quando indexado
└── .docops/               # estado, checkpoints e evidências operacionais
~~~

O diretório <code>.docops/</code> é estado operacional: não deve ser tratado
como corpus nem compartilhado sem revisão. O pacote só é consultável quando
<code>python -m docops validate &lt;pacote&gt;</code> passa.

## Arquitetura

~~~mermaid
flowchart LR
    A["Fonte<br/>nome · URL · Git · pasta"] --> B["resolve"]
    B --> C["plan<br/>diff + políticas"]
    C --> D["run<br/>staging + validação"]
    D --> E["Pacote versionado"]
    E --> S["skill<br/>conceitos"]
    E --> R["router<br/>decisão de rota"]
    E --> I["IR canônica<br/>blocos + locators"]
    I --> G["RAGFlow externo<br/>fatos literais"]
    E --> M["manifest<br/>evidências"]
    S --> H["Harness externo"]
    R --> H
    G -. opt-in / externo .-> H
~~~

O núcleo mantém uma única autoridade editorial e expõe operações de lifecycle
com estado versionado:

1. **Resolver** normaliza a identidade da fonte e aplica limites de aquisição.
2. **Planejar** calcula um plano imutável sem alterar o destino ativo.
3. **Gerar** normaliza documentos, produz skill/router/RAG e registra evidências.
4. **Validar** confere manifesto, schemas, IR, composição, proveniência e políticas.
5. **Promover** exige os gates corretos; aprovação, publicação e rollback são explícitos.
6. **Operar** usa eventos idempotentes, worker retomável, readers pinados e snapshots seguros.

Para o mapa completo de módulos e fronteiras, consulte
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## CLI e API

Use <code>python -m docops ...</code> para garantir que a CLI está ligada ao
mesmo Python do ambiente ativo. No código atual, o launcher de marca é
<code>farol ...</code>; <code>docops ...</code> continua disponível como alias de
compatibilidade. A release publicada <code>v1.1.0</code> ainda deve ser operada
com <code>python -m docops</code>, pois foi empacotada antes do rebrand.

### Comandos do dia a dia

| Comando | Função | Efeito no pacote ativo |
| --- | --- | --- |
| <code>resolve &lt;fonte&gt;</code> | Identifica a origem. | Nenhum |
| <code>plan &lt;fonte&gt; --output &lt;pacote&gt;</code> | Calcula diff, políticas e bloqueios. | Nenhum |
| <code>run &lt;fonte&gt; --output &lt;pacote&gt;</code> | Gera, valida e promove. | Controlado por staging |
| <code>validate &lt;pacote&gt;</code> | Confere o contrato do pacote. | Nenhum |
| <code>golden-candidates &lt;pacote&gt;</code> | Gera perguntas não revisadas. | Escreve evidência |
| <code>evaluate --package ...</code> | Mede recuperação contra Golden revisado. | Registra avaliação |
| <code>config-audit &lt;config.yaml&gt;</code> | Audita transporte configurado. | Nenhum |
| <code>cleanup &lt;pacote&gt;</code> | Remove apenas resíduos expirados e não retomáveis. | Limitado e protegido |

### Hierarquia canônica

Os aliases planos continuam disponíveis durante a migração. Para novos
integradores, prefira a hierarquia canônica:

~~~text
docops lifecycle status
docops lifecycle source {register,reconcile}
docops lifecycle worker {list,run}
docops lifecycle candidate {enrichment-request,enrich,approve,publish,rollback}
docops lifecycle reader {session,query,revoke}
docops lifecycle rag {snapshot,profile-compare}
docops lifecycle learning {submit,review}
docops lifecycle feedback {submit,report}
docops init {start,status,answer,finalize}
docops project {inspect,adopt,source,evidence,change,rollback,health,backup,restore,preset}
docops v2 {start,inspect,apply}
docops supervisor {run,stop,resume}
~~~

A interface Python estável é exportada pela raiz:

~~~python
import docops

request = docops.OperationRequest(
    "documents/fixtures/acme-docs",
    docops.OperationOptions(
        output_dir="artifacts/acme",
        slug="acme",
        license="MIT",
    ),
)

operation = docops.plan(request)
preview = docops.preview(operation)  # sem promover a geração
result = docops.apply(operation)
inspection = docops.inspect("artifacts/acme")
~~~

Detalhes de tipos, imutabilidade e compatibilidade entre a distribuição 1.x e o
contrato 2.0 estão em
[docs/PYTHON-API.md](docs/PYTHON-API.md).

## Segurança e limites

O projeto trata documentação como dado, não como instrução executável.

- Informe a licença real da fonte; a licença MIT do código não licencia o corpus processado.
- Não versione documentos privados/protegidos, credenciais, <code>data/</code>, <code>models_cache/</code> ou <code>.rag_state.json</code>.
- Ambiguidade, autenticação ausente, licença desconhecida, revogação e evidência incompleta permanecem bloqueadas.
- O backend factual é RAGFlow externo; endpoint, token e digest ficam fora do pacote e o transporte remoto exige HTTPS. Desenvolvimento local pode usar loopback explícito.
- O RAGFlow não deve ser exposto publicamente sem política de bearer, logs redigidos e autorização operacional.
- Aquisição web respeita robots, redirects seguros e limites de host, páginas, profundidade, payload e timeout.
- O processo de limpeza deve atingir somente o PID exato do projeto; não use <code>Get-Process python | Stop-Process</code>.

OCR está disponível no perfil opt-in fixado em Docling/RapidOCR; browser
rendering, autenticação de fonte, confirmação de licença e autorizações
comerciais continuam gates explícitos. O manifesto preserva o bloqueio para que
um harness ou operador autorizado decida como prosseguir.

## Estado Farol 2.0

O planejamento normativo e o estado agregado estão em
[specs/farol-2/](specs/farol-2/README.md). A implementação atual cobre IR
canônica, locators, extractors, OCR real, taxonomia hierárquica, múltiplas
skills, lineage, router global e RAGFlow externo `0.27.2`.

Os 21 tickets do esforço e os 33 critérios de aceite estão `verified`. O gate
full final registrou `25/25` etapas, `1045 passed`, `12 skipped` e zero falhas,
bloqueios ou etapas `not_run`. O dual-run terminou em `cutover_approved` e a
contração do backend legado foi concluída; a evidência redigida está em
`artifacts/release-gates-full-20260920-final7/release-gates.json` e nos arquivos
de `specs/farol-2/evidence/`.

O snapshot foi versionado e enviado na branch `farol-v3`. Não há implementação
pendente: o próximo passo é a decisão humana sobre tag/release/publicação, que
continua manual.

### Histórico Farol 1.x

O estado atual do repositório inclui a implementação e a evidência local das
fases P0–P5 e dos 24 tickets do plano master:

| Fase | Foco |
| --- | --- |
| P0 | Baseline, contratos e operação segura |
| P1 | Projeto privado, estado persistente e adoção |
| P2 | Fontes, recuperação, qualidade e preset de domínio |
| P3 | Mudanças, enriquecimento, derivados e promoção |
| P4 | Worker, supervisor, backup, release gates e distribuição |
| P5 | Delegação factual restrita e piloto reproduzível |

Esses artefatos são históricos e não definem o escopo Farol 2.0. Seus testes e
fixtures não concedem autorização comercial, credencial, publicação
externa ou uso do corpus/índice real. A evidência detalhada e as limitações
estão em:

- [docs/MASTER-PLAN.md](docs/MASTER-PLAN.md)
- [docs/MASTER-IMPROVEMENT-PLAN.md](docs/MASTER-IMPROVEMENT-PLAN.md)
- [docs/master-evolution/ROADMAP.md](docs/master-evolution/ROADMAP.md)
- [docs/master-evolution/IMPLEMENTATION-EVIDENCE.md](docs/master-evolution/IMPLEMENTATION-EVIDENCE.md)
- [docs/master-evolution/TDD-EXECUTION.md](docs/master-evolution/TDD-EXECUTION.md)

## Desenvolvimento

Depois de executar <code>python scripts/bootstrap.py --dev</code>, valide
alterações com o conjunto proporcional abaixo:

~~~bash
python -m docops doctor --json
python -m pytest -q
python -m ruff check docops tests scripts
python -m ruff format --check docops tests scripts
python scripts/check_contracts.py --json
python scripts/check_documentation.py --json
python scripts/check_support_matrix.py --json
python scripts/run_release_gates.py --profile core --json
~~~

Os gates de release executam etapas sequenciais em workspaces isolados e
registram evidências redigidas. O perfil <code>full</code> inclui core,
book-to-skill, RAGFlow, OCR, wheel, candidate e supply-chain. O perfil
<code>ragflow</code> exige endpoint, token, digest de imagem e SDK RAGFlow
provisionados; qualquer dependência ou recurso ausente falha fechado, sem
converter integração não executada em aprovação.

## Estrutura do repositório

~~~text
docops/                     núcleo, CLI, lifecycle e contratos
schemas/                    schemas JSON canônicos
tests/                      testes unitários, de contrato e integração
scripts/                    bootstrap, gates, auditorias e utilitários
skills/docops-agent/        skill operacional distribuível
documents/fixtures/         exemplos sintéticos
golden-set/                 casos de avaliação revisáveis
config/ragflow/             lock e override local opt-in do RAGFlow
specs/farol-2/              contratos, tickets, evidências e matriz de aceite
docs/                       arquitetura, uso, planos e runbooks
~~~

Schemas em <code>schemas/</code> são a fonte canônica; a cópia em
<code>docops/schemas/</code> é sincronizada por <code>scripts/sync_schemas.py</code>.

## Documentação

| Quando você quer... | Leia |
| --- | --- |
| Reproduzir o fluxo completo | [docs/TUTORIAL.md](docs/TUTORIAL.md) |
| Consultar comandos e operação | [docs/USE.md](docs/USE.md) |
| Entender arquitetura e recuperação | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Integrar via Python | [docs/PYTHON-API.md](docs/PYTHON-API.md) |
| Conectar um harness | [docs/HARNESSES.md](docs/HARNESSES.md) |
| Consultar schemas | [docs/SCHEMAS.md](docs/SCHEMAS.md) |
| Auditar segurança | [SECURITY.md](SECURITY.md) |
| Preparar uma release | [docs/RELEASE.md](docs/RELEASE.md) |
| Conferir a aceitação Farol 2.0 | [specs/farol-2/acceptance-matrix.md](specs/farol-2/acceptance-matrix.md) |
| Preparar o RAGFlow local | [config/ragflow/README.md](config/ragflow/README.md) |
| Ver limites de suporte | [docs/SUPPORT-MATRIX.json](docs/SUPPORT-MATRIX.json) |
| Contribuir | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Licença

O código deste projeto é distribuído sob a [licença MIT](LICENSE). A licença,
os direitos de redistribuição e a privacidade da documentação processada devem
ser avaliados separadamente em cada execução.

<div align="center">

<sub>Documentação como código: clara para pessoas, rastreável para agentes e segura para operar.</sub>

</div>
