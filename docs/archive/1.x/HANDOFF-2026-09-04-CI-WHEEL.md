# Handoff de continuidade — follow-up do CI do wheel RAG

> **Snapshot atual desta execução (2026-09-04):** esta seção é a referência
> operacional vigente; as seções abaixo preservam o histórico do checkpoint.
>
> - O checkout local estava limpo no momento do snapshot; o SHA exato do
>   candidate deve ser lido no manifesto abaixo. `origin/main` ainda aponta
>   para `912599c8dc6ab7bde30e27a2cc27f0c1f1107c41`.
> - O candidate `1.1.0` final está em `artifacts/candidate-1.1.0/`; leia
>   `candidate-manifest.json` e `candidate-identity.json` para o SHA e digest
>   exatos, evitando referência circular neste handoff.
> - A suíte raiz passou com **234 testes**, o clone limpo passou com **234
>   testes**, o wheel core/RAG e o supply-chain independente passaram, e o
>   smoke/stress RAG final passou sem erros ou warnings.
> - `verify_candidate.py` normal e com `--source-root .` passaram. O modo
>   `--release` continua falhando fechado por ausência de ref/CI do mesmo SHA e
>   pela decisão humana pendente sobre o residual Chroma.
> - Nenhuma tag, release, publicação, anúncio ou alteração de settings foi
>   realizada. Os bloqueios e a sequência de retomada estão em
>   `docs/RELEASE-READINESS-2026-09-04.md` e
>   `docs/PRODUCTION-PUBLICITY-PLAN.md`.

**Data do checkpoint:** 2026-09-04
**Repositório:** `VIDORETTO/agent-knowledge-kit`
**Branch:** `main`
**Base conferida antes da correção:** `7916083df3e930cdaff1e40968040d90ac8e9428` (`HEAD == origin/main`)

## Onde a execução anterior parou

A execução anterior já havia enviado o commit `7916083`. O follow-up ficou
parado na análise do CI desse commit:

- o job Linux do wheel RAG falhou no run `33887455346`;
- a causa raiz confirmada foi o FastEmbed criar symlinks em
  `rag/models_cache`, contaminando o pacote distribuível;
- o wheel RAG real passou localmente em Linux/Python 3.12 e
  Windows/Python 3.14;
- os testes focados reportados eram `7 passed`;
- Ruff, formato, contratos, public seams, matriz de suporte e
  `git diff --check` haviam passado;
- a suíte completa foi interrompida por volta de 35–40%, sem resultado final
  coletado; os dois skips esperados eram de symlink no Windows;
- a correção ainda não tinha commit, push ou novo CI;
- o candidate anterior, produzido a partir de `7916083`, ficou obsoleto;
- nenhuma tag ou release foi criada;
- permanece pendente a decisão humana sobre os quatro CVEs residuais de
  `chromadb==1.5.9`.

## Resultado do primeiro push e correcao adicional encontrada no CI

O primeiro push desta continuacao criou o run `33891442751` para o commit
corretivo. O job `wheel / Python 3.12` passou pela construcao, smoke RAG,
candidate, supply chain e re-medicao de identidade; somente a etapa final de
release falhou de forma esperada por `human_decision_pending`.

Os jobs quick e clean-clone ainda reprovaram os testes do candidate, com a
mesma assinatura ja observada no CI do commit `7916083`: a rotina resolvia
`bin/python` de um venv POSIX para o interpretador de sistema e perdia o `pip`
instalado no venv. A reproducao em um checkout nativo Linux/WSL confirmou a
causa. A correcao adicional em `scripts/prepare_candidate.py` conserva o
launcher do venv e apenas o torna absoluto, sem resolver symlinks.

Depois desse run, `origin/main` avancou por cinco commits do mesmo fluxo:
`1a9fcfa` (runtime do candidate e gate de release manual), `7598016` (fallback
para bootstrap sem `pip`), `754960f` (isolamento do teste de identidade),
`1c034a2` (identidade de clone sem Git) e `9d236ce` (durações positivas nos
recibos de fase). Todos foram preservados no rebase deste checkpoint.

## Correções e estado local atual

A primeira correção faz duas coisas relacionadas à causa raiz:

1. `docops/rag_sync.py` gera `models_cache_dir: ~/.cache/docops/models`, fora
   da árvore do pacote. O cache é estado de execução, não artefato
   distribuível.
2. `scripts/verify_wheel.py` extrai `errors` e `outcome` do JSON de uma CLI que
   falhou, preservando o diagnóstico estruturado mesmo quando o relatório é
   maior que o limite de saída.

A correção adicional preserva launchers POSIX de ambientes virtuais durante a
construção do candidate; `Path.resolve()` não é usado para o interpretador
selecionado.

Há regressões para a configuração renderizada pelo pipeline e para o
diagnóstico do verificador em `tests/test_pipeline.py`, `tests/test_rag_sync.py`
e `tests/test_verify_wheel.py`. A documentação operacional foi alinhada em
`docs/USE.md`; o checklist e as lições desta execução ficam em
`tasks/todo.md` e `tasks/lessons.md`.

## Evidência coletada nesta continuação

- Identidade inicial confirmada: `main`, `HEAD == origin/main`, base
  `7916083df3e930cdaff1e40968040d90ac8e9428`.
- O run `33891442751`, no primeiro commit corretivo, confirmou o caminho feliz
  do pacote RAG e deixou apenas o bloqueio humano do modo release; os demais
  jobs falharam nos testes de candidate antes da correção adicional descrita
  acima.
- A falha do candidate foi reproduzida em Linux/WSL: um launcher
  `.../.venv/bin/python` é symlink para `/usr/bin/python3.12`, que não tinha
  `pip`; preservar o caminho do launcher elimina essa perda de ambiente.
- Testes focados executados:
  `python -m pytest -q tests/test_pipeline.py tests/test_rag_sync.py tests/test_verify_wheel.py` —
  `21 passed, 1 skipped`; o skip é a criação de symlink indisponível neste
  host Windows.
- A suíte anterior, executada com o Python local tolerado 3.14.2, ficou em
  `228 passed, 2 skipped in 419.82s`; os skips são os testes de symlink
  `tests/test_package_contract.py` e `tests/test_pipeline.py` neste Windows.
- A suíte atual, executada no `.venv` do projeto com as versões fixadas,
  passou em `230 passed, 2 skipped in 424.88s`; os mesmos dois skips de symlink
  permanecem esperados neste Windows.
- Os testes atuais de candidate e identidade passaram no `.venv`:
  `10 passed in 100.16s`, incluindo o fallback de um venv criado com
  `--no-install` e sem `pip`.
- Ruff lint, Ruff format, contratos, matriz de suporte, workflows, public seams,
  `compileall` e `git diff --check` passaram.
- `audit_release.py --tracked-only --json` passou com 401 arquivos e
  `audit_release.py --candidate --json` passou com 403 arquivos.
- `pip check` passou no ambiente `.venv` do projeto. O interpretador global
  tinha pacotes externos inconsistentes e não foi usado como evidência do
  projeto.
- Wheel core passou em sequência com `adapter=memory`, `rag=false`; wheel RAG
  passou em sequência com o `.venv` do projeto, `adapter=mcp`, `rag=true`.
- Antes da rebase sobre os cinco commits remotos, um candidate RAG novo foi
  gerado e verificado independentemente com sucesso. Ele pertence ao SHA
  anterior e está obsoleto; o candidate deve ser regenerado depois do commit
  final deste checkpoint. O digest deve ser lido de `candidate-identity.json`,
  sem ser copiado para este documento.
- Uma primeira tentativa paralela dos dois wheels foi descartada: o core teve
  `WinError 2` por corrida nos diretórios de build compartilhados e o RAG foi
  iniciado no interpretador global sem o backend. Após remover somente os
  diretórios gerados/ignorados e executar sequencialmente, ambos passaram.

## Resultado do push final e do CI

O commit de código `6b850adab2b20163a688c475f60dbb78e2216d2e` foi enviado para
`origin/main`. O run `33897740714` do workflow `CI` terminou com sucesso para
esse SHA: os 13 jobs passaram, incluindo wheel Linux/Python 3.12, clean clone
em Ubuntu/Windows/macOS e a matriz quick em Python 3.11, 3.12 e 3.13. O gate
`--release` não é executado em push; ele continua manual e fail-closed.

O handoff e as atualizações de checklist deste documento são uma alteração
documental posterior ao commit de código testado. Se essa alteração gerar um
novo SHA, o CI desse SHA deve ser tratado como a verificação final da árvore,
sem confundir o resultado acima com o novo commit documental.

## Estado após o commit local

O diff foi revisado, o primeiro commit corretivo foi criado e enviado, os cinco
commits que avançaram o remoto foram preservados e o CI do commit de código
final passou. Este handoff está sendo atualizado em um commit documental
posterior; em um computador novo, confirme o estado sincronizado com
`git log -1`, `git rev-parse HEAD`, `git rev-parse origin/main` e `git status
--short`.

Continuidade pós-push:

- conferir que `origin/main` aponta para o novo `HEAD`; o CI do commit de código
  `6b850ad` já passou no run `33897740714`, e qualquer commit documental
  posterior deve ter seu próprio run conferido;
- considerar o candidate gerado pelo CI como o novo candidate, pois qualquer
  bundle anterior baseado em `7916083` não representa esta correção;
- manter release/tag/publicação bloqueadas até a revisão autenticada das
  settings do GitHub e a decisão humana sobre o residual do Chroma;
- não commitar `documents/`, `data/`, `models_cache/`, ambientes, caches ou
  `artifacts/`.

O commit que contém este handoff deve ser identificado com `git log -1` após o
push; este documento não repete seu próprio SHA para evitar referência
circular na identidade do candidate.

## Fechamento da correção de concorrência — 2026-09-04

Durante a execução deste follow-up, o stress remoto ainda falhava porque o
backend instalado pelo PyPI não era a mesma árvore revisada usada pelo DOCOPS.
Depois de apontar o harness para `skills/vendor/knowledge-rag`, a reprodução
local confirmou uma segunda falha real: uma consulta semântica podia receber
`metadata=None` enquanto o Chroma era reindexado e quebrar antes de produzir
uma resposta MCP.

A correção final foi implementada no vendor com TDD: o teste
`TestSemanticMissingMetadataSkipped` falhou com o `AttributeError` original e
passou após o pipeline passar a descartar linhas sem metadados de citação.
Os caminhos de consulta híbrida, FTS5 e similaridade também passaram a falhar
fechados para esse estado transitório; nenhum resultado sem `source` é emitido.
O patch está descrito em `skills/vendor/knowledge-rag/PROVENANCE.json` e no
changelog.

Evidência observada para o commit de código enviado:

- suíte raiz: **233 passed**;
- suíte completa do vendor: **761 passed, 6 skipped, 5 deselected, 8 xfailed**;
- stress local com vendor revisado: **370 buscas**, quatro warmups, zero erros
  ou warnings, reindex bem-sucedido e sem resíduo recuperável;
- CI `33899411357`: todos os 13 jobs passaram, incluindo quick em Ubuntu,
  Windows e macOS para Python 3.11–3.13, clean clone nos três sistemas e
  wheel/candidate RAG;
- Integration `33899437593`: **20.866 buscas** concorrentes, zero erros ou
  warnings, reindex terminal bem-sucedido e índice final com 2 documentos/4
  chunks; avaliação MCP com Recall@5/MRR@5 **1,0**;
- o artifact `candidate-1.1.0-<commit>` do CI passou `verify_candidate.py`
  tanto isolado quanto com `--source-root .`; o candidate RAG local com
  `--profile rag --require-model` também passou supply-chain e verificação
  independente.

Os digests continuam somente nos manifests/identities dos artifacts, para não
criar referência circular ao modificar esta documentação. Nenhum corpus,
índice, cache, modelo, ambiente ou artifact gerado foi versionado.

O produto está pronto para revisão de publicação. Ainda não foram criados tag,
release ou publicação: o modo `--release` permanece fail-closed até um
mantenedor registrar a decisão sobre os quatro CVEs de `chromadb==1.5.9` e
confirmar, autenticadamente, branch protection, reviewers, secret scanning,
push protection e permissões de release.
