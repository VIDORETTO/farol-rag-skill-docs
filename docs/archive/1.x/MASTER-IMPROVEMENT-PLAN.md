# Diagnóstico e plano de melhorias do estado atual

## Escopo, evidência e ordem de execução

Este documento confronta as 12 hipóteses de [MASTER-PLANNING-BRIEF.md](MASTER-PLANNING-BRIEF.md) com o checkout analisado em 2026-09-07. Ele é o diagnóstico histórico que orientou a implementação local registrada em [IMPLEMENTATION-EVIDENCE.md](../../master-evolution/IMPLEMENTATION-EVIDENCE.md); não autoriza publicação externa, alteração do corpus/índice real ou uso de credenciais ausentes. O sistema continua sendo operado por agente em harness externo, sem chatbot ou provedor de modelo embutido.

As referências `arquivo:linha` são posições do checkout auditado, não garantias de posição depois das alterações. O inventário complementar está em [CURRENT-STATE-EVIDENCE.md](../../master-evolution/CURRENT-STATE-EVIDENCE.md). “Existe” significa código/contrato inspecionado; “testado nesta auditoria” identifica execução efetiva; métricas antigas e descrições de CI não equivalem a uma nova execução.

Fases utilizadas neste diagnóstico:

- **P0 — baseline e contratos:** registrar estado e corrigir documentação divergente; reproduzir riscos operacionais antes de classificá-los como bugs.
- **P1 — init e estado:** projeto persistente, conversa retomável, schemas e presets.
- **P2 — fontes e recuperação:** governança, metadados, ingestão, recuperação e avaliação do domínio.
- **P3 — mudanças e derivados:** propostas, impacto, enriquecimento, curso/página e releases coerentes.
- **P4 — operação:** supervisor, recuperação, saúde, backup e dependências.
- **P5 — autonomia restrita:** autorização delegada opt-in sobre gates já existentes.

Prioridades: **P0 crítica** bloqueia o uso afetado; **P1 alta** precede a capacidade dependente; **P2 média** pode ser incremental. Prioridade e fase são eixos diferentes. Uma falha de recuperação confirmada não deve aguardar todas as funcionalidades de P1–P3 para ser corrigida.

## 1. Inicialização incompleta

**Estado/classificação:** lacuna de produto confirmada; não é falha do comando `run`. A CLI constrói pacotes a partir de uma fonte, mas não implementa o `init` conversacional do brief. Evidência: `docops/__main__.py:117` define o parser, `:137` resolve fontes e `:171` registra `run`; a superfície examinada não contém comando de inicialização de projeto com brief, curso e página.

**Causa e impacto:** o domínio atual é pacote de documentação. O harness não tem contrato persistente para transformar objetivos, decisões e restrições em projeto retomável; pode repetir perguntas ou tratar suposições como decisões.

**Prioridade/dependências/fase:** P1 alta; depende dos schemas do item 2; P1. Decisão de produto: quais entregáveis são obrigatórios e quais podem permanecer ausentes. Decisão técnica: armazenamento e transições da sessão.

**Solução mínima:** implementar sessão determinística de init, conduzida pelo harness. Persistir respostas, decisões confirmadas, suposições explícitas, pendências e revisão base; retornar perguntas importantes pendentes e próximo passo. Gerar artefatos em staging, validar e finalizar revisão privada de planejamento; isso não cria aprovação, ativação nem candidata editorial automaticamente. Resolver explicitamente a ambiguidade entre ensinar a vender no Mercado Livre e vender o curso dentro do Mercado Livre. Preset não confirma essa escolha pelo usuário.

**Alternativa/trade-off:** uma skill somente textual é mais barata, mas perde validação e retomada confiáveis; formulário rígido exige intervenção excessiva. Usar skill para a conversa e núcleo para estado/invariantes evita ambos.

**Aceite verificável:** interromper e retomar mantém respostas e decisões; mesmas entradas não criam versões duplicadas; conflito de revisão bloqueia sobrescrita; brief incompleto não vira projeto ativo; preset de outro domínio funciona sem regras Mercado Livre no núcleo; curso e página podem ser explicitamente desabilitados.

## 2. Estado de projeto espalhado

**Estado/classificação:** parcialmente pronto; evolução de contratos e modelagem. Já existem schemas de manifesto, planos, candidatas, registros de fontes, snapshots e leitores em `docops/schemas/`; `docops/lifecycle.py:260` fornece a fachada de lifecycle. Não existe no conjunto examinado um contrato unificado para brief, mapa de curso, especificação de página e decisões de produto.

**Causa e impacto:** estado de pacote foi ampliado por capacidades independentes. Usar `AGENTS.md` como banco de decisões ou copiar o mesmo fato entre arquivos introduziria divergência e dependências ocultas.

**Prioridade/dependências/fase:** P1 alta; precede itens 1 e 3; P1. Produto decide campos e responsabilidades; implementação decide serialização, migração e hashes.

**Solução mínima:** identificar projeto e revisão; definir schemas para brief, decisões, curso, página e políticas; manter referências aos registros existentes, sem duplicá-los. `AGENTS.md` contém somente instruções estáveis. Cada campo factual derivado referencia fonte/revisão; cada decisão possui origem e estado. Manter schemas empacotados e espelhados da raiz sincronizados conforme o contrato atual.

**Alternativa/trade-off:** banco de serviço central facilita consultas futuras, mas acrescenta instalação, migração e operação sem necessidade demonstrada. Arquivos versionados com validação e escrita atômica atendem o host único; estado operacional volátil continua fora do conteúdo editorial.

**Aceite verificável:** v1 existente continua legível; migração é explícita e idempotente, preserva desconhecidos sem inventar consentimento; contrato inválido é recusado antes de mutação; artefatos não duplicam valores autoritativos; pacote distribuído inclui os schemas necessários sem depender do checkout.

## 3. Mudanças futuras sem produto próprio

**Estado/classificação:** parcialmente pronto, não ausência de lifecycle. `docops/operations.py:817` planeja, `:971` produz preview, `:3438` aplica; `docops/candidates.py:72` prepara candidatas; `docops/operations.py:2871`, `:2941`, `:3157` aprovam, publicam e restauram. Falta proposta tipada abrangendo decisões, tópicos, curso e página.

**Causa e impacto:** o plano existente descreve aquisição/pacote. Sem dependências dos novos artefatos, mudanças podem reprocessar tudo ou deixar derivados desatualizados, e remoções podem reaparecer em páginas ou skills.

**Prioridade/dependências/fase:** P1 alta; depende do item 2 e da identidade/política de fontes do item 7; P3.

**Solução mínima:** adicionar proposta versionada com revisão base, operações tipadas, justificativa, classificação de impacto, dependentes e plano de validação. Compilar para o motor existente. Registrar lineage de fontes/revisões para skills, aulas e seções de página. A promoção precisa representar uma composição coerente, mantendo a ativa durante falhas.

**Alternativa/trade-off:** construir novo motor transacional duplicaria recuperação, históricos e gates. Regerar tudo é simples, mas aumenta custo e invalida avaliações desnecessariamente. Dependências explícitas permitem atualização seletiva e diagnóstico.

**Aceite verificável:** mudar apenas CTA da página não reindexa corpus inalterado; atualizar uma fonte invalida seus dependentes; proposta sobre base antiga é recusada; remoção revoga derivados antes de reconstruí-los; rollback não ressuscita fonte revogada. Reutilizar proteção de `tests/test_history_rollback.py:143` e adicionar cenários de curso/página.

## 4. Autonomia contínua incompleta

**Estado/classificação:** supervisor ausente, primitivas operacionais existentes. `docops/__main__.py:300` exige `--once`; `docops/coordination.py:721` executa no máximo um job. Já há SQLite (`:70`), claim transacional (`:453`), recibos de efeito (`:677`), retries (`:772`) e bloqueio terminal (`:791`).

**Causa e impacto:** reconciliação e execução são unidades adequadas ao scheduler externo, mas não formam ainda uma experiência supervisionada de longa duração. Adicionar arquivo não garante processamento por si só.

**Prioridade/dependências/fase:** P1 alta para operação contínua; depende de contrato de mudança e confiabilidade do item 10; P4. Scheduler externo continua opção suportada.

**Solução mínima:** supervisor local opcional com polling, agenda persistida, parada recuperável, último sucesso e próxima tentativa. Chamar as mesmas seams de reconcile/event/work_once. Watcher pode reduzir latência, mas reconciliação periódica recupera eventos perdidos. Não mudar implicitamente política de publicação.

**Alternativa/trade-off:** serviço sempre ativo embutido facilita início, mas aumenta suporte; scheduler externo reduz manutenção. Oferecer adaptadores e um runner mínimo sobre o mesmo protocolo, sem dois algoritmos de worker.

**Aceite verificável:** restart não perde eventos; arquivo repetido não duplica efeitos; fonte indisponível não vira retirada; parada deixa job concluído ou retomável; relógio controlável prova agenda/backoff; worker continua produzindo candidata sem ativação. `tests/test_worker.py:22`, `:221`, `:307`, `:414` são proteções existentes.

## 5. Atualização conceitual dependente de ferramenta externa

**Estado/classificação:** integração por contrato existente, orquestração parcial. A fronteira externa é deliberada. `docops/harness.py:158` exporta request portátil; `:219` vincula candidata/base/hashes/política; `:236` restringe artefatos; `:253` registra espera. `docops/candidates.py:352` importa resultado.

**Causa e impacto:** o harness executa enriquecimento, mas dispatch, timeout e correlação operacional ainda precisam de experiência uniforme. Um scaffold estrutural não equivale a skill enriquecida; uma mensagem do modelo não comprova resultado válido.

**Prioridade/dependências/fase:** P1 alta para atualização conceitual; depende de candidata/impacto do item 3; P3.

**Solução mínima:** ampliar estados e recibos existentes com dispatch, ack, timeout, cancelamento, retry e correlação durável. Adaptador externo configurável executa `book-to-skill` ou equivalente. Preservar neutralidade de provedor/modelo; avaliar a composição devolvida antes de publicar.

**Alternativa/trade-off:** incorporar SDK de LLM torna execução conveniente, mas altera o produto e cria gestão de credenciais, custos e fornecedor. Handoff manual continua fallback legítimo, com estado visível.

**Aceite verificável:** harness indisponível retorna estado acionável; resultado atrasado ou de base antiga é recusado; duplicata não reaplica; saída só altera candidata; segredo/caminho indevido é rejeitado; ausência de evidência de enriquecimento não ganha esse rótulo. Preservar `tests/test_enrichment.py:183`, `:196`, `:231`, `:270`.

## 6. Publicação deliberadamente manual

**Estado/classificação:** gate de segurança intencional e decisão de produto pendente sobre autonomia. Worker restringe política a candidata (`docops/coordination.py:627`); aprovação vincula base/revisão/avaliação/política (`docops/operations.py:2904`); publicação exige recibo e revalida (`:2964`, `:2975`).

**Causa e impacto:** publicar conteúdo derivado pode extrapolar qualidade, direito de uso ou autorização. A intervenção é um custo operacional deliberado, não bug. Identidade do processo local e atestados estruturais (`docops/operations.py:2316`, `:2329`) não equivalem a autenticação remota criptográfica.

**Prioridade/dependências/fase:** P2 média, somente depois de P2–P4 comprovadas; P5. Autonomia é opt-in, revogável e inicialmente privada/factual. Publicação pública e mudanças comerciais/conceituais exigem decisão explícita.

**Solução mínima:** recibo de autorização delegada com escopo, fontes admitidas, prazo, orçamento, revisão de política e composição/avaliação vinculadas. Usar o mesmo publish e as mesmas recusas. Autoridade oficial não concede direito de redistribuir nem autorização de publicação.

**Alternativa/trade-off:** autopublish geral reduz intervenção, mas mistura confiança factual, direitos e autorização. Manter aprovação humana em tudo permanece alternativa válida para projetos sensíveis.

**Aceite verificável:** política expirada/revogada ou fora de escopo bloqueia; candidata alterada após autorização invalida recibo; conflito, privacidade ou licença desconhecida não atravessa a automação; execução incompleta nunca substitui ativa; revogação vale em cache e rollback. Não construir RBAC multiusuário sobre identidade local sem especificação própria.

## 7. Governança de fontes para produto comercial

**Estado/classificação:** parcialmente pronta; lacuna de modelo e políticas, não ausência de governança. `docops/schemas/source-registration.schema.json:23` já define identidade, origem, escopo, idioma e versão; `:31`–`:35` usa strings livres para direitos/privacidade/autoridade e status active/withdrawn. `docops/source_policy.py:349` bloqueia admissão com política desconhecida; `:236` exige readmissão explícita.

**Causa e impacto:** metadados livres registram intenção, mas não distinguem usos permitidos, vigência, região, regra oficial, opinião, experiência, hipótese ou recomendação. O agente pode promover experiência de influencer a regra, confundir acesso público com licença ou publicar dado privado.

**Prioridade/dependências/fase:** P1 alta; bloqueia capacidades comerciais/públicas afetadas; depende do item 2; P2. Jurídico/produto decide permissões e promessas; software aplica decisões, sem inventar aconselhamento jurídico.

**Solução mínima:** contrato versionado de fonte/claim e decisão de uso, com autor/organização, publicação/captura, idioma/região, autoridade explicada, vigência, revisão, conflitos, licença/evidência de permissão e ações permitidas separadas: adquirir, processar internamente, gerar derivado e redistribuir. Política de privacidade inclui escopo e retenção. Metadados devem chegar a RAG, recibos e derivados.

Preservar aquisição protegida (`docops/web_acquirer.py:186` valida destinos/credenciais/DNS; `:505` trata redirects). Para vídeos, MVP aceita transcrição externa em Markdown com timestamps e proveniência: `docops/normalizer.py:152`. VTT/SRT são intencionalmente recusados com `external_transcription_required` (`:445`), coberto em `tests/test_formats_portuguese.py:135`. Download/ASR nativo é evolução separada.

**Alternativa/trade-off:** blacklist de sites ou score único de confiança é fácil, mas não representa direitos nem contexto normativo. Classificação explicitamente desconhecida permite pesquisa privada governada sem inventar autorização pública.

**Aceite verificável:** licença desconhecida bloqueia redistribuição; permitido resumir não implica permitido republicar transcrição; fonte oficial vencida não sobrepõe regra vigente da região correta; opinião aparece como opinião; timestamps ausentes não são inventados. Revogação bloqueia fontes/derivados ativos, inclusive leitores em cache; retenção histórica guarda evidência segura, permitindo apagar bytes pessoais quando exigido. Reaproveitar `docops/rag_sync.py:287` e `tests/test_reader_sessions.py:313`, `:334` para ampliar lineage de curso/página/skill.

## 8. Qualidade de RAG dependente do corpus

**Estado/classificação:** risco real de adequação ao domínio, com infraestrutura parcialmente pronta. `config.yaml:62`–`:65` mantém compact voltado a inglês. Backend já oferece busca híbrida e categoria (`skills/vendor/knowledge-rag/mcp_server/server.py:4108`); seam DOCOPS aceita apenas query/max_results (`docops/retrieval.py:31`, `:380`). Preservação de locators e formato já existe (`:68`, `:421`).

**Causa e impacto:** piloto FastAPI não demonstra desempenho em perguntas do vendedor PT-BR. Contrato de consulta não expressa região, tempo, autoridade e política; documentos relevantes porém inelegíveis podem dominar resultados. Scores de similaridade não medem verdade.

**Prioridade/dependências/fase:** P1 alta; depende do item 7; P2. Seleção de modelo depende de benchmark e capacidade local, não de preferência abstrata.

**Solução mínima:** preset Mercado Livre propõe candidato multilíngue, seguido de rebuild completo e benchmark, sem mudar o padrão de todos os projetos. Estender seam de retrieval com filtros/temporalidade/política e resultados explicáveis. Filtrar elegibilidade antes da seleção ou buscar reposição limitada; descartar top K inelegível sem reposição pode ocultar fonte válida. Cache inclui projeto, geração, revisão de política, região, as-of e filtros, e revalida revogação.

A avaliação já inclui fidelidade/cobertura por recibo externo (`docops/evaluator.py:344`, `:360`, `:400`), não apenas MRR/Recall. O booleano supported vem do revisor; o núcleo não prova semanticamente a verdade. Ampliar Golden e recibos existentes com conflito, vigência, região, abstenção e recomendação sustentada. `docops/divergence.py:22` verifica deriva de versão, não contradição factual.

**Alternativa/trade-off:** trocar embedding sozinho não corrige corpus ruim ou política ausente. Reescrever vendor antecipadamente amplia manutenção. Começar na seam DOCOPS e medir necessidades antes de estender backend.

**Aceite verificável:** Golden revisado representa PT-BR/EN/misto, sinônimos, perguntas normativas, opiniões, fontes conflitantes, expiradas, removidas e ausência de evidência; casos críticos não retornam conteúdo revogado/privado/inelegível nem resposta definitiva sem suporte. Limiares de relevância derivam do baseline do domínio, não das métricas históricas FastAPI. Troca de perfil exige rebuild comprovado (`tests/test_rag_snapshots.py:81`, `tests/test_formats_portuguese.py:179`); ganho médio não compensa regressão crítica.

## 9. Deriva entre documentação e runtime

**Estado/classificação:** defeito documental confirmado. `skills/docops-agent/references/scheduler-runbooks.md:26` recomenda `work --loop --interval-seconds 60`; `references/operations.md:47` e `references/tutorial.md:76` também citam loop. Parser em `docops/__main__.py:300` expõe somente `--once`.

**Causa e impacto:** documentação distribuída com skill ficou fora da cobertura efetiva do contrato. Agente seguindo o runbook executa comando inexistente; instrução incorreta propagada no pacote é mais grave que nota histórica rotulada.

**Prioridade/dependências/fase:** P1 alta; independente de novo runner; P0.

**Solução mínima:** alinhar exemplos executáveis ao runtime atual com scheduler externo e `--once`; rotular propostas futuras. Expandir teste de deriva para referências distribuídas e artefatos empacotados. Quando loop existir, alterar parser, help, runbook e testes juntos.

**Alternativa/trade-off:** implementar loop apenas para justificar texto salta requisitos de operação; remover toda documentação reduz utilidade. Corrigir exemplos agora é menor e verificável.

**Aceite verificável:** comandos documentados de lifecycle/worker são aceitos pelo parser; exemplo inválido introduzido como fixture faz o gate falhar; exemplos futuros explicitamente rotulados não são anunciados como runtime disponível; wheel contém referências corrigidas.

## 10. Operação e escala

**Estado/classificação:** capacidade operacional parcial e dois riscos a reproduzir. Lease local existe (`docops/lease.py:50`); promoção tem journal/recuperação/backup (`docops/operations.py:1760`, `:1944`, `:2008`); observabilidade/redação existem (`docops/observability.py:25`, `:119`). Isso não equivale a serviço distribuído nem backup fora do disco.

**Causa e impacto:** proteção forte do pacote e execução local não compõem automaticamente supervisão, disaster recovery ou ownership de efeitos longos. Inspeção indica possível job eternamente running após crash na última tentativa: claim limita attempt (`docops/coordination.py:470`), incrementa (`:490`), RuntimeError sai sem concluir (`:740`). Renovação durante execução síncrona (`:734`) não foi encontrada. **Não houve reprodução desses dois riscos nesta auditoria.**

**Prioridade/dependências/fase:** P1 alta para produto contínuo; se reprodução demonstrar perda de recuperação/ownership, corrigir antes de ativar concorrência; triagem P0, entrega operacional P4. Depende do supervisor do item 4 apenas para a experiência final, não para testar primitivas.

**Solução mínima:** escrever primeiro testes de falha para último attempt e lease vencida; corrigir somente se reproduzidos. Definir renovação/fencing caso haja concorrência, saúde com lag/último sucesso/blocked, alertas acionáveis e restauração de backup consistente de pacote, histórico, políticas e SQLite. Declarar índice reconstruível e retenção. Host único permanece limite suportado.

**Alternativa/trade-off:** fila distribuída/banco remoto aumenta throughput potencial, mas exige novas garantias de transação e operação. Adiar até métricas demonstrarem gargalo; SQLite e single-writer não são bugs por si.

**Aceite verificável:** após crash no último attempt o job chega a estado recuperável/terminal explicável; worker que perdeu ownership não confirma efeito; backup restaura em pasta nova e reabre a release coerente; falha parcial não substitui ativa; alertas distinguem atraso transitório e ação requerida; testes usam relógio/falhas controláveis, não sleeps arbitrários.

## 11. Plataforma e dependências

**Estado/classificação:** risco residual governado e lacuna delimitada de verificação. `docs/SUPPORT-MATRIX.json:4` suporta Python 3.11–3.13, tolera 3.14; core cobre plataformas declaradas, wheel/RAG têm claims mais restritos. `docs/DEPENDENCIES.md` distingue evidência manual Windows e limitações POSIX/macOS. Não afirmar validação manual completa nessas plataformas.

**Correção da hipótese:** a decisão Chroma **já foi tomada** no registro: `docs/CHROMA-RESIDUAL-DECISION.md:24`–`:29`, mitigate, responsável VIDORETTO, 2026-09-04, `chromadb==1.5.9`/`knowledge-rag==4.8.5`, reavaliação 2026-10-04 ou mudança de threat model. O título ainda diz pendente. Os quatro CVEs são estado documentado; não foi executada auditoria online nova nem confirmada a disponibilidade atual de correção upstream.

**Causa e impacto:** perfil RAG depende de stack maior e resoluções por plataforma. Gate humano valida preenchimento/data/versão (`scripts/verify_supply_chain.py:144`–`:157`), mas não expiração da reavaliação. Um registro completo pode continuar aceito depois do prazo.

**Prioridade/dependências/fase:** P1 alta antes de próxima release afetada; registrar status correto em P0, robustecer gate/evidência em P4. Decisão de aceitação do risco pertence ao mantenedor.

**Solução mínima:** política residual estruturada com expiração verificável e relógio injetável; manter separação entre raw audit e decisão de allowlist. Reexecutar audit e verificar correções upstream na implementação/release. Mudança de versão/advisory/threat model exige nova decisão. Alinhar claims ao que CI e artefatos efetivamente comprovam por perfil/OS/Python.

**Alternativa/trade-off:** remover RAG elimina exposição desse perfil, mas retira capacidade central; trocar banco exige avaliação de compatibilidade e desempenho. Atualizar cegamente não constitui mitigação comprovada.

**Aceite verificável:** prazo vencido, versão divergente, novo advisory, falta de raw audit ou mudança de threat model bloqueiam o gate aplicável; audit vulnerável mantém exit code cru mesmo quando política aceita mitigação (`scripts/audit_dependencies.py:104`); Python tolerado não é reportado como suportado; wheel/core/RAG mantêm evidência independente. Preservar `tests/test_dependency_evidence.py:10` e `tests/test_support_matrix.py:292`.

## 12. Manutenção estrutural

**Estado/classificação:** concentração confirmada, não necessidade de reescrita geral. `docops/operations.py` reúne aquisição (`:484`), plano (`:817`), staging (`:1510`), promoção (`:1731`), recuperação (`:1944`), autorização (`:2313`), publicação (`:2941`), rollback (`:3157`), aplicação (`:3438`) e inspeção (`:3943`). Evidência é diversidade de responsabilidades, não contagem de linhas. Fachada em `docops/lifecycle.py:333` delega operações e preserva API.

**Causa e impacto:** expansão de capacidades em módulo central aumenta custo de revisão e risco ao alterar promoção/recuperação. Outra fachada rasa sem mover regras adicionaria indireção sem reduzir esse risco.

**Prioridade/dependências/fase:** P2 média; baseline comportamental em P0, extrações pequenas associadas às seams necessárias em P1–P4. Corrigir falhas confirmadas antes de mover seu código.

**Solução mínima:** extrair unidades coesas: aquisição/planejamento, transação de geração/recuperação, política de publicação, histórico/restauração. Cada interface esconde uma decisão e seus invariantes. Manter importações públicas, códigos de erro e contratos durante expand-contract. Não combinar refactor amplo com nova regra comercial no mesmo ticket.

**Alternativa/trade-off:** fragmentação por tamanho ou um microserviço por módulo aumenta coordenação sem justificar benefício. Reescrita total sacrifica proteções já existentes. Extração incremental custa mais disciplina, mas oferece comparação objetiva antes/depois.

**Aceite verificável:** respostas públicas, recusas, atomicidade, recovery e rollback equivalentes; testes públicos existentes continuam passando; dependências sem ciclo; cada extração possui responsabilidade explícita e remove decisão da origem, em vez de apenas delegá-la por mais uma camada.

## Verificação efetivamente executada e limites

Nesta auditoria foi executado, com o Python disponível no host:

```text
python -m pytest -q tests/test_source_registry.py tests/test_formats_portuguese.py tests/test_reader_sessions.py tests/test_rag_snapshots.py tests/test_dependency_evidence.py tests/test_support_matrix.py
```

Resultado: **42 passed in 59.90s**. Isso comprova os testes selecionados de registro, formatos/locators, leitores/revogação, snapshots/rebuild, evidência de dependências e matriz. Não comprova benchmark real multilíngue, domínio Mercado Livre, direitos de uma fonte comercial, nova auditoria de CVEs, execução manual multiplataforma ou os riscos de worker acima.

Antes da implementação, cada ticket deve apontar o comportamento público a preservar, primeiro teste RED, mudança mínima GREEN, eventual refactor e comando de validação. Não marcar capacidade como pronta apenas porque o schema existe: provar fluxo completo, persistência, recusa segura e recuperação. Não produzir conteúdo factual Mercado Livre nesta fase como se estivesse verificado; o preset inicial define taxonomia e consultas, e a execução posterior pesquisa, registra e avalia fontes com vigência/região.
