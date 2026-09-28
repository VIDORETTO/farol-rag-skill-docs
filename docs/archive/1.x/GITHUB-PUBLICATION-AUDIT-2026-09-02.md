# Auditoria crítica de publicação no GitHub — estado real

**Data de referência:** 2026-09-02 (execuções locais concluídas em
03-09-2026 por causa do fuso/virada do host)

**Escopo:** avaliar o repositório `agent-knowledge-kit` como produto open
source, comparando a release pública, `HEAD`/`origin/main` e o working tree
candidate 1.1.0. A auditoria inclui código, testes, documentação, workflows,
empacotamento, segurança, dependências, GitHub e a integração RAG/MCP local.

**Restrição:** esta auditoria não implementou código e não executou commit,
push, tag, publicação ou release. Os arquivos de documentação produzidos nesta
etapa são mudanças locais e ainda não constituem a release.

## Adendo de implementação local — 2026-09-04

Os tickets 23–29 foram implementados e revalidados no working tree depois da
auditoria histórica abaixo. O candidato agora tem identidade e re-medição da
fonte, recovery pós-crash, seams públicos verificáveis, resolução de
dependências limitada ao fechamento do lock, evidência crua de `pip-audit`,
bootstrap isolado, assets locais de comunidade, métricas nomeadas e stress
concorrente fail-closed. Consultas, paths locais e diagnósticos de backend são
redigidos nas superfícies públicas. Snapshots externos de modelo são registrados
por manifest/digest e seus bytes não são distribuídos.

A suíte completa final passou com `227 passed, 2 skipped in 431.95s`. Os
dois skips são limitações explícitas de criação de symlink neste Windows. A
falha intermitente de reader/writer foi localizada no uso de `os.kill(pid, 0)`
como probe Windows e corrigida com consulta Win32 sem envio de sinal.
Depois da correção de perfil da supply chain, o clean clone final passou com
`227 passed, 2 skipped in 184.77s` em seu próprio venv core+formats+dev.

Este adendo não transforma o working tree em release. A revalidação anônima
do GitHub em 2026-09-04 encontrou `main` em
`0c766d2d7144a8861efe132fbc4c62498a0cfeb6`, branch sem proteção pública,
descrição/homepage/topics vazios, community health 71%, `v1.0.0` sem assets e
nenhum CI do digest/SHA deste candidato. Settings de segurança protegidos não
podem ser provados anonimamente. A decisão humana sobre os quatro CVEs do
`chromadb==1.5.9` continua pendente. Portanto, o veredito de publicação segue
**fail-closed**. O commit que contém este adendo foi autorizado para push em
`origin/main`; tag, GitHub Release, publicação e mutação de settings não foram
autorizados.

As notas e lacunas descritas abaixo pertencem ao snapshot de auditoria de
2026-09-02. Para o estado implementado, prevalecem este adendo, os tickets
23–29 e a evidência final registrada em `tasks/todo.md`.

## Como ler o relatório

- **Fato** é algo observado em arquivo, saída de comando ou API pública do
  GitHub.
- **Inferência** é a avaliação técnica derivada dos fatos; não é uma garantia
  do produto.
- **Recomendação** é trabalho futuro. Recomendações viraram os tickets 23–29;
  eles não foram implementados nesta etapa.

As notas são julgamentos de prontidão de 0 a 10, não resultados automáticos de
um único gate. A escala usada é: 0–3 bloqueado, 4–5 frágil, 6–7 utilizável com
risco explícito, 8–9 profissional com ressalvas, 10 evidência excepcional.

## Estado de identidade: a distinção que governa todo o veredito

| Objeto | Evidência | Estado observado |
|---|---|---|
| Release/tag pública | `v1.0.0`, tag apontando para `e8083ade7f9533cb220b3cf3288ed3b54a6e79c9` | Publicada; 0 assets; não é o candidato 1.1.0 |
| `HEAD` local e `origin/main` | `855038019abbbe37d027728ac1bf034f4af210fb` | Iguais entre si; a branch local não está à frente do remoto |
| Working tree | `pyproject.toml:5-24`, `docops/__init__.py`, módulos novos, docs e testes modificados/não rastreados | Candidato 1.1.0 local, substancialmente diferente de `HEAD` |
| GitHub público | API REST do repositório, release e health | `main` ainda representa o estado 1.0.0; descrição/homepage/topics nulos; health 57; settings protegidos não verificáveis sem autenticação |

**Fato:** o candidato 1.1.0 não é ainda um commit, branch remoto, tag,
release ou asset público. **Inferência:** não existe hoje um conjunto único
publicável e publicamente verificado que corresponda ao working tree. Esse é o
blocker de publicação mais importante.

## Scorecard

| Setor | Nota | Fatos e evidências concretas | Inferência, risco e recomendação |
|---|---:|---|---|
| Produto, propósito e README | **7,3** | `README.md:3-18` explica o operador, o core sem LLM/provedor e RAG opcional; `README.md:101-113` identifica honestamente o candidato como não publicado. `pyproject.toml:6-18` tem metadados e URLs coerentes. | O produto **Farol** tem identidade pública, e a distribuição técnica `consulta-documentacao` permanece como compatibilidade da release 1.1.0. Ainda não há instalação normal de um registry nem badges. A página pública ainda é 1.0. **Recomendação histórica:** alinhar identidade, instalação e metadata pública (ticket 28). |
| Arquitetura, interface e compatibilidade | **7,2** | `docs/PYTHON-API.md:3-31` define `import docops`, request/options, plan/apply/inspect e aliases 1.0. `docops/pipeline.py:14-55` é um adapter fino; busca estática não encontrou import de `pipeline` em `operations.py`. | O acoplamento bidirecional alegado em auditorias antigas não foi confirmado no código de produção atual. Porém, `docops/operations.py` tem 2.062 linhas e ainda carrega compatibilidade `PipelineOptions`; a cobertura de teste atravessa módulos internos. **Recomendação:** preservar o seam raiz e reduzir conhecimento dos callers (ticket 24). |
| Confiabilidade, lifecycle e dados | **6,5** | `tests/test_post_lifecycle.py`/`test_post_reliability.py` e o gate público deram 27 passes. `operations.py:1500-1528` faz backup e retry da promoção; `operations.py:1921-1942` espera um leitor estável por janela limitada; `operations.py:2025-2033` preserva backups recuperáveis. | A promoção é recuperável no fluxo normal e em falhas injetadas, mas não há prova de reinício depois do ponto `active → backup` antes de `stage → active`: `inspect()` pode apenas relatar ausência e backup. Isso é risco real de durabilidade, não falha observada em toda execução. **Recomendação:** recuperação pós-crash no ticket 25. |
| Testes, TDD e seams públicos | **6,0** | `pytest -q`: 171 passed, 2 skipped. Ruff e compilação passam. `tests/test_public_interface.py:6-89` tem quatro testes de raiz. Em contraste, `tests/test_post_lifecycle.py:16-21` e `tests/test_post_reliability.py:10-12` importam `rag_sync`, `storage`, `lease`, `package_validator` e `pipeline`; outros testes fazem o mesmo. Não há gate de cobertura configurado em `pyproject.toml:35-45`. | O comportamento importante passa, mas a suíte viola a regra declarada de testar somente interfaces públicas e pode quebrar com refactors sem mudança observável. Os skips de symlink são honestos, mas reduzem a prova local. **Recomendação:** migrar caracterizações para a raiz, mantendo poucos testes de compatibilidade explícita (ticket 24). |
| RAG/MCP e integrações reais | **7,5** | Sem RAG: `tests/test_mcp_smoke.py` = 5 passed. Smoke real: handshake, `tools/list` com 13 ferramentas e busca com `knowledge-rag` 4.8.5. Tracer real `run --index-rag → validate → evaluate --adapter mcp` passou com 2 casos, Recall@5=1,0 e MRR@5=1,0. Segurança do vendor: 142 passed, 7 skipped, 5 xfailed. | A integração existe e é fail-closed para ausência/drift. O stress de 20s fez somente 1 busca, portanto não prova carga significativa. O pacote registra `chunks=2`, enquanto o servidor reporta `total_chunks=4`; isso pode ser contagem local versus contagem do backend, mas o contrato semântico não o explica. **Recomendação:** clarificar métricas e obter evidência de concorrência mais forte (ticket 29). |
| Segurança, privacidade e SSRF | **8,0** | O gate focado de web/Git/config/RAG/release = 33 passed. Fixture Git adversarial com paths proibidos aninhados, binário e canário `bearer_token` retornou 6 findings sem ecoar o canário. `.gitignore:1-31` exclui ambientes, caches, dados, documentos adquiridos, artifacts e rede privada. `SECURITY.md:34-60` documenta SSRF, Git HTTPS, MCP stdio e Chroma local. | Os bypasses antigos de path/encoding foram corrigidos no estado atual. A proteção é por política de path e heurísticas de segredo, não um detector universal de corpus privado benignamente nomeado; licença e revisão humana continuam necessárias. A afirmação de que secret scanning/push protection/Dependabot estão habilitados (`SECURITY.md:12-14`) não pôde ser confirmada pela API pública sem autenticação. **Recomendação:** anexar evidência humana e manter revisão de conteúdo/licença. |
| Dependências e supply chain | **5,0** | Em ambiente limpo Python 3.12, `pip-audit --requirement requirements.lock --strict` resolveu 128 dependências e saiu 1 com 1 pacote vulnerável e 4 advisories, todos `chromadb==1.5.9`: `CVE-2026-45829`, `CVE-2026-45830`, `CVE-2026-45831`, `CVE-2026-45833` (também GHSA correspondentes). `pip check` passa. `requirements.lock:1-4` e `docs/DEPENDENCIES.md:10-15` admitem lock direto, sem transitivas/hashes. | O wrapper passa somente por allowlist exata e ameaça local `PersistentClient`; o `pip-audit` cru não está verde. A proveniência vendorizada (`skills/vendor/knowledge-rag/PROVENANCE.json:4-10`) não fixa commit/tag imutável e aponta para `artifacts/supply-chain`, um caminho de evidência local/ignorado. **Recomendação:** decidir formalmente o residual Chroma e tornar resolução/proveniência verificáveis (ticket 26). |
| Empacotamento e reprodutibilidade | **6,0** | `verify_wheel.py` passou no core e, com o ambiente RAG correto, passou com `adapter=mcp`, `rag=true`, versão 1.1.0. `audit_release.py --candidate` passou com 382 arquivos; os contratos passaram com 9 schemas. `scripts/prepare_candidate.py` gera digest, SBOM, checksums e bundle. | O wheel é funcional, mas o bundle é apenas local e o verificador valida consistência interna; não recompõe o digest de uma origem independente nem tem assinatura configurada (`attestation: not-configured`). O lock e o vendor não dão reprodutibilidade completa. **Recomendação:** candidate identity/CI e supply-chain são pré-requisitos antes de chamar o bundle de release (tickets 23 e 26). |
| CI, release e GitHub readiness | **4,0** | Workflows locais alterados (`.github/workflows/ci.yml:11-107`) declaram quick 3×3, clean clone 3 plataformas, wheel e integração; actions usam SHAs completos e `contents: read`. Porém essas alterações não estão em `origin/main`; o GitHub público reportou release v1.0.0, 0 assets, description/homepage/topics nulos e health 57. Endpoints de protection/security retornaram 401 sem autenticação. | Há um bom desenho de gates no working tree, mas zero evidência pública de que o candidato passou esses gates. Publicar hoje confundiria 1.0 pública com 1.1 local. **Recomendação:** um commit candidato imutável, CI no mesmo SHA, revisão humana de settings e asset de release (ticket 23; metadata/community no 28). |
| Documentação e experiência do operador | **6,5** | `docs/RELEASE.md:3-35` fornece ordem executável; `docs/USE.md`, `docs/ARCHITECTURE.md`, `docs/SCHEMAS.md`, `SECURITY.md` e `docs/PYTHON-API.md` cobrem operação, contratos e riscos. | A documentação anterior à auditoria misturava resultados históricos com o estado atual e assumia dependências instaladas para `verify_clean_clone.py`. Este relatório, a especificação e o plano TDD atualizados corrigem a narrativa local, mas ainda não estão públicos. **Recomendação:** manter histórico explicitamente rotulado e documentar bootstrap por perfil (tickets 27 e 28). |
| Portabilidade | **6,0** | `scripts/check_support_matrix.py --json` passou; `docs/SUPPORT-MATRIX.json:3-38` declara Python 3.11–3.13, Ubuntu/Windows/macOS, 3.14 tolerado e perfis separados. Clean clone recém-criado em Python 3.12 passou com 171/2. O host local não fornece macOS; os dois skips são symlink. | A matriz é principalmente um checker textual de markers; prova local forte existe para Windows e Python 3.12/3.14, mas não para macOS nem RAG em todas as plataformas. A claim “cross-platform” é mais ampla que a evidência local disponível. **Recomendação:** amarrar cada claim a job/artefato executado e tornar o bootstrap autocontido (ticket 27). |
| Manutenibilidade e qualidade | **6,0** | `ruff check`, `ruff format --check`, `compileall` e `git diff --check` passaram; 75 arquivos já estavam formatados. A arquitetura de produção atual é unidirecional entre operations e o adapter legado. | O módulo central de operations tem 2.062 linhas; vendor, scripts de auditoria e várias políticas estão concentrados no mesmo candidato. Isso não é um bug isolado, mas aumenta custo de revisão e risco de mudanças divergentes. **Recomendação:** refatorar somente depois de contratos públicos verdes; não transformar ticket de qualidade em reescrita especulativa. |
| Comunidade open source | **4,5** | Existem localmente `.github/CODEOWNERS`, templates e `community/{CODE_OF_CONDUCT,GOVERNANCE,MAINTAINERS,SUPPORT}.md`, além de `docs/REPOSITORY-METADATA.json`. | A API pública de community health ainda mostra 57, sem CoC/template reconhecido, porque esses arquivos não estão no estado público; não há descrição, homepage, topics, discussions ou assets. O local `community/` pode não ser descoberto automaticamente por todas as superfícies do GitHub. **Recomendação:** publicar metadata e arquivos em locais reconhecidos, com revisão humana de ownership (ticket 28). |

### Notas agregadas

- **Nota geral:** **6,2/10** — o core e vários fluxos reais são utilizáveis, mas a
  prova de publicação, a cadeia de dependências e a durabilidade pós-crash ainda
  têm lacunas materiais.
- **Publicar hoje:** **3,0/10** — a release pública é 1.0.0 e o candidato 1.1.0
  só existe no working tree; não há CI público para o conjunto candidato nem
  decisão final sobre os quatro CVEs.
- **Produção estável:** **5,3/10** — a operação normal está bem exercitada, mas
  o residual Chroma, a resolução transitiva não fixada, a recuperação depois de
  crash e a disciplina de seams impedem afirmar estabilidade profissional ampla.

## Revalidações especiais solicitadas

### Smoke sem `knowledge-rag`

**Fato:** `python -m pytest -q tests/test_mcp_smoke.py` passou com **5 passed** no
interpretador raiz sem `knowledge-rag`. A suspeita histórica de falha foi
corrigida no working tree. O gate RAG explícito no mesmo interpretador falhou
com mensagem clara de runtime ausente quando `DOCOPS_REQUIRE_WHEEL_RAG=1` foi
definido; isso é o comportamento fail-closed esperado, não fallback silencioso.

### `pip-audit` limpo e CVEs do ChromaDB

**Fatos independentes:**

1. O wrapper `scripts/audit_dependencies.py --requirements requirements.lock
   --local --strict` retornou `ok=true` porque permite exatamente os quatro IDs
   sob a política local.
2. O `pip-audit` cru no ambiente RAG saiu com código 1 e reportou somente
   `chromadb==1.5.9`, quatro vulnerabilidades.
3. Um venv limpo Python 3.12, contendo apenas o instalador do audit e a
   resolução de `requirements.lock`, reproduziu 128 dependências, 1 pacote e 4
   vulnerabilidades.

**Inferência:** o projeto não está “sem vulnerabilidades”; está explicitamente
operando uma exceção arquitetural. Isso só é aceitável para um escopo local
com revisão humana, não como claim genérico de supply chain limpa.

### HEAD, working tree e release pública

**Fato:** `HEAD == origin/main == 8550380...`; `v1.0.0` continua no commit
`e8083ad...`; `pyproject.toml` local é 1.1.0, enquanto `git show
origin/main:pyproject.toml` é 1.0.0. `git ls-tree origin/main` não contém os
arquivos novos de candidate, community, support matrix e interface raiz.

**Conclusão:** resultados locais do candidato não podem ser apresentados como
resultados da release pública. O primeiro ticket deve fechar essa identidade.

### `operations.py` e `pipeline.py`

**Fatos:** `pipeline.py` tem 55 linhas e delega para `operations`; não foi
encontrado import de `pipeline` em `operations.py`. A engine é grande, mas o
acoplamento bidirecional alegado no diagnóstico antigo não está presente na
implementação atual.

**Risco remanescente:** muitos testes importam ambos os lados internos e a
compatibilidade `PipelineOptions` ainda faz parte do caminho. Isso é risco de
manutenibilidade/testabilidade, não evidência de ciclo de import em produção.

### Claims de multiplataforma

**Fato:** a matriz e os workflows declaram Python 3.11–3.13 em três runners;
`check_support_matrix.py` passa. **Fato:** a revalidação local comprovou
Windows com Python 3.12 e 3.14; não houve host macOS e a integração RAG real
local foi Windows. **Inferência:** “suportado” significa CI declarado para o
core, não prova manual de todos os perfis RAG/filesystem em cada plataforma.

### Corpus, índices, tokens e dados privados

**Fatos:** `.gitignore`, `docs/PUBLISHING-POLICY.md:16-31`, `SECURITY.md:23-28`
e `audit_release.py --candidate` formam uma defesa em camadas. O teste
adversarial adicionou paths proibidos aninhados e conteúdo binário/estruturado;
o auditor bloqueou o conjunto e não ecoou o canário.

**Limitação:** nenhuma heurística garante detectar todo corpus privado com nome
ou conteúdo não reconhecível. Licença, origem, autorização e revisão do
conjunto candidato continuam responsabilidade humana. `documents/fixtures/`
e partes do vendor são exceções deliberadas e precisam de provenance/licença.

## Gates executados

Todos os comandos abaixo foram executados com o prefixo `rtk` exigido por
`RTK.md`; os nomes mostram o comando do projeto. Os resultados são do working
tree no momento da auditoria.

| Gate | Resultado | Evidência/observação |
|---|---|---|
| `python -m pytest -q` | **PASS** | 171 passed, 2 skipped em 278,81s; skips de criação de symlink no host. O interpretador raiz era Python 3.14.2, tolerado, não supported. |
| Clean clone Python 3.12 | **PASS** | venv recém-criado, instalação `.[dev,formats]`, doctor + release audit + 171 passed/2 skipped em 63,06s. |
| Ruff lint | **PASS** | `All checks passed!` |
| Ruff format | **PASS** | 75 files already formatted. |
| `compileall` / `git diff --check` | **PASS** | Sem erros. |
| Contratos | **PASS** | `scripts/check_contracts.py --json`: 9 artefatos, zero findings. |
| Support matrix | **PASS** | `scripts/check_support_matrix.py --json`: Python 3.11–3.13 supported, 3.14 tolerated, runners e gates coerentes. |
| Release audit tracked | **PASS** | 329 arquivos rastreados, zero findings. |
| Release audit candidate | **PASS** | 383 arquivos tracked + não ignorados, zero findings. |
| Candidate bundle final | **PASS local** | `prepare_candidate.py` + `verify_candidate.py`: versão 1.1.0, `source_commit=855038019abbbe37d027728ac1bf034f4af210fb`, digest SHA-256 de 64 caracteres, `source_state=working-tree-candidate`; attestation `not-configured`. Isso prova consistência local, não uma release pública. |
| Release audit full no working tree | **FAIL esperado** | Encontrou venvs, caches, `data`, `models_cache`, `.scratch` e artifacts locais. A policy manda usar `--candidate`/`--tracked-only` no checkout sujo; o clean clone passou em modo full. |
| Dependência wrapper | **PASS de política** | `audit_dependencies.py --local --strict` = `ok=true`, com residual explicitamente allowlisted. |
| `pip-audit` cru/limpo | **FAIL de segurança residual** | Código 1; 128 dependências resolvidas, `chromadb` e 4 CVEs. Não há outros pacotes vulneráveis no snapshot. |
| `pip check` | **PASS** | Ambiente RAG consistente. |
| Smoke sem RAG | **PASS** | 5 testes. |
| Smoke MCP real | **PASS** | handshake 2024-11-05, knowledge-rag 4.8.5, 13 tools, busca real. |
| Fluxo RAG real | **PASS** | `run --index-rag`, `validate`, `evaluate --adapter mcp`; 2 casos, MRR/Recall 1,0, backend 4.8.5. |
| Reindex concorrente | **PASS limitado** | 20s, zero erros, índice consistente; somente 1 busca foi observada, evidência fraca de carga. |
| Wheel core | **PASS** | `verify_wheel.py`: 1.1.0, adapter memory, rag=false. |
| Wheel RAG | **PASS no ambiente correto** | `DOCOPS_REQUIRE_WHEEL_RAG=1` no venv RAG: adapter mcp, rag=true. No interpretador sem RAG, falhou corretamente por runtime ausente. |
| Vendor security | **PASS com ressalvas** | 142 passed, 7 skipped, 5 xfailed, 1 warning de telemetria/depreciação. |
| Web/Git/config/release focados | **PASS** | 33 testes. |
| GitHub público (somente leitura) | **OBSERVADO, não gate local** | `Invoke-RestMethod` nos endpoints públicos de repositório/release/community retornou `main`/release v1.0.0, health 57, 0 assets e metadata incompleta; endpoints de protection/security sem autenticação retornaram 401. |

## Falhas de ambiente versus riscos de reprodutibilidade

| Observação | Classificação correta |
|---|---|
| Rodar `verify_clean_clone.py` em Python 3.12 antes de instalar pytest | Falha de ambiente; o script depende do perfil instalado. Também é risco de UX/reprodutibilidade, pois o comando isolado não faz bootstrap sozinho. Depois de instalar `.[dev,formats]`, passou. |
| Python local 3.14 | Ambiente fora do suporte principal; a matriz o tolera. Não prova 3.11–3.13. |
| Dois testes de symlink pulados | Limitação de capacidade do host, explicitamente observada pelo teste; o CI precisa continuar sendo a prova dessas variantes. |
| RAG requerido no interpretador sem `knowledge-rag` | Falha de capacidade solicitada e fail-closed esperado; não é defeito do smoke sem RAG. |
| Full release audit no checkout sujo | Uso inadequado do modo full; candidate/tracked e clean clone são os gates corretos. Revela resíduos locais, não vazamento para o conjunto candidate. |
| MacOS não disponível localmente e RAG não executado localmente em todas as plataformas | Lacuna de evidência e risco de claim; não permite converter a declaração de CI em validação manual universal. |

## Blockers ordenados

### P0 — impede chamar o estado atual de release pública

1. **Identidade candidate/remoto não fechada (ticket 23).** O 1.1.0 está só no
   working tree; `main`, tag e release públicas são 1.0.0; não há CI remoto do
   mesmo digest. Sem um commit/branch candidato e execução de CI naquele SHA,
   não há artefato auditável por terceiros.
2. **`pip-audit` cru reproduz quatro CVEs Chroma (ticket 26).** O allowlist é
   defensável para o threat model local, mas qualquer release profissional deve
   registrar uma decisão explícita de aceite, mitigação/upgrade ou redução de
   escopo. O gate não pode ser descrito como “zero vulnerabilidades”.

### P1 — impede afirmar estabilidade ampla sem ressalvas

3. **Recuperação pós-crash da promoção não provada (ticket 25).** A janela de
   rename pode deixar apenas backup até outro processo recuperar; a garantia
   pública atual espera um writer, mas não define reparação após reinício.
4. **Testes relevantes atravessam internals (ticket 24).** A especificação TDD
   diz seam público, enquanto a maior parte do lifecycle/reliability importa
   modules/helpers internos.
5. **Supply chain não é reprodutível/independentemente ancorada (ticket 26).**
   Lock direto sem hashes/transitivas, provenance sem ref imutável e attestation
   não configurada.
6. **Claims de suporte não estão ligados a evidência executada do candidato
   (ticket 27).** O checker confirma markers; não substitui CI no SHA candidato
   nem prova RAG/filesystem para todas as plataformas.
7. **GitHub/community metadata ainda não existe publicamente (ticket 28).**
   Health 57, 0 assets, metadata pública incompleta e arquivos locais não
   reconhecidos no perfil atual.

### P2 — qualidade profissional e operação futura

8. Stress concorrente fraco, sem carga mínima definida, e sem política de
   coverage.
9. Sem instalação/distribuição normal documentada em registry; o operador
   depende de bootstrap local e perfis.
10. A árvore vendorizada inclui instaladores/scripts upstream que merecem
    decisão explícita de poda, provenance e superfície de distribuição, mesmo
    não sendo executados pelo caminho DOCOPS principal.
11. Semântica de `chunks` local versus `server_stats.total_chunks` precisa ser
    documentada para evitar métricas enganadoras.

## Próximo passo exato do modelo implementador

Começar imediatamente pelo **ticket 23 — identidade do candidato e evidência CI
remota**. Em paralelo, o mantenedor deve decidir o tratamento dos quatro CVEs
do ticket 26; essa decisão é um gate obrigatório antes de uma release, mas não
impede o red local de identidade. O primeiro ciclo deve ser red: uma verificação que falhe quando o
candidate digest não corresponde a um commit/CI único; green mínimo: manifest,
source state e job que provem o mesmo SHA sem publicar nada. Depois seguir as
dependências 24 → 25 → 26 → 27 → 28 → 29, sempre com um teste por seam público,
sem tocar nos tickets implementados 13–22 salvo caracterização de
compatibilidade.

Os detalhes normativos estão em `docs/POST-1.0-IMPROVEMENT-SPEC.md`, os ciclos
em `docs/POST-1.0-TDD-PLAN.md` e os tickets executáveis em
`.scratch/post-1-0-reliability/issues/`.

## Revalidação Goal Mode — 2026-09-03

Esta seção atualiza o estado executável sem apagar o relatório histórico acima.
Os tickets 23–29 foram implementados no working tree e revalidados por seams
públicos, CLI/JSON, subprocessos reais, candidate bundle e MCP local.

### Evidência local observada

- identidade do candidate: digest e lista determinística de arquivos, vínculo
  com commit/CI, re-medição por `--source-root` e modo release fail-closed;
- seams públicos: `tests/test_public_seams.py`, `tests/SEAMS.md` e checker
  estático sem imports privados nos novos testes;
- promoção: failpoints reais em subprocesso entre os renames e após a troca,
  recuperação por journal, `inspect()` classificável e cleanup conservador;
- supply chain: resolução transitiva do interpretador, SBOM/checksums, vendor
  com ref/commit/licença/digest e auditoria crua separada da allowlist;
- suporte: claims correlacionados com jobs/gates, preflight/bootstrap de clone
  explícitos e skips de capacidade visíveis;
- comunidade: metadata/assets/arquivos reconhecidos localmente e checklist de
  settings autenticadas sem qualquer mutação GitHub;
- observabilidade: métricas nomeadas e stress RAG real com quatro readers,
  10 segundos, mínimo de 40 buscas, estado final e resíduos.

### Revalidação final dos gates — 2026-09-04

- O clean clone final criou um venv próprio com core+formats+dev, passou
  preflight/doctor, auditoria de release e a suíte completa: `227 passed, 2
  skipped in 184.77s`; os skips são exclusivamente a capacidade de criar
  symlink no host Windows.
- O working tree passou Ruff, format, compileall, contratos, public-seams,
  matriz de suporte, `pip check`, auditoria de release tracked/candidate e
  verificação independente do supply chain; os wheels core e RAG passaram. O
  candidate local `artifacts/candidate-goal-final7` foi verificado; o
  `candidate-identity.json` do bundle é a fonte do digest calculado e do
  `source_commit=0c766d2d7144a8861efe132fbc4c62498a0cfeb6`. O digest não é
  duplicado nesta auditoria para não criar uma referência circular na
  identidade do candidato.
- A workflow `package` agora retém esse diretório já auditado como artifact
  `candidate-1.1.0-${GITHUB_SHA}`, incluindo arquivos ocultos, com erro se a
  evidência não existir; isso preserva a prova do CI sem publicar a release.
- O MCP real respondeu handshake, `tools/list` com 13 ferramentas e busca
  híbrida. O Golden FastAPI passou com Recall@5 `1.0` / MRR@5 `0.9048`; o
  fixture MCP passou com `1.0` / `1.0`; o stress obteve 202 buscas em 10s,
  quatro readers, sem erros/warnings e sem resíduos finais.
- O `pip-audit` cru continua vermelho: a auditoria JSON preserva exatamente os
  quatro advisories do `chromadb==1.5.9`; a invocação direta por requirements no
  Python 3.14 também terminou com falha de resolução de `python-docx`. O wrapper
  strict passa somente pela allowlist exata e continua reportando esse residual;
  isso permanece um bloqueio humano, não uma auditoria limpa.
- A evidência de supply chain agora vincula explicitamente o perfil `core` ou
  `rag` ao fechamento observado. No core, somente `knowledge-rag` pode estar
  ausente; versões divergentes e qualquer outra ausência reprovam. O perfil RAG
  exige todas as raízes, enquanto `--require-model` controla separadamente a
  presença do snapshot externo.

### Limites que permanecem deliberadamente abertos

1. O `pip-audit` cru continua vermelho enquanto `chromadb==1.5.9` reportar
   `CVE-2026-45829`, `CVE-2026-45830`, `CVE-2026-45831` e `CVE-2026-45833`.
   O wrapper strict passa somente pela allowlist exata e pelo threat model
   local; isso não é um audit limpo. A decisão de aceitar, mitigar, atualizar
   ou remover está pendente em `docs/CHROMA-RESIDUAL-DECISION.md`.
2. O commit que contém este registro foi autorizado para push em `origin/main`;
   seu SHA deve ser conferido no próprio histórico Git. CI do mesmo SHA,
   branch protection, reviewers, Dependabot, secret scanning, push protection
   e assets públicos ainda devem ser confirmados por mantenedor autenticado
   conforme `community/GITHUB-SETTINGS-CHECKLIST.md`. Tag, GitHub Release e
   publicação não foram autorizados.

Portanto, o resultado local é implementado e auditável, mas o candidato não é
apresentado como release-ready até esses gates externos serem concluídos.
