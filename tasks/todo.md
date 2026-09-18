# Planejamento master de evolução — 2026-09-07

Escopo: estudar `docs/MASTER-PLANNING-BRIEF.md` e o checkout atual; entregar
diagnóstico, especificações, fases, tickets locais e plano TDD. Somente documentos.
Preservar alterações anteriores deste arquivo e o briefing ainda não versionado.

- [x] Ler briefing, instruções, lessons e skills to-spec/to-tickets/tdd.
- [x] Confirmar branch, SHA, remoto e estado inicial.
- [x] Confrontar as 12 hipóteses com código, contratos e testes.
- [x] Especificar arquitetura, init, estado, governança, RAG e preset Mercado Livre.
- [x] Criar roadmap, tickets verticais com dependências e guia TDD.
- [x] Verificar cobertura, referências e consistência; registrar limites da evidência.

Plano conferido contra o pedido: reutilizar o lifecycle existente; não implementar,
publicar, instalar scheduler nem alterar corpus, índice ou versão ativa. Tickets
locais são a entrega solicitada, sem publicação em tracker externo.

## Revisão desta entrega

Entrega: docs/MASTER-PLAN.md, docs/MASTER-IMPROVEMENT-PLAN.md e
docs/master-evolution/ com SPEC, contratos, evidências, qualidade, preset,
roadmap, guia TDD e 24 tickets individuais distribuídos em seis fases (P0–P5).
Diagnóstico cobre 12 hipóteses; roadmap mapeia as 14 perguntas do brief.

Verificação: dois runs focados com 50 passed (233,58s) e 42 passed (59,90s),
com sobreposição explicitada em TDD-EXECUTION.md. Checker documental passou;
o defeito preexistente de flags no guia foi confirmado por help da CLI e
registrado para T01, sem correção de runtime nesta etapa. Revisão cruzada
alinhou permissões por finalidade, precisão de datas, enum de claims/conflitos,
recuperação de composição e dependência de P5 nos gates de distribuição.

Nenhuma implementação, commit, push, publicação, scheduler, captura de fontes
reais ou alteração de corpus/índice ativo foi realizada. Métricas históricas,
CVEs atuais, direitos comerciais e benchmark multilíngue não foram apresentados
como evidência nova. O briefing e alterações anteriores em todo.md foram preservados.

# Análise comparativa para consolidação da main — 2026-09-05

Objetivo: comparar o baseline `main`, o working tree local e
`origin/feat/continuous-knowledge`; decidir a arquitetura-alvo para aprendizado
contínuo e uso agente-first das skills; produzir somente documentação de
especificação, tickets e TDD. Nenhuma implementação, merge, rebase, commit,
push, publicação, reindexação ou alteração de estado ativo faz parte do escopo.

## Auditoria do produto agent-first — 2026-09-07

Objetivo: avaliar o estado atual do projeto como sistema autônomo de geração de
skill, atualização contínua e consulta RAG para agentes de IA; separar o que é
comprovado no código/gates do que ainda depende de harness, política ou ação
humana.

### Plano executável

- [x] Confirmar checkout, branch, remoto, instruções e lessons relevantes.
- [x] Mapear o fluxo completo: fonte → skill/router → candidata → publicação → reader/RAG.
- [x] Auditar autonomia, atualização incremental, remoção, citações, segurança,
  observabilidade e pontos de falha.
- [x] Rodar verificações proporcionais: suíte, lint/contratos e gates de integração
  disponíveis no snapshot atual.
- [x] Comparar a evidência atual com os objetivos do produto e atribuir nota por eixo.
- [x] Registrar revisão, limitações, riscos prioritários e veredito final.

### Revisão e evidências

- Checkout auditado: branch `codex/main-consolidation`, commit `c438c82`; a
  alteração deste arquivo é somente o registro desta auditoria.
- Suíte no ambiente do projeto (`.venv\Scripts\python.exe`): **373 passed,
  3 skipped**, sem falhas. O primeiro comando usou o Python global e produziu
  três falsos negativos por ambiente; os três testes foram repetidos no `.venv`
  e passaram.
- Ruff, contratos, matriz de suporte, seams públicos, documentação como módulo,
  auditoria de release e configuração passaram. O gate registrado para o mesmo
  commit tem 22/22 estágios verdes, incluindo wheel, clean clone, MCP real,
  crash/recovery, revogação e concorrência RAG.
- O produto é forte como pipeline local/single-writer operado por agente: gera
  skill/router, corpus normalizado, RAG híbrido com citação, snapshots pinned,
  leases, checkpoints, candidatos, rollback e fila idempotente.
- O produto ainda não é um serviço autônomo “zero usuário”: o arquivo sozinho
  não dispara o ciclo; reconcile e worker dependem de scheduler externo, o CLI
  expõe `work --once`, o fold-in conceitual depende de `book-to-skill` externo e
  publicação exige candidate/approval/publish explícitos.
- Limitações/riscos: perfil padrão de embedding é focado em inglês e PT-BR exige
  perfil multilíngue + rebuild completo; o Golden RAG observado é pequeno e
  sintético; o suporte declarado é Python 3.11–3.13; há quatro CVEs residuais
  documentados do Chroma para o uso local permitido; `operations.py` é um
  hotspot de manutenção.
- Veredito: **8,2/10 técnico**, **8,8/10 para o escopo documentado agent-first**
  e **6,4/10 para a promessa adicional de autoatualização totalmente autônoma
  sem ação do usuário**. Estado: candidato técnico sólido/estável em execução
  local preparada, ainda não produto autônomo de produção.

## Briefing master para evolução do sistema — 2026-09-07

- [x] Consolidar as mensagens iniciais e a correção de escopo do caso Mercado Livre.
- [x] Separar requisitos do núcleo genérico, do `init`, do curso, da página e do domínio.
- [x] Criar briefing Markdown para estudo externo e planejamento master, sem implementação.
- [x] Revisar requisitos de fontes, transcrições, RAG, atualização, versionamento e governança.
- [x] Incluir no briefing os problemas atuais, lacunas e o pedido de um documento de melhorias verificável.

## Plano

- [x] Confirmar repositório, branch, remoto, baseline, working tree e instruções.
- [x] Ler integralmente as skills `to-spec`, `to-tickets` e `tdd` e seus
  materiais obrigatórios.
- [x] Buscar `origin/feat/continuous-knowledge` e confirmar ancestralidade.
- [x] Inventariar baseline, branch remota e working tree por capacidades,
  contratos, estado, CLI, skills, segurança, testes e documentação.
- [x] Simular integração fora do working tree e registrar conflitos textuais e
  semânticos.
- [x] Executar verificações somente leitura/proporcionais para validar as
  conclusões, sem modificar a implementação.
- [x] Definir a decisão arquitetural e a estratégia de consolidação da main.
- [x] Criar uma especificação completa no formato `to-spec`.
- [x] Criar tickets locais tracer-bullet, um arquivo por ticket, com blockers.
- [x] Criar o plano TDD por seams públicos, RED → GREEN e gates de estabilidade.
- [x] Revisar documentos contra as evidências, registrar limitações e concluir
  esta seção com o veredito final.

## Revisão

- Baseline: `HEAD == origin/main == 15cfaa6a919eaac7fca315241a4b396b1902f8f8`.
- Comparado com `origin/feat/continuous-knowledge == 2eaa9c24c9f809db0e0ce8b73206500ba1ed73e6`.
- A branch remota está 10 commits à frente e 0 atrás; o histórico limpo permite
  fast-forward, mas o working tree local sobrepõe 41 dos 88 caminhos remotos.
- A simulação isolada encontrou 33 conflitos: 29 de conteúdo e 4 `add/add`.
- Decisão: consolidação seletiva orientada por contratos, preservando o núcleo
  modular local e portando `docops-agent`, distribuição, router/harness e
  enforcement MCP read-only da branch remota.
- Branch remota verificada em clone isolado: 260 testes passaram, 2 foram
  ignorados; Ruff, contratos, documentação e `git diff --check` passaram.
- Working tree: Ruff, 33 contratos e `git diff --check` passaram. O teste
  `test_candidate_falls_back_when_bootstrap_no_install_leaves_a_venv_without_pip`
  permanece falhando e bloqueia promoção.
- Documentos produzidos em `docs/main-consolidation/`: comparação/decisão,
  especificação, plano TDD e 13 tickets tracer-bullet.
- Três auditorias independentes GPT-5.6 Luna/max revisaram Git/conflitos,
  arquitetura e aderência às skills; os documentos foram corrigidos para
  separar evidência observada de requisito futuro.
- Tickets permanecem `draft-pending-confirmation`; publicação local em
  `.scratch/main-consolidation/issues/` só ocorre após confirmação humana de
  granularidade, seams e blockers.
- Nenhuma implementação, integração, publicação, reindexação, commit ou push
  foi realizada.

---

# Execução do planejamento de atualização contínua de conhecimento — T01–T18

Objetivo: implementar os 18 tickets de `docs/continuous-knowledge/` por
seams públicos, em ciclos RED → GREEN → REFACTOR, preservando compatibilidade
e as invariantes de segurança. Esta seção pertence à execução atual; o
histórico abaixo foi preservado.

## Plano executável

- [x] Revalidar estado inicial, contratos e seams públicos.
- [x] T01 — proteger skill enriquecida contra sobrescrita.
- [x] T02 — vincular revisões e evidências aos hashes exatos.
- [x] T03 — separar atualização factual da camada conceitual.
- [x] T04 — preparar candidata sem ativar.
- [x] T05 — comprovar indexação, erros terminais e perfil real.
- [x] T06 — receber enriquecimento externo em candidata.
- [x] T07 — avaliar candidata/resposta com evidência independente.
- [x] T08 — aprovar e publicar hashes exatos.
- [x] T09 — reter e restaurar gerações publicadas.
- [x] T10 — registrar fontes e reconciliar escopo completo.
- [x] T11 — persistir eventos com deduplicação e debounce.
- [x] T12 — executar jobs com lease, retomada e autorização.
- [x] T13 — disparar enriquecimento por impacto conceitual.
- [x] T14 — fixar geração por sessão e restringir MCP de consulta.
- [x] T15 — reaproveitar índice apenas com snapshot consistente.
- [x] T16 — preservar localizadores e avaliar português/formats.
- [x] T17 — verificar propostas de conversa antes da admissão.
- [x] T18 — priorizar investigação por uso e qualidade.
- [x] Executar suíte completa, lint, contratos e verificações públicas.
- [x] Atualizar documentação normativa, tickets, status e lições quando aplicável.
- [x] Revisar diff final; não fazer deploy, push, release, reindex real ou captura.

## Execução concluída — T10

- [x] RED: registrar uma segunda fonte falhou porque o seam ainda não existia.
- [x] GREEN: registrar fontes, versões, direitos, privacidade e completude.
- [x] REFACTOR: separar registro desejado, observação de aquisição e retirada
  autorizada.
- [x] Rodar testes públicos e contratos; lint/formato e diff-check seguem no
  gate regressivo da execução.
- [x] Atualizar ticket/status/contratos sem publicar ou alterar corpus ativo.

## Execução concluída — T11

- [x] RED: o primeiro teste falhou porque `event-submit`/`jobs` ainda não
  existiam.
- [x] GREEN: registrar eventos duráveis por identidade e janela.
- [x] REFACTOR: separar emissão, deduplicação e reconciliação.
- [x] Rodar testes públicos, contratos, lint/formato e diff-check.
- [x] Atualizar ticket/status/contratos sem publicar ou alterar corpus ativo.

## Execução atual — T12

- [x] Ler o ticket, confirmar T08/T11 e definir o primeiro seam de worker.
- [x] RED: o primeiro teste falhou porque o comando `work --once` ainda não existia.
- [x] GREEN: lease, retomada e autorização persistida.
- [x] REFACTOR: separar aquisição de lease, execução e reconhecimento.
- [x] Rodar cenários de política, autorização ausente, crash/retomada,
  eventos durante execução e retry transitório limitado.
- [x] Atualizar ticket/status/contratos sem publicar ou alterar corpus ativo.

## Execução concluída — T12

- [x] `work --once` reclama um job com lease e executa uma operação limitada.
- [x] Recibo por job/revisão reconcilia o efeito após crash sem duplicação.
- [x] Autorização RAG persistida é obrigatória e autopublicação fica bloqueada.
- [x] Retries têm limite; eventos concorrentes ficam para lote posterior.
- [x] Testes focados, contratos, Ruff e diff-check passam em fixtures sintéticas.

## Execução concluída — T13

- [x] Ler o ticket, confirmar T06/T10/T12 e definir o primeiro seam de impacto.
- [x] RED: os testes públicos falharam porque `impact-assess` ainda não existia.
- [x] GREEN: cursor por documento/revisão, impacto líquido, lote, backlog e
  revogação.
- [x] REFACTOR: contrato `conceptual-impact` e CLI sem acoplamento ao SQLite.
- [x] Rodar testes focados, contratos, Ruff e diff-check em fixtures sintéticas.
- [x] Atualizar ticket/status/contratos sem publicar ou alterar corpus ativo.

## Execução concluída — T14

- [x] Ler o ticket, confirmar T08/T09 e definir o seam público de sessão leitora.
- [x] RED: os testes públicos falharam porque `reader-session` ainda não existia.
- [x] GREEN: sessão pinada, query somente leitura, cache por geração e revogação.
- [x] REFACTOR: mover estado runtime para `.<package>.readers/`, separado da
  composição ativa e ignorado pelo Git.
- [x] Atualizar schemas, contratos, ticket, status e uso operacional.
- [x] Rodar teste focado; gates conjuntos ficam para a verificação final.

## Execução concluída — T15

- [x] Ler o ticket, confirmar T05/T09/T14 e definir o seam público de snapshot.
- [x] RED: os testes públicos falharam porque `rag-snapshot` ainda não existia.
- [x] GREEN: snapshot relocável, diff por hash, fallback de rebuild e
  verificação de busca sem promoção.
- [x] REFACTOR: encapsular inventário do backend e plano incremental no módulo
  `docops.rag_sync`, com schemas e exemplos versionados.
- [x] Rodar os cinco testes públicos focados e atualizar contrato/uso/status.
- [x] Registrar limitações, evidência sintética e rollback sem tocar no índice
  ativo.

## Execução atual — T16

- [x] Ler o ticket, confirmar T05/T07/T10 e definir o seam público de
  localizadores e formatos.
- [x] RED: a busca pública não devolvia `locators`; a comparação de perfil ainda
  não tinha comando público.
- [x] GREEN: preservar localizadores/citações, declarar limites sem localizador,
  aceitar transcrição somente como Markdown externo, quarentenar extrações
  suspeitas e expor `rag-profile-compare`.
- [x] REFACTOR: padronizar o envelope de localizador e separar o diagnóstico de
  perfil da mutação/reindexação.
- [x] Rodar testes focados, contratos, Ruff, formato e diff-check.
- [x] Atualizar ticket/status/contratos/uso sem publicar ou alterar corpus ativo.

## Execução concluída — T17

- [x] RED: propostas de conversa não tinham seam público nem quarentena.
- [x] GREEN: `learning-submit` exige opt-in e minimização; `learning-review`
  exige autoridade/evidência e mantém conversa não revisada fora do RAG ativo.
- [x] REFACTOR: preferências privadas, fatos derivados, revogação e tombstones
  ficaram separados da composição ativa; rollback não ressuscita revogados.
- [x] Verificação: `rtk pytest -q tests\test_learning.py` — 3 passed;
  contratos/Ruff/formato/diff-check no gate regressivo.
- [x] Nenhuma conversa real, captura abrangente, publicação ou reindexação foi
  executada.

## Execução concluída — T18

- [x] RED: o primeiro teste falhou porque `feedback-submit` ainda não existia.
- [x] GREEN: `feedback-submit` redige perguntas e guarda hashes/métricas;
  `feedback-report` agrega uma janela de sete dias, deduplica ocorrências por
  sessão/pergunta/geração e abre investigação somente após três ocorrências.
- [x] REFACTOR: `work --once` aceita o job `feedback_report` e reconhece um
  recibo durável; a execução nunca altera Golden, resposta esperada ou RAG
  ativo. Candidatas permanecem `reviewed=false`.
- [x] Verificação: `rtk pytest -q tests\test_usage_feedback.py` — 3 passed;
  `scripts/check_contracts.py --json` e Ruff PASS.
- [x] Relatórios incluem latência/custo, denominadores e `not_comparable` para
  gerações/conjuntos incompatíveis; nenhuma pergunta privada sai na projeção.
- [x] Limite: o seam só prepara investigação/candidata local; revisão humana,
  publicação e eventual reindexação continuam gates separados.

## Verificação final da execução T01–T18

- [x] Suíte completa no `.venv` alinhado ao lock: `317 passed, 2 skipped`;
  os dois skips são apenas a indisponibilidade de criação de symlink neste
  host Windows.
- [x] Gates estáticos: Ruff lint, Ruff formato, `compileall`,
  `scripts/check_contracts.py --json`, `scripts/check_support_matrix.py --json`,
  `scripts/check_public_seams.py --json` e `git diff --check`.
- [x] RED foi observado nos seams públicos registrados para cada ticket; os
  focused checks de T17 e T18 passaram com 3 testes cada.
- [x] As fixtures e estados operacionais usados nesta execução são sintéticos
  e temporários; nenhum corpus, índice ativo, conversa real ou publicação foi
  alterado.
- [x] A evidência de MCP real permanece restrita ao pacote sintético isolado
  documentado em T05; T17–T18 não executam MCP, harness externo ou captura real.
- [x] Nenhum ticket foi fechado com stub essencial, TODO de implementação ou
  gate ignorado; revisão final preservou mudanças preexistentes do worktree.

## Critérios de execução

- [x] T01 — proteção de artefatos gerados implementada e verificada.
- [x] T02 — revisões estáveis e invalidação observável implementadas; a parte
  de aprovação humana permanece no gate específico do T08.
- [x] T03 — atualização factual preserva a camada conceitual e registra
  defasagem/cobertura desconhecida.
- [x] T04 — política candidata prepara artefato revisável/retomável sem
  alterar a geração ativa; aprovação fica reservada ao T08.
- [x] T05 — indexação só declara sucesso com conclusão, stats e busca
  verificáveis; fingerprint efetivo e full rebuild por mudança de embedding
  registrados; MCP real executado apenas em pacote sintético temporário.
- [x] T06 — hand-off externo determinístico, recibo com hashes e importação
  restrita à candidata; submissão não publica nem aceita credenciais.

- [x] Cada ticket teve RED funcional observado antes do GREEN.
- [x] Fixtures são sintéticas e os estados operacionais ficam em temporários.
- [x] Integração MCP real, quando disponível, foi reportada separadamente das
  fixtures.
- [x] Nenhum ticket foi marcado concluído com stub essencial, TODO ou gate
  ignorado.

---

# Registro de autoanálise e especificação pós-1.0

## Plano autônomo de prontidão para produção e divulgação — 2026-09-04

O plano ponta a ponta, com fases, gates, canário, divulgação progressiva,
rollback e limites de autonomia, está em
[`docs/PRODUCTION-PUBLICITY-PLAN.md`](../docs/PRODUCTION-PUBLICITY-PLAN.md).
Esta seção é a checklist de retomada do Goal Mode; ela não transforma gates
humanos ou publicação externa em ações implícitas.

### Estado de entrada revalidado (baseline do plano)

- [x] `main` limpo e sincronizado em
  `912599c8dc6ab7bde30e27a2cc27f0c1f1107c41`.
- [x] CI multiplataforma verde no SHA final: run `33900149915`.
- [x] Integration RAG/MCP verde no SHA final: run `33900161429`.
- [x] Candidate local verificado com checksums, SBOM, provenance e identidade;
  nenhum candidate, cache, corpus ou modelo foi publicado.
- [ ] Artifact de CI do mesmo SHA/digest final verificado e comparado; o CI
  observado pertence ao baseline remoto, não às mudanças locais desta execução.
- [ ] Gate `verify_candidate.py --release` fechado após decisão humana Chroma e
  evidência autenticada das settings GitHub.

### Plano executável resumido

- [ ] Congelar escopo e canais: GitHub Release como canal canônico e registry
  somente se houver trusted publishing e ownership verificados.
- [ ] Reexecutar o runbook completo em clone limpo e gerar candidate final do
  SHA que será promovido.
- [ ] Fechar dependências, os quatro advisories do Chroma, licenças,
  provenance, branch protection, reviewers, CODEOWNERS e permissões de release.
- [ ] Confirmar CI/Integration, comparar digest/lista/SHA e passar o gate
  `--release` sem enfraquecer exceções.
- [ ] Criar tag imutável, construir assets em ambiente limpo, publicar release
  controlada e validar instalação pelo canal público.
- [ ] Executar canário, observar 24h, atualizar documentação/metadata e só
  então ampliar a divulgação para canais previamente autorizados.
- [ ] Manter rollback por nova versão/yank/correção, sem mover tag nem expor
  dados derivados; registrar o handoff pós-lançamento.

### Gates que exigem decisão ou autoridade externa

- [ ] Mantenedor registrar `accept`, `mitigate`, `upgrade` ou `remove` em
  `docs/CHROMA-RESIDUAL-DECISION.md`.
- [ ] Administrador autenticar e registrar a checklist de settings do GitHub.
- [ ] Definir/autorizar registry, trusted publisher, conta e canais de
  divulgação; sem isso o agente prepara artefatos e rascunhos, mas não envia.
- [ ] Autorizar explicitamente tag, GitHub Release, publicação de pacote e
  anúncios externos quando essas mutações forem desejadas.

### Critério de encerramento

- [ ] Só marcar produção/divulgação como prontas quando o Definition of Done
  completo do plano tiver evidência; enquanto houver gate pendente, manter o
  estado `release-ready-pending-human-gate`.

## Execução de preparação para commit/push — 2026-09-04

### Plano executável

- [x] Confirmar antes de qualquer alteração: cwd, branch, remote, `HEAD`,
  `origin/main`, working tree e arquivos ignorados; preservar todas as mudanças
  recebidas do usuário.
- [x] Ler integralmente instruções, lições, documentação normativa, tickets
  19–29, workflows, schemas e superfícies públicas relacionadas.
- [x] Revalidar o baseline atual sem confiar em resultados históricos: versão,
  metadata, lista distribuível, suíte, Ruff, formato, contratos, support matrix,
  public seams, release audit e `git diff --check`.
- [x] Auditar os tickets 19–29 por dependência técnica e confirmar gaps reais
  em promoção/recovery, identidade do candidate, supply chain/CVEs, suporte,
  workflows/community e observabilidade/stress.
- [x] Para cada gap local confirmado, executar TDD estrito no seam público:
  teste focado RED, GREEN mínimo de causa-raiz, classe relacionada e regressão.
- [x] Reexecutar os gates locais completos: bootstrap/doctor, pytest, Ruff,
  compileall, contratos, matriz, public seams, clean clone, wheels core/RAG,
  `pip check`, raw `pip-audit`, wrapper strict, supply chain, auditorias,
  vendor security/chaos, MCP/Golden/fixture, stress e metadata/workflows.
- [x] Gerar, depois do commit, um candidate novo em `artifacts/` e verificar lista/digest/identidade,
  auditoria, supply chain, re-medição da fonte e modo release fail-closed.
- [x] Atualizar docs, tickets, changelog, auditoria, este registro e lessons com
  apenas evidência observada nesta execução; revisar elegância e diff final.
- [x] Confirmar working tree pronto, criar os commits corretivos necessários e
  fazer push para `origin/main`, conforme autorização explícita posterior do
  usuário. Tag, GitHub Release e publicação continuam fora do escopo.

### Classificação de pendências e evidência

**Pendências locais implementáveis**

- [x] Corrigir somente gaps reproduzidos por testes/gates atuais, sem reabrir
  conclusões históricas por suposição.
- [x] Eliminar warning inesperado, workaround frágil, drift documental ou gate
  local vermelho encontrado durante a revalidação.

**Gates que exigem ambiente externo**

- [x] CI remoto no SHA exato do candidate, incluindo Ubuntu/Windows/macOS e
  Python 3.11–3.13; run `33899411357` e artifact vinculado foram verificados.
- [ ] Estado autenticado de branch protection, required reviewers, secret
  scanning, push protection, Dependabot e permissões de release.

**Decisões do mantenedor humano**

- [ ] Registrar `accept`, `mitigate`, `upgrade` ou `remove` para o residual
  Chroma; manter release fail-closed enquanto a decisão estiver pendente.
- [x] Commit e push foram autorizados explicitamente pelo usuário em 2026-09-04.
- [ ] Autorizar separadamente tag, GitHub Release e publicação; nenhuma dessas
  ações está autorizada nesta execução.

**Evidência já confirmada nesta execução**

- [x] Repositório correto em `main`, remote
  `https://github.com/VIDORETTO/agent-knowledge-kit`, com
  baseline inicial `HEAD == origin/main == 0c766d2d7144a8861efe132fbc4c62498a0cfeb6`;
  o estado final desta fase está registrado abaixo.
- [x] Working tree recebido contém mudanças rastreadas e novos arquivos; dados,
  corpus, caches, ambientes e estado RAG aparecem apenas como ignorados.
- [x] Suíte completa final: `227 passed, 2 skipped in 431.95s`; ambos os
  skips são a capacidade de symlink indisponível neste host Windows.
- [x] A race real que interrompia a suíte foi reproduzida: no Windows,
  `os.kill(pid, 0)` usado por um reader enviava um evento de console ao writer.
  A correção usa `OpenProcess`/`GetExitCodeProcess`; o teste focado passou e a
  classe lifecycle/reliability/recovery fechou com `27 passed`.
- [x] Raw `pip-audit` saiu 1 para quatro CVEs de `chromadb==1.5.9`; wrapper
  strict saiu 0 com residual=4/unresolved=0 e evidência crua preservada.
- [x] Wheels core/RAG, supply-chain, auditorias tracked/candidate, Golden/MCP e
  três execuções do stress concorrente passaram no estado implementado.
- [x] O clean clone final criou venv próprio com core+formats+dev, passou doctor,
  auditoria de release e a suíte inteira: `227 passed, 2 skipped in 184.77s`.
- [x] O gate de supply chain agora declara perfil `core` ou `rag`: somente a
  ausência de `knowledge-rag` é opcional no core; qualquer outra ausência ou
  qualquer versão divergente reprova, e o perfil RAG exige a raiz completa.

**Evidência ainda ausente ou externa**

- [x] Candidate RAG local reconstruído a partir do commit de código enviado,
  com snapshot externo de modelo e re-medição da fonte; o release continua
  fail-closed sem evidência remota/decisão humana.
- [x] CI remoto do mesmo SHA/digest: run `33899411357`, artifact do candidate
  e re-medição com `--source-root .` passaram; integration MCP/stress do mesmo
  SHA passou no run `33899437593`.
- [ ] Settings autenticadas do GitHub e decisão humana Chroma; permanecem
  necessárias antes de tag, release ou publicação.

### Registro de verificação

- [x] TDD red → green → verificação registrado para cada mudança nova.
- [x] Revisão final de privacidade, arquivos proibidos, status e pendências antes
  do commit/push.

## Follow-up pós-CI do primeiro push — 2026-09-04

- [x] Confirmar o run `33891442751` no SHA publicado e separar o caminho feliz
  do wheel RAG do bloqueio humano do modo release.
- [x] Confirmar que a falha dos testes de candidate também existia no CI do
  commit-base `7916083`, portanto não foi causada pelo ajuste do cache.
- [x] Reproduzir em checkout Linux/WSL que `Path.resolve()` removia o launcher
  do venv POSIX e selecionava um Python sem `pip`.
- [x] Corrigir `scripts/prepare_candidate.py` para tornar o caminho absoluto
  sem resolver symlinks e atualizar changelog, handoff e lessons.
- [x] Reexecutar o teste de candidate e os gates locais disponíveis.
- [x] Confirmar no novo CI (`33897740714`) que quick, clean-clone e package
  passam no mesmo SHA; manter o release gate bloqueado enquanto a decisão
  Chroma estiver pendente.

## Fechamento do checkpoint apos o CI — 2026-09-04

- [x] Preservar os commits que chegaram ao remoto durante a execução e fazer
  merge do handoff sobre o `origin/main` mais recente.
- [x] Executar a suíte completa no `.venv` com versões fixadas: `230 passed,
  2 skipped`; os skips são apenas os testes de symlink indisponível neste
  Windows.
- [x] Reexecutar os testes de candidate/identidade: `10 passed`, incluindo o
  fallback de venv criado com `--no-install` e sem `pip`.
- [x] Enviar o commit de código `6b850ad` para `origin/main` e confirmar
  `HEAD == origin/main`.
- [x] Confirmar o CI `33897740714`: os 13 jobs passaram, incluindo wheel RAG,
  clean clone nos três sistemas e toda a matriz quick.
- [x] Regenerar e verificar um candidate RAG local a partir do commit de código
  enviado; a identidade é local e não substitui a evidência remota de release.
- [ ] Revisar settings autenticadas do GitHub e decidir explicitamente os
  quatro CVEs residuais de `chromadb==1.5.9`; sem isso, não criar tag, release
  ou publicar.

## Fechamento da correção de concorrência — 2026-09-04

- [x] Reproduzir a falha restante com TDD: uma linha Chroma com
  `metadata=None` fazia a consulta semântica quebrar durante reindex.
- [x] Corrigir o vendor revisado para descartar resultados sem metadados de
  citação nos caminhos híbrido, FTS5 e similaridade; registrar o downstream
  patch em `skills/vendor/knowledge-rag/PROVENANCE.json`.
- [x] Validar o vendor no diretório correto: `761 passed, 6 skipped,
  5 deselected, 8 xfailed`; os 67 testes focados também passaram.
- [x] Validar o stress local com o vendor revisado: 370 buscas, quatro
  warmups, zero erros/warnings, reindex concluído e sem resíduo recuperável.
- [x] Confirmar CI `33899411357`: 13 jobs verdes, incluindo a matriz quick,
  clean clone e wheel/candidate.
- [x] Confirmar Integration `33899437593`: 20.866 buscas concorrentes,
  zero erros/warnings, reindex bem-sucedido, índice 2 documentos/4 chunks e
  Recall@5/MRR@5 1,0 na avaliação MCP.
- [x] Candidate RAG local com snapshot externo, `--profile rag
  --require-model`, supply-chain e verificação independente passou; todos os
  bundles foram mantidos fora do Git.
- [ ] Executar a etapa de publicação: bloqueada corretamente até a decisão
  humana dos quatro CVEs e a revisão autenticada das settings GitHub.

### Evidência do diagnóstico adicional

- O job `wheel / Python 3.12` do run `33891442751` passou construção, smoke RAG,
  candidate, supply chain e re-medição; a etapa `--release` retornou
  `human_decision_pending` como esperado.
- Os jobs quick/clean-clone falharam nos testes de candidate porque o venv
  POSIX era canonicalizado para `/usr/bin/python3.12`, sem `pip`.

## Execução Goal Mode — revalidação e implementação — 2026-09-03

**Estado inicial revalidado:** `HEAD == origin/main == 0c766d2d7144a8861efe132fbc4c62498a0cfeb6`, working tree limpo, Python local 3.14.2 (tolerado), `171 passed, 2 skipped`, Ruff/format/contratos/matriz verdes. Os skips são exclusivamente a capacidade de criar symlink neste host Windows.

**Seams públicos aprovados:** raiz `docops`, CLI/JSON, pacote ativo/`inspect()`, repositório candidate/auditor, wheel instalado, fixtures externas/processos MCP e concorrência observável. Nenhum teste novo deve importar helpers privados, verificar call count ou ordem interna.

### Plano executável

- [x] 23 — fechar identidade candidate: digest/lista/SHA, modo release fail-closed, evidência CI transportável e invalidação após mutação.
- [x] 24 — migrar caracterizações relevantes para a raiz/CLI e isolar compatibilidade legada.
- [x] 25 — tornar promoção recuperável após interrupção entre transições, com `inspect()`/`cleanup()` seguros e limites de filesystem documentados.
- [x] 26 — tornar resolução/provenance verificáveis, separar raw `pip-audit` do wrapper e registrar decisão explícita para os quatro CVEs Chroma.
- [x] 27 — ligar claims a jobs/perfis executados e tornar clean clone/bootstrap acionável e reproduzível.
- [x] 28 — completar verificador local de metadata/assets/community e checklist humana de settings, sem mutações GitHub.
- [x] 29 — desambiguar métricas de chunks e fortalecer stress concorrente com carga mínima repetível, resíduos e warnings separados.
- [x] Executar red → green → gate proporcional em cada ticket, nessa ordem, atualizando ticket, spec, docs e changelog quando necessário.
- [x] Reexecutar os gates locais em clone limpo e wheel core/RAG; classificar honestamente skips, limitações ambientais e residual de CVEs.
- [ ] Encerrar a release somente após decisão humana Chroma, identidade remota/CI do mesmo SHA e settings autenticadas; não fazer commit, push, tag, release ou publicação nesta tarefa.

### Registro de verificação desta execução

- Baseline completo: `rtk python -m pytest -q` → `171 passed, 2 skipped`.
- Gates rápidos: `rtk python -m ruff check docops tests scripts`, `rtk python -m ruff format --check docops tests scripts`, `rtk python scripts/check_contracts.py --json` e `rtk python scripts/check_support_matrix.py --json` → PASS.
- Próximo red: teste público de identidade do candidate que exige referência verificável para modo release e detecta mutação pós-digest.
- SPEC-23 red → green: `tests/test_candidate_identity.py` começou falhando sem `identity` e sem `--source-root`; após `scripts/candidate_identity.py`, re-medição, CI identity e supply-chain binding, o alvo passou (`4 passed`).
- SPEC-23 revisão: o modo `--release` permanece fechado sem working tree limpo, ref remota verificada e evidência GitHub Actions. A publicação/CI remoto real depende de um commit posterior e continua proibida nesta execução.

## Auditoria real atual — plano documental — 2026-09-02

**Status:** auditoria concluída; documentos revisados; tickets 23–29
intencionalmente não implementados.

> Este é o plano vigente para a auditoria solicitada. As seções abaixo são
> registros históricos de auditorias e execuções anteriores; não substituem a
> revalidação atual do estado público, do `HEAD` e do working tree.

- [x] Ler `AGENTS.md`, `RTK.md`, `README.md`, `tasks/lessons.md`, documentação
  existente, issues locais e o estado do Git antes de concluir qualquer nota.
- [x] Comparar release/tag pública `v1.0.0`, `origin/main`/`HEAD` e working tree
  candidato 1.1.0, incluindo arquivos rastreados e não rastreados.
- [x] Revalidar os riscos solicitados: smoke sem RAG, `pip-audit` limpo,
  CVEs Chroma, acoplamento de módulos, claims de plataforma e publicação de
  corpus/índices/tokens.
- [x] Executar gates proporcionais de testes, lint, formato, contratos,
  dependências, release, clean clone, wheel, suporte e RAG/MCP real.
- [x] Aplicar o vocabulário de módulo/interface/seam do `codebase-design` à
  especificação e separar fatos, inferências e recomendações.
- [x] Aplicar a disciplina `tdd` ao plano: red observável, green mínimo,
  tracer bullets e testes somente nos seams públicos.
- [x] Criar a auditoria atual, revisar a especificação e o plano TDD, e criar
  tickets 23–29 ordenados por blocker, aceite e dependência.
- [x] Revalidar os documentos gerados e registrar o resultado final nesta
  seção.
- [x] Implementar tickets 23–29 — concluído posteriormente no ciclo Goal Mode
  de 2026-09-03; esta linha registra o histórico da auditoria, não uma pendência.

### Revisão da auditoria atual

As conclusões vigentes estão em
`docs/GITHUB-PUBLICATION-AUDIT-2026-09-02.md`. A nota geral é **6,2/10**;
“publicar hoje” é **3,0/10** porque o candidato 1.1.0 existe apenas no working
tree e ainda não tem CI público para o mesmo conteúdo; “produção estável” é
**5,3/10** devido ao residual de quatro CVEs do Chroma, locks sem hashes/transitivas,
recuperação pós-crash não provada e cobertura insuficiente do seam raiz.

Os tickets novos são 23–29 em
`.scratch/post-1-0-reliability/issues/`. Nenhuma implementação, alteração de
código, commit, push, tag, publicação ou release foi feita nesta auditoria.

## Auditoria real de prontidão GitHub — 2026-09-01

> Registro histórico. Os números e resultados abaixo pertencem à execução de
> 2026-09-01 e foram revalidados/contestados quando necessário pela auditoria
> atual; não são o estado vigente por si só.

- [x] Inventariar documentação, código e os estados `v1.0.0`, `HEAD/origin/main` e working tree.
- [x] Executar auditoria crítica pelos 13 setores solicitados, distinguindo fatos, inferências e recomendações.
- [x] Rodar gates proporcionais no ambiente atual e em ambientes limpos: testes, lint, contratos, dependências, release, suporte, clone, wheel e RAG/MCP quando disponível.
- [x] Registrar falhas de ambiente separadamente de defeitos do produto e riscos de reprodutibilidade.
- [x] Produzir relatório de auditoria com notas, blockers, comandos, resultados e evidências localizáveis.
- [x] Aplicar `to-spec` aos achados confirmados e revisar `docs/POST-1.0-IMPROVEMENT-SPEC.md`.
- [x] Aplicar `to-tickets` e revisar os tickets em `.scratch/post-1-0-reliability/issues/` por severidade e dependências.
- [x] Aplicar `tdd` para definir seams públicos, tracer bullets e ciclos red → green, sem implementar tickets.
- [x] Revalidar todos os documentos produzidos e registrar a revisão final nesta seção.

> Restrição desta auditoria: não implementar código e não fazer commit, push,
> tag ou release. Mudanças preexistentes devem ser preservadas.

### Revisão da auditoria real

Concluída sem implementar código. O baseline candidato **não está verde**:
`pytest` teve `1 failed, 153 passed, 2 skipped`; o clean clone preparado
reproduziu a mesma falha sem RAG; o wheel construiu e falhou no contrato de
metadata do adapter. Ruff lint, contratos, matriz e `git diff --check`
passaram; Ruff format reportou 54 arquivos fora do formato. A integração RAG
real passou por run indexado, validate, evaluate MCP e concorrência.

A auditoria de dependências passou após o pin documentado de pip, mantendo
quatro CVEs Chroma allowlisted como risco residual. O auditor de release
tracked retornou sucesso, mas um fixture Git adversarial confirmou falsos
negativos para dados privados aninhados; portanto esse resultado não autoriza
publicação. As notas e comandos estão em
`docs/GITHUB-PUBLICATION-AUDIT-2026-09-01.md`, a spec atual em
`docs/POST-1.0-IMPROVEMENT-SPEC.md`, o plano red → green em
`docs/POST-1.0-TDD-PLAN.md` e os novos tickets são 13–22.

> Objetivo: produzir uma crítica técnica e de produto baseada em evidências,
> uma especificação de melhoria e tickets TDD executáveis por GPT-5.6 Luna Max,
> sem implementar as mudanças nesta etapa.

- [x] Inventariar contratos, fluxos, módulos, documentação, testes, CI e
  dependências do estado atual.
- [x] Executar auditorias independentes de arquitetura, qualidade/segurança e
  experiência do operador/produto com revisores GPT-5.6 Sol High.
- [x] Verificar cada achado relevante no código, nos testes ou por comandos
  reproduzíveis; distinguir fatos, inferências e propostas.
- [x] Escolher os seams públicos de teste e a estratégia red-green por tracer
  bullet, preservando o contrato DOCOPS e a fronteira com o harness externo.
- [x] Publicar uma especificação completa e tickets locais em ordem de
  dependência, dimensionados para contextos frescos do Luna Max.
- [x] Executar os gates atuais para estabelecer o baseline, revisar a
  elegância do plano e registrar resultados, riscos e decisões nesta seção.

## Revisão da autoanálise

Registro histórico de 2026-08-30, anterior ao working tree atual. Naquele
baseline, a suíte permaneceu verde (`107 passed, 2 skipped`,
Ruff e auditoria de release aprovados). A análise confirmou como prioridades:
outcome terminal único, contratos executáveis, plan sem efeitos, apply
transacional, retomada verificável, lease de writer, readiness honesto e gates
de avaliação pelas rotas reais. A especificação está em
`docs/POST-1.0-IMPROVEMENT-SPEC.md`; 12 tickets locais estão em
`.scratch/post-1-0-reliability/issues/`. Esse resultado foi supersedido para o
candidato atual pela auditoria de 2026-09-01 acima.

---

# Plano de estabilização e publicação — agent-knowledge-kit

> Checklist operacional da release técnica pública 1.0.0. Cada item marcado
> abaixo tem uma decisão, um teste ou uma evidência verificável. Corpus,
> índices, caches, tokens, ambientes virtuais e artefatos gerados permanecem
> fora do Git.

## Estado da execução

- **Data da execução:** 2026-08-30.
- **Versão:** `1.0.0` em `pyproject.toml`.
- **Baseline:** `736c321eb46d1e279e49be7d77727f857b5fe62a` (estado recebido).
- **Escopo anunciado:** protocolo DOCOPS, skills, MCP/RAG opcional e fixtures
  sintéticas; o produto não hospeda nem escolhe um LLM.
- **Suporte verificado:** OpenCode 1.18.25 e Codex CLI 0.151.0 no Windows.
  Claude Code não está instalado e não é anunciado nesta versão.
- **Plataformas:** Windows comprovado manualmente; Linux/macOS cobertos pela
  matriz pública do CI final verde `33320817617`. Não há alegação de bootstrap
  manual local nesses dois sistemas.

## Fase 0 — contrato, escopo e política

- [x] Confirmar a fronteira: o harness externo executa o modelo; este projeto
  fornece protocolo, skills, artefatos, ferramentas e MCP opcional.
- [x] Definir o seam de teste como o pacote de conhecimento validável:
  `skill/`, `router/`, `rag/`, `manifest.json`, `harness.json` e checkpoints.
- [x] Fixar MIT para o código e manter documentos adquiridos fora do release
  salvo licença/permissão explícita no manifesto.
- [x] Definir política de fontes, redaction, proveniência, ambiguidade e
  citações factuais (`path#secao` ou `path:linha`).
- [x] Definir que `stdio` local é o padrão e que HTTP/SSE é opt-in protegido.

## Fase 1 — clone, instalação e empacotamento

- [x] Manter `README.md`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`,
  `docs/USE.md`, `docs/RELEASE.md` e os schemas no repositório.
- [x] Remover caminhos absolutos do produto e preservar configurações já
  existentes; o pacote gerado usa caminhos relativos.
- [x] Fixar dependências diretas: `knowledge-rag==4.8.5`, `PyYAML==6.0.3`,
  `pypdf==6.16.2`, `python-docx==1.2.0`, `pytest==9.1.1`, `ruff==0.12.7`,
  `pip-audit==2.10.1` e `setuptools==84.0.0`; bootstrap usa
  `pip==26.2.1`/`setuptools==84.0.0`.
- [x] Manter o vendor revisado de `knowledge-rag` sem Git aninhado e alinhar
  `serverInfo.version` com `4.8.5`.
- [x] Configurar `.gitignore` e o auditor para impedir corpus adquirido,
  `.rag_state.json`, `data/`, `models_cache/`, `.venv*`, tokens, logs e saídas.
- [x] Adicionar `dependabot.yml` para atualizações semanais de pip e actions;
  Dependabot security updates e secret scanning/push protection estão ativos
  no repositório público.

## Fase 2 — tracer bullet DOCOPS local

- [x] Resolver nome, URL, repositório HTTPS e pasta local com ambiguidade e
  erros estruturados.
- [x] Adquirir e normalizar Markdown, texto, HTML, PDF, DOCX, OpenAPI, YAML,
  JSON, notebooks, XLSX e PPTX conforme capacidades e limites declarados.
- [x] Aplicar SSRF, robots/sitemap, limites de páginas/payload/tempo/retries,
  redaction, conteúdo não confiável e licenciamento.
- [x] Gerar skill, router, corpus normalizado, `config.yaml`, `harness.json`,
  manifesto, schemas e checkpoints de forma idempotente.
- [x] Executar a fixture `documents/fixtures/acme-docs` com `docops run`,
  `validate` e `evaluate`; resultado observado: 2 documentos, 4 chunks e
  Recall@5/MRR@5 de 1.0 na avaliação lexical.
- [x] Validar a skill FastAPI e o router sem warnings no validator; a skill
  roteadora exige citações para fatos literais e sinaliza divergência.

## Fase 3 — RAG híbrido e MCP

- [x] Manter `knowledge-rag` opcional, `PersistentClient` local, cache de
  modelos ignorado e transporte padrão `stdio`.
- [x] Integrar o vendor revisado ao runtime do reindex/smoke quando o pacote
  é executado a partir deste checkout; não depender silenciosamente de uma
  cópia instalada com versão diferente.
- [x] Executar smoke MCP real: handshake, `tools/list`, busca híbrida e
  verificação de `serverInfo.version == 4.8.5` passaram.
- [x] Executar a fixture com `--index-rag`: 2 documentos e 4 chunks indexados,
  sem erro; o perfil observado foi `BAAI/bge-small-en-v1.5`.
- [x] Executar `scripts/evaluate_golden.py --cases golden-set/test-cases.json`:
  10 casos, Recall@5 `1.0` e MRR@5 `0.95`.
- [x] Executar reindexação concorrente por 5 segundos: 2 buscas, zero erros,
  reindexação final inativa e 2 documentos/4 chunks.

## Fase 4 — qualidade, segurança e dependências (P0/P1/P2)

### P0 — publicação e compatibilidade

- [x] Confirmar visibilidade pública anônima: API e página GitHub retornaram
  HTTP 200, `isPrivate=false`, `visibility=PUBLIC`; `git ls-remote` anônimo
  encontrou `origin/main` no baseline antes desta execução.
- [x] Executar sessão real somente leitura no OpenCode 1.18.25; versão 1.0.0,
  comando MCP relativo, `stdio` e contrato foram confirmados.
- [x] Executar sessão real somente leitura no Codex CLI 0.151.0; manifesto
  gerado foi validado contra Draft 2020-12 sem erros. O runner global não tinha
  diretório temporário utilizável para pytest, mas a suíte do projeto passou no
  `.venv` dedicado.
- [x] Remover Claude Code da promessa de suporte por não estar instalado neste
  host; outros harnesses são suportados apenas pelo protocolo Agent Skills +
  MCP e não por uma sessão específica não verificada.
- [x] Ajustar a documentação de plataforma: bootstrap/doctor/testes foram
  comprovados no Windows; em Ubuntu WSL passaram `doctor` e `compileall`, mas o
  bootstrap completo foi bloqueado pela ausência de `python3-venv`/`pip` e pela
  falta de permissão administrativa; não há host macOS disponível. A matriz CI
  continua sendo a evidência automatizada para Linux/macOS.
- [x] Corrigir o fallback YAML para comentários inline sem corromper `#` dentro
  de strings; o clone limpo agora aceita o `config.yaml` sem PyYAML.
- [x] Corrigir métricas do avaliador para usar `recall_at_<k>`/`mrr_at_<k>`
  coerentes com `--top-k`, com regressão para `top_k=1`.

### P0 — dependências vulneráveis

- [x] Atualizar pip e pytest vulneráveis para `pip==26.2.1` e `pytest==9.1.1`;
  incluir `pip-audit==2.10.1` no perfil de desenvolvimento.
- [x] Criar `scripts/audit_dependencies.py` e gate CI. Auditoria de lock e
  ambiente local passou com `--strict`: não há findings fora da política.
- [x] Registrar explicitamente o residual de `chromadb==1.5.9`: somente
  `CVE-2026-45829`, `CVE-2026-45830`, `CVE-2026-45831` e `CVE-2026-45833`, sem
  versão de correção no snapshot. Qualquer outro advisory reprova o gate.
- [x] Registrar a justificativa limitada: uso `PersistentClient` local,
  `stdio` por padrão, sem `HttpClient` nem `trust_remote_code`; o risco não é
  descrito como ausência de vulnerabilidades.
- [x] Definir política de atualização: pins diretos sincronizados, auditoria a
  cada release/CI, vendor revisado manualmente e sem lock transitivo falso por
  plataforma; procedência/hash dos modelos externos é limitação declarada.

### P1 — correções implementadas

- [x] Tornar `scripts/mcp_smoke.py` não bloqueante em timeout, EOF e stderr;
  preservar diagnósticos e cobrir timeout/EOF/stderr com testes.
- [x] Alinhar o `serverInfo` vendorizado com `knowledge-rag==4.8.5` e fazer o
  smoke detectar drift entre servidor e pacote instalado.
- [x] Completar `SECURITY.md` com canal privado, escopo, versões, metas de
  resposta, modelo de ameaça, gates e procedimento para não expor corpus/
  tokens. O endpoint privado do GitHub permaneceu indisponível; o fallback
  privado está documentado.
- [x] Testar bearer HTTP dinamicamente: token ausente recusa antes do bind,
  token correto atravessa e token incorreto falha; perfil de exemplo mantém
  placeholder fora do Git.
- [x] Cobrir limites de clone, formatos opcionais, symlink quando permitido,
  autenticação, config, auditoria, pacote e regressões de rede; symlink é skip
  explícito em hosts Windows sem privilégio.

### P2 — investigações preventivas

- [x] Fechar DNS rebinding/TOCTOU em URLs: validar e conectar aos IPs aprovados
  com Host/SNI original; redirects são revalidados a cada hop.
- [x] Endurecer clone Git: somente HTTPS remoto, redirects HTTP desativados,
  `protocol.file.allow=never`, sem tags/submódulos/prompts, blob filter, DNS
  fixado por `http.curloptResolve` e limite pós-clone de 500 MiB.
- [x] Documentar procedência, cache, integridade não fixada e confiança dos
  modelos RAG externos em `SECURITY.md` e `docs/DEPENDENCIES.md`.
- [x] Registrar o processo de atualização da cópia vendorizada: revisar versão,
  diff, `serverInfo`, testes de segurança, suíte raiz, smoke, reindex e audit.

## Fase 5 — gates finais locais

- [x] `scripts/bootstrap.py --dev --rag`: passou no Windows com JSON `ok=true`.
- [x] `python -m pytest -q`: **107 passed, 2 skipped**; os skips são apenas
  symlink indisponível no Windows.
- [x] Suíte de segurança do vendor: **142 passed, 7 skipped, 5 xfailed**;
  apenas o warning de depreciação do telemetry do upstream foi observado.
- [x] Ruff em `docops tests scripts` e vendor de segurança: **All checks passed**.
- [x] `compileall`, `pip check` e `git diff --check`: passaram; pip reportou
  nenhum requisito quebrado.
- [x] `python -m docops doctor --json`: passou com RAG disponível e `stdio`.
- [x] `python -m docops config-audit config.yaml --json`: passou; o perfil
  `config/network.example.yaml` foi rejeitado como esperado por token
  placeholder.
- [x] Auditoria de release `--tracked-only`: passou; clone limpo copiado fora
  do checkout também passou sem findings.
- [x] Wheel `consulta_documentacao-1.0.0-py3-none-any.whl`: construído,
  instalado em alvo isolado e smoke de import passou.
- [x] Repetir `run → validate → evaluate`, smoke MCP, golden real e concorrência
  RAG após as correções: todos passaram com os resultados acima.

## Fase 6 — publicação pública e prova remota

- [x] Criar a tag anotada e imutável `v1.0.0` somente no commit validado
  `e8083ade7f9533cb220b3cf3288ed3b54a6e79c9`; `git show` confirmou a tag e o
  commit, enquanto `git ls-remote --tags origin` confirmou o objeto anotado
  `bfc89d2e69e27fa75d90c2c4c2d33020dbc02d1f` e o peeled SHA esperado.
- [x] Publicar a release GitHub `v1.0.0` com notas e links para changelog,
  release, aceitação, segurança e evidências; a API reportou `isDraft=false`,
  `isPrerelease=false`, e a página pública retornou HTTP 200:
  https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.0.0.
- [x] Fazer push do commit e da tag para `origin`; a tag/release apontam para o
  commit de produto validado `e8083ade7f9533cb220b3cf3288ed3b54a6e79c9`, e
  `origin/main` recebeu depois o commit documental `73e6aa2216e0f87d0b92eed1364569d69d239eaa`
  com esta evidência. A API pública confirmou `isPrivate=false`,
  `visibility=PUBLIC`, Dependabot alerts/security updates, secret scanning e
  push protection ativos; `git ls-files` não encontrou `.venv-rag/`, `data/`,
  `models_cache/`, `.rag_state.json` ou artefatos gerados.
- [x] Aguardar os workflows públicos do commit final e registrar a prova:
  CI completo `33320817617` (13 jobs verdes: 9 combinações rápidas, 3 clones
  limpos e wheel), integração RAG `33320989219` e docs-reindex
  `33320989436`; todos no SHA `e8083ade7f9533cb220b3cf3288ed3b54a6e79c9`, com
  status `success` e URLs públicas:
  https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33320817617,
  https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33320989219,
  https://github.com/VIDORETTO/agent-knowledge-kit/actions/runs/33320989436.

## Revisão de segurança

- [x] Nenhum segredo, token, corpus adquirido, índice, cache, ambiente virtual
  ou artefato gerado está listado por `git ls-files`.
- [x] Secret scanning, push protection, Dependabot alerts/security updates e
  workflow de auditoria estão ativos/documentados.
- [x] O residual Chroma está classificado e não bloqueia silenciosamente novas
  vulnerabilidades; revisar upstream antes de ampliar transporte ou escopo.
- [x] Revisão manual ainda requerida para licença de qualquer corpus futuro,
  firewall/TLS ao usar HTTP/SSE, rotação de token e integridade dos modelos.

## Veredito e registro final

Os gates locais, as decisões de suporte, a tag, a release, o push e os
workflows públicos foram observados e registrados. O residual de Chroma e as
revisões manuais descritas acima continuam sendo limitações conhecidas, não
falhas silenciosas do gate.
# Execução tickets 13–22 — plano ativo

> Objetivo: implementar os gaps pós-1.0 sobre o working tree recebido,
> preservando os tickets 01–12 e sem commit, push, tag, publicação ou release.
> Cada ticket será executado verticalmente: red observável → green mínimo →
> gate proporcional → atualização deste plano e do ticket.

## Ordem de dependência e ciclos

- [x] 13 — Auditoria de candidato fail-closed: Git tracked/candidate, paths
  proibidos, binários, canários de token e relatório redigido.
- [x] 14 — Contrato MCP determinístico: runtime selecionado, drift, ausência,
  timeout/EOF/stderr e smoke real.
- [x] 16 — Interface Python raiz: request/options, plan/apply/inspect, contratos
  imutáveis/versionados e compatibilidade observável.
- [x] 15 — Tracer do wheel instalado: core e RAG sem fallback silencioso,
  metadata de adapter/backend/perfil/proveniência coerente.
- [x] 17 — Expandir primitives internas: ownership unidirecional sem imports
  privados do legado, mantendo todos os seams verdes.
- [x] 18 — Migrar e contrair pipeline legado: callers pela interface nova,
  revalidação por snapshot sem readquisição completa sob lease e remoção segura.
- [x] 19 — Promoção/resíduos: reader concorrente, falhas de promoção, inspect,
  retenção e limpeza segura, com garantia por filesystem.
- [x] 20 — Supply chain: locks por perfil/plataforma, hashes, SBOM, vendor/model
  provenance e allowlist Chroma fail-closed.
- [x] 21 — Suporte perfilado/runbook: matriz por capacidade, wrappers, skips
  obrigatórios, ordem em clean clone e checker de drift docs/workflows.
- [x] 22 — Readiness profissional versionado: identidade nova, bundle de
  candidato verificável, metadata/community e prova de digest único.

## Método de verificação

- [x] Registrar cada red com comando e falha antes da implementação.
- [x] Executar testes somente nos seams públicos já aprovados em
  `docs/POST-1.0-TDD-PLAN.md`; não testar helpers privados/call counts.
- [x] Rodar testes rápidos após cada slice e gates de ticket ao concluir cada
  dependência.
- [x] Rodar suíte sem RAG e com RAG, auditoria de candidato, contratos, lint e
  format como gates separados.
- [x] Reproduzir clean clone, wheel core/RAG, security/dependency/portability,
  e tracer real RAG/MCP sobre o mesmo bundle antes do readiness final.
- [x] Manter falha ambiental separada de defeito do produto e não declarar
  release-ready sem evidência executável.

## Registro de execução

- Baseline inicial: `pytest -q` = 1 failed, 153 passed, 2 skipped; falha em
  `test_public_smoke_cli_rejects_server_version_drift` porque o launcher
  encerra com EOF em vez de reportar drift.
- Cwd/projeto: `<workspace>`, branch `main`, origin
  `https://github.com/VIDORETTO/agent-knowledge-kit`.

# Execução SPEC-002 pós-1.0 — registro histórico

> Esta seção registra a execução anterior do SPEC-002. Para o estado vigente,
> consulte a auditoria de 2026-09-02 e a revisão documental no início deste
> arquivo.

> Atualizado em 2026-09-01 após a implementação dos 12 tickets. `[x]` significa
> implementação e evidência executada; a seção histórica acima foi preservada.

## Ordem e critérios de aceite

- [x] Baseline e seams públicos caracterizados; mudanças preexistentes preservadas.
- [x] 01 — contratos normativos executáveis, outcome terminal único e drift gate.
- [x] 02 — `plan` completo, imutável/sem efeitos, diff fiel e plano verificável.
- [x] 03 — invariantes observáveis de `create`, `update` e `run`.
- [x] 04 — staging no mesmo volume, validação completa e promoção transacional,
  incluindo restauração segura, falhas por fase e leitores concorrentes.
- [x] 05 — recibos atômicos verificáveis, invalidação seletiva e retomada segura.
- [x] 06 — lease local recuperável; um writer por pacote e readers preservados.
- [x] 07 — readiness monotônico com evidências de scaffold, skill, RAG e release.
- [x] 08 — avaliação por rota/adaptador, backend/proveniência e gate MCP real.
- [x] 09 — resolver providers explícitos sem descoberta silenciosa de rede.
- [x] 10 — contexto de runtime explícito e procedência verificável em checkout e
  wheel, incluindo detecção de drift.
- [x] 11 — eventos e diagnósticos limitados, redigidos e derivados de recibos reais.
- [x] 12 — matriz, CI, release gates e documentação alinhados.
- [x] Suíte completa e todos os gates locais/integrados abaixo executados com
  sucesso; os únicos skips são symlinks indisponíveis neste host Windows.

## Evidência por ticket

| Ticket | Teste/artefato proporcional | Resultado atual | Pendência explícita |
|---|---|---|---|
| 01 | `tests/test_post_contracts.py`; `scripts/check_contracts.py --json` | PASS; 9 contratos, sem findings | Nenhuma conhecida |
| 02 | `tests/test_post_lifecycle.py` — plan, imutabilidade, diff e stale plan | PASS | Nenhuma conhecida |
| 03 | `tests/test_post_lifecycle.py` — create/update/run e blockers | PASS | Nenhuma conhecida |
| 04 | lifecycle, promoção/restauração, staging seguro e concorrência | PASS | Nenhuma conhecida no escopo local |
| 05 | lifecycle/reliability — receipts, resume, truncamento/adulteração | PASS | Nenhuma conhecida |
| 06 | `tests/test_post_reliability.py`; teste de reindex concorrente | PASS | Nenhuma conhecida |
| 07 | contratos, package validator e readiness | PASS | Nenhuma conhecida |
| 08 | `tests/test_evaluator.py`; tracer MCP real e Golden fixture | PASS; Recall@5/MRR@5 1,0 | Nenhuma conhecida |
| 09 | `tests/test_source_resolver.py` — catálogo, providers e entradas legadas | PASS | Nenhuma conhecida |
| 10 | `tests/test_runtime.py`; `scripts/verify_wheel.py` com MCP; clean clone | PASS | Nenhuma conhecida |
| 11 | `tests/test_post_observability.py`, MCP, smoke e redaction | PASS | Nenhuma conhecida |
| 12 | `scripts/check_support_matrix.py`; workflows, docs e auditorias | PASS | Nenhuma conhecida |

## Gates executados

- `python -m pytest -q`: **154 passed, 2 skipped** em 17,63 s; os skips são
  criação de symlink indisponível neste host Windows.
- `python -m ruff check docops scripts tests`: **PASS**; `compileall` e
  `git diff --check`: **PASS**.
- `scripts/check_contracts.py --json`: **PASS**, 9 contratos e nenhum finding.
- `scripts/check_support_matrix.py --json`: **PASS**; Python 3.11–3.13
  suportado, 3.14 tolerado, Ubuntu/Windows/macOS declarados e gates coerentes.
- `scripts/audit_release.py --tracked-only --json`: **PASS**, 324 arquivos
  rastreados, nenhum finding.
- `scripts/audit_dependencies.py --requirements requirements.lock --local
  --strict`: **ok=true**; os quatro advisories residuais do Chroma 1.5.9 estão
  explicitamente classificados como permitidos apenas para `PersistentClient`
  local, sem HTTP/trust_remote_code.
- `python -m docops doctor --json`: **ok=true**; config, lock, skill e RAG
  disponíveis. O Python local é 3.14, tolerado pela matriz.
- `python -m docops config-audit config.yaml --json`: **ok=true**; transporte
  `stdio`, sem erros ou warnings.
- `scripts/verify_wheel.py`: **PASS**; wheel 1.0.0 construído e instalado em
  alvo isolado, com `run --index-rag` → `validate` → `evaluate --adapter mcp`;
  saída confirmou `adapter=mcp`, `rag=true` e proveniência `installed-package`.
- Clean clone: **PASS**, doctor, auditoria de release e suíte (**154 passed,
  2 skipped**) em árvore temporária sem estado local.
- Tracer público RAG: **PASS** — `run --index-rag` → `validate` →
  `evaluate --adapter mcp`, com `knowledge-rag` 4.8.5, perfil compact, 2 casos,
  Recall@5=1,0 e MRR@5=1,0; o pacote registrou aquisição, artifacts, index,
  state e validate.
- `scripts/mcp_smoke.py "background tasks"`: **PASS**; handshake, tools/list e
  busca real, com conteúdo, caminhos e stderr redigidos/omitidos.
- `scripts/test_reindex_concurrency.py --seconds 20`: **PASS**; nenhum erro,
  reindex encerrado e índice consistente.
- TDD do gate do wheel: o red inicial expôs drift do backend instalado
  (`serverInfo=4.6.0` versus metadata `4.8.5`); o green usa runtime pinned
  isolado e falha explicitamente se `DOCOPS_REQUIRE_WHEEL_RAG=1` não puder
  executar MCP real.
- Revisão crítica: compatibilidade de `run` e manifests legados preservada;
  symlink/path traversal, SSRF, tokens, corpus e diagnósticos cobertos;
  staging/backup evita sobrescrever dados do usuário; mudanças preexistentes e
  o updater legado foram preservados.

## Pendências e limites honestos

- [x] Nenhum commit, push, tag, publicação ou release foi executado nesta tarefa.

## Revisão Goal Mode — evidência final local — 2026-09-04

- [x] Implementação local dos tickets 23–29 concluída e revalidada contra os
  seams públicos; o checkout preserva o working tree sem commit/push/tag.
- [x] Suíte completa no estado final: `184 passed, 2 skipped`; os dois skips são
  exclusivamente a capacidade de criar symlink neste host Windows.
- [x] Clean clone atual: doctor, release audit e `184 passed, 2 skipped`, sem
  `.rag_state.json`, corpus adquirido ou outro estado local no clone.
- [x] Ruff lint/format, compileall, contratos, public-seams, support matrix,
  diff-check e release audit tracked/candidate: PASS.
- [x] Wheel core e RAG: PASS; o wheel RAG executou adapter MCP e registrou
  `knowledge-rag==4.8.5` como runtime instalado.
- [x] RAG/MCP real: estado local `164` arquivos e servidor `170` documentos /
  `3296` chunks; Golden FastAPI `Recall@5=1.0`, `MRR@5=0.9048`; fixture MCP
  `Recall@5=1.0`, `MRR@5=1.0`; stress com quatro readers/10s/40 buscas obteve
  `202` buscas, zero erros/warnings e estado final consistente.
- [x] Security/privacidade: vendor security/chaos PASS (`142 passed, 7 skipped,
  5 xfailed`); auditorias não imprimem corpus, tokens ou caminhos privados.
- [x] Dependências: `pip check` PASS; o wrapper strict PASS com allowlist
  estreita e provenance verificável. O raw `pip-audit` permanece explicitamente
  vermelho: a auditoria JSON preserva quatro advisories sem fix para
  `chromadb==1.5.9`, e a invocação direta por requirements no Python 3.14
  também terminou com falha de resolução de `python-docx`; nenhum resultado
  vermelho foi mascarado como auditoria limpa.
- [x] Candidate local final: `artifacts/candidate-goal-final7` passou a
  verificação normal e supply-chain independente; o manifest/identity do
  bundle registra o digest calculado, `source_commit` local e estado
  `working-tree-candidate`. `--release` falha fechadamente sem CI remoto e
  sem decisão humana. O digest não é repetido nesta fonte para evitar uma
  referência circular entre a documentação e a identidade do candidato.
- [ ] Release/publicação: ainda requer decisão humana sobre o residual Chroma,
  commit/ref remoto e CI do mesmo digest, além da revisão autenticada de
  settings GitHub. Esses gates não podem ser inventados nem executados sob a
  proibição explícita de commit/push/release desta tarefa.
- [x] O CI declara a matriz Python 3.11–3.13 e runners Ubuntu/Windows/macOS;
  a execução local desta rodada ocorreu no Windows com Python 3.14 tolerado.
- [x] A decisão sobre o residual de Chroma, licença de novos corpora e eventual
  transporte HTTP/SSE continua exigindo revisão operacional antes de qualquer
  publicação futura.

## Revisão histórica — tickets 13–22 (2026-09-03)

Esta seção é a evidência da execução anterior dos tickets 13–22; os números
históricos acima foram preservados. Ela não substitui a auditoria atual nem
significa que os tickets 23–29 foram implementados.

### TDD red → green

- [x] 13: os testes de candidate audit iniciaram sem seleção de conjunto
  candidato; o CLI agora audita exatamente tracked + novos arquivos aprovados,
  incluindo binários e canários estruturados, sem ecoar segredos.
- [x] 14: o baseline reproduziu EOF em vez de `server_version_drift`; o smoke
  agora seleciona o interpretador real e separa ausência, drift, timeout e EOF.
- [x] 15: o red do wheel mostrou `serverInfo=4.6.0` contra metadata 4.8.5; o
  tracer agora usa o runtime pinado e falha se RAG obrigatório cair em fallback.
- [x] 14/15 follow-up: o módulo MCP redirecionava a versão para stderr e o
  wheel via `selected_version=None`; o contrato agora lê `sys.__stdout__` sem
  contaminar o canal JSON-RPC.
- [x] 16: o seam raiz e o teste de imutabilidade falharam antes dos exports e
  snapshots; `docops` agora expõe tipos versionados e resultados profundamente
  imutáveis e serializáveis.
- [x] 17: callers ainda dependiam da engine/adapter legado; primitives e
  geração foram extraídos e o pipeline legado ficou somente como adapter fino.
- [x] 18: o teste de lease observou 9 requests, acima do limite 6; a
  revalidação agora usa snapshot/fingerprint sem readquirir o corpus sob lease.
- [x] 19: o reader separado observou a janela de rename e a suíte reproduziu
  `WinError 5`; o red revelou que `inspect()` lia a geração durante o lease.
  O green final faz o reader esperar o writer antes de abrir arquivos; retry e
  inspect estável fecham a garantia pública no Windows.
- [x] 20: o teste de bundle iniciou sem gerador; generator/verifier agora
  produzem e validam locks, hashes, SBOM, vendor/model provenance e allowlist.
- [x] 21: o checker de suporte iniciou sem CLI; matriz, workflows, wrappers,
  skips e ordem de gates agora são validados como contrato.
- [x] 21 follow-up: o wrapper POSIX inicialmente não importava o checkout e
  sobrescrevia o venv Windows; o bootstrap agora carrega a raiz antes da
  instalação e separa `.venv-posix`/`.venv-windows` por configuração nativa.
- [x] 21 follow-up: o clean clone inicialmente tentou copiar o symlink `lib64`
  do venv POSIX; os dois diretórios específicos agora são ignorados também
  pelo copiador, auditor e builder de candidato.
- [x] 22: o teste de candidato iniciou sem builder; o bundle 1.1.0 agora é
  digest-bound, verificável independentemente e explicitamente unpublished.

### Gates finais executados

- [x] `rtk python -m pytest -q` e o mesmo comando no `.venv` RAG: **171 passed,
  2 skipped**. Os skips são exclusivamente a capacidade de criar symlink neste
  host Windows.
- [x] `ruff check`, `ruff format --check`, `compileall`, `git diff --check`,
  `check_contracts.py --json`, `check_support_matrix.py --json` e auditoria
  tracked/candidate: **PASS**, sem findings.
- [x] Wheel core e RAG: **PASS**, versão 1.1.0, adapter memory/mcp conforme o
  perfil; o RAG instalado confirmou `knowledge-rag==4.8.5`.
- [x] Dependências: `pip check` limpo; auditoria estrita **ok=true**, com
  exatamente os quatro CVEs Chroma permitidos pelo threat model local
  `PersistentClient` e sem unresolved.
- [x] Smoke MCP real e ciclo RAG: handshake/tools/search **PASS**; run
  indexado, validate, evaluate MCP e reindex concorrente **PASS**, com
  Recall@5=1.0 e MRR@5=1.0.
- [x] Security vendor: **160 passed, 7 skipped, 5 xfailed**; warning apenas de
  depreciação externa do Chroma.
- [x] Clean clone: **171 passed, 2 skipped**; doctor, release audit e suíte
  passaram sem estado local.
- [x] Candidate final: `artifacts/candidate-1.1.0-final11`, manifest e
  verificação independente **PASS**, source commit
  `855038019abbbe37d027728ac1bf034f4af210fb`; o digest final é o valor
  emitido e verificado no `manifest.json` do bundle.
- [x] Portabilidade: bootstrap Python, PowerShell e execução POSIX **PASS**;
  `--no-install` não exige `ensurepip`. O bootstrap completo com instalação de
  dependências ainda requer `pip`/`python3-venv` no host Linux, enquanto os
  wrappers e a matriz CI permanecem cobertos.
- [x] Nenhum commit, push, tag, publish ou release foi executado. A assinatura,
  branch/release protections, licença de corpus e decisão sobre o residual
  Chroma continuam como revisão humana antes de qualquer publicação.

## Follow-up do CI Linux após o commit `7916083` — 2026-09-04

- [x] Reproduzir no Linux/Python 3.12 a falha do job wheel do run
  `33887455346` e capturar os erros completos de validação.
- [x] Manter o cache FastEmbed fora da árvore distribuível do pacote em todos
  os sistemas, com regressão automatizada.
- [x] Melhorar o diagnóstico do gate do wheel para preservar erros estruturados
  sem depender dos últimos 2.000 caracteres do stdout.
- [x] Executar testes focados, suíte/gates proporcionais e os smokes reais dos
  wheels no Windows; o wheel RAG foi executado com o runtime exigido.
- [x] Atualizar documentação/revisão com a evidência local final e preparar o
  commit/push corretivo desta execução. Não criar tag nem release.
- [ ] Confirmar no GitHub o novo CI do mesmo SHA depois do push; a execução
  remota e suas plataformas continuam evidência externa.

### Evidência final local deste follow-up

- `python -m pytest -q`: **228 passed, 2 skipped em 419,82s**; ambos os skips
  são a capacidade de criar symlink neste host Windows.
- Testes focados (`test_pipeline.py`, `test_rag_sync.py` e
  `test_verify_wheel.py`): **21 passed, 1 skipped**.
- Ruff lint/formato, contratos, matriz de suporte, workflows, public seams,
  `compileall` e `git diff --check`: **PASS**.
- Auditoria de release: **PASS**, 401 arquivos tracked e 403 arquivos no
  candidate set.
- `pip check` no `.venv` do projeto: **PASS**.
- `verify_wheel.py --core`: **PASS**, `adapter=memory`, `rag=false`.
- `verify_wheel.py --require-rag` no `.venv` do projeto: **PASS**,
  `adapter=mcp`, `rag=true`.
- A tentativa paralela dos wheels foi descartada por corrida nos diretórios
  `build/` compartilhados; a repetição sequencial passou. Os diretórios
  `build/` e `consulta_documentacao.egg-info/` foram removidos antes da
  repetição por serem artefatos gerados e ignorados.

## Execução da consolidação main — T01–T13

Objetivo: integrar seletivamente `origin/feat/continuous-knowledge` ao núcleo
modular local em `codex/main-consolidation`, seguindo os contratos de
`docs/main-consolidation/` e o ciclo RED → GREEN mínimo → verificação →
refatoração. O checkout `main` foi preservado no baseline; não haverá push,
merge em `main`, release, publicação, reindexação ou alteração de corpus/RAG
real.

### Plano executável

- [x] Ler README, decisão, SPEC, TDD, índice e tickets na ordem prescrita.
- [x] Registrar estado inicial, branch, remoto e mudanças locais.
- [x] T01 — congelar baselines e decisão de integração seletiva.
- [x] T02 — definir lifecycle, estado e compatibilidade canônicos.
- [x] T03 — impor MCP read-only, pinning e revogação.
- [x] T04 — consolidar geração, harness e router.
- [x] T05 — distribuir e descobrir a skill operacional; checkout/wheel,
  bootstrap idempotente/read-only e harness guidance verificados.
- [x] T06 — unificar a CLI com aliases expand-contract; hierarquia canônica,
  mapa explícito e equivalência de contrato verificados.
- [x] T07 — consolidar candidata, avaliação, aprovação, publicação e rollback;
  autoridade, revogação e recuperação de crash verificadas.
- [x] T08 — consolidar fontes, eventos e worker retomável; gates de política,
  reautorização, deduplicação e crash/retry verificados.
- [x] T09 — consolidar readers e snapshots RAG; sessão fixa release/snapshot,
  compatibilidade completa e revogação/smoke fail-closed verificados.
- [x] T10 — governar aprendizado e feedback; consentimento, evidência,
  feedback autenticado/anti-replay/rate-limit e revogação propagada verificados.
- [x] T11 — eliminar drift de contratos e documentação.
- [x] T12 — provar clean clone, wheel e plataformas.
- [x] T13 — criar candidato de integração e preparar decisão humana.
- [x] Executar gates finais sequenciais, sem promover `main`.

### Registro inicial

- Branch de trabalho: `codex/main-consolidation`, criada em
  `origin/main`; `main` continua em `15cfaa6a919eaac7fca315241a4b396b1902f8f8`.
- Mudanças locais existentes foram carregadas intactas na branch; não houve
  reset, checkout destrutivo, merge ou cópia sobre o working tree.
- T01 foi executado com o teste de supply chain conhecido em RED; a correção
  fica bloqueada para o ticket/gate que a possui no escopo.

### Execução concluída — main-consolidation T10

- [x] RED: evidência independente declarada sem verificação e feedback sem
  origem autenticada foram aceitos antes dos guards.
- [x] GREEN: opt-in/minimização, consentimento escopado com validade/hash,
  evidência verificável, exclusão de recursão, autenticação de feedback,
  identidade de evento, anti-replay e rate limit.
- [x] REFACTOR: tombstones de aprendizado passaram a compor a identidade de
  revogação de snapshots e os guards de candidata/rollback.
- [x] Verificação: `tests/test_learning.py tests/test_usage_feedback.py
  tests/test_reader_sessions.py` — 18 passed; `tests/test_candidate_publication.py`
  — 13 passed; Ruff PASS.
- [x] Ticket, status, schemas e rollback documentados; nenhum corpus/RAG real
  foi alterado.

### Execução concluída — main-consolidation T11

- [x] RED: o checker documental ainda não existia; a coleta do teste público
  falhou antes da implementação.
- [x] GREEN: fonte canônica `schemas/`, sincronização por conteúdo, política de
  versão/compatibilidade e checkers de contratos/documentação.
- [x] REFACTOR: documentação histórica foi explicitamente excluída do contrato
  normativo, enquanto README/status/arquitetura/uso/tickets apontam para as
  mesmas superfícies e comandos canônicos.
- [x] Verificação: 35 testes passaram e 1 foi pulado por limitação de symlink;
  `sync_schemas`, `check_contracts`, `check_documentation` e Ruff passaram.
- [x] Nenhum corpus, índice RAG, publicação ou estado externo foi alterado.

### Revisão

- Atualizar esta seção após cada ticket com RED, GREEN, gates, limitações e
  rollback observável.

### Execução concluída — main-consolidation T12

- [x] RED: o runner não existia; os ciclos seguintes capturaram e corrigiram
  locale Windows, intérprete/vendor RAG do runtime temporário e o estado limpo
  de recuperação (`recovery.status=none`).
- [x] GREEN: `scripts/run_release_gates.py --profile full` executou os 22
  estágios em série, sem diretórios de build compartilhados.
- [x] Verificação: `artifacts/release-gates-final-20260907/release-gates.json`
  registra `ok=true`, 22/22 `passed`, 7793 verificações passadas, 57 skips
  explícitos e zero falhas; clean clone RAG, wheels, MCP real, crash matrix,
  revogação e reindexação concorrente estão nos artefatos por estágio.
- [x] POSIX/WSL: compileall, bootstrap sem instalação, doctor, contratos e
  documentação passaram; limitações de pip/venv/Ruff/pytest/RAG ficaram como
  skips documentados em `docs/DEPENDENCIES.md`.
- [x] Refatoração/rollback: evidências permanecem em `artifacts/` ignorado e o
  rollback não toca corpus, índice RAG real ou geração ativa.

### Execução concluída — main-consolidation T13

- [x] RED: `tests/test_integration_candidate.py` falhou antes de existir o
  seam `scripts/prepare_integration_candidate.py`.
- [x] GREEN: o relatório consolida comparação `origin/main` versus
  `origin/feat/continuous-knowledge`, feature trace, compatibilidade, estado
  versionado, riscos e o bundle opcional.
- [x] Verificação: o teste focado passou; o relatório final foi gerado em
  `artifacts/integration-candidate-final-20260907/`, com digest registrado no
  JSON e bundle pronto em `artifacts/integration-bundle-final-20260907-v4/`,
  usando o gate T12 acima; `verify_candidate.py` também retornou `ok=true` e
  identidade consistente.
- [x] Decisão: promoção para `main` permanece `performed=false` e `blocked`,
  sem autorização humana, merge, push, release, publicação ou mutação de
  corpus/RAG.

### Revisão final

- [x] Branch isolada: `codex/main-consolidation`; `main` e o remoto não foram
  alterados.
- [x] Gates Windows, POSIX/WSL, clean clone, wheel core/RAG e MCP real
  registrados e verificáveis.
- [x] Não foram versionados `.venv*`, `data/`, `models_cache/`,
  `.rag_state.json` nem corpus privado; fixtures sintéticas e dados do vendor
  revisado seguem a allowlist documentada.
- [x] Próximo passo externo: revisão humana de um commit limpo e CI vinculada
  ao digest antes de qualquer promoção.

## Execução do planejamento master — T01–T24

Escopo desta execução: implementar os contratos de `docs/MASTER-PLAN.md`,
`docs/MASTER-IMPROVEMENT-PLAN.md` e `docs/master-evolution/` em ordem de
dependências, preservando a API/lifecycle existentes. A validação usa somente
fixtures sintéticas e diretórios temporários; não altera corpus/índice ativo,
não publica, não instala scheduler e não inventa licença, credencial ou
autorização comercial. Cada ticket exige uma fatia observável em seam pública,
RED funcional registrado, GREEN mínimo, regressões, segurança/recuperação e
evidência segura antes de ser marcado concluído.

### Estado inicial e regras de execução

- [x] Ler RTK, `AGENTS.md`, `tasks/lessons.md`, skill TDD, contratos, planos,
  especificação, roadmap, TDD-EXECUTION e os 24 tickets.
- [x] Confirmar checkout, branch, remoto, dirty state e ambiente Python antes
  de alterar o runtime.
- [ ] Registrar resultado do baseline executável sem confundir documentação
  histórica com comportamento novo.
- [ ] Executar uma fatia por vez na ordem topológica; atualizar este registro
  após cada ticket, com comando, exit code, contagens e limitações.
- [ ] Executar gates de fase e suíte completa; manter `schemas/` canônico e usar
  `scripts/sync_schemas.py --write` para a cópia distribuída.
- [ ] Revisar simplicidade, diff, segurança, rollback e recursos empacotados;
  deixar pendências externas explicitamente bloqueadas.

### P0 — baseline e contrato operacional

- [ ] T01 — RED do checker para flag inválida; GREEN para flags válidas,
  placeholders e propostas futuras; corrigir runbooks/aliases sem daemon;
  validar documentação, wheel e regressões.

### P1 — projeto privado e estado retomável

- [ ] T02 — RED de init/retomada entre processos; GREEN para sessão persistida,
  revisão esperada, idempotência e pergunta de intenção ambígua; validar
  recusa sem sobrescrita e instruções distribuídas.
- [ ] T03 — RED de finalização sem composição separada; GREEN para brief,
  curso/página opcionais, projeções revisáveis, pendências e origem por ID;
  validar ausência de preço/promessa inventada e edição divergente.
- [ ] T04 — RED de adoção v1 sem seam de migração; GREEN para dry-run,
  importação idempotente, backup/rollback e preservação de release/source IDs;
  validar falha parcial, versão desconhecida e ausência de direitos inferidos.
- [ ] Gate P1 — init completo em subprocessos distintos, contratos sincronizados,
  API anterior verde, lint e `git diff --check`.

### P2 — fontes, recuperação e qualidade governada

- [ ] T05 — RED de direitos/vigência granulares; GREEN para política por uso,
  região/datas/autor, unknown fail-closed e metadados persistidos; validar
  aquisição incompleta sem retirada e invalidação de autorização.
- [ ] T06 — RED de locator temporal da transcrição; GREEN para Markdown externo,
  segmentos válidos, proveniência e derivado ligado; validar limites, prompt
  injection tratado como dado e proibição de redistribuição indevida.
- [ ] T07 — RED de filtro/isolamento no reader público; GREEN para elegibilidade,
  refill limitado, locators e cache governado; validar projetos A/B, revogação
  pós-cache e filtros inválidos.
- [ ] T08 — RED de troca de perfil sem rebuild seguro; GREEN para comparação,
  snapshot pinado, full rebuild e reader antigo durante falha; validar MCP real
  com PT-BR e não alteração do default global.
- [ ] T09 — RED de classificação/abstenção ausente; GREEN para norma, fato,
  opinião, conflito, vigência/região e insufficient_evidence; validar prioridade
  oficial, conflito explícito e citações próximas.
- [ ] T10 — RED de avaliação sem Golden do domínio/casos críticos; GREEN para
  Golden revisado, métricas com denominadores e bloqueio de regressão crítica;
  validar candidata com Recall maior mas vazamento/revogação.
- [ ] T11 — RED de preset acoplado/inexistente; GREEN para preset Mercado Livre
  e neutro sobre protocolo comum, taxonomia e candidatos sintéticos; validar
  ausência de claims comerciais reais e distinção da intenção do curso.
- [ ] Gate P2 — fontes governadas, query citada/isolada, rebuild/revogação,
  Golden revisado, contratos/documentação e regressões do RAG fixture.

### P3 — mudanças, enriquecimento e derivados

- [ ] T12 — RED de proposta sem impacto transitivo; GREEN para change/diff,
  revisão base, dry-run e dependências por artefato; validar divergência sem
  efeito e recomputação somente dos dependentes.
- [ ] T13 — RED de revogação não transitiva; GREEN para tombstones e bloqueio
  de source/claim/aula/página/cache/rollback; validar histórico preservado sem
  ressuscitar conteúdo.
- [ ] T14 — RED de dispatch externo não retomável; GREEN para request/ack,
  timeout, retry, stale-base, correlação e idempotência; validar ausência de
  harness/credencial, resultado duplicado e candidata ativa intacta.
- [ ] T15 — RED de curso/página não avaliáveis; GREEN para derivados separados,
  claims/provas, exercícios e pendências comerciais; validar edição localizada
  e bloqueio de CTA/preço/garantia desconhecidos.
- [ ] T16 — RED de promoção híbrida; GREEN para composição atômica, journal,
  hash/manifest e recuperação velha ou nova inteira; validar falha antes/depois
  do commit, dependências e revogações.
- [ ] Gate P3 — change/impacto, enrichment, derivados e composição publicados
  somente por gates existentes; rollback e leitura segura demonstrados.

### P4 — operação confiável e distribuição local

- [ ] T17 — RED de crash na última tentativa/lease longa; GREEN para estado
  terminal recuperável, renewal/fencing/ownership e nenhum efeito duplicado;
  validar subprocesso real e worker antigo sem confirmação.
- [ ] T18 — RED de ausência de supervisor; GREEN para reconcile/worker polling,
  agenda persistida, parada retomável, debounce e restart; validar origem
  indisponível sem revogação e sem instalar scheduler.
- [ ] T19 — RED de status sem incidente acionável; GREEN para health/lag,
  incidentes deduplicados/fechados e redação; validar que diagnóstico não
  muta, não expõe query/token/documento e respeita limiares.
- [ ] T20 — RED de backup sem tombstones/recibos; GREEN para manifest/checksum,
  backup consistente e restore isolado; validar checksum inválido, job em curso,
  revogação preservada e não repetição de efeitos.
- [ ] T21 — RED de mitigação expirada aceita; GREEN para auditoria bruta separada,
  owner/prazo/threat-model/versão/advisory verificáveis e relógio injetável;
  validar Python tolerado sem virar suportado.
- [ ] T22 — RED de clean clone/wheel incompletos; GREEN para gates sequenciais,
  recursos novos empacotados, matriz por perfil e cenário sintético core/MCP;
  validar bundle sem corpus/cache/segredos e falha externa mantendo ativa.
- [ ] Gate P4 — release gates completos e sequenciais, evidência vinculada ao
  mesmo candidate, clean clone/wheel, recovery, backup e segurança.

### P5 — autonomia factual restrita e piloto reproduzível

- [ ] T23 — RED de delegação ampla/flag genérica; GREEN para receipt escopado,
  prazo/orçamento/owner, revalidação e kill switch; validar factual elegível e
  bloqueio de conflito, conceito, preço, licença, expiração e revogação.
- [ ] T24 — RED do roteiro integrado; GREEN para piloto ML/neutro sintético,
  init→consulta→mudança→crash→restore→delegação revogada; validar matriz de
  evidências e separar prontidão técnica de autorização pública.
- [ ] Gate P5/final — todas as fases e 24 tickets comprovados, limitações
  externas registradas, relatório final e working tree revisado sem publicação.

### Progresso verificado nesta execução

Os requisitos abaixo são o status autoritativo desta execução; os itens
descritivos acima permanecem como a especificação original dos critérios.

- [x] Baseline, contratos, skill TDD, estado inicial e limitações foram registrados.
- [x] P0: T01 e gate de contrato/documentação verificados.
- [x] P1: T02, T03 e T04 verificados com persistência, adoção, backup e rollback.
- [x] P2: T05, T06, T07, T08, T09, T10 e T11 verificados em fixtures; MCP real permanece externo.
- [x] P3: T12, T13, T14, T15 e T16 verificados com diff, revogação, enrichment, derivados e recovery.
- [x] P4: T17, T18, T19, T20, T21 e T22 verificados localmente; scheduler, CI multiplataforma e advisories upstream permanecem externos.
- [x] P5: T23 e T24 verificados com delegação factual restrita e fixture provider-free.
- [x] Schemas canônicos/distribuídos, documentação, seams, lint, compilação, segurança e regressões foram reexecutados; o gate core final terminou com 21/21 estágios, 6.530 passados, 70 skips explícitos, zero falhas e zero não executados.

O status não concede autorização comercial, credencial, publicação ou uso do
MCP/índice real. Resultados históricos anteriores permanecem separados e os
detalhes RED/GREEN estão em
`docs/master-evolution/IMPLEMENTATION-EVIDENCE.md`.

## Revisão de harmonia do README — 2026-09-08

### Plano

- [x] Auditar o README atual contra a CLI, os documentos normativos e o estado
  implementado de P0–P5.
- [x] Reorganizar a entrada para onboarding rápido, arquitetura, segurança,
  desenvolvimento e navegação documental.
- [x] Remover redundâncias e status obsoletos sem alterar contratos ou comandos.
- [x] Validar links, exemplos, Markdown, diff e regressões do pacote.

### Revisão

- Resultado: README reorganizado de 619 para 392 linhas, com navegação por
  intenção, onboarding curto, arquitetura, CLI canônica, segurança, status P0–P5
  e documentação normativa.
- Consistência: links locais e âncoras passaram no checker documental; o status
  antigo que dizia que a evolução contínua não estava implementada foi removido.
- Verificação: `check_documentation.py --json` — 112 Markdown, zero findings;
  `tests/test_contract_doc_drift.py` — 4 passed; fixture sintética — resolve,
  plan, run e validate passaram sequencialmente.
- Escopo: nenhuma alteração de contrato, código de runtime, corpus real ou
  índice real; `.scratch/readme-sequential` contém somente a validação local.

### Revisão desta execução

- Resultado: todas as fases P0–P5 e os 24 tickets têm implementação e evidência
  local; o fixture provider-free e o runner core estão verdes.
- Segurança/recuperação: governança fail-closed, revogação, journal de ativação,
  fencing/leases, backup com checksum e snapshot isolado da fila foram exercitados.
- Auditoria TDD final: propostas e defaults não confirmam decisões de produto;
  segmentos estruturados de transcrição fora de ordem são rejeitados.
- Limitações: o perfil full/MCP, rebuild do índice/corpus real, scheduler externo,
  CI de outras plataformas, advisories upstream e autorização/credenciais
  comerciais permanecem bloqueios explícitos; não são aceites técnicos
  inferidos.

## Renomeação de produto para Farol — 2026-09-09

### Plano

- [x] Mapear ocorrências do nome antigo e separar marca pública, identificadores
  técnicos, compatibilidade de distribuição e evidências históricas.
- [x] Atualizar a marca pública para Farol em documentação, metadata, configuração,
  fixtures e materiais de contribuição.
- [x] Preservar o namespace/CLI `docops`, contratos e artefatos de release legados
  quando a troca direta pudesse quebrar consumidores existentes.
- [x] Validar sincronização de schemas, candidate gates, testes, links e ausência
  de regressão funcional.

### Revisão

- Resultado: marca pública, metadata, licença, governança, configuração, fixture,
  guia do agente e materiais de divulgação atuais foram alinhados para **Farol**.
- Compatibilidade: `farol` foi adicionado como launcher; `docops`, o identificador
  de distribuição `consulta-documentacao` da v1.1.0, `$id` dos schemas e nomes de
  assets históricos foram mantidos de forma explícita e documentada.
- Verificação: `check_documentation.py --json` passou com 112 Markdown e zero
  findings; `check_contracts.py --json` passou; `sync_schemas.py --check` passou;
  candidate core passou; suíte focada passou com 13 testes; Ruff check/format e
  `git diff --check` passaram.
- Regressões/limitações: a suíte completa antes do ajuste do checker observou 390
  passes, 3 skips por symlink indisponível no Windows e 3 falhas; a falha do
  relatório de integração foi corrigida e passou no rerun focado. Permanecem duas
  limitações externas ao rebrand: MCP EOF e ambiente sem as versões travadas no
  fallback de supply-chain.

## Continuação T02 → T04 — migração legada e artefatos opcionais — 2026-09-09

### Plano executável

- [x] Revalidar o checkout, a branch principal, os contratos, os seams públicos,
  as lições e o teste T02 já verde.
- [x] Caracterizar T03/T04 pela API raiz, CLI, JSON persistido e pacote DOCOPS,
  identificando qualquer lacuna além dos testes existentes.
- [x] Escrever um teste RED por comportamento faltante antes do código: artefatos
  opcionais revisáveis e adoção idempotente de pacote legado com locator relativo.
- [x] Implementar somente o mínimo para cada RED, preservando `docops`, os
  readers/índices/releases legados e ausência de autorização inferida.
- [x] Validar recuperação, CAS/idempotência, hashes/contratos, wheel/CLI e
  regressões dos seams públicos; atualizar tickets/evidências com comandos reais.
- [x] Fechar a revisão do plano somente se todos os critérios demonstrados forem
  comprovados; registrar limites externos sem convertê-los em sucesso técnico.

### Seams fixados

`import docops`, subprocesso `python -m docops`, JSON em `project.json`,
`init/session.json`, `revisions/<id>/` e `package/`, além dos schemas normativos.
O pacote DOCOPS existente continua sendo locator independente; não será duplicado
nem convertido em estado editorial do projeto.

### Revisão

- RED → GREEN confirmado em `test_unconfirmed_commercial_values_never_enter_page_offer`,
  `test_adoption_dry_run_is_non_mutating_and_receipt_uses_portable_locators`,
  `test_audience_correction_invalidates_only_dependent_derivatives` e
  `test_project_init_resumes_across_cli_processes_without_repeating_answers`;
  o caso de preço estruturado também foi coberto após o RED de tipo inválido.
- Suíte completa: `399 passed, 3 skipped`; os três skips são limitações de
  symlink no Windows. Gate core final: `21/21` estágios, `6530 passed`, `70
  skipped`, `failed=0`, `not_run=0`; clean clone: `394 passed, 8 skipped`.
- Gates adicionais verdes: schemas sincronizados (`54`), contratos, documentação
  (`112` Markdown), seams públicos, Ruff, compilação, diff-check, crash matrix
  (`17 passed`), revocation (`25 passed`), fixture provider-free e wheel core.
- Limitações externas preservadas: MCP/índice RAG real, rebuild multilíngue,
  credenciais/autorização comercial, publicação externa, CI multiplataforma e
  decisão humana sobre advisories upstream não foram simulados como sucesso;
  fixtures sintéticas mantêm esses fluxos bloqueados/`unknown`.
