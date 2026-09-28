# Auditoria crítica de prontidão para publicação no GitHub

**Data:** 2026-09-01 (execuções atravessaram a meia-noite local durante os gates RAG)
**Escopo:** release pública `v1.0.0`, `HEAD/origin/main` e working tree candidato
**Restrições:** somente auditoria e documentação; nenhum código, commit, push, tag ou release

## Veredito executivo

O repositório público já é uma release técnica séria para um projeto jovem, mas
o working tree atual **não está profissionalmente publicável hoje**. Ele contém
uma evolução pós-1.0 ampla e majoritariamente não publicada, com bons contratos,
lifecycle recuperável, segurança de aquisição forte e integração RAG real. Ao
mesmo tempo, três gates fundamentais falham e o auditor que deveria impedir a
publicação de dados privados tem falsos negativos confirmados.

As notas avaliam o estado real do working tree; a release `v1.0.0` é tratada
separadamente para evitar herdar evidência que não foi executada sobre o
candidato atual.

| Setor | Nota | Síntese baseada em evidência |
|---|---:|---|
| Produto, propósito e README | 7,5 | propósito e fronteira são claros; identidade, instalação publicada e maturidade ainda são ambíguas |
| Arquitetura, interface pública e compatibilidade | 6,0 | seam `plan/apply/inspect` é promissor, mas a interface raiz está incompleta e a engine nova depende de privados da antiga |
| Confiabilidade, lifecycle e preservação de dados | 7,0 | rollback, stale-plan, lease e retomada têm testes; promoção não é atomicamente observável e resíduos não têm retenção |
| Testes, TDD e cobertura dos seams públicos | 6,0 | 154 testes coletados passam em grande parte, mas a suíte está vermelha, há skips e a interface raiz não é exercitada |
| RAG/MCP e integrações reais | 7,5 | tracer real completo passou; o smoke sem o extra RAG é ambiente-dependente e quebra o CI rápido candidato |
| Segurança, privacidade e SSRF | 6,0 | SSRF e Git remoto têm controles fortes; o release auditor aceita corpus/índice/token rastreado em caminhos aninhados |
| Dependências e supply chain | 5,5 | pins diretos e auditoria estreita existem; transitivas/modelos/vendor não têm hashes/proveniência completa e há 4 CVEs residuais |
| Empacotamento e reprodutibilidade | 5,0 | o wheel constrói, mas seu tracer end-to-end falha; lock não é transitivo e nenhum artefato é distribuído |
| CI, release e GitHub readiness | 6,5 | CI público do estado publicado é amplo e verde; o candidato não passou os gates locais e ainda há políticas/artefatos ausentes |
| Documentação e experiência do operador | 7,0 | documentação é extensa e honesta em vários limites; checklist de release é contraditório e a spec antiga ficou obsoleta |
| Portabilidade | 7,0 | núcleo comprovado no CI em três SOs; wrappers, RAG multiplataforma, symlinks e nova matriz ainda não têm prova equivalente |
| Manutenibilidade e qualidade do código | 5,0 | lint passa, mas formatação não; `operations.py` tem 1.566 linhas, circularidade e engine duplicada |
| Comunidade open source | 4,5 | MIT, SECURITY e CONTRIBUTING existem; faltam CoC raiz, templates, governança, suporte e metadata comunitária |

**Nota geral:** **6,2/10**.
**Nota para publicar hoje:** **3,0/10** — há blockers reproduzíveis e arquivos essenciais ainda não rastreados.
**Nota para produção estável:** **4,5/10** — a base técnica é boa, mas faltam prova de continuidade de leitura, cadeia de suprimentos reproduzível, gates fail-closed, distribuição e governança operacional.

## Como ler as conclusões

- **Fato**: observado em arquivo, Git, teste ou comando executado.
- **Inferência**: conclusão técnica sustentada pelos fatos, mas não diretamente
  executável como uma asserção.
- **Recomendação**: trabalho futuro; não foi implementado nesta auditoria.

## Estados Git e release pública

### Fatos

- `HEAD` e `origin/main` apontam para
  `855038019abbbe37d027728ac1bf034f4af210fb`.
- A tag `v1.0.0` aponta para `e8083ade...`; entre a tag e `HEAD`, somente
  `tasks/todo.md` mudou.
- A release GitHub `v1.0.0` é pública, não draft e não prerelease, publicada em
  2026-08-30. Não possui assets.
- O working tree tinha, antes dos documentos desta auditoria, 35 arquivos
  rastreados modificados e 21 entradas não rastreadas. Entre os não rastreados
  estavam `docops/operations.py`, `docops/contracts.py`, schemas empacotados,
  `docs/SUPPORT-MATRIX.json` e os novos gates.
- `pyproject.toml:7` e `docops/__init__.py:4` continuam declarando `1.0.0`.
- O CI público de `HEAD` passou; os workflows e contratos modificados no working
  tree ainda não possuem essa evidência remota.

### Inferências

- A release pública comprova o baseline 1.0.0, não a revisão pós-1.0 atual.
- Publicar o working tree sem nova identidade de versão produziria dois
  comportamentos materialmente diferentes chamados `1.0.0`.
- `audit_release --tracked-only` não representa o candidato enquanto módulos
  essenciais permanecem não rastreados.

### Recomendações

- Tratar o working tree como novo release candidate e atribuir versão nova
  somente após contratos e compatibilidade serem decididos.
- Executar todos os gates sobre o conjunto exato a publicar, inclusive arquivos
  ainda não adicionados ao índice, antes de qualquer commit de release.

## Evidências por setor

### 1. Produto, propósito e README — 7,5/10

**Fatos.** `README.md:3-10` define um operador portátil, explicitamente sem LLM
ou provedor. `README.md:24-67` oferece quick start e fluxo completo;
`README.md:69-84` cobre harness e política de dados. O nome do pacote
O produto **Farol** agora tem identidade pública própria, enquanto a distribuição
técnica `consulta-documentacao` permanece como identificador de compatibilidade.
Não há instalação por registry, badge de CI/release ou aviso frontal de que os
recursos pós-1.0 estão somente no working tree.

**Inferência.** Um avaliador entende o propósito, mas pode confundir o estado
publicado com o candidato local e não encontra um canal de distribuição normal.

**Recomendação.** Unificar a identidade pública, mostrar maturidade e suporte
por perfil e documentar instalação a partir de artefato versionado.

### 2. Arquitetura, interface pública e compatibilidade — 6,0/10

**Fatos.** A raiz exporta `OperationPlan`, `OperationRequest`, `plan`, `apply` e
`inspect` (`docops/__init__.py:3-35`). `plan` aceita `PipelineOptions`
(`docops/operations.py:697-700`), mas esse tipo não é exportado pela raiz. Os
testes importam o seam por `docops.pipeline`, não por `docops`. O módulo novo
importa `PipelineOptions`, `PipelineResult` e oito helpers privados da engine
legada (`docops/operations.py:30-41`); `pipeline.py:755-798` importa a engine
nova e até os privados `_failure_result` e `_outcome`. O legado completo ainda
existe em `pipeline.py:394-750`.

**Inferência.** Há acoplamento bidirecional tolerado por imports lazy, duas
engines e uma interface pública que callers não conseguem aprender apenas pela
raiz do pacote. Isso enfraquece compatibilidade e locality.

**Recomendação.** Estabilizar request/result/options públicos, testar imports da
raiz, caracterizar compatibilidade e migrar helpers para um módulo interno
unidirecional antes de contrair o legado.

### 3. Confiabilidade, lifecycle e preservação de dados — 7,0/10

**Fatos.** Testes exercitam plano sem efeitos, stale plan, create/update,
retomada, rollback e lease (`tests/test_post_lifecycle.py` e
`tests/test_post_reliability.py`). `apply` revalida antes e depois do lease
(`docops/operations.py:1347-1434`). A promoção renomeia primeiro a geração ativa
para backup e depois o staging para o destino (`docops/operations.py:1292-1307`),
criando uma janela na qual o path ativo não existe. Não há teste de reader
concorrente. Tentativas ficam no sibling `.<pacote>.docops-attempts`
(`docops/operations.py:835-858`), enquanto `docs/ARCHITECTURE.md` as atribui a
`.docops/`; não há política de retenção/GC. `apply` pode executar aquisição
durante replanejamento, inclusive sob lease.

**Inferência.** Recuperabilidade está bem provada; atomicidade observável e
disponibilidade contínua para readers não estão. Fontes lentas ampliam a
contenção do writer.

**Recomendação.** Definir precisamente a garantia de promoção, testá-la com
reader/processo concorrente e separar revalidação barata de nova aquisição.

### 4. Testes, TDD e seams públicos — 6,0/10

**Fatos.** `pytest -q` retornou `1 failed, 153 passed, 2 skipped`. Os skips são
de symlink indisponível no host Windows. Ruff lint passou; `ruff format --check`
reportou 54 arquivos a reformatar e 10 já formatados. Contratos e lifecycle têm
boa cobertura comportamental, mas não há teste importando e usando diretamente
`docops.plan/apply/inspect` da raiz. Não há gate de cobertura configurado no
projeto.

**Inferência.** A disciplina de testes é acima da média, mas o seam anunciado
não é o seam realmente protegido, e a suíte vermelha invalida release hoje.

**Recomendação.** Corrigir primeiro pelo seam público, adicionar tracer bullets
da raiz/CLI e definir uma política explícita de formatação e cobertura por
capacidade, sem perseguir percentual cego.

### 5. RAG/MCP e integrações reais — 7,5/10

**Fatos.** Em pacote temporário, `run --index-rag`, `validate`,
`evaluate --adapter mcp` e `test_reindex_concurrency.py` passaram. A fixture teve
2 documentos, backend `knowledge-rag==4.8.5`, perfil `compact`, Recall@5 1,0 e
MRR@5 1,0. O smoke real listou 13 ferramentas e omitiu conteúdo do corpus nos
logs. Em venv sem `[rag]`, porém, `tests/test_mcp_smoke.py` teve `1 failed,
2 passed`: `_server_version_error` retorna `None` quando o metadata do pacote
não existe (`scripts/mcp_smoke.py:61-74`), portanto não detecta drift e termina
em EOF.

**Inferência.** A integração existe e funciona; a prova rápida é frágil e o CI
quick candidato falharia porque instala apenas `[dev,formats]`.

**Recomendação.** Derivar a versão esperada do runtime efetivamente selecionado
ou de contrato explícito e testar presença, ausência e drift sem depender do
ambiente do launcher.

### 6. Segurança, privacidade e SSRF — 6,0/10

**Fatos.** `web_acquirer.py:181-220,449-554` valida esquema, credenciais, IPs e
redirects e conecta ao IP aprovado preservando Host/SNI. O acquirer Git fixa
DNS, recusa protocolos inseguros, prompts, redirects e submódulos
(`repository_acquirer.py:237-289`). Os 37 testes focados passaram. O auditor de
release, porém, ignora qualquer arquivo que contenha um componente chamado
`data`, `artifacts`, `models_cache` ou `.docops` antes de analisá-lo
(`docops/release_audit.py:119-120`). A proteção de corpus e network config só é
raiz-específica (`:121-125`), e a regex de segredo não cobre de forma confiável
`bearer_token` (`:25-32`). Um repositório Git temporário com dados proibidos
forçados em caminhos aninhados retornou `ok: true`.

**Inferência.** A superfície de entrada é bem defendida, mas a última barreira
contra exfiltração acidental é fail-open em casos confirmados.

**Recomendação.** Auditar todo arquivo rastreado antes de qualquer skip,
classificar artefatos proibidos em qualquer profundidade e cobrir chaves de
credencial estruturadas com canários em um repositório Git real.

### 7. Dependências e supply chain — 5,5/10

**Fatos.** O bootstrap fixa `pip==26.2.1` e `setuptools==84.0.0`; as dependências
diretas estão pinadas. `requirements.lock` não contém transitivas nem hashes
(`docs/DEPENDENCIES.md:10-15`). Um venv Python 3.12 recém-criado veio com
`pip==25.3` e a auditoria encontrou cinco vulnerabilidades de pip; após executar
o pin documentado, o gate passou. `chromadb==1.5.9` permaneceu com exatamente
quatro CVEs sem `fix_versions`: CVE-2026-45829, -45830, -45831 e -45833. O
wrapper retorna `ok: true` por allowlist; isso não é uma auditoria sem CVEs. O
vendor e os modelos não têm manifesto de hash/proveniência completo.

**Inferência.** A ordem do bootstrap é parte da segurança e o lock isolado não
reproduz o ambiente. A mitigação dos CVEs é plausível apenas enquanto o produto
usar `PersistentClient` local/stdio e proibir os vetores HTTP/remote model.

**Recomendação.** Produzir lock/constraints transitivos por plataforma com
hashes, SBOM, procedência verificável do vendor/modelos e manter a exceção
Chroma estreita e reavaliada em toda release.

### 8. Empacotamento e reprodutibilidade — 5,0/10

**Fatos.** `py -3.12 scripts/verify_wheel.py` construiu
`consulta_documentacao-1.0.0-py3-none-any.whl`, mas falhou em
`scripts/verify_wheel.py:174`: a avaliação instalada não reportou o adapter
executado. O `HEAD` limpo passa o wheel antigo, menos rigoroso. Não há wheel,
SBOM, checksum, assinatura ou attestation anexados à release e o projeto não
está no PyPI.

**Inferência.** Buildar não é o mesmo que reproduzir o comportamento instalado;
o candidato falha exatamente nessa diferença.

**Recomendação.** Corrigir o contrato público de avaliação, provar o wheel em
ambiente isolado com e sem RAG e só então produzir artefatos versionados e
verificáveis.

### 9. CI, release e GitHub readiness — 6,5/10

**Fatos.** O estado público possui CI verde em Ubuntu/Windows/macOS e Python
3.11-3.13. A working tree fixa Actions por SHA, mas essa correção não está no
`HEAD` público. A integração RAG é agendada/manual. O checklist em
`docs/RELEASE.md:8-15` manda criar `.venv` e depois executar a auditoria completa,
que reprova `.venv`; a variante `--tracked-only` passa, mas não enxerga novos
arquivos. Não há workflow de release/attestation. A API pública não mostrou
rulesets; proteção clássica não pôde ser confirmada anonimamente.

**Inferência.** O baseline público tem CI melhor que muitos projetos iniciais,
mas o processo de candidato não é auto-consistente nem fail-closed.

**Recomendação.** Definir ordem de gates executável, política de branch, CI por
paths críticos, release reproducível e publicação somente a partir do mesmo
commit que passou todos os gates.

### 10. Documentação e experiência do operador — 7,0/10

**Fatos.** Há guias de arquitetura, uso, schemas, harnesses, segurança,
dependências, publicação e release. A spec pós-1.0 ainda descrevia como atuais
vários problemas já implementados e afirmava gates verdes, contrariando o
baseline desta auditoria. `CONTRIBUTING.md` é curto e orientado ao agente, sem um
fluxo OSS convencional completo.

**Inferência.** A cobertura documental é forte, mas o volume acumulou drift e
faz o operador escolher entre instruções conflitantes.

**Recomendação.** Manter um documento de estado factual, gerar checks a partir
de uma matriz normativa e tornar runbooks copiáveis em clone, checkout sujo e
wheel instalado.

### 11. Portabilidade — 7,0/10

**Fatos.** O CI publicado cobre três sistemas e três versões Python. O host
Windows tinha Python 3.12 e 3.14; a suíte pulou dois testes de symlink. O RAG
real candidato foi comprovado localmente no Windows e no CI publicado apenas em
Ubuntu/Python 3.12. Os wrappers `bootstrap.ps1` e `bootstrap.sh` não são
exercitados pela matriz; o CI instala diretamente via pip. A nova
`SUPPORT-MATRIX.json` ainda não está rastreada.

**Inferência.** O claim é sólido para o núcleo 1.0 publicado, mas amplo demais
se lido como suporte equivalente para RAG, wrappers e semântica de filesystem.

**Recomendação.** Publicar matriz por perfil e executar wrappers, wheel/RAG e
testes de filesystem nas plataformas que anunciarem suporte.

### 12. Manutenibilidade e qualidade do código — 5,0/10

**Fatos.** Ruff lint e `git diff --check` passam. Ruff format não. Os maiores
módulos são `operations.py` (1.566 linhas), `pipeline.py` (798),
`web_acquirer.py` (788) e `evaluator.py` (400). `operations.py` importa helpers
privados da engine antiga e o legado continua duplicado.

**Inferência.** A complexidade está concentrada, mas não atrás de uma interface
realmente independente; o custo de mudança é alto e a circularidade esconde
ordem de inicialização.

**Recomendação.** Prefatorar por seam, expandir/migrar/contrair mantendo CI
verde e só aplicar formatação em mudança dedicada para não misturar semântica.

### 13. Comunidade open source — 4,5/10

**Fatos.** Existem MIT, README, SECURITY e CONTRIBUTING. O community profile
consultado reportou 57%. Faltam Code of Conduct raiz, issue/PR templates,
GOVERNANCE/MAINTAINERS/SUPPORT, descrição e homepage do repositório. Discussions
está desativado. A release não possui assets.

**Inferência.** O código é publicável como fonte, mas o projeto ainda não oferece
uma experiência comunitária completa ou expectativas claras de manutenção.

**Recomendação.** Completar community files, ownership, suporte, templates,
metadata e documentação de entrada acessível sem depender de instruções de
agentes.

## Blockers ordenados por severidade

1. **P0 — auditor de release aceita dados privados rastreados.** Falso negativo
   confirmado para corpus/índice/config/token em caminhos aninhados; risco de
   publicação irreversível de dados.
2. **P0 — suíte e clean clone candidatos estão vermelhos sem `[rag]`.** O teste
   do smoke depende do metadata ambiental de `knowledge-rag`.
3. **P0 — wheel candidato falha no tracer instalado.** A avaliação não reporta
   o adapter exigido pelo contrato do gate.
4. **P0 — identidade de versão/proveniência é inválida.** Uma revisão ampla e
   incompatível ainda se apresenta como `1.0.0`, igual à release existente.
5. **P1 — conjunto candidato não é auditado exatamente.** `--tracked-only`
   ignora módulos novos; auditoria completa mistura estado local e o checklist
   a executa depois de criar `.venv`.
6. **P1 — interface pública raiz não está fechada nem testada.** O tipo exigido
   por `plan` vive na interface legada e não é exportado.
7. **P1 — acoplamento bidirecional e aquisição repetida.** Engine nova e antiga
   dependem de privados uma da outra; apply pode readquirir fonte sob lease.
8. **P1 — promoção/reader e resíduos operacionais não cumprem toda a narrativa.**
   Recuperação existe, mas há janela sem geração ativa e ausência de retenção.
9. **P1 — supply chain não é plenamente reproduzível.** Transitivas, vendor e
   modelos carecem de hashes/proveniência; quatro CVEs Chroma continuam ativos.
10. **P1 — claims de portabilidade não são perfilados.** Core, wrappers, RAG e
    semântica de filesystem têm evidências diferentes.
11. **P2 — distribuição e comunidade incompletas.** Sem artefatos verificáveis,
    templates, CoC raiz, governança e suporte.

## Gates executados e resultados

| Comando | Resultado | Classificação |
|---|---|---|
| `python -m pytest -q` | **FAIL** — 1 failed, 153 passed, 2 skipped | defeito do candidato; skips de ambiente Windows |
| venv sem RAG + `pytest -q tests/test_mcp_smoke.py` | **FAIL** — 1 failed, 2 passed | reprodução determinística do blocker |
| `python -m ruff check docops tests scripts` | PASS | gate de lint |
| `python -m ruff format --check docops tests scripts` | **FAIL** — 54 reformatariam | dívida de formatação; não é o mesmo que lint |
| `python scripts/check_contracts.py --json` | PASS — 9 famílias | contrato executável |
| `python scripts/check_support_matrix.py --json` | PASS | consistência do arquivo atual, ainda não rastreado |
| `python scripts/audit_release.py --tracked-only --json` | PASS — 324 arquivos | insuficiente: ignora untracked e tem falsos negativos |
| auditor de release em repo Git adversarial temporário | **FAIL de segurança do gate** — retornou `ok: true` | defeito confirmado |
| `python -m docops doctor --json` | PASS; RAG disponível no `.venv` | ambiente local |
| clean clone Python 3.12 sem dependências | **FAIL de ambiente** — pytest ausente | risco de UX/reprodutibilidade, não defeito isolado |
| clean clone com `[dev,formats]` | **FAIL** — mesmo teste MCP; 153 passed | defeito do candidato |
| pip-audit em venv antes do pin de pip | **FAIL** — 5 CVEs de pip 25.3 | ordem de bootstrap necessária |
| pin pip 26.2.1 + auditoria requirements/local strict | PASS com 4 CVEs Chroma allowlisted | risco residual, não “zero CVEs” |
| `pip check` no venv RAG limpo | PASS | consistência instalada |
| 37 testes focados em segurança/RAG | PASS | aquisição/SSRF/config/auditoria parcial |
| `config-audit config.yaml` | PASS (`stdio`) | configuração default segura |
| `config-audit config/network.example.yaml` | **FAIL esperado** — token placeholder | controle fail-closed correto |
| `py -3.12 scripts/verify_wheel.py` | **FAIL** na validação de metadata do adapter | blocker de empacotamento |
| RAG `run --index-rag` em pacote temporário | PASS | integração real |
| `docops validate` no pacote temporário | PASS | contrato do pacote |
| `evaluate --adapter mcp` | PASS — Recall@5 1,0; MRR@5 1,0 | Golden fixture, não claim universal |
| `test_reindex_concurrency.py --package <temp>` | PASS — 1 busca, 0 erros | integração concorrente real |
| `git diff --check` | PASS | higiene textual do diff |

## Falhas de ambiente separadas de defeitos

- Python 3.12 estava instalado, mas sem pytest; `verify_clean_clone.py --python`
  falhou até preparar um venv. No CI, o profile é instalado previamente.
- O Python global 3.14 não tinha `pip-audit`; a auditoria correta foi executada
  em venv limpo. Isso é falha do ambiente global e risco de runbook, não CVE do
  produto.
- Dois testes de symlink foram pulados porque o host Windows não permitiu criar
  links. A prova deve vir de runners com a capacidade habilitada.
- O perfil de rede de exemplo falhou deliberadamente por token placeholder;
  isso é comportamento correto.

## Riscos que impedem uma release profissional

- Exfiltração acidental por falso negativo do auditor de publicação.
- CI/clean clone e wheel vermelhos no candidato.
- Mesma versão para dois comportamentos diferentes.
- Interface pública não protegida pelo próprio conjunto de testes.
- Garantia documental de “promoção transacional” maior que a continuidade
  observável provada.
- Dependências transitivas/modelos/vendor sem cadeia de hashes completa.
- Quatro CVEs Chroma ativos, aceitáveis somente sob o threat model local atual.
- Prova multiplataforma desigual entre core, wrappers, wheel, RAG e symlinks.
- Ausência de artefatos assinados/atestados e de governança comunitária básica.

## Critério de saída desta auditoria

A documentação a seguir deve converter somente estes achados confirmados em
especificação, tickets e estratégia TDD. Nenhum ticket é implementado nesta
etapa. O primeiro modelo implementador deve começar pelo ticket P0 de auditoria
fail-closed, usando um repositório Git temporário e canários como seam público.
