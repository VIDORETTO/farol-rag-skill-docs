# Verificação dos assets RC.1 e retenção do backup Farol v3

Data da verificação: 2026-09-24. Escopo: TK-020/TK-021, sem publicação ou
promoção de versão.

## RC `v2.0.0-rc.1`

- A branch remota `release/farol-2.0.0-rc.1` aponta para commit
  `be40e16f09153cfc12e3ea389302793f920c40b2`; `origin` aponta para o mesmo
  commit. O checkout local usado para a reconstrução tinha `state.json`
  modificado; esta evidência foi criada depois e está untracked. O digest local
  dos arquivos candidatos é
  `d78eca2cdccce517dbd281261d5c83ad72d9c3f5f159eaa4ff1842bb6f23c4b6`.
- O gate core deste commit passou `22/22` estágios, sem falha, bloqueio,
  skip ou estágio `not_run`. Relatório local:
  `artifacts/release-gates-rc1-core/release-gates.json`, SHA-256
  `1fc8cd7ea8c90ffaa15d5f880148849ba9bd414d5dd96b800aed3822ebef584a`.
- Bundle local gerado por
  `.venv-rag\Scripts\python.exe scripts/prepare_candidate.py --root . --output artifacts/rc1-assets-20260924-validation --python .venv-rag\Scripts\python.exe --profile core`.
  O `verify_candidate.py --root artifacts/rc1-assets-20260924-validation
  --source-root .` retornou `ok=true`, sem erros, no commit e digest acima.
  `audit_release.py --root . --candidate --json` retornou `ok=true`, sem
  findings. A inspeção posterior do wheel revelou que esses resultados não
  validaram a superfície interna do wheel.
- O bundle tem 31 arquivos, versão `2.0.0rc1`, manifest SHA-256
  `05f2bf54d5f113be48ba2332fd369f69e460385c47f85e029fc8e48afeb964c4` e
  `SHA256SUMS` SHA-256
  `b3b1ad888dc6b1c71388e79bb4d779d4abd7dfd5b31de179c25d8a3b799bc6a5`.
  A wheel `consulta_documentacao-2.0.0rc1-py3-none-any.whl` tem 408662 bytes,
  versão interna `2.0.0rc1` e SHA-256
  `f1ee6fb2c99b000949fa0763d28804c48ca13ec118d3db31e8ec7d58d02d6251`. Ela
  contém 164 entradas; três módulos Farol v3 (`docops/backends/legacy_knowledge_rag.py`,
  `docops/mcp_client.py` e `docops/rag_sync.py`) aparecem apenas no diretório
  ignorado `build/lib/`, não no código-fonte rastreado. `git check-ignore -v`
  confirma que `build/` é ignorado (`.gitignore:26:/build/`). O builder chama
  `pip wheel` diretamente contra a raiz do checkout e pode reaproveitar esse
  resíduo. Este bundle local fica rejeitado para distribuição; `build/` foi
  preservado sem alterações.
- A execução de push do GitHub Actions `35802632753` terminou com sucesso para
  o commit `be40e16f09153cfc12e3ea389302793f920c40b2` (13 jobs aprovados) e
  publicou o artefato `candidate-2.0.0rc1-be40e16f09153cfc12e3ea389302793f920c40b2`.
  A cópia baixada para `artifacts/rc1-ci-candidate-20260924/` foi verificada
  independentemente com `python scripts/verify_candidate.py --root
  artifacts/rc1-ci-candidate-20260924`: `ok=true`, sem erros; commit e digest
  CI `23af626b78dc2c5db09599c968dad335c03944793f3a800d4bdf68f8d4f2e51e`
  conferem com o manifesto. A wheel tem 390923 bytes, 161 entradas e SHA-256
  `61037e01e38e0085e0774b3007288c9759ee8e082eb60cc0b56a2581f778a7d4`; os
  três módulos residuais não estão nela. O manifesto CI tem SHA-256
  `28371ef4edea3d860d27ca55930db82230afba50148da095c2fcb7aed5d135e8` e
  `SHA256SUMS` tem SHA-256
  `7a792ee00dae0434a1088a989a6ae229b68032d38095b8b5a4dd840aaad4fc73`.
  Este artefato CI é o único bundle RC verificado nesta revisão; ele continua
  sem publicação. O repositório não contém tag ou GitHub Release RC.1.
- O builder precisa de uma fatia de correção: construir a wheel de um staging
  isolado dos arquivos candidatos e adicionar regressão para `build/lib/`
  obsoleto. TK-021 consta como `verified`; a precondição de execução da skill
  híbrida não pôde ser satisfeita porque `scripts/hybrid.py`/`.hybrid/` não
  existem neste checkout, então nenhuma mudança de código/status de ticket foi
  feita nesta continuação.
- `publication.performed=false`; a atestação de assinatura está
  `not-configured`.
- `run_book_to_skill_profile.py --json` passou nesta revisão: harness
  `526f362552562d88c1a8bbf8012d2cee93f831d5`, duas skills verificadas e
  escaneadas, hash de saída `79373f1fd679d3c9483372f6e6a64b18be0db0ebac90b35a43c2adafac98b21c`,
  sem alteração de estado externo. O relatório agregado anterior
  `artifacts/release-gates-rc1-book-to-skill/release-gates.json` (SHA-256
  `3dae40521bc4db3dc39e8c449a6eea513ebcda19b98d4f798fce507dcb9ddb06`)
  está incompleto: `ok=false`, sem `finished_at`, apesar de 13 etapas comuns
  passadas. Ele não foi convertido em aprovação do perfil agregado.
- `gh release view v2.0.0-rc.1` retornou `release not found`; não existe tag
  local ou remota `v2.0.0-rc.1`. Portanto, os assets verificados são locais e
  não há download público da RC.1. O wheel `1.1.0` previamente presente em
  `dist/` não é asset da RC.
- O gate full registrado em TK-020 é de `93bb8894d816aad3c3b3682ccec317db1da39d45`,
  não deste commit de preparação RC.1. Esta evidência não o reutiliza como
  gate full atual. O full gate deverá ser executado no commit final antes de
  qualquer decisão de GA.
- `.venv-rag\Scripts\python.exe scripts/run_ragflow_profile.py --json` foi
  executado para a RC atual e retornou `status=blocked`, `reason=missing_external_inputs`;
  faltam `DOCOPS_RAGFLOW_ENDPOINT`, `DOCOPS_RAGFLOW_TOKEN`,
  `DOCOPS_RAGFLOW_IMAGE_DIGEST` e `DOCOPS_RAGFLOW_SDK_VERSION`. O full gate
  atual não foi executado e permanece `not_run`, não aprovado.

## Backup Farol v3

- A tag anotada `farol-v3-backup-2026-09-21` existe localmente e em `origin`;
  objeto da tag `5fa11d68a3faec8ce24337a573fb2f30b20ff226`, apontando para o
  commit `79f9887c52e102351cd5c8d3b5ff7aaab5b7a07d`, árvore
  `358db1c1a89a3aa8d1ce07b5641e612c681be876`.
- A branch `farol-v3` local e remota aponta para o mesmo commit. A comparação
  `git diff --quiet refs/tags/farol-v3-backup-2026-09-21 refs/heads/farol-v3`
  terminou com código 0; tag e branch têm a mesma árvore.
- `git fsck --connectivity-only --no-reflogs --no-dangling refs/tags/farol-v3-backup-2026-09-21`
  terminou com código 0. A travessia encontrou 1707 objetos alcançáveis. O
  backup permanece retido; nenhum ref ou conteúdo foi alterado.

## Revalidação do estado remoto e do backup — 2026-09-25

- `origin/release/farol-2.0.0-rc.1` continua em
  `be40e16f09153cfc12e3ea389302793f920c40b2`. A API autenticada retornou zero
  releases e zero refs para `v2.0.0-rc.1`. Na captura desta auditoria, as 33
  entradas locais de hardening estavam sem commit; em seguida foram consolidadas
  em commit local limpo, ainda sem push. O run CI de 13 jobs no commit `be40`
  continua anterior às alterações e não verifica a fonte atual. O SHA local
  atual consta do manifesto do bundle final.
- O backup anotado segue íntegro: tag object
  `5fa11d68a3faec8ce24337a573fb2f30b20ff226`, target commit
  `79f9887c52e102351cd5c8d3b5ff7aaab5b7a07d`, árvore
  `358db1c1a89a3aa8d1ce07b5641e612c681be876`; `farol-v3` local/remota apontam
  ao mesmo target, `git diff --quiet` retornou 0 e `git fsck --connectivity-only`
  retornou 0 com 1707 objetos alcançáveis. As refs não foram alteradas.
- O full gate RC segue `not_run`/`blocked` até haver serviço e os quatro inputs
  RAGFlow; a ausência registrada pelo usuário permanece a fonte do bloqueio.

## Próximo passo

Quando serviço e inputs RAGFlow estiverem disponíveis, executar o full gate no
source registrado em `state.json`. Depois de autorização explícita de push,
atualizar o PR #16 para CI no source exato e revisão em `main` protegida; tag,
release e promoção a GA continuam decisões explícitas e separadas.

## Revalidação do backup Farol v3 — 2026-09-26

Comandos somente de leitura observados:

```powershell
git rev-parse refs/tags/farol-v3-backup-2026-09-21
git rev-parse "refs/tags/farol-v3-backup-2026-09-21^{}"
git rev-parse "refs/tags/farol-v3-backup-2026-09-21^{tree}"
git rev-parse refs/heads/farol-v3
git diff --quiet refs/tags/farol-v3-backup-2026-09-21 refs/heads/farol-v3
git ls-remote origin refs/tags/farol-v3-backup-2026-09-21 refs/tags/farol-v3-backup-2026-09-21^{} refs/heads/farol-v3
git fsck --connectivity-only --no-reflogs --no-dangling refs/tags/farol-v3-backup-2026-09-21
```

A tag local continua sendo o objeto `5fa11d68a3faec8ce24337a573fb2f30b20ff226`,
apontando ao commit `79f9887c52e102351cd5c8d3b5ff7aaab5b7a07d` e à árvore
`358db1c1a89a3aa8d1ce07b5641e612c681be876`. A branch local `farol-v3` aponta ao
mesmo commit; `git diff --quiet` e `git fsck --connectivity-only` terminaram com
código 0. `origin` mantém a mesma branch e tag anotada. Nenhuma ref ou conteúdo
do backup foi alterado.
