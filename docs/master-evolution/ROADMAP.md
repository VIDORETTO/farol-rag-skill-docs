# Roadmap, dependências e entrega para implementação

Status de todos os tickets: implementação local verificada nesta execução; fronteiras externas permanecem explicitamente bloqueadas por escopo. Um arquivo por ticket local. Não foram publicadas issues externas. A convenção local em docs mantém os documentos entregáveis junto do planejamento do repositório, em vez de usar área scratch descartável.

## Fases e gates

| Fase | Entrega demonstrável | Gate de saída |
|---|---|---|
| P0 | Contrato operacional confiável | T01: exemplos normativos e flags conferidos com parser, aliases preservados |
| P1 | Projeto privado iniciado e retomado | T02–T04: dois processos retomam mesma sessão, entregáveis opcionais, pacote legado intacto |
| P2 | Perguntas citadas sobre conhecimento governado | T05–T11: fonte autorizada, busca elegível, perfil PT-BR avaliado, conflitos/abstenção, Golden e preset |
| P3 | Mudança de projeto com derivados e release completa | T12–T16: diff/lineage, revogação transitiva, harness retomável, curso/página e promoção atômica |
| P4 | Produto local operável e distribuível | T17–T22: recovery, scheduler, saúde, restore, dependências e wheel/plataformas |
| P5 | Autonomia factual restrita demonstrada | T23–T24: delegação explícita, kill switch e piloto completo |

MVP = P0–P2, manutenção guiada pelo agente e publicação manual. Produto local completo = P0–P4, sujeito a curadoria, decisões de produto e autorização de distribuição. P5 é expansão opcional; não deve atrasar a entrega útil do MVP. Multi-host, SaaS, renderização de página, hospedagem de curso e conectores autenticados de marketplace permanecem fora deste roadmap.

## Tickets em ordem topológica

| Ticket | Fase | Título / entrega | Blocked by | Hipóteses |
|---|---|---|---|---|
| [T01](tickets/01-corrigir-contrato-de-operacao-e-seu-verificador.md) | P0 | Corrigir contrato de operação e seu verificador | — | 9 |
| [T02](tickets/02-iniciar-e-retomar-projeto-por-respostas-estruturadas.md) | P1 | Iniciar e retomar projeto por respostas estruturadas | T01 | 1,2 |
| [T03](tickets/03-finalizar-brief-e-entregaveis-opcionais-revisaveis.md) | P1 | Finalizar brief e entregáveis opcionais revisáveis | T02 | 1,2 |
| [T04](tickets/04-adotar-pacote-existente-sem-alterar-a-geracao-ativa.md) | P1 | Adotar pacote existente sem alterar a geração ativa | T03 | 2 |
| [T05](tickets/05-governar-uma-fonte-do-cadastro-ao-uso-autorizado.md) | P2 | Governar uma fonte do cadastro ao uso autorizado | T04 | 7 |
| [T06](tickets/06-ingerir-transcricao-externa-com-proveniencia-temporal.md) | P2 | Ingerir transcrição externa com proveniência temporal | T05 | 7 |
| [T07](tickets/07-recuperar-apenas-evidencias-elegiveis-do-projeto.md) | P2 | Recuperar apenas evidências elegíveis do projeto | T05 | 7,8 |
| [T08](tickets/08-construir-candidata-multilingue-sem-interromper-leitores.md) | P2 | Construir candidata multilíngue sem interromper leitores | T07 | 8 |
| [T09](tickets/09-distinguir-norma-estrategia-conflito-e-ausencia-de-evidencia.md) | P2 | Distinguir norma, estratégia, conflito e ausência de evidência | T07 | 7,8 |
| [T10](tickets/10-avaliar-candidata-com-golden-do-dominio-e-casos-criticos.md) | P2 | Avaliar candidata com Golden do domínio e casos críticos | T08, T09 | 8 |
| T11 (removido por TK-017) | P2 | Preset de domínio declarativo sem acoplar o núcleo | T03, T05 | 1,7,8 |
| [T12](tickets/12-preparar-mudanca-com-diff-e-impacto-transitivo.md) | P3 | Preparar mudança com diff e impacto transitivo | T04, T05 | 3,12 |
| [T13](tickets/13-revogar-fonte-e-derivados-sem-ressuscitar-conteudo.md) | P3 | Revogar fonte e derivados sem ressuscitar conteúdo | T12, T07 | 3,7 |
| [T14](tickets/14-orquestrar-enriquecimento-externo-retomavel.md) | P3 | Orquestrar enriquecimento externo retomável | T12 | 5 |
| T15 (removido por TK-017) | P3 | Derivados editoriais avaliáveis | T03, T11, T12, T14 | 1,3,5,7 |
| [T16](tickets/16-promover-composicao-do-projeto-de-forma-atomica.md) | P3 | Promover composição do projeto de forma atômica | T10, T13, T15 | 3,6 |
| [T17](tickets/17-recuperar-worker-apos-ultimo-crash-e-proteger-lease-longo.md) | P4 | Recuperar worker após último crash e proteger lease longo | T01 | 4,10 |
| [T18](tickets/18-agendar-reconcile-e-worker-com-parada-e-retomada.md) | P4 | Agendar reconcile e worker com parada e retomada | T05, T17 | 4,10 |
| [T19](tickets/19-expor-saude-e-incidentes-operacionais-acionaveis.md) | P4 | Expor saúde e incidentes operacionais acionáveis | T18 | 10 |
| [T20](tickets/20-restaurar-backup-consistente-de-projeto-e-revogacoes.md) | P4 | Restaurar backup consistente de projeto e revogações | T16, T17 | 10 |
| [T21](tickets/21-vincular-gates-de-dependencia-a-validade-da-mitigacao.md) | P4 | Vincular gates de dependência a validade da mitigação | T01 | 11 |
| [T22](tickets/22-provar-distribuicao-e-operacao-do-produto-local.md) | P4 | Provar distribuição e operação do produto local | T16, T19, T20, T21 | 9,10,11,12 |
| [T23](tickets/23-delegar-apenas-atualizacoes-factuais-de-baixo-risco.md) | P5 | Delegar apenas atualizações factuais de baixo risco | T10, T16, T19, T21, T22 | 6 |
| [T24](tickets/24-validar-piloto-e-entregar-operacao-reproduzivel.md) | P5 | Validar piloto e entregar operação reproduzível | T11, T22, T23 | 1,2,3,4,5,6,7,8,9,10,11,12 |

## Execução pela fronteira

Um ticket é elegível somente quando todos os blockers têm aceite comprovado. A fase indica agrupamento de produto, não uma dependência artificial: T17 e T21 podem ser antecipados depois de T01; T06, T07 e T11 podem avançar após seus próprios blockers. T10 não depende do preset implementado: usa taxonomia especificada e fixtures próprias; T24 prova a integração final.

Trabalho paralelo deve evitar alterações simultâneas no mesmo schema/engine. Se duas fatias tocarem a mesma seam, reservar um responsável pelo contrato e integrar sequencialmente. Não rodar builds de wheel concorrentes no mesmo checkout. Cada ticket deve caber em contexto novo; se a primeira investigação encontrar mudança estrutural maior que o descrito, subdividir antes de editar, conservando comportamento demonstrável e blockers explícitos.

Prefatoração é localizada ao ticket que precisa dela: caracterizar seam pública, extrair responsabilidade sem alterar resultado e então adicionar comportamento. Se for necessária migração ampla, usar expand → migrações por consumidor → contract; manter aliases/formatos antigos até todos os consumidores e o wheel passarem. Não criar ticket “reescrever operations” apenas por contagem de linhas.

## Rastreabilidade das 14 perguntas do brief

| Pergunta | Resposta normativa nesta entrega | Tickets |
|---|---|---|
| 1 Interface/retomada init | STATE-CONTRACTS: protocolo de sessão | T02 |
| 2 Artefatos/schemas | STATE-CONTRACTS: contratos e revisões | T03–T04 |
| 3 Núcleo/preset | MASTER-PLAN e preset declarativo | T11 |
| 4 Fontes/licenças/conflitos | KNOWLEDGE-QUALITY: fontes e claims | T05, T09 |
| 5 Aquisição/transcrições | KNOWLEDGE-QUALITY: aquisição | T05–T06 |
| 6 RAG/router/citação | KNOWLEDGE-QUALITY: consulta elegível | T07–T09 |
| 7 Impacto por mudança | MASTER-PLAN: matriz; STATE-CONTRACTS | T12–T16 |
| 8 Oficial/influencer | KNOWLEDGE-QUALITY: intenção e autoridade | T09 |
| 9 Avaliação/frescor | KNOWLEDGE-QUALITY: Golden e gates | T10 |
| 10 Autonomia segura | KNOWLEDGE-QUALITY: delegação | T23 |
| 11 Operação/rollback | KNOWLEDGE-QUALITY e TDD-EXECUTION | T16–T20 |
| 12 Privacidade/direitos/promessas | KNOWLEDGE-QUALITY e preset | T05, T06, T15 |
| 13 Outros domínios | Preset declarativo, dois projetos de prova | T11, T24 |
| 14 Menor roadmap | Fases e gates acima | P0–P2 |

## Decisões que podem bloquear somente a ação dependente

- Sentido do curso e entregáveis: capturar no init; permitir conhecimento operacional sem curso.
- Direitos/privacidade de fonte real: bloqueiam sua aquisição/uso não autorizado; fixtures sintéticas permitem desenvolver.
- Preço/garantia/provas/canal: bloqueiam publicação da oferta correspondente, não os contratos do projeto.
- Delegação de publicação: ausente significa manual; T23 pode ser testado com autorização sintética.
- Limiares/SLO de piloto: propostas explícitas no plano de qualidade; medir e revisar com justificativa antes de declarar prontidão.
- Auditoria atual de dependências e CI no SHA: bloqueiam distribuição, não escrita dos documentos ou testes locais.

## Checklist de conclusão do ticket

Aceite observado, teste RED relevante, GREEN e regressões pertinentes; contratos e recursos distribuídos atualizados; rollback/recovery demonstrado quando houver mutação; ausência de corpus/segredos nos artefatos; resultados e skips declarados; diagnóstico antigo não confundido com comportamento novo; handoff com próximo ticket elegível. Critério que falhou permanece desmarcado.
