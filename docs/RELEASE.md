# Release e handoff Farol 2.0

Este é o runbook atual para a release candidate Farol 2.0. Scripts e gates
produzem evidência local, mas não fazem commit, push, tag, merge ou publicação
automaticamente. O código Farol 2.0 está integrado em `main`, mas não há tag ou
GitHub Release `v2.0.0-rc.1` na consulta de 2026-09-27. A lista de releases do
GitHub estava vazia nessa consulta. Qualquer publicação exige revisão manual
de conteúdo, permissões e artefatos.

## Snapshot atual da candidata — 2026-09-27

O source limpo `129d517a899e5ed39b1d48666ae736de246e09a6` passou o perfil `core`
em 22/22 etapas (`1050 passed`, `12 skipped`, zero falhas/bloqueios/not_run).
O bundle e a cadeia de suprimentos desse source passaram por verificação
independente, sem findings. O manifesto fixa o source e os digests exatos. O
perfil `core` não substitui o gate `full`, e os recibos de `129d517` não cobrem
os commits locais de documentação posteriores.

O `full` permanece `blocked/not_run`: o serviço RAGFlow e os quatro inputs
`DOCOPS_RAGFLOW_ENDPOINT`, `DOCOPS_RAGFLOW_TOKEN`,
`DOCOPS_RAGFLOW_IMAGE_DIGEST` e `DOCOPS_RAGFLOW_SDK_VERSION` estão indisponíveis.
O preflight de 27 de setembro terminou com `status=blocked`,
`reason=missing_external_inputs` e exit code 1; nenhum subprocesso de integração
foi iniciado. As quatro variáveis estavam ausentes nos escopos Process, User e
Machine. O Docker Desktop Linux engine também estava inacessível, então não foi
possível obter uma listagem de containers locais.

Não foi observada CI remota para o head local. Em 27 de setembro, a branch RC
remota ainda estava em `be40e16`; o PR #16 seguia aberto, `BLOCKED` e
`REVIEW_REQUIRED`. Os 26 checks verdes eram de dois runs concluídos em 23 de
setembro para aquele SHA antigo. Não existe tag `v2.0.0-rc.1` nem GitHub
Release. Atualizar o PR exige autorização explícita de push; review/merge em
`main`, tag, release e promoção a GA continuam decisões separadas.

As revisões locais do README e deste runbook ainda precisam passar pela
auditoria do candidato e integrar o source final antes de gerar artefatos de
publicação. Nenhum recibo de `129d517` deve ser tratado como validação dessas
alterações posteriores.

## Evidência histórica de gates anteriores

Em 20 de setembro de 2026, a execução full final registrou:

- `25/25` etapas concluídas;
- `1045 passed` e `12 skipped` explícitos;
- zero falhas, bloqueios ou etapas `not_run`;
- RAGFlow `0.27.2`, Docling/RapidOCR e `book-to-skill` reais executados;
- dual-run aprovado com receipt `cutover_approved`;
- 33 critérios de aceite `verified` na matriz Farol 2.0.

O relatório redigido está em
`artifacts/release-gates-full-20260920-final7/release-gates.json`, com SHA-256
`EFFE3B18D009CC659326C3F58F7B43FCABBC75540945F7F55B23EEBD0FD29824`. O
artefato é evidência local e não deve ser copiado para um pacote público sem a
auditoria de retenção correspondente. Esse gate está ligado ao commit de
implementação `93bb8894d816aad3c3b3682ccec317db1da39d45`, não ao commit de
preparação `be40e16f09153cfc12e3ea389302793f920c40b2`; a full gate nesse
candidato continua `not_run` e o preflight RAGFlow está `blocked` pelas quatro
entradas externas descritas abaixo.

Em 25 de setembro de 2026 UTC, o perfil `core` passou 22/22 etapas na árvore
local da RC baseada em `be40e16f09153cfc12e3ea389302793f920c40b2`, com 33
entradas alteradas capturadas antes da execução: `1050 passed`, `12 skipped` e
zero falhas/bloqueios/not_run. O relatório local está em
`artifacts/release-gates-20260924-214526-7c34711add8a7bd5/release-gates.json`
(`9600f5da900b691abb24da839f2ed6cae029d7cbe5df2dd3321f08da2d262c60`). Esse
core não valida integração RAGFlow, não é execução full e não torna a árvore
suja elegível para distribuição.

## Preparação do ambiente

Para o core:

```text
python scripts/bootstrap.py --dev
python -m docops doctor --json
```

Para RAGFlow e OCR, use um ambiente Python 3.13 separado:

```text
python -m pip install --editable ".[dev,formats,ragflow,ocr]"
```

O perfil externo exige, fora do repositório:

```text
DOCOPS_RAGFLOW_ENDPOINT=https://...
DOCOPS_RAGFLOW_TOKEN=<secret>
DOCOPS_RAGFLOW_IMAGE_DIGEST=<repository>@sha256:<64-hex>
DOCOPS_RAGFLOW_SDK_VERSION=0.27.2
```

Em desenvolvimento local, o Compose fixado em `config/ragflow/` publica apenas
loopback e exige os digests das imagens RAGFlow e TEI. O core não inicia esses
containers sozinho.

## Ordem dos gates

Execute a partir de um checkout limpo ou de um candidato explicitamente
selecionado:

```text
python -m docops doctor --json
python -m pip check
python -m pip_audit --requirement requirements.lock --format json
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict
python scripts/check_support_matrix.py --json
python scripts/check_contracts.py --json
python scripts/check_documentation.py --json
python scripts/check_acceptance_matrix.py --check --json
python scripts/check_public_seams.py --json
python scripts/check_farol_v2_surface.py --surface all \
  --allow-path tests/test_cutover_dual.py
python -m pytest -q
python -m ruff check docops tests scripts
python -m ruff format --check docops tests scripts
python scripts/verify_clean_clone.py
python scripts/verify_wheel.py
python scripts/generate_supply_chain.py --root . --wheel dist/<wheel>.whl \
  --output artifacts/supply-chain --profile core
python scripts/verify_supply_chain.py --root . --evidence artifacts/supply-chain
python scripts/prepare_candidate.py --root . --output artifacts/candidate-2.0.0rc1 --profile core
python scripts/verify_candidate.py --root artifacts/candidate-2.0.0rc1 --source-root .
python scripts/audit_release.py --candidate --json
python scripts/run_release_gates.py --profile core --timeout 3600 --json
python scripts/run_release_gates.py --profile book-to-skill --timeout 3600 --json
python scripts/run_release_gates.py --profile ragflow --timeout 3600 --json
python scripts/run_release_gates.py --profile full --timeout 3600 --json
```

O perfil `full` repete o core e acrescenta wheel, candidate, supply-chain,
`book-to-skill`, RAGFlow, OCR e oráculos de documentação, contratos, superfície
e matriz de aceite. Qualquer dependência ou serviço ausente permanece
`blocked`/`not_run`.

## Identidade e artefatos

Antes da publicação, capture e preserve:

- commit exato e árvore de arquivos do candidato;
- wheel e `SHA256SUMS`;
- `candidate-manifest.json`, identidade/proveniência e bundle de supply-chain;
- receipts de RAGFlow, OCR, `book-to-skill`, dual-run e aceite;
- resultado de `verify_clean_clone.py`, `verify_candidate.py` e dos gates;
- licença e direitos das fontes distribuíveis.

Não inclua documentos privados, corpus adquirido, índices, caches, modelos,
tokens, credenciais ou caminhos locais. A mudança do perfil de embedding exige
`full_rebuild` e evidência nova.

## Decisão de publicação

A publicação é uma etapa humana separada. Antes de criar tag ou release, o
mantenedor deve revisar:

1. a matriz [`specs/farol-2/acceptance-matrix.md`](../specs/farol-2/acceptance-matrix.md);
2. o estado agregado em [`specs/farol-2/state.json`](../specs/farol-2/state.json);
3. a política de segurança em [`SECURITY.md`](../SECURITY.md);
4. licença, provenance, proteção de branch, reviewers e permissões do GitHub;
5. o conteúdo final do wheel e do candidate bundle.

Os comandos de verificação não concedem autorização de promoção para GA. Para
esta RC, o resultado é registrado no changelog e na evidência de release; uma
eventual `v2.0.0` final deve repetir os gates com o commit final e receber uma
decisão humana separada.

## Histórico

Os runbooks e auditorias de `v1.0.0`/`v1.1.0`, incluindo decisões sobre o
piloto FastAPI e riscos do backend legado, permanecem em documentos datados.
Eles são evidência histórica e não substituem este runbook Farol 2.0.
