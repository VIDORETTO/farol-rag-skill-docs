# Revisão de prontidão da release — 2026-09-24

Escopo: correções locais de empacotamento, CI, documentação pública e controles
de release para Farol 2.0. Nenhum commit, push, tag ou release foi criado.
O acompanhamento autenticado de 2026-09-25 habilitou somente o recebimento
privado de vulnerabilidades; a alteração está registrada abaixo.

## Defeitos encontrados e correções locais

- O rebuild local da RC reutilizava `build/lib/` ignorado e incluía três módulos
  1.x que não existem nos arquivos candidatos. `prepare_candidate.py` agora
  constrói a wheel numa staging temporária apenas com inputs do pacote; o
  verificador rejeita `docops/mcp_client.py`, `docops/rag_sync.py` e
  `docops/backends/legacy_knowledge_rag.py`. O diretório local `build/` foi
  preservado sem alterações.
- O workflow CI instalava o extra inexistente `rag`; foi corrigido para
  `ragflow`, e `validate_workflows.py` agora confere grupos extras contra
  `pyproject.toml`.
- `.github/workflows/reindex-docs.yml` chamava `scripts/update_rag.py`, removido
  na superfície Farol 2.0. O workflow foi excluído. `update_docs.ps1` agora
  informa que é necessário passar `-Sources` em vez de chamar esse script.
- A integração RAGFlow tinha agenda semanal apesar da indisponibilidade atual
  do serviço e das credenciais. O disparo manual foi mantido e a agenda removida.
- A ação de artifacts foi atualizada para `actions/upload-artifact` v7.0.1,
  SHA `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`, versão corrente verificada no
  repositório oficial da action.
- README, release notes, metadados, runbook e SECURITY não apontam mais para
  downloads/tag da RC que não existem nem declaram uma release estável atual.

## Verificações observadas

- Testes focados:
  `.venv-rag\Scripts\python.exe -m pytest -q tests/test_candidate_bundle.py::test_candidate_wheel_build_is_byte_reproducible tests/test_candidate_bundle.py::test_candidate_wheel_ignores_stale_build_lib_modules_and_audits_them tests/test_candidate_bundle.py::test_candidate_bundle_has_new_identity_and_reproducible_release_assets tests/test_candidate_identity.py::test_candidate_identity_omits_deleted_tracked_paths tests/test_release_audit.py::test_candidate_audit_ignores_deleted_tracked_files_and_rejects_an_empty_tree tests/test_workflow_yaml.py tests/test_repository_metadata.py`
  — `9 passed`.
- `scripts/validate_workflows.py --json` — `ok=true`, dois workflows ativos.
- `scripts/check_documentation.py --root . --json` — `ok=true`, 167 arquivos
  Markdown após registrar esta evidência.
- Reconciliação de contratos: os 21 estados de ticket coincidem com
  `state.json`; os 33 AC de `spec.md` coincidem com as 33 linhas da matriz;
  todos os paths de evidência referidos e todos os tickets `verified` têm
  evidência presente. `scripts/check_acceptance_matrix.py --check` retornou
  33 `verified`, sem AC sem atribuição ou findings de backlog. `TK-020` segue
  `in_progress`/`blocked` pelo gate externo, conforme o ticket.
- A skill `hybrid-check` foi executada em modos de consistência e convergência
  manuais porque este checkout não contém `scripts/hybrid.py` nem `.hybrid/`.
  A revisão reconciliou tickets, ACs, evidências e projeções; os textos de
  checkpoint que ainda diziam que o bundle estava pendente foram corrigidos.
  O repositório não tem registry `FD-*` para registrar findings.
- `scripts/audit_dependencies.py --requirements requirements.lock --local
  --strict --evidence-dir artifacts/readiness-audit-20260925` retornou
  `ok=true`: auditorias de lock e ambiente local com exit code 0, zero findings
  e política `pass`. Lock SHA-256
  `0d7521e0337029ab512db1bbeb0322dd71e355abd9d4dc56d961e0492571a0fa`;
  relatório em `artifacts/readiness-audit-20260925/summary.json`.
- Gate local `core` executado em Windows 11 / Python 3.13.12, branch
  `release/farol-2.0.0-rc.1`, commit `be40e16f09153cfc12e3ea389302793f920c40b2`
  com 33 entradas alteradas no worktree capturadas antes da execução. Resultado:
  22/22 etapas, `1050 passed`, `12 skipped`, zero `failed`, `blocked` ou
  `not_run`; pytest e clone limpo registraram `479 passed, 6 skipped`, crash
  matrix `17 passed`, revocation `25 passed`. Relatório:
  `artifacts/release-gates-20260924-214526-7c34711add8a7bd5/release-gates.json`,
  SHA-256 `9600f5da900b691abb24da839f2ed6cae029d7cbe5df2dd3321f08da2d262c60`.
  Este é um gate `core` sobre uma árvore suja, não o full gate nem aprovação
  para distribuição.
- Bundle local construído em `artifacts/rc1-readiness-hardening-pass1-20260924`
  e verificado novamente com `scripts/verify_candidate.py --root ...
  --source-root .`: `ok=true`, identidade do source correspondente, auditoria
  sem findings e supply-chain verificada. Digest da candidata
  `f41c31a3a8f65be3e464c8588dca1ae33f6323220795e2c9ec11ae5ce3613b71`; wheel
  `consulta_documentacao-2.0.0rc1-py3-none-any.whl`, 392899 bytes, SHA-256
  `44245568bd811f97cb8592dcd857191377940f8cacf13748b73877d7fe827861`. A wheel
  não contém `docops/mcp_client.py`, `docops/rag_sync.py` nem
  `docops/backends/legacy_knowledge_rag.py`. O manifesto registra atestação
  `not-configured`, publicação `false` e identidade `working-tree-candidate`.
  Uma cópia de fechamento foi gerada depois deste recibo e verificada
  independentemente em `artifacts/rc1-readiness-hardening-final-20260924`:
  digest `ac2e1767694255c8a160d8655c4f5139448d9117d488d8bdf81d1878d582a9ab`,
  manifesto SHA-256
  `7617e654444ec05644ff74743ab88fe1d93fae67fcdbe57079e80208c581bab0`,
  checksums SHA-256
  `6334de3723c1bbf904e96defc9885127266dd71c5b3b89d12600b79431c5469c`.
  Essa cópia também é `working-tree-candidate`, sem publicação nem atestação.
- Depois desta captura, o bundle final foi preparado em
  `artifacts/farol-2.0.0-rc.1-clean-commit-audit-20260925` e validado pelo
  verificador independente contra `--source-root .`. A identidade do source e
  os checksums correspondem, o supply-chain audit passou e a wheel não inclui
  módulos legados. O recibo do verificador fica junto aos artefatos locais;
  `state.json` registra o resultado sem copiar hashes autorreferentes. O bundle
  representa um `local-commit-candidate` com worktree limpo; não há CI remoto
  para este source, publicação ou atestação.
- A API autenticada do GitHub não retornou releases estáveis ou RC; a consulta
  de tags também não encontrou `v1.1.0` ou `v2.0.0-rc.1` neste repositório.
  Nenhum artefato público para instalação foi confirmado.
- Revisão autenticada de 2026-09-24: branch protection de `main`, 13 checks obrigatórios,
  aprovação de code owner, Dependabot, secret scanning e push protection ativos;
  nenhum alerta aberto retornado. Naquele snapshot, **private vulnerability
  reporting estava desativado**; foi habilitado e confirmado no follow-up
  autenticado abaixo.
- A execução histórica de integração `35500245195`, no SHA antigo
  `2ff00fcfc581147ba9367b6a2a84dc1b1d6cbab5`, falhou no passo `MCP smoke` com
  `mcp_eof`; o log de stderr está redigido e não permite diagnóstico adicional.
  Ela não valida o código atual.

## Atualização autenticada de configuração — 2026-09-25

O objetivo de fechar os bloqueios controláveis pelo repositório autorizou a
correção desse item. O endpoint autenticado retornou `false` antes da mudança;
`gh api --method PUT repos/VIDORETTO/farol-rag-skill-docs/private-vulnerability-reporting`
concluiu sem erro; a consulta de verificação retornou `true`. A configuração
agora está habilitada e o canal foi atualizado em `SECURITY.md`. A autenticação
foi fornecida pelo GitHub CLI local; nenhum segredo foi exibido nem registrado
neste relatório. Não houve commit, push, tag ou release.
Os requisitos de permissão e o comportamento do recurso seguem a
[documentação de configuração do GitHub](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).

## Gates e bloqueios

- O gate core local passou; ele está registrado acima e em `state.json`.
- O full gate RC continua `not_run`: o usuário confirmou que não há serviço nem
  credenciais disponíveis agora. Faltam `DOCOPS_RAGFLOW_ENDPOINT`,
  `DOCOPS_RAGFLOW_TOKEN`, `DOCOPS_RAGFLOW_IMAGE_DIGEST` e
  `DOCOPS_RAGFLOW_SDK_VERSION`; o status é `blocked`, nunca aprovado.
- A RC não tem tag, GitHub Release nem autorização de GA. Publicação continua
  separada e requer autorização explícita.

## Revisão manual Standards/Spec — revisão 1, 2026-09-25

Baseline de revisão: `be40e16f09153cfc12e3ea389302793f920c40b2`, a branch
`release/farol-2.0.0-rc.1`. `git diff <baseline>...HEAD` e `git diff --cached`
estavam vazios; `git diff` continha 31 paths rastreados (incluindo a remoção do
workflow obsoleto) e `git status --short` mostrava 33 entradas ao incluir dois
arquivos de evidência novos. O runner híbrido e um `review.md` não existem no
checkout; a revisão manual leu o contrato, plano, `AGENTS.md`, padrões do repo e
o diff completo, inclusive arquivos novos.

### Standards

- **STD-01 — resolvido:** `README.md` anunciava Python 3.11+ embora
  `docs/DEPENDENCIES.md`, `docs/SUPPORT-MATRIX.json` e os workflows declarem
  3.11–3.13, com 3.14 apenas tolerado. A claim pública agora reproduz o suporte
  declarado e explicita a condição de 3.14.
- Nenhum finding Standards local permanece aberto após a correção.

### Spec

- **SPEC-01 — resolvido:** a mesma claim ultrapassava o ambiente do plano
  técnico (Python 3.11–3.13), enfraquecendo o limite explícito de suporte. O
  README foi alinhado à matriz aceita.
- A reconciliação AC→evidência continua sem gaps: 33 critérios verificados e
  nenhum finding de backlog. Nenhum finding Spec local permanece aberto.

### Evidência e limites

`check_support_matrix.py --json`, `check_acceptance_matrix.py --check`,
`check_documentation.py --root . --json`, `check_contracts.py --json`,
`validate_workflows.py --json`, `check_public_seams.py --json` e
`audit_release.py --candidate --json` passaram após a correção documental.
TK-020 segue `in_progress`/`blocked` pelo full gate externo: faltam os quatro
inputs RAGFlow. CI remoto para estas mudanças segue sem execução porque a fonte
local ainda não foi enviada; push, tag, release e GA não foram feitos.

## Observação de governança GitHub — 2026-09-25

A consulta autenticada confirmou em `main` 13 status checks obrigatórios, uma
aprovação de code owner e descarte de reviews stale; `enforce_admins=false`,
conforme o bypass administrativo documentado no checklist. A branch
`release/farol-2.0.0-rc.1` retornou `Branch not protected` (HTTP 404) e a consulta
de rulesets do repositório e ancestrais retornou lista vazia. Não alterei a
configuração. Para publicar a partir da fonte revisada, o caminho protegido é
abrir PR para `main`; usar diretamente a branch RC exige decisão explícita do
owner sobre adicionar proteção equivalente. Este é um ponto de governança, não
um finding de código nos eixos Standards/Spec.

## Core gate no commit limpo — 2026-09-25

Após consolidar a revisão de prontidão em `98d2a1df0364ab79d82852bca14308d6dc44a22a`,
o worktree estava limpo (zero entradas). O perfil `core` foi executado nesse SHA
exato; o relatório também confirma `source_commit=98d2a1df0364ab79d82852bca14308d6dc44a22a`
e `worktree_entries=0`.

Comando observado:

```powershell
.venv-rag\Scripts\python.exe scripts/run_release_gates.py --root . --python .venv-rag\Scripts\python.exe --output artifacts/release-gates-clean-commit-98d2a1d --profile core --timeout 3600 --json
```

Resultado: `ok=true`; 22/22 etapas passaram; agregado de 1050 aprovados,
12 skips explícitos, zero falhas, bloqueios ou etapas não executadas. A suíte
principal e o clone limpo registraram cada um `479 passed, 6 skipped`; crash
matrix `17 passed`; revogação `25 passed`. Windows 11, Python 3.13.12, AMD64.
Início `2026-09-25T02:05:05Z`; conclusão `2026-09-25T02:13:29Z`. Relatório:
`artifacts/release-gates-clean-commit-98d2a1d/release-gates.json`, SHA-256
`629a8231cff7d6f0c09f039503646b401b6255fa2a3dca57f6e70b7aa0bfa2ed`.

Esse é somente o perfil `core`. O perfil `full` continua `blocked/not_run` porque
o usuário confirmou indisponibilidade do serviço e das quatro entradas RAGFlow;
não foi registrado como sucesso. O CI remoto do source revisado também não foi
executado: o commit permanece local e push não foi autorizado. Tag, release e
promoção a GA continuam não executadas.

Na captura deste checkpoint, baseada no core do commit `98d2a1d`, o bundle final
ainda aguardava geração e verificação independente. Isso foi concluído depois:
o bundle do source `23a39c3` aparece como intermediário abaixo, e a verificação
final no source `6878aa4` está registrada na seção final deste recibo. Não resta
pendência local de geração ou verificação do bundle.

## Candidate intermediário `23a39c3` — 2026-09-26

Esta primeira execução limpa foi validada antes do recibo GitHub/v3 ser
consolidado. O candidate final, com essas atualizações documentais incluídas,
foi novamente verificado no commit `6878aa4` abaixo; este bloco é mantido como
trilha do candidate intermediário.

### Core no source exato do bundle

O perfil `core` foi executado em `23a39c31bd09f8098af6d71bd57671d7495d10a9`,
o mesmo commit registrado pela identidade do bundle. O relatório confirma
worktree limpo (`worktree_entries=0`), `ok=true`, 22 etapas e denominadores
`1050 passed`, `12 skipped`, `0 failed`, `0 blocked`, `0 not_run`. A suíte
principal e o clone limpo tiveram cada um `479 passed, 6 skipped`; crash matrix
`17 passed`; revogação `25 passed`. Ambiente: Windows 11, Python 3.13.12, AMD64.

Comando:

```powershell
.venv-rag\Scripts\python.exe scripts/run_release_gates.py --root . --python .venv-rag\Scripts\python.exe --output artifacts/release-gates-clean-commit-23a39c3 --profile core --timeout 3600 --json
```

Relatório: `artifacts/release-gates-clean-commit-23a39c3/release-gates.json`,
SHA-256 `8671273db85621a5fa21f29742176a9bb10999677afe2feb9e93ae6cf1c4ee38`.
Início `2026-09-26T19:14:23Z`; término `2026-09-26T19:23:09Z`. Isso não executa
nem substitui o perfil `full`.

### Bundle candidate

Comandos:

```powershell
.venv-rag\Scripts\python.exe scripts/prepare_candidate.py --root . --output artifacts/farol-2.0.0-rc.1-clean-commit-audit-20260926 --python .venv-rag\Scripts\python.exe --profile core
.venv-rag\Scripts\python.exe scripts/verify_candidate.py --root artifacts/farol-2.0.0-rc.1-clean-commit-audit-20260926 --source-root .
```

`prepare_candidate` gerou
`artifacts/farol-2.0.0-rc.1-clean-commit-audit-20260926` e retornou `ok=true`.
O verificador independente retornou `ok=true`, `errors=[]`; commit, estado
`local-commit-candidate` e digest do source coincidem entre checkout,
`candidate-identity.json` e manifesto. O
artefato contém 31 arquivos e 596320 bytes; candidate audit sem findings;
supply-chain verifier sem erros. A wheel `consulta_documentacao-2.0.0rc1-py3-none-any.whl`
tem 392925 bytes, SHA-256
`c018bd6096670ea4051f8059e615d95fa53116e705edc55fd071d33cd8c83169`; os três
módulos Farol 1.x removidos não aparecem nela.

| Evidência | SHA-256 |
|---|---|
| Digest do candidato | `082749b681a9f40930eaef2da9ea3b67b8307a381035d59159848175b52eff3f` |
| `candidate-identity.json` | `45f90390777359762f386e5f5cbc7fef8d940e6605c811f94705b21cc914e51e` |
| `candidate-manifest.json` | `c20aa8a895890461e7639cdac0fa08b091a65487c97450bdb1f1d77193f90b1e` |
| `SHA256SUMS` | `47ab540aa4189957b7b3549201577cd4d0bc145121876768bda0de4f2c904b04` |
| wheel | `c018bd6096670ea4051f8059e615d95fa53116e705edc55fd071d33cd8c83169` |
| recibo `prepare_candidate.py` | `93e03832eb4e024887d86e10709bf001cfc97e8e3a601d713edbd2c218f55796` |
| recibo `verify_candidate.py` | `10cbde8c00bc54c1dfe3e57808f777f810311ee987cf814ea21e009ff4bd6b17` |

Os recibos de build/verificação ficam em `artifacts/`, fora do bundle. A
identidade registra CI remota como `not-observed`, source não alcançável pelo
remote e atestação `not-configured`; não houve publicação.

### Snapshot autenticado do GitHub

Consultas somente de leitura em 2026-09-26 confirmaram: `main` em
`a939e0a4b856ea3df86ac5f8055f329ebd15f5fd`; branch RC remota em
`be40e16f09153cfc12e3ea389302793f920c40b2`; sem tag `v2.0.0-rc.1` ou GitHub
Release. O [PR #16](https://github.com/VIDORETTO/farol-rag-skill-docs/pull/16)
segue aberto e mergeable para `main`, mas mantém head `be40e16` e decisão
`REVIEW_REQUIRED`. Seus checks requeridos passaram em 2026-09-23 para esse head
antigo; nenhum run cobre o candidato local `23a39c3`.

`main` exige 13 checks, uma aprovação de code owner e descarta reviews stale;
`enforce_admins=false`. A branch RC continua sem branch protection (HTTP 404) e
sem ruleset de repositório/ancestral. Private vulnerability reporting retornou
`true`. Nenhuma configuração foi alterada nesta verificação.

Comandos de leitura observados:

```powershell
git ls-remote origin refs/heads/release/farol-2.0.0-rc.1 refs/heads/main refs/tags/v2.0.0-rc.1
gh release list --repo VIDORETTO/farol-rag-skill-docs --limit 20
gh pr list --repo VIDORETTO/farol-rag-skill-docs --head release/farol-2.0.0-rc.1 --state all --json number,state,title,headRefOid,baseRefName,url
gh pr view 16 --repo VIDORETTO/farol-rag-skill-docs --json number,state,title,headRefOid,baseRefOid,baseRefName,mergeable,reviewDecision,statusCheckRollup,url
gh api repos/VIDORETTO/farol-rag-skill-docs/branches/main/protection
gh api repos/VIDORETTO/farol-rag-skill-docs/branches/release%2Ffarol-2.0.0-rc.1/protection
gh api repos/VIDORETTO/farol-rag-skill-docs/rulesets --jq length
gh api repos/VIDORETTO/farol-rag-skill-docs/private-vulnerability-reporting --jq .enabled
gh run list --repo VIDORETTO/farol-rag-skill-docs --branch release/farol-2.0.0-rc.1 --limit 10
```

O usuário confirmou que não há serviço RAGFlow nem credenciais disponíveis; o
full gate permanece `blocked/not_run` pelos quatro inputs listados em
`state.json`. O source local e a atualização do PR aguardam autorização explícita
de push. Tag, GitHub Release e promoção a GA não foram feitas.

## Candidate local anteriormente final — source `6878aa4` — 2026-09-26

Este source foi final na verificação anterior. Depois da revisão documental,
corrigimos a referência de candidato na checklist GitHub empacotada. O source
atualizado `cbee436`, com nova execução do core e do bundle, está documentado
na última seção deste recibo.

### Core no source exato

O perfil `core` foi reexecutado após consolidar as atualizações de evidência,
em `6878aa44f91e61e05d706c044bec5d6439cd26ef`. O relatório confirma branch RC,
worktree limpo (`worktree_entries=0`), `ok=true`, 22 etapas e denominadores
`1050 passed`, `12 skipped`, `0 failed`, `0 blocked`, `0 not_run`. A suíte
principal e o clone limpo tiveram cada um `479 passed, 6 skipped`; crash matrix
`17 passed`; revogação `25 passed`. Ambiente: Windows 11, Python 3.13.12, AMD64.

Comando:

```powershell
.venv-rag\Scripts\python.exe scripts/run_release_gates.py --root . --python .venv-rag\Scripts\python.exe --output artifacts/release-gates-clean-commit-6878aa4 --profile core --timeout 3600 --json
```

Relatório: `artifacts/release-gates-clean-commit-6878aa4/release-gates.json`,
SHA-256 `ad0850bea58701a3b389e1a6dc26edc26f49aa55f2bff06e236e46410802b82b`.
Início `2026-09-26T19:41:18Z`; término `2026-09-26T19:49:40Z`. O perfil `full`
continua sem execução por bloqueio RAGFlow.

### Bundle auditável

Comandos:

```powershell
.venv-rag\Scripts\python.exe scripts/prepare_candidate.py --root . --output artifacts/farol-2.0.0-rc.1-final-audit-20260926 --python .venv-rag\Scripts\python.exe --profile core
.venv-rag\Scripts\python.exe scripts/verify_candidate.py --root artifacts/farol-2.0.0-rc.1-final-audit-20260926 --source-root .
```

`prepare_candidate` e o verificador independente retornaram `ok=true`; o
segundo teve `errors=[]`, comparou commit/digest com o source e verificou o
supply-chain. O candidate audit não tem findings. O bundle contém 31 arquivos,
597231 bytes, digest
`4c822f2f3af2e184f5dc0b1fda27490954134a119edb7990de0d2b07e9adf850`; o
checklist GitHub distribuído no pacote é idêntico ao arquivo versionado.

| Evidência | SHA-256 |
|---|---|
| `candidate-identity.json` | `6b4050bda963706683e50aad71c8c9cbdcf390e42ffe906ca18a33eb5224500b` |
| `candidate-manifest.json` | `dafcbdfe06c14627043af81f76a20296d214de20142f7275ef67c266f12788eb` |
| `SHA256SUMS` | `5604aa8229638460fc8db68ceb3b7c5f6d749364bde7c762e6abb4d8c8ab3a42` |
| recibo `prepare_candidate.py` | `0de9d6984bde0a1352ad81224b3ea8c76da2b5e95fd54975ccb1452e22e75f2e` |
| recibo `verify_candidate.py` | `86aef679baab25973343391fc9afbbbe36c3a70390d301a9afc6182421b19bc9` |
| wheel `consulta_documentacao-2.0.0rc1-py3-none-any.whl` | `c018bd6096670ea4051f8059e615d95fa53116e705edc55fd071d33cd8c83169` |

A wheel tem 392925 bytes e 161 membros; não inclui `docops/mcp_client.py`,
`docops/rag_sync.py` nem `docops/backends/legacy_knowledge_rag.py`. Recibos
ficam ignorados em `artifacts/`, fora do bundle. Identidade local limpa, mas
remote reachability/CI são `unverified`/`not-observed`; atestação
`not-configured`; nenhuma publicação ocorreu.

### Remote no source final

Consulta de leitura após o gate confirmou que `main` continua em
`a939e0a4b856ea3df86ac5f8055f329ebd15f5fd`, a branch RC remota em
`be40e16f09153cfc12e3ea389302793f920c40b2`, sem tag RC ou GitHub Release.
O PR #16 segue aberto e mergeable para `main`, mas com head `be40e16` e decisão
`REVIEW_REQUIRED`; os checks verdes são de 2026-09-23 e não cobrem `6878aa4`.
O branch source local não foi enviado. O full gate segue `blocked/not_run` por
indisponibilidade confirmada do serviço e dos quatro inputs RAGFlow.

## Candidate final local — source `cbee436` — 2026-09-26

### Core no source exato

Após corrigir a referência de candidato na checklist GitHub distribuída, o
perfil `core` foi executado no source limpo
`cbee436d5e42aeb81f7c27006f65406e724fa4a9`. O relatório confirmou `ok=true`,
22 etapas, `1050 passed`, `12 skipped`, zero `failed`, `blocked` ou `not_run`,
e zero entradas no worktree. Suíte principal e clone limpo: `479 passed, 6
skipped` cada; crash matrix: 17; revogação: 25. Ambiente: Windows 11, Python
3.13.12, AMD64. O perfil full segue `not_run` por bloqueio RAGFlow.

Comando:

```powershell
.venv-rag\Scripts\python.exe scripts/run_release_gates.py --root . --python .venv-rag\Scripts\python.exe --output artifacts/release-gates-clean-commit-cbee436 --profile core --timeout 3600 --json
```

Relatório: `artifacts/release-gates-clean-commit-cbee436/release-gates.json`,
SHA-256 `e01c3eca91f791515552a42a3b575a419bb3e7940974618f50887bec207f6eee`.
Início `2026-09-26T20:01:59Z`; término `2026-09-26T20:10:09Z`.

### Bundle auditável

Comandos:

```powershell
.venv-rag\Scripts\python.exe scripts\prepare_candidate.py --root . --output artifacts\farol-2.0.0-rc.1-cbee436-final-audit-20260926 --python .venv-rag\Scripts\python.exe --profile core
.venv-rag\Scripts\python.exe scripts\verify_candidate.py --root artifacts\farol-2.0.0-rc.1-cbee436-final-audit-20260926 --source-root .
```

Preparação e verificação independente retornaram `ok=true`; `errors=[]`,
source commit/digest conferidos e supply-chain aprovado. Candidate audit sem
findings. O bundle contém 31 arquivos, 597298 bytes, digest
`023d4ef786f8d2f43ae9d5c90672a58085a0b8f3db83fb7919417dea79ce387b`.
Checklist GitHub no bundle e na fonte tem SHA-256 idêntico
`02cb992a723d69fce258104a2d4c0cbc4adcaeb4b6f465757961b0f6fe2c2b66`.

| Evidência | SHA-256 |
|---|---|
| `candidate-identity.json` | `9a23e354f5a0438c86621df4f5b70d1199724bb8e80f6656efdfb03b8f698ca7` |
| `candidate-manifest.json` | `9ccc8aa1764127a5f445852aceb342efa749c4eb9980eb195bd4d444998144b9` |
| `SHA256SUMS` | `124b787e2f6ffdb66989a157efe52e6fff6c2fdf45d2a270c958214c07194335` |
| Recibo `prepare_candidate.py` | `76f9d65d640ba967b1baf05ae5a6ac1b3cbbbb296f5f0c89d6df4f2d98d59b5a` |
| Recibo `verify_candidate.py` | `94ae508dec7b9ec05eefd751d5562735abde62e9ab42f84d9963a12c56e438984` |
| Wheel `consulta_documentacao-2.0.0rc1-py3-none-any.whl` | `c018bd6096670ea4051f8059e615d95fa53116e705edc55fd071d33cd8c83169` |

A wheel tem 392925 bytes e não contém `docops/mcp_client.py`,
`docops/rag_sync.py` nem `docops/backends/legacy_knowledge_rag.py`. Recibos
ficam em `artifacts/`, fora do bundle. Remote reachability/CI seguem
`unverified`/`not-observed`; atestação `not-configured`; publicação não feita.

### GitHub após o candidate final

Consultas de leitura em 2026-09-26 confirmaram `main` em
`a939e0a4b856ea3df86ac5f8055f329ebd15f5fd` e a branch RC remota em
`be40e16f09153cfc12e3ea389302793f920c40b2`; tag e GitHub Release RC seguem
ausentes. O PR #16 está aberto e mergeable para `main`, com decisão
`REVIEW_REQUIRED`; os dois runs CI retornados pertencem ao SHA antigo `be40e16`
e não cobrem `cbee436`. A atualização do PR aguarda autorização explícita de
push. Private vulnerability reporting está habilitado; nenhuma configuração
remota foi alterada.

O full gate continua `blocked/not_run`: o usuário confirmou indisponibilidade
do serviço e das quatro entradas RAGFlow listadas em `state.json`. Tag, release
e promoção a GA continuam decisões separadas e não executadas.

### Reconciliação de contratos e documentação

Após registrar o candidate e atualizar os checkpoints, as verificações locais
de consistência passaram: `check_acceptance_matrix.py --check` reportou 33 AC
verificados e nenhum finding; `check_documentation.py --root . --json` checou
167 Markdown sem findings; `check_contracts.py --json` e
`validate_workflows.py --json` retornaram `ok=true`, com 2 workflows; os
checks de support matrix e public seams não apontaram findings; e
`audit_release.py --candidate --json` retornou `ok=true`, 578 arquivos
verificados e zero findings. Essas verificações cobriram também o registro
documental atualizado; não alteraram o payload do bundle source `cbee436`.
