# Plano TDD para profissionalização pós-1.0

**Status:** execução Goal Mode concluída localmente em 2026-09-03; release
remains blocked by explicit remote and human gates

**Disciplina:** red → green por tracer bullet vertical; review/refactor somente
depois do green

**Regra central:** testar comportamento pelos contratos públicos, não pela
implementação interna

## 1. Contexto de execução

Este plano deriva de `docs/GITHUB-PUBLICATION-AUDIT-2026-09-02.md` e da
especificação `docs/POST-1.0-IMPROVEMENT-SPEC.md`. Os tickets 13–22 já tinham
implementação no working tree antes desta auditoria; não se deve repetir seus
reds históricos como se fossem falhas atuais. O objetivo presente é fechar
lacunas confirmadas, sem implementar nada durante a auditoria documental.

A execução implementadora preservou o working tree, leu as instruções e manteve
a proibição de commit/push/tag/release. Os reds, greens e gates observados
estão registrados nos tickets 23–29 e em `tasks/todo.md`.

## 2. Seams públicos aprovados

1. **CLI + JSON + pacote observável:** resolução, lifecycle, validação,
   avaliação, outcomes, códigos de saída e auditorias que o operador executa.
2. **Raiz Python instalada:** `import docops`,
   `OperationRequest`/`OperationOptions`/`OperationPlan`/`OperationResult`,
   `plan`, `preview`, `apply`, `inspect` e `cleanup`.
3. **Repositório Git candidato:** arquivos realmente rastreados/planejados,
   candidate digest e relatório do auditor.
4. **Wheel instalado:** execução fora do checkout nos perfis core e RAG.
5. **Fontes externas controladas:** filesystem temporário, HTTP fixture,
   repositório Git fixture e processo MCP real.
6. **Retrieval:** adapter memory em ciclos rápidos e MCP real em integração.
7. **Concorrência observável:** processos reader/writer observando apenas o
   pacote ativo, `inspect()` e outcomes.
8. **GitHub/readiness:** manifest, checksums, SBOM, metadata e evidência de CI;
   settings que exigem autenticação ficam em checklist humana.

Não são seams: helpers `_...`, call counts, ordem entre colaboradores, classes
internas, imports privados em novos testes ou a forma física do staging que
não aparece no contrato de `inspect()`.

## 3. Regras de cada ciclo

- **Red antes de green:** escrever um único cenário observável e executá-lo
  antes de tocar na implementação.
- **Um tracer por vez:** cada ciclo atravessa uma capacidade vertical; não
  escrever todos os testes do ticket antes de aprender com o primeiro.
- **Green mínimo:** fazer somente a mudança necessária para o red atual; não
  antecipar abstrações ou tickets bloqueados.
- **Fronteiras externas:** mockar apenas DNS/rede, subprocesso MCP, relógio,
  filesystem ou metadata de distribuição quando uma falha real não for
  controlável. Não mockar módulos próprios internos.
- **Esperados independentes:** usar literais da spec, fixtures conhecidas,
  códigos/outcomes e artefatos observáveis; nunca recomputar o esperado com a
  mesma função da implementação.
- **Review depois:** refactor, redução de duplicação e melhoria de locality
  entram depois do gate verde do ciclo; não misturar com o red/green.
- **Segurança:** canários devem ser redigidos; o teste verifica ausência do
  valor, e não imprime o segredo no relatório.
- **Registro:** cada red, green, comando, ambiente, resultado e limitação entra
  no ticket e em `tasks/todo.md`.

## 4. Ordem e dependências

| Ordem | Ticket | Tracer principal | Depende de |
|---:|---|---|---|
| 1 | 23 | digest/manifest de um candidate commit e mutação rejeitada | nenhum |
| 2 | 24 | o mesmo comportamento de lifecycle pela raiz `docops` | 23 para identidade final |
| 3 | 25 | interrupção de writer e `inspect()`/recuperação após reinício | 24 |
| 4 | 26 | raw `pip-audit` + provenance/checksum adulterado | 23; decisão humana Chroma |
| 5 | 27 | claim/job/runner inconsistente e clean clone sem dependências | 23, 24, 26 |
| 6 | 28 | metadata/assets/comunidade incoerentes no candidate | 23, 26, 27 |
| 7 | 29 | métricas de chunks e carga de reader/reindex | 24, 25, 27 |

Os arquivos executáveis de cada ticket estão em
`.scratch/post-1-0-reliability/issues/`. Nenhum desses ciclos foi iniciado
nesta auditoria.

## 5. Ciclos por ticket

### 23 — Identidade do candidato e evidência CI

**Red:** construir um bundle e alterar fonte ou manifest depois do digest;
comparar `source_commit`, lista, digest, wheel e evidência. O estado atual
consegue verificar checksums internos, mas não prova uma origem independente
nem impede que o working tree seja confundido com release.

**Green mínimo:** `audit_release --candidate`/`verify_candidate` devolve um
outcome estruturado e não zero quando commit, lista ou digest divergem; o modo
release exige referência alcançável e o manifest registra o mesmo SHA/digest
que o CI.

**Próximos tracer bullets:** arquivo novo, arquivo ignorado forçado, mudança
após `prepare`, wheel com versão divergente, workflow de SHA anterior e
candidate sem assinatura.

**Gate:** contracts, candidate audit, bundle verifier, wheel, supply chain,
clean clone, `git diff --check` e workflow remoto no SHA candidato. Publicação
continua fora do ciclo.

### 24 — Testes somente nos seams públicos

**Red:** pegar um cenário existente de update/falha que hoje depende de
`docops.pipeline`, `rag_sync`, `storage`, `lease` ou `package_validator` e
escrevê-lo pela raiz/CLI. Registrar a observação pública que falta ou a
divergência da documentação, sem testar o helper interno.

**Green mínimo:** migrar uma fatia para `docops`/CLI e manter o mesmo outcome,
imutabilidade e artefato observável; deixar caracterização do adapter legado
isolada e explícita.

**Próximos tracer bullets:** plan sem efeitos; apply/inspect; falha preservando
geração anterior; cleanup; ausência/drift RAG; wheel core/RAG.

**Gate:** busca estática revisada, suíte core/RAG, smoke sem RAG, contract
conformance, wheel e Ruff. Não criar teste de call count ou ordem interna.

### 25 — Recuperação pós-crash da promoção

**Red:** usar subprocesso e uma fronteira de filesystem controlada para
interromper o writer durante a promoção; reiniciar e observar que o contrato
atual não define restauração inequívoca em toda a janela.

**Green mínimo:** a próxima chamada pública preserva/restaura a geração válida
ou devolve um outcome recuperável; nunca reporta sucesso com ativo ausente.

**Próximos tracer bullets:** falha antes da troca, entre trocas, após troca;
reader concorrente; backup/staging expirado; cleanup com writer vivo; retomada
de staging válido.

**Gate:** testes públicos de lifecycle/reliability, processos reader/writer,
Windows e POSIX quando disponíveis, suíte, candidate audit e documentação de
limites de filesystem.

### 26 — Locks, provenance e Chroma

**Red:** rodar `pip-audit` cru em venv limpo e registrar os quatro advisories;
adulterar lock, provenance, vendor digest, modelo ou checksum e verificar que
a evidência atual não possui uma raiz independente de confiança.

**Green mínimo:** qualquer advisory fora da política falha; os quatro residuais
continuam visíveis e classificados; provenance/ref/digest e artefatos de lock
são verificados fora de paths locais ignorados.

**Próximos tracer bullets:** marker de plataforma, pacote transitivo, vendor ref
inexistente, modelo ausente, advisory novo do Chroma, attestation ausente e
attestation inválida.

**Gate:** venv limpo em versões supported, `pip check`, raw `pip-audit`, wrapper
strict, generator/verifier, vendor security, wheel e candidate audit. A
decisão humana de aceitar/mitigar/remover o perfil Chroma é pré-condição de
release; o red não pode ser escondido pelo allowlist.

### 27 — Suporte executado e bootstrap limpo

**Red:** numa cópia temporária, declarar claim/job/runner sem gate e executar o
checker; executar clean clone antes de instalar dependências e capturar o
diagnóstico atual de pytest ausente.

**Green mínimo:** o checker valida estrutura real de YAML/jobs/claims e o
clean-clone informa o bootstrap/perfil necessário ou instala o perfil de modo
documentado, sem depender do launcher global.

**Próximos tracer bullets:** Python 3.11/3.12/3.13, Ubuntu/Windows/macOS,
wrappers por shell, RAG opcional/obrigatório, symlink capability, wheel e
filesystem.

**Gate:** CI de três runners, clean clone novo, wrappers, doctor, matrix
checker, wheel e RAG real onde o claim existir. Python 3.14 permanece tolerated
e não ganha claim por conveniência local.

### 28 — GitHub, distribuição e comunidade

**Red:** validar o candidate contra checklist de metadata/assets e comparar com
o perfil público; registrar descrição/homepage/topics/health/assets/community
ausentes. Settings autenticadas devem aparecer como “não verificadas”, não como
pass.

**Green mínimo:** verificador local exige identidade coerente, assets mínimos e
arquivos de comunidade reconhecíveis; gera checklist para settings humanas sem
mutá-las.

**Próximos tracer bullets:** README/package identity; Code of Conduct,
CONTRIBUTING, issue/PR; release assets; checksum/SBOM; CODEOWNERS; branch rules;
secret scanning/push protection/Dependabot.

**Gate:** candidate audit, bundle verifier, README/link check, health check
público, retenção do candidate no artifact `candidate-1.1.0-${GITHUB_SHA}` e
retenção dos resultados RAG redigidos no artifact de integração; revisão
autenticada antes de qualquer publicação humana.

### 29 — Métricas e stress operacional

**Red:** executar a fixture de dois documentos e mostrar a divergência entre
`chunks` do operador e `server_stats.total_chunks`; executar o stress atual e
registrar sua baixa contagem de buscas.

**Green mínimo:** nomes/semântica distinguem as contagens, fixture verifica a
relação e o stress reporta carga mínima determinística, erros e estado final.

**Próximos tracer bullets:** corpus vazio, documento longo, full rebuild,
readers simultâneos, writer busy, timeout e warning do backend.

**Gate:** run indexado, validate, evaluate MCP, stress, suíte, Ruff e candidate
audit. O relatório continua redigido.

## 6. Gating global e encerramento

Depois de cada ticket (cumprido nesta execução):

1. registrar o red e o green no ticket;
2. executar o gate proporcional e a regressão do seam público;
3. revisar diff e documentação, sem formatar arquivos não relacionados;
4. atualizar `tasks/todo.md`, `CHANGELOG.md` quando o ticket pedir e o status
   da spec;
5. conservar falhas ambientais separadas de defeitos do produto;
6. não marcar release-ready enquanto candidate commit, CI do mesmo SHA,
   supply-chain/CVE decision, clean clone, wheel, RAG real e revisão humana
   não estiverem todos evidenciados.

Gates finais obrigatórios, na ordem documentada em `docs/RELEASE.md`:

```text
python scripts/bootstrap.py --dev
python -m docops doctor --json
python scripts/audit_dependencies.py --requirements requirements.lock --local --strict
python scripts/check_support_matrix.py --json
python scripts/check_contracts.py --json
python -m pytest -q
python -m ruff check docops tests scripts
python -m ruff format --check docops tests scripts
python scripts/verify_clean_clone.py
python scripts/verify_wheel.py
python scripts/run_release_gates.py --profile ragflow --json
python scripts/run_release_gates.py --profile ragflow --json
python scripts/audit_release.py --candidate --json
python scripts/prepare_candidate.py --root . --output artifacts/candidate-1.1.0
python scripts/verify_candidate.py --root artifacts/candidate-1.1.0
```

No ciclo final pode executar publicação; a autorização humana é um passo
separado após os resultados.

## 7. Critério de qualidade do plano

Um teste é mantido se continuaria válido depois de substituir a implementação
interna mantendo a interface. Um ticket é concluído somente quando há um
comportamento observável, uma evidência independente e uma documentação que
não promete mais que o gate executou. Complexidade que não aumenta leverage ou
locality deve ser recusada na revisão.
