# Roadmap de produto e prontidão para GitHub

> Status: release 1.0.0 publicada e verificável no GitHub
> Data da auditoria: 2026-08-29
> Método: `to-spec` → `to-tickets` → `tdd` → `implement` → `verify`
> Referência das skills: `VIDORETTO/mattpocock-skills-filtered`, commit
> `efdb6f8cb1f715755c1a0743edf26e8dbdf6acf1`

## 1. Veredito executivo

O produto está publicado como versão 1.0.0: o protocolo, as aquisições, os
artefatos, o validador, o RAG opcional, a segurança e o bootstrap foram
implementados, testados e publicados sem depender de uma IA neste repositório.
O commit estabilizado, a tag, a release e o primeiro workflow público estão
registrados na checklist operacional `tasks/todo.md`.

O objetivo foi atingido em dois níveis diferentes:

| Objetivo | Estado | Evidência |
|---|---|---|
| Demonstrar que skill estruturada + RAG híbrido + roteador funciona | **Concluído** | Fixture local indexada pelo MCP real; smoke, skill, router e validador passaram; piloto FastAPI mantém Recall@5 1,0 |
| Fazer o agente do harness executar todo o fluxo após receber apenas nome/URL | **Concluído no protocolo** | `docops resolve/run` aceita nome, URL, repositório ou pasta e produz pacote sem copiar/colar; a execução do modelo continua no harness externo |
| Lidar com qualquer documentação web com maleabilidade | **Concluído com limites explícitos** | Sitemap/robots, fallback limitado, canonicalização, SSRF, redirects, retries, formatos especiais e falhas JS/OCR/autenticação são tratados de forma segura |
| Ser instalável e utilizável a partir de um clone público | **Concluído para 1.0.0** | README, licença, lock, bootstrap, testes, auditorias, empacotamento e o resultado do CI público estão no repositório |

Portanto, o resultado deve ser apresentado como **release técnica pública
1.0.0**, com FastAPI como piloto de qualidade e com fontes de terceiros,
índices e artefatos derivados mantidos fora da publicação até a revisão de
licença.

## 2. Evidências da auditoria

### 2.1 O que já está sólido

- A arquitetura central está correta: skill para modelos mentais, RAG para fatos
  literais e roteador para decidir entre as duas camadas.
- O piloto FastAPI percorreu as Fases 0–5 e tem Golden Set medido.
- O servidor MCP inicializa, lista 13 ferramentas e responde busca híbrida.
- O sincronizador incremental mantém hashes e checkpoints por documento.
- Há regras explícitas para citação, divergência skill/RAG e proteção do corpus.
- `knowledge-rag` está fixado como dependência opcional `==4.8.5`; o vendor
  limpo não contém Git aninhado e permanece separado dos corpora/runtime.
- A execução real da fixture passou por `docops run --index-rag` e por
  `scripts/test_reindex_concurrency.py`.

### 2.2 Limitações após a publicação

1. A conformidade comprovada nesta release cobre OpenCode e Codex CLI; Claude
   Code não está instalado neste host e não é um alvo anunciado.
2. Um corpus de terceiros só pode acompanhar uma release depois da revisão de
   licença; o padrão continua a produzir artefatos privados e a ignorar
   `documents/`, índices, caches e estado.
3. O fold-in rico por `book-to-skill` continua sendo uma etapa executada pelo
   harness externo; o pipeline fornece o scaffold estrutural validável e um
   handoff explícito, sem embutir uma IA no produto.

## 3. Problem Statement

Desenvolvedores querem abrir seu harness de agentes preferido — OpenCode,
Codex ou outro compatível — informar apenas um identificador de
documentação e receber um pacote de conhecimento pronto para apoiar a
implementação no projeto em que já estão trabalhando. O modelo é escolhido e
fornecido pelo próprio usuário através do harness. Este repositório não integra,
hospeda nem chama uma IA.

O repositório agora oferece um protocolo único, reproduzível e verificável para
esse ciclo. O agente externo ainda decide quando pedir uma confirmação material,
mas pode resolver a fonte, escolher escopo/versão, adquirir e normalizar o
conteúdo, gerar os artefatos, indexar o RAG e avaliar o pacote por meio de
`docops` e das skills fornecidas.

## 4. Solution

Construir e distribuir um **cérebro portátil para agentes**: skills, protocolo
operacional, ferramentas auxiliares, servidor RAG e validadores. O usuário
instala ou referencia esse pacote no harness que já utiliza. O modelo carregado
pelo harness lê `doc-to-rag-operator` e executa o fluxo usando shell, filesystem,
web e MCP conforme as capacidades disponíveis.

O repositório não fornece chat, runtime de agente, SDK de provedor, seleção de
modelo ou credenciais de IA. Sua responsabilidade termina em ensinar e dar
ferramentas para o agente externo produzir e consultar conhecimento com
qualidade.

### 4.1 Fronteira de execução

```text
usuário escolhe harness + modelo
              ↓
harness carrega doc-to-rag-operator + ferramentas + knowledge-rag MCP
              ↓
modelo do usuário segue o protocolo e gera o pacote de conhecimento
              ↓
agente no projeto consulta skill + RAG por meio do roteador
```

- **Harness externo:** executa o modelo, oferece ferramentas e gerencia a
  conversa.
- **Modelo do usuário:** interpreta a skill e toma decisões dentro das regras.
- **Este repositório:** fornece o cérebro, o fluxo, os artefatos, os comandos de
  apoio e os critérios de validação.
- **Projeto do usuário:** recebe o benefício; não precisa incorporar este
  repositório como aplicação ou biblioteca de IA.

### 4.2 Contrato de entrada no harness

Entrada mínima:

```text
documentação: <nome | URL | URL de repositório | caminho local>
```

Opções que o agente do harness pode inferir ou fornecer:

- slug;
- versão/tag/branch;
- idioma;
- escopo ou subdiretório;
- modo `create`, `update` ou `dry-run`;
- política de crawl e limite de páginas;
- diretório privado de artefatos.

O agente só deve interromper o fluxo quando houver ambiguidade material entre
fontes oficiais, credenciais necessárias, conflito de versão ou dúvida de
licença que possa mudar a ação permitida.

### 4.3 Contrato de saída do fluxo

Cada execução produz um manifesto/relatório versionado legível pelo agente e,
quando útil, por máquina, além de um resumo na conversa do harness contendo:

- fonte resolvida, versão, idioma, data e método de descoberta;
- licença/proveniência encontrada e decisão de redistribuição;
- manifesto de URLs/arquivos aceitos, ignorados e com erro;
- localização e validação da skill gerada;
- localização e validação do roteador gerado;
- quantidade de fontes e chunks no RAG, sem duplicação lógica;
- resultado do smoke test e métricas do Golden Set;
- avisos, decisões inferidas e ações que realmente exigem intervenção humana.

O sucesso só é reportado pelo agente quando os três produtos estão utilizáveis
em conjunto: **skill + índice RAG + roteador**.

## 5. User Stories

1. Como desenvolvedor, quero informar `FastAPI` e receber uma proposta de fonte
   oficial e versão antes da ingestão quando houver mais de uma opção plausível.
2. Como desenvolvedor, quero informar uma URL de documentação e ter o site
   percorrido dentro de limites seguros, sem listar cada página manualmente.
3. Como desenvolvedor, quero informar um repositório e ter a pasta de docs,
   tag e arquivos suportados identificados automaticamente.
4. Como desenvolvedor, quero apontar uma pasta local e obter o pacote completo
   sem acesso à internet.
5. Como usuário recorrente, quero executar a mesma entrada duas vezes sem criar
   documentos ou chunks duplicados.
6. Como mantenedor, quero atualizar uma documentação e processar apenas as
   mudanças, preservando a habilidade existente por fold-in.
7. Como agente implementador, quero consultar conceitos pela skill e detalhes
   atuais pelo RAG com citação, sem precisar conhecer a arquitetura interna.
8. Como usuário, quero saber exatamente quais fontes e versões sustentam uma
   resposta.
9. Como responsável por segurança, quero que URLs privadas, redirecionamentos,
   conteúdo hostil e credenciais sejam tratados por políticas explícitas.
10. Como autor de documentação, quero que licença e proveniência sejam
    registradas e que o corpus não seja publicado por acidente.
11. Como usuário de Windows, Linux ou macOS, quero instalar e rodar o fluxo com
    os mesmos resultados essenciais.
12. Como contribuidor, quero executar testes rápidos sem baixar o corpus
    FastAPI nem modelos pesados.
13. Como mantenedor, quero testes de integração opcionais que validem o MCP e
    o modelo de embedding real do RAG antes de uma release.
14. Como usuário, quero que falhas parciais possam ser retomadas sem refazer
    downloads ou perder estado confirmado.
15. Como agente, quero receber erros estruturados e próximos passos objetivos,
    em vez de depender de texto de terminal truncado.
16. Como mantenedor, quero substituir `book-to-skill` ou `knowledge-rag` sem
    reescrever descoberta, aquisição e política de execução.
17. Como usuário de OpenCode, Codex ou outro harness compatível,
    quero carregar o mesmo cérebro sem depender de um modelo ou provedor
    específico.
18. Como usuário, quero que minhas chaves, prompts e chamadas de modelo
    permaneçam sob controle do harness escolhido, sem passarem por este sistema.

## 6. Implementation Decisions

### 6.1 Protocolo do operador e contrato de artefatos

O seam de produto é comportamental e baseado em artefatos:

```text
prompt no harness + doc-to-rag-operator
    → pacote de conhecimento validado
      (skill + RAG + roteador + manifesto/relatório)
```

A skill operadora é a interface pública. Os scripts e ferramentas são
primitivas que o agente combina; eles não formam um runtime próprio e não
chamam um modelo. Um validador determinístico inspeciona o pacote final e torna
os critérios de conclusão verificáveis sem integrar IA ao sistema.

### 6.2 Capacidades oferecidas ao agente

- **Source resolver:** diferencia nome, URL de página, site de docs, repositório
  e caminho local.
- **Web acquisition:** sitemap primeiro; navegação interna limitada como
  fallback; canonicalização, deduplicação e manifesto de crawl.
- **Repository acquisition:** clone raso da versão selecionada e detecção de
  árvores comuns de documentação.
- **Document normalizer:** preserva títulos, headings, exemplos e origem;
  converte apenas quando necessário.
- **Skill generator:** encapsula `book-to-skill`, captura metadados completos e
  valida o resultado sem etapa de copiar/colar.
- **RAG tooling:** oferece chamadas MCP e sincronização idempotente ao agente.
- **Router generator:** gera de um template versionado e valida referências à
  skill e ao corpus reais.
- **Evaluator:** executa smoke e Golden Set, produzindo métricas no relatório.

As ferramentas externas podem ser substituídas sem mudar o protocolo e o
contrato de artefatos. A decisão de quando e como chamá-las continua com o
modelo executado pelo harness.

### 6.3 Maleabilidade para documentação web

O operador não promete que todo site será processado da mesma forma. Ele deve
classificar e escolher estratégia:

1. Markdown/repositório oficial;
2. sitemap XML com HTML estático;
3. site estático sem sitemap;
4. site renderizado por JavaScript;
5. OpenAPI/Swagger;
6. PDF com texto ou PDF que exige OCR;
7. documentação autenticada;
8. documentação multilíngue e/ou multiversão.

Cada estratégia precisa declarar capacidade, limites e fallback. “Qualquer
documentação web” significa seleção adaptativa e falha explicável, não crawl
ilimitado ou garantia de contornar autenticação e bloqueios.

### 6.4 Configuração por corpus

Configuração de infraestrutura e ajustes de relevância devem ser separados.
Aliases FastAPI, perfil de embedding, reranker e Golden Set pertencem ao pacote
do corpus, não ao padrão global. Troca de perfil de embedding deve forçar rebuild
completo e ficar registrada no manifesto/relatório da execução.

### 6.5 Estado, idempotência e retomada

O estado deve ser derivado de identidade canônica da fonte, versão e hash de
conteúdo. Uma execução repetida não cria novas identidades lógicas. Cada fase
grava checkpoint atômico; retomada continua da última saída validada.

### 6.6 Distribuição

- Escolher e publicar uma licença para o código deste projeto.
- Consumir dependências por versão/commit fixado; não manter repositório Git
  aninhado sem submódulo declarado.
- Manter corpora, índices, caches e skills potencialmente derivadas fora do
  repositório público.
- Versionar templates, fixtures sintéticas, esquemas e documentação necessária
  para que um clone limpo funcione.
- Oferecer bootstrap equivalente em Windows, Linux e macOS.
- Documentar instalação da skill e do MCP nos harnesses suportados sem incluir
  SDK, API key ou dependência de um provedor de modelos.

## 7. Testing Decisions

### 7.1 Seam de TDD proposto para confirmação

O seam testável é o contrato do pacote de conhecimento. Dada uma fixture e os
artefatos produzidos pelo fluxo, o validador confirma skill, RAG, roteador,
manifesto, proveniência, estado e métricas. Testes determinísticos não iniciam
nem mockam um modelo.

O comportamento instrucional da skill é verificado com cenários de conformidade
executados em harnesses externos selecionados. Esses cenários observam apenas a
entrada dada ao agente, as decisões registradas e o pacote final.

### 7.2 Estratégia

- Cada ticket começa com um teste falhando no contrato de artefatos ou na
  ferramenta determinística que está sendo adicionada.
- Implementar o menor tracer bullet que faça esse teste passar.
- Refatorar somente depois do verde.
- Mockar apenas fronteiras externas: rede pública, subprocessos das ferramentas
  de terceiros e relógio quando necessário.
- Preferir servidor HTTP local e repositórios-fixture reais a mocks de detalhes
  internos do crawler.
- Separar testes rápidos, integração MCP e cenários de conformidade em harnesses.
- Toda correção de bug adiciona primeiro uma reprodução no contrato observável.
- Não exigir um modelo em CI; validar instruções estaticamente e executar uma
  pequena matriz de harnesses antes de releases.

### 7.3 Matriz mínima de aceitação

| Cenário | Resultado obrigatório |
|---|---|
| Pasta Markdown local | skill + RAG + roteador + relatório válidos |
| Uma URL HTML | fonte baixada uma vez, origem preservada e consultável |
| Site com sitemap | páginas internas corretas, limites e deduplicação aplicados |
| Repositório com docs | versão e subdiretório registrados |
| Nome conhecido | fonte oficial resolvida ou ambiguidade reportada |
| Segunda execução idêntica | zero duplicatas e zero trabalho desnecessário |
| Atualização de uma página | fold-in e reindex incremental coerentes |
| URL hostil/privada | bloqueio seguro e erro estruturado |
| Clone limpo em três sistemas | bootstrap e fixture local passam |

## 8. Out of Scope

- Redistribuir documentação de terceiros sem permissão.
- Burlar autenticação, paywall, robots ou controles do site.
- Garantir OCR perfeito ou renderização de todo framework JavaScript existente.
- Hospedar um serviço RAG público multiusuário na primeira release.
- Integrar ou hospedar LLM, escolher provedor/modelo, armazenar API keys, criar
  chat próprio ou substituir os harnesses externos usados pelo usuário.
- Garantir que todos os modelos sigam instruções com comportamento idêntico; o
  sistema fornece protocolo, validação e recuperação de falhas.
- Gerar implementação do framework para o desenvolvedor; o produto prepara e
  consulta conhecimento para o agente que fará essa implementação.
- Otimizar relevância para todo domínio sem um Golden Set representativo.

## 9. Fases e gates

### Fase 0 — Confirmar contrato e política de publicação

**Gate:** fronteira harness/cérebro, contrato de artefatos, licença do projeto e
definição de “fonte oficial” aprovados.

- [x] Confirmar que o produto não integra IA e que a skill operadora é a
  interface pública executada pelo harness do usuário.
- [x] Confirmar o pacote de conhecimento e seu validador como seam de TDD.
- [x] Definir licença do código e política para artefatos derivados.
- [x] Definir comportamento de ambiguidade para entradas por nome.
- [x] Decidir dependências: pacote fixado, submódulo ou vendor limpo.
- [x] Definir suporte inicial: Python e versões de Windows/Linux/macOS.

### Fase 1 — Tornar o repositório clonável

**Gate:** pessoa nova consegue instalar, executar `doctor` e rodar testes rápidos
em clone limpo.

- [x] Inicializar Git e revisar exatamente o que será versionado (sem commit,
  conforme autorização).
- [x] Criar README, LICENSE, CONTRIBUTING e SECURITY na raiz.
- [x] Documentar instalação/configuração em OpenCode e Codex, além do caminho
  genérico para qualquer harness compatível com Agent Skills + MCP; Claude Code
  não é anunciado sem uma sessão verificável.
- [x] Criar manifesto e lock de dependências reproduzíveis.
- [x] Remover caminhos absolutos e detectar ambiente virtual de modo portátil.
- [x] Preservar templates e fixtures necessários apesar das regras de ignore.
- [x] Resolver o repositório `knowledge-rag` aninhado.
- [x] Substituir ou marcar claramente o workflow placeholder.

### Fase 2 — Tracer bullet local completo

**Gate:** um agente em harness externo segue a skill sobre uma pasta fixture e
produz os três artefatos sem intervenção manual após o prompt inicial.

- [x] Definir manifesto/relatório estruturado, checkpoints e validador do pacote.
- [x] Integrar pasta local → scaffold de skill com handoff para `book-to-skill` →
  skill validada.
- [x] Integrar os mesmos documentos → RAG idempotente.
- [x] Gerar roteador a partir de template versionado.
- [x] Executar smoke e retornar relatório único.
- [x] Remover do usuário as instruções de copiar/colar do caminho feliz; o
  próprio agente pode invocar skills e ferramentas auxiliares.

### Fase 3 — URL e site web

**Gate:** fixtures de página única e site com sitemap passam de ponta a ponta.

- [x] Adicionar aquisição de página HTML com origem e canonical preservados.
- [x] Adicionar sitemap, limites, include/exclude, deduplicação e retries.
- [x] Aplicar políticas de SSRF, redirects, tamanho, timeout e tipo de conteúdo.
- [x] Produzir manifesto completo, inclusive erros parciais.
- [x] Adicionar fallback controlado para site sem sitemap.

### Fase 4 — Repositório, nome e formatos especiais

**Gate:** pelo menos um exemplo de cada estratégia suportada passa pelo seam
público e capacidades não suportadas falham de forma explicável.

- [x] Resolver URL de repositório, versão e diretório de documentação.
- [x] Resolver nome para candidatos oficiais com evidência e confiança.
- [x] Tratar documentação multiversão e multilíngue.
- [x] Integrar OpenAPI e PDF textual.
- [x] Detectar necessidade de OCR, autenticação ou browser renderizado e emitir
  fallback/ação necessária sem fingir sucesso.

### Fase 5 — Atualização, qualidade e recuperação

**Gate:** criar, repetir, atualizar e retomar produzem estado coerente e métricas
aceitáveis.

- [x] Garantir identidade canônica e ausência de chunks/fontes duplicados.
- [x] Implementar fold-in/reindex incremental coordenados; o enriquecimento
  semântico continua no `book-to-skill` do harness externo.
- [x] Gerar perguntas Golden candidatas e exigir revisão antes de usá-las como
  critério de qualidade.
- [x] Definir limites mínimos de Recall@5/MRR@5 por corpus.
- [x] Testar interrupção e retomada em cada fase mutável.
- [x] Registrar divergência entre skill e documentação indexada.

### Fase 6 — Segurança, CI e release pública

**Gate:** release candidate passa em clone limpo e não publica dados derivados.

- [x] Executar suíte rápida em toda mudança e integrações em agenda/release.
- [x] Executar matriz Windows, Ubuntu e macOS.
- [x] Adicionar varredura de segredos, dependências e artefatos proibidos.
- [x] Verificar que transporte de rede exige autenticação.
- [x] Criar tutorial reproduzível com fixture licenciada/sintética.
- [x] Validar instalação fora da máquina do autor; o resultado detalhado da
  matriz e a limitação de macOS estão em `docs/HARNESSES.md` e
  `docs/DEPENDENCIES.md`.

## 10. Tickets verticais

Os tickets abaixo seguem `to-tickets`: cada um entrega comportamento observável
de ponta a ponta e explicita bloqueios. Eles permanecem neste documento até a
Fase 0 confirmar o contrato de artefatos e a granularidade; depois podem virar
issues independentes.

### DOCOPS-001 — Clone limpo até diagnóstico funcional

**Bloqueado por:** Fase 0.

**Status: concluído.** `docops doctor`, bootstrap portátil, metadados,
dependências fixadas, config relativa e auditoria de release foram validados em
clone temporário.

- Teste vermelho: em ambiente temporário limpo, instalar e executar `doctor`.
- Implementar metadados do projeto, dependências fixadas, config relativa e
  descoberta portátil de executáveis.
- Aceite: Windows/Linux/macOS informam capacidades, incluindo integração MCP e
  localização das skills para o harness, sem usar caminhos da máquina do autor.

### DOCOPS-002 — Pasta local até pacote consultável

**Bloqueado por:** DOCOPS-001.

**Status: concluído.** `docops run` produz skill estrutural, RAG, router,
`harness.json` e manifesto; o validador rejeita pacotes incompletos.

- Teste vermelho: o validador rejeita pacote incompleto da fixture Markdown.
- Implementar o menor caminho completo por skill, RAG e roteador.
- Aceite: em um harness de referência, o agente gera pacote válido após um único
  prompt; uma consulta conceitual e uma factual usam as camadas corretas.

### DOCOPS-003 — Uma página web até pacote consultável

**Bloqueado por:** DOCOPS-002.

**Status: concluído.** Aquisição HTTP local/testável preserva origem e
canonical, normaliza HTML e devolve erros estruturados.

- Teste vermelho: URL em servidor HTTP local aparece no manifesto e no RAG.
- Implementar aquisição, normalização, proveniência e erro estruturado.
- Aceite: conteúdo e origem são consultáveis; repetição não duplica a fonte.

### DOCOPS-004 — Site com sitemap até pacote consultável

**Bloqueado por:** DOCOPS-003.

**Status: concluído.** Sitemap/robots, limites, filtros, retries,
canonicalização e fallback de links internos estão implementados e testados.

- Teste vermelho: sitemap fixture ingere somente URLs permitidas.
- Implementar crawl limitado, canonicalização, filtros, retries e manifesto.
- Aceite: loops, duplicatas, assets e links externos não inflam o corpus.

### DOCOPS-005 — Repositório de documentação até pacote consultável

**Bloqueado por:** DOCOPS-002.

**Status: concluído.** Clone raso, tag/branch, escopo, idioma, árvore de docs,
commit e licença são registrados pelo adquirente de repositório.

- Teste vermelho: repositório fixture resolve tag e árvore de docs.
- Implementar clone raso, detecção de docs e registro do commit.
- Aceite: atualização de commit altera somente fontes afetadas.

### DOCOPS-006 — Nome de tecnologia até fonte oficial resolvida

**Bloqueado por:** DOCOPS-003 e DOCOPS-005.

**Status: concluído.** O catálogo oficial e catálogos JSON do usuário retornam
candidatos, confiança, evidência e decisão explícita em caso de empate.

- Teste vermelho: catálogo fixture retorna candidato, confiança e evidência.
- Implementar descoberta por nome com ranking e política de ambiguidade.
- Aceite: confiança alta continua; empate material pede decisão; fonte não
  oficial nunca é tratada silenciosamente como oficial.

### DOCOPS-007 — Execução idempotente e retomável

**Bloqueado por:** DOCOPS-002.

**Status: concluído.** Estado por identidade canônica/hash, checkpoints atômicos,
reconciliação add/update/remove e escrita idempotente estão cobertos por testes.

- Testes vermelhos: segunda execução não duplica; falha intermediária retoma.
- Implementar identidade canônica, checkpoints atômicos e reconciliação.
- Aceite: contagens lógicas correspondem ao manifesto após create/update/remove.

### DOCOPS-008 — Avaliação de utilidade para o agente implementador

**Bloqueado por:** DOCOPS-004, DOCOPS-005 e DOCOPS-007.

**Status: concluído.** Há geração de candidatos Golden, exigência de revisão,
Recall@5/MRR@5 configuráveis, smoke e detector de divergência skill/RAG.

- Teste vermelho: pacote responde conjunto misto conceitual/factual com origem.
- Implementar geração assistida e revisão de Golden, métricas e diagnóstico de
  divergência.
- Aceite: thresholds são por corpus e configuração medida fica no relatório.

### DOCOPS-009 — Limites de segurança e licença

**Bloqueado por:** DOCOPS-003.

**Status: concluído.** SSRF, credenciais, redirects, limites de payload,
conteúdo não confiável, licença e auditoria de configuração/release falham
fechado quando necessário.

- Testes vermelhos: localhost/metadata, redirect malicioso, payload excessivo,
  prompt injection e licença ausente seguem a política definida.
- Implementar guardas nas fronteiras externas e trilha de proveniência.
- Aceite: o pipeline falha fechado quando a ação pode expor rede, segredo ou
  conteúdo não autorizado.

### DOCOPS-010 — Release candidate pública

**Bloqueado por:** DOCOPS-001 a DOCOPS-009.

**Status: concluído como release pública 1.0.0.** CI, empacotamento, tutorial,
changelog, auditorias, validação em clone limpo, smoke test do wheel, tag,
release e sessões externas verificadas estão registrados em `tasks/todo.md`.

- Teste vermelho: instalação em três runners e validação do tutorial fixture.
- Implementar CI, empacotamento, documentação, changelog e checklist de release.
- Aceite: clone público não depende de cache, corpus ou estado da máquina do
  autor; as sessões de conformidade comprovadas passam em OpenCode e Codex sem
  o repositório integrar ou escolher o modelo. Claude Code permanece fora do
  suporte anunciado desta versão.

## 11. Protocolo `tdd` → `implement` por ticket

Para cada DOCOPS:

1. abrir contexto somente com este documento e o ticket;
2. escrever um teste falhando no contrato de artefatos ou na ferramenta de apoio;
3. verificar que a falha acontece pelo motivo esperado;
4. implementar o menor tracer bullet;
5. executar teste alvo, suíte rápida e checagem de tipos/lint;
6. refatorar com tudo verde;
7. fazer revisão final contra os critérios de aceite;
8. registrar no manifesto/relatório ou changelog qualquer decisão nova;
9. só então marcar o ticket concluído e desbloquear dependentes.

Não usar testes de implementação interna como substituto dos testes do contrato.
Não adicionar um LLM fake como se este repositório fosse um runtime de agentes.
Dependências externas podem ser substituídas por fakes nas fronteiras, mas ao
menos uma suíte de integração deve exercitar as ferramentas reais e cenários de
conformidade devem ser executados nos harnesses antes da release.

## 12. Definition of Done do objetivo primário

O objetivo “dar apenas link ou nome da documentação ao agente no harness para
ele fazer todo o processo e trabalhar melhor no projeto atual” estará concluído
quando:

- [x] OpenCode, Codex ou outro harness compatível consegue carregar
  a skill operadora e conectar o MCP;
- [x] uma invocação com nome, URL, repo ou pasta segue o mesmo protocolo;
- [x] o agente resolve ou pede somente decisões realmente ambíguas;
- [x] skill, RAG e roteador são produzidos e validados sem copiar/colar;
- [x] toda fonte tem versão, proveniência e licença registradas;
- [x] repetir e atualizar não cria duplicação ou dessincronização;
- [x] documentação web usa estratégia adaptativa e limites seguros;
- [x] consultas conceituais e factuais passam por avaliação reproduzível;
- [x] clone limpo funciona em Windows, Linux e macOS na matriz publica do CI;
- [x] README e licença permitem que terceiros entendam instalação, limites e uso;
- [x] nenhum LLM, provedor, seletor de modelo, chat ou API key faz parte deste
  sistema; tudo isso permanece responsabilidade do harness e do usuário;
- [x] nenhum corpus, índice, cache, segredo ou artefato não autorizado entra na
  release pública.

Os itens técnicos passaram. O estado honesto, incluindo a matriz real de
harnesses, a limitação de plataforma e a publicação, está registrado em
`tasks/todo.md` e `docs/HARNESSES.md`.
