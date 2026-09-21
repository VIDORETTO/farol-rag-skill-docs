# Especificação: Farol 2.0 — conhecimento de alta fidelidade para agentes

**Esforço:** `farol-2`
**Revisão:** 1
**Estado:** aceita
**Baseline observado:** `81d5dcb2e189d00406cdd9b9e671d94e3f23cd58`
**Decisões:** `docs/adr/0001`, `0002`, `0003`

## Problema e resultado desejado

O Farol 1.x governa fontes e produz skill, router e corpus RAG, mas a skill rica
depende de uma etapa externa informal, a unidade de saída continua sendo uma
skill por slug, o parsing reduz muitos formatos a texto e o backend real é
`knowledge-rag`, não RAGFlow. Documentos de uma iniciativa de Mercado Livre,
curso, página e oferta também ampliaram o produto para fora de seu objetivo.

Farol 2.0 deve permitir que um agente receba fontes heterogêneas, proponha uma
taxonomia, produza várias skills conceituais coordenadas e mantenha um índice
factual RAGFlow com citações verificáveis. Skills e RAG devem derivar da mesma
interpretação versionada, e toda mudança deve preservar direitos, lineage,
recuperação e a última geração válida.

## Consumidores e atores

- **Usuário do projeto:** informa objetivos e fontes, aprova taxonomia inicial e
  decisões materiais.
- **Agente operador:** conduz a conversa, executa CLI/API JSON e entrega resultados
  estruturados sem escolher provedor de modelo.
- **Agente leitor:** carrega skills e consulta evidência factual pelo router.
- **Mantenedor:** instala adapters, opera RAGFlow, define budgets e publica releases.
- **RAGFlow:** backend externo reconstruível de parsing/indexação/retrieval.
- **Sintetizador conceitual:** capacidade externa do harness; `book-to-skill` é o
  primeiro adapter.

## Escopo

### Incluído

- Projeto de conhecimento com taxonomia hierárquica e múltiplas skills.
- IR canônica estruturada, versionada e comum a skill e RAG.
- Registry de extractors e níveis explícitos de fidelidade.
- Primeira fatia de alta fidelidade: Markdown/HTML, PDF textual/escaneado, DOCX,
  EPUB e repositório de código selecionado.
- Preservação honesta dos formatos 1.x enquanto não recebem gates próprios.
- Contrato retomável de síntese conceitual e adapter `book-to-skill`.
- RAGFlow como backend estratégico, com migração e rollback do backend legado.
- Router global conceitual/factual/híbrido.
- Atualização, conflito, revogação, candidata, avaliação e promoção atômica.
- Migração planejada de pacotes Farol 1.x.
- Remoção de Mercado Livre, curso, página e oferta no contrato 2.0.
- Experiência conversacional apoiada por CLI/API JSON determinísticas.

### Excluído

- Chatbot, LLM, escolha de modelo/provedor ou armazenamento de credenciais de IA.
- Administração implícita de RAGFlow em produção.
- Dois backends RAG permanentes.
- SaaS multi-tenant, billing, UI visual de pipeline ou editor visual de chunks.
- Compreensão multimodal completa de diagramas/imagens na primeira fatia.
- Promessa de volume ilimitado ou suporte de formato sem conformance suite.
- Publicação automática de material protegido.
- Migração de dados de curso, página, oferta ou preset Mercado Livre.

## Jornadas e cenários

### US-001 — Criar projeto por conversa (P1)

Como usuário, quero informar objetivo e fontes sem conhecer os comandos internos,
para receber um projeto retomável e auditável.

Demonstração independente: duas execuções retomam a mesma sessão, não repetem
respostas confirmadas e produzem o mesmo plano para as mesmas entradas.

- **AC-001** — Dado objetivo e fontes válidos, quando o agente inicia o projeto,
  então a CLI/API retorna projeto, revisão, pendências materiais e próxima ação.
- **AC-002** — Dada interrupção, quando a operação é retomada com a mesma
  identidade, então checkpoints válidos são reutilizados sem duplicar efeitos.
- **AC-003** — Dada ambiguidade irrelevante, o fluxo continua com hipótese
  reversível; direitos, privacidade, custo externo, taxonomia inicial e ativação
  conceitual exigem decisão explícita.

### US-002 — Extrair uma fonte com fidelidade declarada (P1)

Como agente operador, quero transformar cada artefato em IR estruturada, para que
todos os consumidores compartilhem conteúdo, locators e qualidade.

Demonstração independente: fixtures por formato produzem blocos e locators
esperados ou uma degradação/erro tipado, nunca sucesso vazio.

- **AC-004** — Cada extração retorna `structured-native`, `text-fallback`,
  `external-converter`, `metadata-only` ou `unsupported`, com adapter e versão.
- **AC-005** — Markdown/HTML preservam hierarquia, listas, tabelas, código e origem.
- **AC-006** — PDF textual preserva página e blocos; PDF escaneado registra OCR,
  confiança e quarentena quando o limiar não é atingido.
- **AC-007** — DOCX e EPUB preservam ordem, headings, tabelas disponíveis e origem.
- **AC-008** — Repositório inclui docs, contratos, schemas e declarativos por
  padrão; código exige escopo explícito e preserva arquivo/símbolo/linha.
- **AC-009** — Uma falha opcional permanece no staging; falha de fonte obrigatória
  ou cobertura insuficiente impede ativação.

### US-003 — Aprovar taxonomia e gerar skills temáticas (P1)

Como usuário, quero revisar a organização conceitual antes da ativação, para
evitar que a estrutura de arquivos vire a estrutura de conhecimento.

Demonstração independente: um corpus com assuntos sobrepostos gera proposta,
ownership, dependências e skills sem duplicar o conceito canônico.

- **AC-010** — A proposta de taxonomia informa cobertura, sobreposições, assuntos
  órfãos e blocos sustentadores; a primeira ativação exige aprovação.
- **AC-011** — Cada conceito possui uma skill proprietária; referências cruzadas
  não copiam a mesma síntese.
- **AC-012** — Cada `SKILL.md` respeita budget configurado com padrão aproximado
  de 4 mil tokens e direciona detalhes a capítulos sob demanda.
- **AC-013** — Afirmação factual sintetizada possui lineage para blocos elegíveis;
  fonte revogada ou conflito não declarado bloqueia a candidata.
- **AC-014** — O sintetizador usa request/receipt vinculado a IR, taxonomia,
  adapter, versão e hashes; timeout/retry não duplica publicação.

### US-004 — Consultar conceitos e fatos (P1)

Como agente leitor, quero receber orientação compacta e evidência literal, para
raciocinar sem despejar o corpus no contexto nem inventar fatos.

Demonstração independente: casos conceitual, factual, ambíguo e sem evidência
seguem rotas distintas e observáveis.

- **AC-015** — Router global seleciona skills para consulta conceitual, RAGFlow
  para factual e ambos para consulta ambígua, atual ou de alto risco.
- **AC-016** — Todo resultado factual publicado contém source/revision e locator
  verificável (`section`, `line`, `page`, `bbox`, `slide`, `cell` ou `timestamp`).
- **AC-017** — Evidência inelegível é filtrada antes do top-k; ausência retorna
  `insufficient_evidence`; divergência retorna conflito explícito.
- **AC-018** — Documentos permanecem no idioma original; skills usam o idioma do
  projeto e preservam termos canônicos e links ao original.

### US-005 — Indexar e recuperar com RAGFlow (P1)

Como operador, quero usar RAGFlow sem entregar a ele a autoridade do projeto,
para obter parsing/retrieval avançados com reconstrução e rollback.

Demonstração independente: uma candidata cria dataset isolado, indexa a revisão
correta, responde, é descartada/reconstruída e não altera a geração ativa.

- **AC-019** — `doctor` reporta endpoint, versão, autenticação, capacidades e
  saúde sem revelar segredo; Compose local é opcional e produção nunca é criada.
- **AC-020** — Lifecycle de backend é idempotente para provisionar, ingerir,
  remover, aguardar, obter stats, buscar, obter documento, snapshot e fechar.
- **AC-021** — IDs do RAGFlow ficam em mapeamento por projeto/revisão; apagar o
  índice e reconstruí-lo da IR preserva o comportamento contratado.
- **AC-022** — RAGFlow indisponível permite IR/candidata retomável, mas impede os
  estados `indexed`, `queryable` e `active` da composição completa.
- **AC-023** — HTTP remoto exige opt-in, TLS ou localhost conforme política,
  autenticação, timeout, retry limitado e logs redigidos.

### US-006 — Atualizar e revogar sem inconsistência (P1)

Como mantenedor, quero alterar fontes e conceitos sem expor uma composição
parcial, para que leitores continuem na última revisão válida.

Demonstração independente: add/update/remove/revogação e crash entre trocas
mantêm a geração anterior ou a nova por inteiro.

- **AC-024** — Mudança factual autorizada, sem conflito/direitos/impacto conceitual,
  pode ser ativada automaticamente após os gates e guarda rollback.
- **AC-025** — Mudança conceitual, taxonômica, de direitos, conflito ou revogação
  exige candidata e invalida somente derivados alcançados pelo lineage.
- **AC-026** — Promoção coordenada de IR, skills, router e snapshot RAG é atômica
  para leitores e recuperável após interrupção.

### US-007 — Migrar e simplificar o produto (P1)

Como usuário 1.x, quero uma migração inspecionável, para preservar conhecimento
válido sem importar acoplamentos abandonados.

Demonstração independente: fixture 1.x produz plano, candidata 2.0 e rollback;
campos excluídos aparecem no relatório, não no projeto novo.

- **AC-027** — Migração executa `inspect → plan → staging → validate →
  promote`, preserva 1.x e nunca converte Chroma em autoridade.
- **AC-028** — Mercado Livre, curso, página e oferta não existem nos schemas,
  runtime, CLI, distribuição, testes ou documentação normativa 2.0.
- **AC-029** — `knowledge-rag` só é removido depois de paridade, rollback e
  reconstrução RAGFlow aprovados; nenhum novo projeto 2.0 o seleciona.

### US-008 — Operar com privacidade e capacidade honestas (P1)

Como responsável por dados, quero controlar plugins, uploads e claims de escala,
para que conveniência não ultrapasse autorização ou evidência.

Demonstração independente: plugin remoto não autorizado é bloqueado, relatórios
não vazam conteúdo e o perfil declara somente benchmarks executados.

- **AC-030** — Plugin declara formatos, fidelidade, execução, permissões,
  dependências e versão; terceiro inicia desabilitado até autorização.
- **AC-031** — Original fica em armazenamento privado governado; release inclui
  somente derivados permitidos e proveniência segura.
- **AC-032** — Logs padrão não contêm query, trecho, segredo ou caminho privado;
  diagnóstico de conteúdo exige opt-in local explícito.
- **AC-033** — `plan` valida budgets de arquivo, corpus, concorrência e timeout;
  claims de escala referenciam ambiente e benchmark reproduzível.

## Requisitos

- **FR-001** — O sistema DEVE manter projeto, sessão e operações retomáveis com
  resultados JSON versionados e idempotentes.
- **FR-002** — O sistema DEVE registrar fonte, artefato, revisão, proveniência,
  direitos, vigência, idioma e finalidade antes do uso.
- **FR-003** — O sistema DEVE produzir IR canônica estruturada e imutável por
  revisão, com locators e qualidade.
- **FR-004** — O sistema DEVE negociar extractors por capacidade e declarar
  fidelidade/degradação sem fallback silencioso.
- **FR-005** — O sistema DEVE oferecer a primeira matriz de alta fidelidade
  definida nesta especificação e preservar compatibilidade honesta dos demais.
- **FR-006** — O sistema DEVE propor taxonomia hierárquica com cobertura,
  ownership e dependências antes de sintetizar skills.
- **FR-007** — O sistema DEVE tratar síntese conceitual como capacidade externa,
  observável, retomável e substituível.
- **FR-008** — O sistema DEVE gerar múltiplas skills temáticas compactas e
  lineage para toda afirmação factual.
- **FR-009** — O sistema DEVE gerar router global que separe consultas
  conceituais, factuais e híbridas.
- **FR-010** — O sistema DEVE integrar RAGFlow como backend reconstruível sem
  usar suas funções de chat/agente como autoridade.
- **FR-011** — O sistema DEVE filtrar elegibilidade antes do ranking e devolver
  citações verificáveis ou abstenção/conflito.
- **FR-012** — O sistema DEVE manter candidatas isoladas e promover composições
  coordenadas somente após validação.
- **FR-013** — O sistema DEVE atualizar e revogar incrementalmente por lineage,
  preservando readers e rollback.
- **FR-014** — O sistema DEVE permitir migração 1.x sem mutação in-place e
  remover os contratos editoriais excluídos na versão 2.0.
- **FR-015** — O sistema DEVE bloquear acesso remoto, plugin e extractor sem
  política/autorizacão compatível e redigir diagnósticos.
- **FR-016** — O sistema DEVE manter idioma original na evidência e permitir
  idioma configurado nas skills sem substituir a fonte.
- **FR-017** — O sistema DEVE avaliar retrieval, citações, skill, recuperação e
  segurança antes de remover o backend legado ou publicar 2.0.

## Limites, erros e compatibilidade

- Entradas hostis são dados não confiáveis e nunca instruções para o agente.
- Symlinks, traversal, SSRF, redirects proibidos, archives abusivos e payloads
  acima do budget falham de forma tipada.
- Um extractor remoto requer consentimento por projeto/fonte e receipt do
  provedor/finalidade; ausência de consentimento não aciona fallback remoto.
- Revisão divergente falha por compare-and-swap; retry com mesma idempotency key
  e payload repete o resultado, payload diferente é conflito.
- Escrita continua single-writer por projeto nesta entrega. Multi-host e
  multi-tenant permanecem fora do contrato.
- Formato reconhecido sem estrutura suficiente é `text-fallback`, não
  `structured-native`.
- Farol 1.x permanece legível durante a migração; Farol 2.0 não promete escrever
  contratos 1.x nem preservar derivados excluídos.

## Hipóteses e dependências

- **H-001:** a API RAGFlow v0.27.x expõe lifecycle suficiente para dataset,
  documentos, parsing, chunks e retrieval. Impacto: bloqueia adapter real.
  Verificação: contract test contra versão fixada e documentação oficial.
- **H-002:** DeepDoc/Docling conseguem exportar blocos/locators necessários sem
  usar RAGFlow como autoridade. Impacto: define adapter de extração. Verificação:
  spike limitado com fixtures PDF/DOCX.
- **H-003:** `book-to-skill` pode consumir IR renderizada sem reler originais e
  devolver lineage verificável. Impacto: pode exigir adapter/prompt complementar.
  Verificação: contrato com duas fontes sobrepostas e validação do receipt.
- **H-004:** thresholds atuais são alcançáveis no corpus de referência. Impacto:
  remoção do legado. Verificação: dual-run controlado, sem dual-write ativo.
- **Dependência:** RAGFlow `v0.27.2`, observado em 2026-09-11; fixar por digest
  antes de implementação.
- **Dependência:** harness compatível com Agent Skills e executor externo de
  síntese; ausência deixa candidata pendente, não autoriza modelo interno.

## Critérios de sucesso

### Verificáveis na entrega

- **SC-001** — Recall@5 ≥ 1,0 em casos factuais críticos revisados.
- **SC-002** — MRR@5 ≥ 0,86 no conjunto de substituição declarado.
- **SC-003** — 100% dos hits factuais publicados possuem locator verificável.
- **SC-004** — Zero afirmação factual da skill sem lineage elegível.
- **SC-005** — Add/update/delete/revogação, rebuild, crash recovery e rollback
  passam por Interfaces públicas.
- **SC-006** — Fixtures dos formatos da primeira fatia provam conteúdo, estrutura,
  locator, fidelidade e uso por skill/RAG.
- **SC-007** — Mercado Livre, curso, página, oferta, Chroma e `knowledge-rag`
  não existem no artefato final 2.0, salvo documentação explícita de migração.
- **SC-008** — Gates de segurança e release passam em core e integração RAGFlow,
  com skips e recursos externos declarados.

### Observação pós-entrega

- **SC-009** — Medir taxa de perguntas resolvidas sem fallback e sem correção
  humana por tipo de consulta.
- **SC-010** — Medir custo/tempo por formato, tamanho de corpus e perfil de
  infraestrutura antes de ampliar claims de escala.
- **SC-011** — Medir taxa de reorganizações taxonômicas e conflitos para calibrar
  a autonomia conceitual.

## Decisões e perguntas abertas

Todas as decisões materiais de produto foram confirmadas na descoberta. As
hipóteses H-001–H-004 são questões técnicas verificáveis; resultado negativo
retorna ao planejamento e não autoriza reduzir silenciosamente os requisitos.
