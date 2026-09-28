# Release e handoff Farol 2.0

Este é o runbook atual para a release candidate Farol 2.0. Scripts e gates
produzem evidência local, mas não fazem commit, push, tag, merge ou publicação
automaticamente. O código Farol 2.0 está integrado em `main`, mas não há tag ou
GitHub Release `v2.0.0-rc.1` na consulta de 2026-09-27. A lista de releases do
GitHub estava vazia nessa consulta. Qualquer publicação exige revisão manual
de conteúdo, permissões e artefatos.

## Retomada de instalação e integração — 2026-09-27

O PR #16 recebeu `1afd00e` e seus 26 checks passaram. O serviço RAGFlow local
foi recuperado, com os quatro inputs disponíveis somente no ambiente privado
do processo; a integração real passou com 2 testes e zero skips. O TK-022
corrige instalação, diagnóstico da wheel e configuração opcional, e inclui
um [guia de primeiro uso](../../GETTING-STARTED.md). O gate completo será ligado ao
novo candidato; os resultados históricos abaixo não são aprovação dessas
mudanças. Revisão, merge e publicação permanecem pendentes.

## Snapshot histórico de prontidão local — 2026-09-27, antes da retomada

No snapshot de validação documentado nesta seção, o gate core foi executado no source limpo
`8f06ee7d31fbd4431de63f953ca9f843035c6859`: 22/22 etapas, `1050 passed`,
`12 skipped`, zero falhas/bloqueios/not_run e zero entradas no worktree. O
relatório `artifacts/release-gates-8f06ee7-core-20260927/release-gates.json`
tem SHA-256 `e97d024b5416e9e7fc4b68bd6af430880164fc18b2bd8b9569ed6b20090efc53`.
Os skips são integrações OCR/RAGFlow opt-in e casos que dependem de criar
symlink neste host Windows.

O bundle local correspondente,
`artifacts/farol-2.0.0-rc.1-final-20260927`, tem 31 arquivos e digest
`6bc0784cf884675f9a4aa2690a11b5217abe3efa4a9d1d32478dc9596a88c464`. O
verificador independente retornou `ok=true`, sem erros, com identidade do
source correspondente e supply-chain aprovada. Os hashes da wheel e dos
manifestos estão no `state.json`. Este bundle é local e não foi publicado.

Book-to-skill passou 23/23 etapas e OCR passou 1/1 no predecessor documental
`c0859b61941459575d68d35fa1e856f63856e1d1`; os resultados são suplementares e
não substituem integração no source final.

O gate `full` permanece `blocked/not_run`: faltam o serviço e os quatro inputs
`DOCOPS_RAGFLOW_ENDPOINT`, `DOCOPS_RAGFLOW_TOKEN`,
`DOCOPS_RAGFLOW_IMAGE_DIGEST` e `DOCOPS_RAGFLOW_SDK_VERSION`. O preflight de 27
de setembro terminou com `blocked/missing_external_inputs` antes de iniciar o
subprocesso de integração; os inputs estavam ausentes em Process, User e
Machine. O Docker Desktop Linux engine também estava indisponível.

Na consulta remota de 27 de setembro, a branch RC permanecia em `be40e16` e o
PR #16 seguia aberto, `BLOCKED` e `REVIEW_REQUIRED`. Os 26 checks verdes eram
de dois runs concluídos em 23 de setembro para esse head antigo. Não há tag
`v2.0.0-rc.1`, GitHub Release ou CI remota do candidato local. A branch local
evidenciada permanece sem push; atualizá-la no PR requer autorização explícita.
`main` exige os checks configurados e aprovação de code owner. Merge, tag,
release e promoção a GA continuam decisões separadas.

As verificações documentais registradas passaram: 167 Markdown sem findings,
matriz de aceite com 33 AC sem gaps, support matrix e contratos válidos, e
auditoria do candidato com 578 arquivos e zero findings. Um commit posterior
`c42832e` registra somente recibos/checkpoints e não altera código de produto.
Atestação não está configurada. A distribuição pública deve ser reconstruída a
partir do source aprovado/mesclado e passar os gates finais nesse source.

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

1. a matriz [`specs/farol-2/acceptance-matrix.md`](../../../specs/farol-2/acceptance-matrix.md);
2. o estado agregado em [`specs/farol-2/state.json`](../../../specs/farol-2/state.json);
3. a política de segurança em [`SECURITY.md`](../../../SECURITY.md);
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
