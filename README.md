
<div align="center">

# Farol

<p>
  <img src="assets/farol-logo-horizontal.png" alt="Logotipo do Farol: um farol amarelo sobre fundo azul-marinho" width="420">
</p>

**Documentação rastreável e versionada para agentes de IA.**

Converta documentação em um pacote de conhecimento com **IR canônica**,
**skills**, **roteador**, corpus RAG rastreável e evidências verificáveis.
RAGFlow é opcional e executado como serviço externo.

<p>
  <a href="https://github.com/VIDORETTO/farol-rag-skill-docs/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/VIDORETTO/farol-rag-skill-docs/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <img alt="Python 3.11–3.13; 3.14 tolerado" src="https://img.shields.io/badge/Python-3.11--3.13-3776AB?logo=python&logoColor=white">
  <a href="https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/LICENSE"><img alt="Licença MIT" src="https://img.shields.io/github/license/VIDORETTO/farol-rag-skill-docs"></a>
  <img alt="RAGFlow externo" src="https://img.shields.io/badge/RAGFlow-external%20%7C%20opt--in-0f766e">
</p>

**Versão do pacote:** `2.0.0rc1` (RC.1, pré-lançamento; não é uma versão estável)

**Publicação:** não há tag ou GitHub Release `v2.0.0-rc.1`. O gate RAGFlow e a
validação remota do candidato atual continuam pendentes. Consulte
[o estado da release](docs/RELEASE.md); nenhuma promoção a GA foi feita.

</div>

> **Em uma linha:** <code>fonte → pacote de conhecimento → agente capaz de responder com contexto e evidência</code>.

## Navegação

**Começar:** [requisitos](#requisitos) · [instalação](#instalacao) · [primeiro pacote](#primeiro-pacote)

**Entender:** [pacote gerado](#o-pacote-gerado) · [arquitetura](#arquitetura) · [segurança](#seguranca-e-limites)

**Desenvolver:** [CLI e API](#cli-e-api) · [configuração](#configuracao) · [desenvolvimento](#desenvolvimento) · [estrutura](#estrutura-do-repositorio)

**Comunidade:** [contribuir](#contribuir) · [suporte](#suporte) · [governança](community/GOVERNANCE.md)

## 🧭 O que é

O <code>Farol</code> é uma ferramenta de linha de comando Python e uma API para
construir bases de conhecimento rastreáveis para agentes. Recebe uma fonte —
pasta, arquivo, URL, repositório Git ou nome de catálogo — e produz um pacote
portátil com:

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

## 📋 Visão rápida

| Item | Estado |
| --- | --- |
| Entrada | Nome, URL, repositório Git, pasta ou arquivo local |
| Saída | Pacote autocontido com skill, router, corpus, manifesto e harness |
| Python oficialmente suportado | 3.11–3.13; 3.14 é tolerado, mas não está na garantia de suporte |
| RAG | Backend externo RAGFlow `0.27.2`; integração opt-in com endpoint, token e imagem fixados por digest |
| OCR | Docling `2.129.0` + ONNX Runtime `1.30.0` + RapidOCR no perfil Python 3.13 |
| Distribuição | Pré-lançamento `2.0.0rc1`; sem tag ou GitHub Release `v2.0.0-rc.1` na consulta de 2026-09-27 |
| Exemplos públicos | Fixtures sintéticas em <code>documents/fixtures/</code> |

## 📋 Requisitos

| Uso | Requisitos |
| --- | --- |
| Core e formatos | Python 3.11–3.13 em Ubuntu, Windows ou macOS. O perfil `formats` vem habilitado pelo bootstrap. |
| Python 3.14 | Tolerado em alguns ambientes; fora da garantia oficial de suporte. |
| RAGFlow e OCR | Python 3.13. RAGFlow também exige um serviço externo configurado; ambos os perfis são opcionais. |

Confira [a matriz de suporte](docs/SUPPORT-MATRIX.json) para os limites por
perfil e plataforma.

## 📦 Instalação

O pacote declara a versão `2.0.0rc1`, que é uma release candidate e não deve ser
divulgada como versão estável. Na consulta de 2026-09-27, não havia tag ou
GitHub Release `v2.0.0-rc.1`. Para avaliar o projeto, instale a partir do código:

### Trabalhar a partir do código-fonte

~~~bash
git clone https://github.com/VIDORETTO/farol-rag-skill-docs.git
cd farol-rag-skill-docs
python scripts/bootstrap.py --dev
~~~

O bootstrap cria o ambiente virtual e instala o perfil de desenvolvimento em
modo editável. Ative o ambiente criado antes de usar os comandos
`python -m docops`:

~~~powershell
.\.venv\Scripts\Activate.ps1
python -m docops doctor --json
~~~

Em Linux e macOS:

~~~bash
source .venv/bin/activate
python -m docops doctor --json
~~~

Se o bootstrap tiver selecionado um ambiente específico da plataforma, use o
caminho informado no JSON que ele imprime. Para executar os perfis externos de
RAGFlow e OCR, ative um ambiente Python 3.13 e instale os extras fixados:

~~~bash
python -m pip install --editable ".[dev,formats,ragflow,ocr]"
~~~

Há wrappers equivalentes em <code>scripts/bootstrap.sh</code> e
<code>scripts/bootstrap.ps1</code>. Para remover a instalação local, desative o
ambiente e remova somente o diretório virtual criado pelo bootstrap; o caminho
do interpretador aparece no JSON de saída. O código-fonte pode ser removido
separadamente quando não houver dados que você queira preservar.

## 🚀 Primeiro pacote

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

O perfil é opcional e depende de um serviço externo. Consulte
[Configuração](#configuracao) para os quatro inputs e o exemplo de execução.
O core não inicia containers nem faz rede. Sem os inputs externos, o perfil
falha fechado como `blocked`/`not_run`.

### Escolha da rota no agente

| Pergunta | Rota |
| --- | --- |
| “Qual padrão devo usar para fazer X?” | <code>skill/</code>, para raciocínio e orientação. |
| “Qual é o default, assinatura ou versão?” | <code>rag/</code>, para o trecho literal com fonte. |
| “A evidência é ambígua ou sensível?” | Skill para interpretar + RAG para confirmar. |

## 📦 O pacote gerado

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

---

# 🔧 Technical Documentation

## 🏗️ Arquitetura

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

## 🖥️ CLI e API

Use <code>python -m docops ...</code> para garantir que a CLI está ligada ao
mesmo Python do ambiente ativo. No código atual, o launcher de marca é
<code>farol ...</code>; <code>docops ...</code> continua disponível como alias de
compatibilidade. O comando <code>python -m docops</code> também permanece
disponível para instalações antigas.

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

## ⚙️ Configuração

O core funciona sem credenciais. Configure RAGFlow somente para executar o
perfil opcional; mantenha os valores no ambiente local ou no gestor de segredos
do CI, nunca em arquivos versionados. Use HTTPS para endpoints remotos; loopback
é permitido apenas no desenvolvimento local explicitamente configurado.

| Variável | Obrigatória no perfil RAGFlow | Valor |
| --- | --- | --- |
| `DOCOPS_RAGFLOW_ENDPOINT` | Sim | URL HTTPS do serviço acessível pelo runner; loopback é permitido no desenvolvimento local. |
| `DOCOPS_RAGFLOW_TOKEN` | Sim | Bearer token; não registre nem compartilhe o valor. |
| `DOCOPS_RAGFLOW_IMAGE_DIGEST` | Sim | Referência da imagem fixada por `sha256` e digest de 64 caracteres hexadecimais. |
| `DOCOPS_RAGFLOW_SDK_VERSION` | Sim | Versão do SDK instalada; para este candidato, `0.27.2`. |

Em Bash, substitua cada valor pelo dado real fornecido pelo operador:

~~~bash
export DOCOPS_RAGFLOW_ENDPOINT='https://ragflow.example.invalid'
export DOCOPS_RAGFLOW_TOKEN='SUBSTITUA_LOCALMENTE'
export DOCOPS_RAGFLOW_IMAGE_DIGEST='registry.example/ragflow@sha256:SUBSTITUA_PELO_DIGEST_REAL'
export DOCOPS_RAGFLOW_SDK_VERSION='0.27.2'
python scripts/run_release_gates.py --profile ragflow --json
~~~

No Windows PowerShell:

~~~powershell
$env:DOCOPS_RAGFLOW_ENDPOINT = 'https://ragflow.example.invalid'
$env:DOCOPS_RAGFLOW_TOKEN = 'SUBSTITUA_LOCALMENTE'
$env:DOCOPS_RAGFLOW_IMAGE_DIGEST = 'registry.example/ragflow@sha256:SUBSTITUA_PELO_DIGEST_REAL'
$env:DOCOPS_RAGFLOW_SDK_VERSION = '0.27.2'
python scripts/run_release_gates.py --profile ragflow --json
~~~

Os exemplos são modelos e não passam no gate até que sejam substituídos por
inputs válidos para uma instância autorizada. Para desenvolvimento local, veja
o Compose e as restrições de rede em [config/ragflow/README.md](config/ragflow/README.md).

## 🔐 Segurança e limites

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

## 📌 Estado Farol 2.0

O planejamento normativo e o estado agregado estão em
[specs/farol-2/](specs/farol-2/README.md). A implementação atual cobre IR
canônica, locators, extractors, OCR real, taxonomia hierárquica, múltiplas
skills, lineage, router global e RAGFlow externo `0.27.2`.

O gate full com `25/25` etapas, `1045 passed` e `12 skipped` foi executado no
commit de implementação `93bb8894d816aad3c3b3682ccec317db1da39d45`; esse
resultado não substitui a validação do commit de preparação da RC.1. A
reconciliação de release e seus bloqueios atuais estão em
[`specs/farol-2/state.json`](specs/farol-2/state.json) e nas evidências de
[`specs/farol-2/evidence/`](specs/farol-2/evidence/). A promoção para GA exige
gates atuais e autorização explícita do mantenedor.

Na validação local de 27 de setembro de 2026, o source limpo `8f06ee7` passou
o core em 22/22 etapas (`1050 passed`, `12 skipped`, zero falhas/bloqueios/
not_run). O bundle desse source, com 31 arquivos, foi verificado
independentemente; manifesto, wheel e supply-chain estão ligados ao mesmo SHA.
Book-to-skill (23/23) e OCR (1/1, PDF sintético sem envio remoto) passaram no
predecessor documental `c0859b6`; esses perfis suplementares não substituem o
full gate RAGFlow, que segue `blocked` pela falta do serviço e dos quatro
inputs. A CI remota ainda cobre apenas o head antigo do PR #16. A candidata não
tem tag ou GitHub Release. Consulte o [runbook de release](docs/RELEASE.md) e o
[estado agregado](specs/farol-2/state.json) para hashes, recibos e limitações.

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

## 🧪 Desenvolvimento

Depois de executar <code>python scripts/bootstrap.py --dev</code>, ative o
ambiente virtual indicado no JSON do bootstrap e valide alterações com o
conjunto proporcional abaixo:

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

## 🗂️ Estrutura do repositório

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

## 📚 Documentação

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

## 🤝 Contribuir

Leia [CONTRIBUTING.md](CONTRIBUTING.md) antes de abrir uma alteração. As
contribuições devem usar fixtures sintéticas, respeitar os contratos públicos
e passar pelos checks proporcionais à mudança.

## 🆘 Suporte

Para relatar um problema, consulte a [política de suporte](community/SUPPORT.md)
e inclua versão ou commit, sistema operacional, versão do Python, perfil,
comando, saída sanitizada e uma reprodução mínima sintética. Não anexe corpus,
índices, caches, tokens ou credenciais. Vulnerabilidades devem ser reportadas
privadamente conforme [SECURITY.md](SECURITY.md).

## 🏛️ Releases e governança

As versões e alterações estão no [CHANGELOG](CHANGELOG.md). A publicação segue
o [runbook de release](docs/RELEASE.md) e requer revisão humana dos gates,
artefatos e permissões. Consulte também a
[governança](community/GOVERNANCE.md), a
[lista de mantenedores](community/MAINTAINERS.md) e o
[código de conduta](CODE_OF_CONDUCT.md).

## 📄 Licença

O código deste projeto é distribuído sob a [licença MIT](LICENSE). A licença,
os direitos de redistribuição e a privacidade da documentação processada devem
ser avaliados separadamente em cada execução.

<div align="center">

<sub>Documentação como código: clara para pessoas, rastreável para agentes e segura para operar.</sub>

</div>
