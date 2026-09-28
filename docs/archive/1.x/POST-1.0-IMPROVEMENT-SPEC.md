# Especificação de profissionalização pós-1.0

**Status:** implementação local Goal Mode concluída em 2026-09-03; a liberação
permanece bloqueada apenas por evidência remota/autenticada e decisão humana
explicitamente registradas

**Base factual:** `docs/GITHUB-PUBLICATION-AUDIT-2026-09-02.md`

**Método:** achados confirmados → especificação → tickets ordenados → plano
TDD → implementação vertical → gates reproduzíveis. O working tree contém a
implementação local e conserva a separação entre evidência observada e decisão
de release.

## Estado da execução Goal Mode — 2026-09-03

Os tickets 23–29 foram implementados localmente na ordem de dependência e têm
testes, documentação e evidência nos próprios tickets. Permanecem dois gates
fora da autoridade desta execução: (1) um commit/CI remoto no mesmo SHA do
candidato, pois commit/push/publicação foram proibidos; e (2) a decisão do
mantenedor sobre o residual dos quatro CVEs do Chroma, mantida como
`pending-maintainer-decision` em `docs/CHROMA-RESIDUAL-DECISION.md`. Isso não é
apresentado como release-ready.

## Problem Statement

O produto tem uma release pública 1.0.0 e um working tree 1.1.0 com uma
implementação pós-1.0 substancial. O core, os contratos, o lifecycle normal, o
wheel e o tracer RAG/MCP funcionam nos ambientes executados. A evolução
anterior também separou a engine de `operations.py` do adapter fino
`pipeline.py`; o antigo diagnóstico de acoplamento bidirecional não é mais
fato no código de produção.

Ainda não há evidência suficiente para chamar o working tree de release
profissional:

1. o candidato 1.1.0 existe somente no working tree; `HEAD`, `origin/main` e
   a release pública ainda representam 1.0.0;
2. `pip-audit` cru reproduz quatro advisories do `chromadb==1.5.9`, enquanto o
   wrapper passa por uma allowlist estreita para o threat model local;
3. locks de entrada são diretos e sem hashes/transitivas por plataforma, e a
   provenance do vendor não tem uma referência upstream imutável;
4. a promoção normal tem backup/retry, mas a recuperação após interrupção entre
   os renames não está provada por um processo reiniciado;
5. parte importante da suíte importa módulos internos apesar da regra de
   testar somente seams públicos; a raiz tem apenas quatro testes diretos;
6. a matriz de suporte é coerente como documento/checker, mas o working tree
   ainda não tem resultados CI públicos no seu próprio commit e a prova local
   não cobre macOS/RAG em todas as combinações declaradas;
7. metadata e arquivos de comunidade existem localmente, mas não estão no
   GitHub público nem necessariamente em locais reconhecidos pelo GitHub;
8. stress concorrente e semântica das métricas de chunks ainda não fornecem
   evidência operacional forte.

### 1.1 Fatos já confirmados e preservados

Os tickets 13–22 foram implementados antes desta auditoria e não devem ser
reabertos por suposições antigas:

- o auditor `tracked`/`candidate` bloqueia paths proibidos aninhados, binários e
  canários estruturados sem ecoá-los;
- o smoke sem RAG diferencia ausência e drift; `tests/test_mcp_smoke.py` passa
  sem o extra instalado;
- `import docops` exporta request/options/plan/result e o resultado é
  profundamente imutável;
- `pipeline.py` é um adapter de compatibilidade fino e a engine atual não o
  importa de volta;
- staging, lease, receipts, readiness, avaliação MCP, wrappers, wheel e
  candidate bundle têm contratos executáveis;
- URL/Git/MCP/configuração e publicação têm controles de segurança testados.

Esses fatos são evidência positiva, não autorização de release. Cada novo
ticket deve manter a compatibilidade observável e evitar regressão desses
fluxos.

## Solution

Construir uma cadeia de publicação que possa responder, com evidência no mesmo
commit: “este é o conjunto exato de arquivos; ele foi auditado, testado nos
perfis declarados, empacotado, associado a uma provenance verificável e não
confunde a release pública anterior com um candidato local”. A cadeia deve
preservar o pequeno seam de produto e a opcionalidade local do RAG.

## User Stories

1. Como mantenedor, quero distinguir working tree, `HEAD`, branch remoto, tag e
   release, para que nenhum resultado local seja apresentado como prova pública.
2. Como release manager, quero um digest determinístico do conjunto candidato,
   para que qualquer alteração posterior invalide a auditoria.
3. Como revisor, quero comparar o digest do bundle com o commit do CI, para que
   wheel, SBOM e checksums sejam do mesmo conteúdo.
4. Como consumidor, quero saber a versão e o estado de publicação do artefato,
   para que eu não confunda um candidato com a release estável anterior.
5. Como caller Python, quero usar uma interface raiz pequena e versionada, para
   que refactors internos não quebrem meu código.
6. Como caller legado, quero que o adapter 1.0 permaneça compatível, para que a
   migração possa ocorrer sem uma quebra silenciosa.
7. Como mantenedor, quero que testes de comportamento usem o seam público, para
   que uma refatoração que preserve o contrato não exija reescrever a suíte.
8. Como operador, quero planejar sem efeitos colaterais, para que preview não
   altere meu pacote nem o meu corpus.
9. Como operador, quero aplicar uma geração nova sem perder a anterior, para que
   uma falha de processo não destrua dados válidos.
10. Como reader, quero observar apenas uma geração válida, para que uma
    promoção não cause indisponibilidade ou leitura parcial.
11. Como operador, quero que `inspect()` classifique estados recuperáveis, para
    que eu consiga agir depois de um crash sem ler dados privados.
12. Como operador, quero que cleanup preserve ativo, lease e staging válido,
    para que manutenção automática não remova a única cópia recuperável.
13. Como responsável por segurança, quero que corpus, índice, estado e
    configuração privada sejam bloqueados em qualquer profundidade, para que
    reorganizar diretórios não crie um bypass.
14. Como responsável por segurança, quero que binários proibidos sejam rejeitados
    antes da decodificação, para que encoding não mascare um artefato privado.
15. Como responsável por segurança, quero que tokens sejam redigidos de todos os
    relatórios, para que o próprio gate não vaze credenciais.
16. Como operador web/Git, quero que SSRF, redirects inseguros, file URLs e
    submódulos não sejam aceitos, para que a aquisição remota respeite o threat
    model documentado.
17. Como operador RAG, quero que ausência, drift e runtime selecionado tenham
    outcomes diferentes, para que um EOF não esconda uma incompatibilidade.
18. Como operador sem RAG, quero que o core funcione sem o extra instalado, para
    que a dependência opcional seja realmente opcional.
19. Como operador RAG, quero que o wheel execute MCP real e informe sua
    proveniência, para que importabilidade não seja confundida com integração.
20. Como responsável por supply chain, quero conhecer dependências transitivas,
    markers e hashes por perfil, para que a resolução seja reproduzível.
21. Como responsável pelo vendor, quero uma ref upstream imutável e um digest,
    para que a cópia revisada possa ser reconstituída e auditada.
22. Como responsável por segurança, quero ver os quatro advisories do Chroma
    separadamente do allowlist, para que uma mitigação local não pareça uma
    auditoria limpa.
23. Como operador de modelo, quero identidade e digest do snapshot quando ele
    for fornecido, para que troca de artefato externo seja detectável.
24. Como usuário Windows, Linux ou macOS, quero saber qual perfil foi realmente
    exercitado no meu sistema, para que “multiplataforma” não seja uma claim
    ampla demais.
25. Como release manager, quero que clean clone tenha bootstrap/preflight
    acionável, para que um pacote ausente não pareça defeito funcional.
26. Como release manager, quero que cada claim aponte para um job e gate, para
    que o checker não valide apenas texto parecido com um workflow.
27. Como consumidor, quero baixar wheel, checksum e SBOM da release correta,
    para que não precise instalar de um checkout mutável.
28. Como contribuidor, quero templates de issue e PR que o GitHub reconheça,
    para que reproduções e contexto cheguem consistentes.
29. Como membro da comunidade, quero Code of Conduct, governança, maintainers e
    suporte visíveis, para que expectativas de colaboração sejam explícitas.
30. Como mantenedor, quero description, homepage e topics coerentes, para que o
    projeto seja encontrável e compreensível.
31. Como operador, quero métricas que distingam contagens do operador e do
    backend, para que dashboards não apresentem unidades diferentes como uma só.
32. Como release manager, quero stress concorrente com carga mínima declarada,
    para que “zero erros em 20 segundos” não seja confundido com prova de carga.
33. Como revisor, quero que warnings de dependência/telemetria sejam separados
    de falhas funcionais, para que a decisão de risco seja explícita.
34. Como agente implementador, quero tickets verticais com blockers claros,
    para que cada contexto termine em comportamento demonstrável.
35. Como revisor, quero que cada ticket declare seu seam público, para que a
    suíte não congele detalhes privados.
36. Como mantenedor, quero uma prova final sobre um único commit, para que
    nenhum arquivo mude entre auditoria, build e autorização humana.

## Implementation Decisions

### 3. Contrato externo e vocabulário de design

O módulo público é o pacote `docops`; sua interface inclui tipos, invariantes,
ordenação, outcomes, erros, serialização e requisitos de ambiente. O módulo
deve ser profundo: muito comportamento deve ficar atrás de um seam pequeno.

- **Interface:** `import docops`, `OperationRequest`, `OperationOptions`,
  `OperationPlan`, `OperationResult`, `plan`, `preview`, `apply`, `inspect` e
  `cleanup`, mais CLI/JSON para operadores.
- **Seam:** ponto público onde callers e testes observam comportamento sem
  conhecer a implementação.
- **Adapter:** `docops.pipeline`/`PipelineOptions` continuam compatíveis para
  callers 1.0, mas não são o seam de novos testes.
- **Adapters externos:** filesystem, processo MCP, DNS/rede, Git/HTTP e
  interpretador RAG; devem ser controlados como fronteiras externas quando um
  teste realmente precisar de falha.
- **Depth/leverage/locality:** a implementação interna pode continuar
  composta, mas a mudança deve reduzir o conhecimento exigido dos callers e
  concentrar a correção em um módulo.

## 4. Requisitos normativos dos tickets atuais

### SPEC-23 — identidade do candidato e evidência remota

O candidato publicável deve ser identificável por um commit/branch remoto
alcançável, uma versão, uma lista exata de arquivos e um digest determinístico.
O manifest deve distinguir explicitamente `working-tree-candidate` de um
commit verificável.

Aceite mínimo:

- verificar rejeita candidato sem commit/branch verificável quando o modo é
  release;
- candidate audit, wheel, SBOM, checksums, bundle e CI registram o mesmo SHA e
  digest de arquivo;
- uma alteração depois da auditoria torna a identidade inválida;
- existe evidência de CI para aquele SHA, não apenas para `HEAD` anterior;
- a rotina continua sem executar qualquer publicação automática.

### SPEC-24 — conformidade dos testes com o seam público

Novos testes de comportamento devem importar `docops` ou executar a CLI/JSON,
wheel, Git/HTTP fixture ou processo MCP real. Testes de compatibilidade do
adapter legado podem existir, mas devem ser poucos, nomeados como
compatibilidade e não servir de cobertura principal da engine.

Aceite mínimo:

- lifecycle, reliability, contracts e cenários de usuário têm caracterização
  equivalente pela raiz/CLI;
- nenhum novo teste importa helper privado ou verifica call count/ordem
  interna;
- os quatro testes existentes de raiz são ampliados apenas onde há um
  comportamento público não coberto;
- a suíte continua verde com e sem o extra RAG;
- a especificação de `docs/PYTHON-API.md` e a suíte não se contradizem.

### SPEC-25 — recuperação após interrupção da promoção

Depois de uma interrupção do processo em qualquer transição de atualização,
uma nova operação pública deve preservar ou restaurar a última geração válida,
ou retornar um diagnóstico estruturado que permita recuperação sem apagar o
ativo. `inspect()` deve descrever a situação sem expor corpus ou tokens.

Aceite mínimo:

- teste observável usa subprocessos/filesystem temporários e apenas
  `plan`/`apply`/`inspect`/`cleanup`;
- reiniciar depois de cada classe de falha não produz ativo silenciosamente
  perdido;
- staging retomável e backup recuperável têm estados e ownership redigidos;
- cleanup nunca remove o ativo nem staging válido e documenta o que preserva;
- a garantia é descrita por capacidade do filesystem, sem chamar toda troca de
  diretório de universalmente atômica.

### SPEC-26 — resolução, CVEs e provenance da supply chain

Cada perfil distribuído deve ter evidência da resolução efetiva por Python/SO,
com hashes ou mecanismo equivalente de integridade. O vendor deve apontar para
uma versão/ref upstream imutável e seu digest. A evidência deve ser
transportável e ter uma raiz de confiança explícita.

Aceite mínimo:

- o lock/policy define transitivas, markers por plataforma e hashes dos
  artefatos consumidos, ou documenta uma alternativa verificável equivalente;
- `pip-audit` cru e o wrapper são reportados separadamente;
- os quatro CVEs do Chroma são listados por ID e escopo, nunca apresentados
  como “zero vulnerabilidades”;
- a decisão de aceitar, mitigar, atualizar ou retirar o perfil RAG é registrada
  por um mantenedor antes da release;
- provenance, vendor, modelos e SBOM podem ser verificados fora de um caminho
  local ignorado; assinatura/attestation, quando disponível, é anexada sem
  ser simulada.

### SPEC-27 — suporte executado por perfil e bootstrap limpo

Cada claim de suporte deve apontar para um job que executa o perfil relevante,
não apenas para uma string na matriz. O fluxo de clean clone deve ser
autocontido ou falhar com instrução de bootstrap inequívoca.

Aceite mínimo:

- core, formats, bootstrap, wheel, RAG/MCP e filesystem têm perfis distintos;
- a verificação cruza claims, job, runner, versão Python e gate efetivamente
  executado;
- Python 3.11–3.13 continua supported e 3.14 continua apenas tolerated, salvo
  decisão documentada;
- skips de symlink/RAG registram a condição e nunca viram sucesso silencioso;
- o runbook reproduz clean clone e wheel em um ambiente novo sem depender de
  pacotes acidentalmente instalados no launcher.

### SPEC-28 — GitHub, distribuição e comunidade

O repositório público deve ter identidade coerente, metadata consumível e
arquivos de comunidade em locais reconhecidos. A release deve oferecer assets
verificáveis e manter autorização humana para publicar.

Aceite mínimo:

- descrição, homepage, topics, versão, changelog e documentação apontam para
  a mesma linha de release;
- Code of Conduct, contribuição, issue/PR templates, governança, manteners e
  suporte estão em locais que o GitHub reconhece ou são explicitamente
  referenciados;
- wheel, checksums e SBOM aparecem como assets da release, sem corpus/índice/
  token/model cache;
- os jobs públicos de pacote e integração retêm, vinculada a `${GITHUB_SHA}`,
  a evidência auditada do candidate e somente os resultados RAG redigidos;
- CODEOWNERS, branch protection, revisão obrigatória, secret scanning,
  push-protection e Dependabot são verificados por um mantenedor autenticado;
- nenhuma ferramenta local faz a mutação dessas settings como parte do gate.

### SPEC-29 — métricas e evidência operacional

As métricas do pacote devem distinguir contagens calculadas pelo operador das
contagens retornadas pelo backend. O gate de concorrência deve ter carga mínima
repetível e observar readers/writer sem transformar detalhes internos em
contrato.

Aceite mínimo:

- `corpus_documents`, `operator_chunks` e `backend_total_chunks` têm nomes e
  semântica documentados, ou são uma única contagem comprovadamente equivalente;
- uma fixture conhecida verifica a relação esperada entre essas contagens;
- o teste de reindex concorrente executa carga suficiente e registra buscas,
  erros, estado final e resíduos;
- qualquer warning de telemetria/depreciação fica separado de falha funcional;
- o relatório não inclui conteúdo, caminhos privados ou tokens.

## 5. Ordem de dependência

| Ordem | Ticket | Motivo | Depende de |
|---:|---|---|---|
| 1 | 23 — identidade candidate/CI | Sem um SHA único, todos os outros resultados podem ser de conteúdo diferente | nenhum; decisão humana de release continua necessária |
| 2 | 24 — seams públicos | Define a superfície de regressão que os tickets seguintes devem preservar | 23 para registrar o candidate final; caracterização pode começar localmente |
| 3 | 25 — promoção pós-crash | Fecha a maior lacuna de preservação de dados | 24 |
| 4 | 26 — locks/provenance/CVEs | Decide se o perfil RAG pode ser distribuído de forma defensável | 23; decisão explícita sobre os CVEs |
| 5 | 27 — suporte/bootstrap | Faz os claims dependerem de execução reproduzível | 23, 24, 26 |
| 6 | 28 — GitHub/community/assets | Publica identidade, assets e expectativas somente após gates técnicos | 23, 26, 27 |
| 7 | 29 — métricas/stress | Fecha a evidência operacional e pode usar todos os seams estabilizados | 24, 25, 27 |

Todos os tickets 23–29 têm implementação local nesta execução. A tabela segue
como a ordem normativa; a evidência de cada tracer está nos tickets e em
`tasks/todo.md`.

### 6. Decisões de compatibilidade e segurança

- `docops` raiz é o seam normativo; `docops.pipeline` permanece como adapter de
  compatibilidade 1.0 durante a transição.
- `plan()` não escreve no destino; `apply()` opera com staging/lease e retorna
  resultado versionado; `inspect()`/`cleanup()` são as superfícies de lifecycle.
- CLI, JSON, schemas, exit codes e outcomes são contratos; detalhes privados
  não são contrato.
- RAG continua opcional no core e explícito no perfil MCP. Ausência opcional,
  ausência requerida e drift de versão são outcomes distintos.
- Chroma HTTP, `trust_remote_code`, repositórios remotos de modelo e exposição
  de dados locais continuam fora da política aprovada.
- auditoria de release bloqueia arquivos proibidos por path antes de depender
  de decodificação textual; revisão de licença/conteúdo continua humana.
- nenhum relatório, diagnóstico, SBOM ou bundle deve ecoar token, corpus,
  índice privado, log ou caminho de usuário.
- a versão, tag, wheel, manifest, checksums e CI devem concordar antes de
  qualquer autorização humana de publicação.

### 7. Critérios globais de pronto

Uma implementação dos tickets só poderá ser considerada pronta quando:

1. houver um candidate commit público e um digest único reproduzível;
2. todos os gates aplicáveis passarem nesse mesmo candidate, com falhas
   ambientais e skips explicitamente classificados;
3. o core passar sem RAG e o perfil RAG passar com MCP real no ambiente
   anunciado;
4. o `pip-audit` cru e o allowlist forem reportados honestamente, e a decisão
   dos quatro CVEs estiver registrada;
5. os testes de comportamento novos atravessarem apenas seams públicos;
6. a recuperação pós-crash e a preservação de dados tiverem evidência
   observável;
7. suporte, community files, metadata e assets forem verificáveis no GitHub;
8. nenhum corpus adquirido, índice, cache, modelo, token ou log privado entrar
   no conjunto candidato;
9. a revisão humana autorizar a publicação — o agente implementador não deve
   publicar por conta própria.

## Testing Decisions

### 8. Seams e decisões TDD

Seams aprovados para os testes dos tickets:

1. CLI + JSON + pacote observável;
2. raiz Python instalada (`import docops`);
3. repositório Git candidato e auditor de release;
4. wheel instalado fora do checkout;
5. filesystem temporário, HTTP/Git fixture e subprocesso MCP real;
6. adapter memory em ciclos rápidos e MCP real em integração;
7. processos reader/writer observando apenas pacote ativo, `inspect()` e
   outcomes.

Não são seams: helpers `_...`, call counts, ordem de colaboradores, classes
internas, imports de módulos privados para novos testes ou a forma física do
staging que não aparece em `inspect()`.

Cada ticket deve seguir um tracer bullet vertical: um red observável, o menor
green que o corrige, o gate proporcional, e só depois review/refactor. Mockar
somente fronteiras externas — rede/DNS, processo MCP, relógio, filesystem ou
metadata de distribuição — e preferir fixtures reais.

O plano executável detalhado está em `docs/POST-1.0-TDD-PLAN.md`.

## Out of Scope

- publicar, commitar, fazer push, criar tag/release ou publicar em registry;
- adicionar LLM, provedor, chat, API key, multi-tenancy ou UI;
- expor ChromaDB/MCP na rede;
- publicar corpus de terceiros, índices, caches, modelos, tokens ou logs;
- prometer atomicidade universal onde o filesystem não a oferece;
- substituir todo `knowledge-rag`/ChromaDB nesta iniciativa;
- transformar cobertura percentual ou testes de helpers em objetivo de
  qualidade;
- reescrever `operations.py` por estética sem um comportamento público que
  exija a mudança.

## Further Notes

### Histórico preservado

O diagnóstico que originou os tickets 01–12 e a execução 13–22 permanece no
histórico local de `tasks/todo.md` e nos tickets existentes. Alguns textos
antigos descrevem o red que já foi resolvido; eles não devem ser tratados como
falhas atuais sem reexecução. A auditoria de 2026-09-01 também foi preservada
como registro histórico. O relatório vigente é
`docs/GITHUB-PUBLICATION-AUDIT-2026-09-02.md`.

### Referências operacionais

- `docs/RELEASE.md` — ordem atual dos gates e limites do candidato;
- `docs/PUBLISHING-POLICY.md` — política de corpus, índices e artifacts;
- `docs/DEPENDENCIES.md` — pins, residual Chroma e perfis;
- `docs/PYTHON-API.md` — interface raiz e compatibilidade;
- `docs/SUPPORT-MATRIX.json` — claims e gates declarados;
- `SECURITY.md` — threat model, SSRF, MCP e divulgação privada;
- `.scratch/post-1-0-reliability/issues/README.md` — índice dos tickets
  implementáveis.
