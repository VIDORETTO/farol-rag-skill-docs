# Release e handoff Farol 2.0

Este é o runbook atual para o candidato Farol 2.0. Scripts e gates produzem
evidência local, mas não fazem commit, push, tag, merge ou publicação
automaticamente. A release pública existente continua sendo `v1.1.0`; o
snapshot atual está na branch `farol-v3` e ainda requer autorização humana para
virar uma nova release.

## Estado do candidato

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
auditoria de retenção correspondente.

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
python scripts/prepare_candidate.py --root . --output artifacts/candidate-2.0 --profile core
python scripts/verify_candidate.py --root artifacts/candidate-2.0 --source-root .
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

Os comandos de verificação não concedem autorização de publicação. O resultado
deve ser registrado no ticket de entrega e no changelog antes da tag.

## Histórico

Os runbooks e auditorias de `v1.0.0`/`v1.1.0`, incluindo decisões sobre o
piloto FastAPI e riscos do backend legado, permanecem em documentos datados.
Eles são evidência histórica e não substituem este runbook Farol 2.0.
