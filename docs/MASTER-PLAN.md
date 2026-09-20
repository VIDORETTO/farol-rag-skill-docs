# Plano master histórico — evolução de projetos de conhecimento

> **Supersedido para trabalho futuro:** este documento registra a evolução
> Farol 1.x e inclui linhas de produto que não pertencem ao Farol 2.0. A fonte
> normativa atual é [`specs/farol-2/`](../specs/farol-2/README.md). Não crie
> novos tickets a partir deste plano.

Data: 2026-09-07. Baseline estudado: `c438c82e6350f9dc4971a355a4f0dcb9931d74c3`, branch `codex/main-consolidation`.
Status: especificação implementada localmente nesta execução; publicação pública, corpus/índice real e autorizações externas continuam fora do escopo.

## Objetivo e diagnóstico

Transformar o pipeline de pacotes existente em um sistema de projetos de conhecimento operado por agente: conversa retomável → decisões registradas → fontes governadas → candidata → avaliação → release → consulta citada → mudança incremental.

O núcleo já oferece operações determinísticas, geração de skill/router, aquisição, registros de fonte, fila, enrichment externo, avaliação e lifecycle. A lacuna principal é a composição dessas capacidades em um projeto com objetivos, curso e página independentes. Não reconstruir o lifecycle nem inserir uma LLM no pacote. Evidências e limitações: [diagnóstico](MASTER-IMPROVEMENT-PLAN.md) e [auditoria técnica](master-evolution/CURRENT-STATE-EVIDENCE.md).

Não confundir três produtos: conhecimento operacional do vendedor, curso sobre um tema e página que apresenta uma oferta. Cada um tem revisão e critérios próprios; a página não pode virar fonte independente para comprovar suas próprias promessas.

## Ordem de leitura e autoridade

1. Este documento: arquitetura, fases e decisões de escopo.
2. [Diagnóstico das 12 hipóteses](MASTER-IMPROVEMENT-PLAN.md): por que cada mudança existe.
3. [SPEC](master-evolution/SPEC.md): comportamento desejado e histórias.
4. [Contratos de estado](master-evolution/STATE-CONTRACTS.md): protocolo e invariantes.
5. [Fontes, RAG e avaliação](master-evolution/KNOWLEDGE-QUALITY.md).
6. Preset de domínio declarativo (documento editorial removido por TK-017).
7. [Roadmap e tickets](master-evolution/ROADMAP.md), [TDD e execução](master-evolution/TDD-EXECUTION.md).

Para fatos atuais, código e evidência executada prevalecem sobre planos anteriores. Para a implementação nova, estes contratos propostos prevalecem sobre sugestões genéricas dos tickets. Se houver conflito entre documentos desta entrega, interromper apenas o ticket dependente e registrar a decisão; não escolher silenciosamente. Segurança existente não é relaxada por omissão do plano.

## Arquitetura alvo

| Módulo | Responsabilidade | Reuso e interface |
|---|---|---|
| Harness externo + skill operacional | Entender conversa, apresentar perguntas, produzir conteúdo derivado | Usa comandos estruturados; não possui autoridade implícita para aprovar |
| Projeto | Sessão de init, revisões, decisões e referências de artefatos | Nova interface pequena para iniciar, responder, inspecionar e finalizar rascunho |
| Mudanças | Validar base, calcular impacto e preparar composição | Adapta plan/preview/apply e lifecycle existentes |
| Fontes | Identidade, versões, direitos, privacidade, vigência e conflitos | Estende registro/reconcile; preserva estados existentes na migração |
| Conhecimento | Normalizar, indexar, recuperar e citar | Mantém MCP local híbrido e readers pinned; filtros de projeto e elegibilidade |
| Derivados | Skill, curso e página com dependências rastreáveis | Conteúdo produzido pelo harness; validação determinística de contrato |
| Publicação | Avaliar, autorizar, promover e reverter composição | Reutiliza candidato, recibo e promoção atômica; sem segundo motor paralelo |
| Operação | Agendar reconcile, executar fila, relatar saúde, recuperar | Scheduler externo supervisiona execução limitada; SQLite/single-writer no MVP |
| Preset | Perguntas, taxonomia, consultas, critérios específicos | Dados declarativos; nenhuma regra Mercado Livre no núcleo |

O projeto referencia pacotes/releases existentes. A nova revisão de projeto não renomeia nem substitui o identificador de geração do pacote. Uma sessão de leitura fixa a composição completa e a identidade do índice. Revogações atuais continuam sobrepondo snapshots históricos.

## Init por conversa

O harness envia respostas estruturadas ao protocolo de projeto; DOCOPS retorna perguntas pendentes e rascunho validado. Não existe chat embutido nem escolha de provedor. Retomar exige identificador da sessão e revisão esperada, nunca reconstruir estado a partir de uma conversa resumida.

Sequência: identificar objetivo e domínio; resolver ambiguidade do curso; definir público/resultado/restrições; escolher entregáveis; registrar fontes e permissões; estruturar curso quando habilitado; estruturar página quando habilitada; apresentar decisões e pendências; finalizar revisão privada. Cada resposta confirmada fica persistida com origem, autor e versão. Respostas já conhecidas não são perguntadas novamente. Correções invalidam apenas os artefatos dependentes.

O init pode terminar com fontes pendentes e sem índice. Preço, garantia, promessas, canal de venda e direitos não podem ser inventados. Decisões ausentes bloqueiam a ação correspondente, não toda a conversa. O protocolo completo, campos e transições estão nos contratos de estado.

## Modelo de mudança

| Entrada | Impacto mínimo | Condição de conclusão |
|---|---|---|
| Nova fonte factual elegível | Corpus + índice candidato | Proveniência e avaliação de recuperação |
| Nova regra ou conflito conceitual | RAG + candidata de skill + derivados afetados | Revisão conceitual e teste do harness |
| Remoção/revogação | Elegibilidade imediata + invalidação transitiva | Readers antigos não revelam fonte; rollback não a ressuscita |
| Novo módulo de curso | Mapa e conteúdo do curso | Objetivos, exercícios e fontes rastreáveis |
| Mudança de página | Especificação da página e claims | Evidência/termos aprovados para claims afetados |
| Mudança de embedding | Snapshot totalmente reconstruído | Comparação de perfis, Golden, troca atômica |
| Correção de decisão | Nova decisão substituindo anterior | Diff explícito de todos os dependentes |

Toda proposta fixa revisão base, inventário de fontes e hash da política. Se qualquer um mudar, replanejar antes de promover. Execução interrompida pode deixar candidata retomável, nunca versão ativa parcialmente atualizada.

## Menor roadmap de valor

**P0 — baseline confiável:** corrigir deriva operacional e provar o comportamento preservado. **P1 — projeto privado:** init retomável, artefatos separados e primeira fonte autorizada. **P2 — conhecimento confiável:** proveniência, PT-BR, conflitos, avaliação e preset. Esses três blocos entregam o MVP de agente com manutenção manual guiada.

**P3 — evolução integrada:** mudanças, dependências, enrichment e composição de releases de curso/página. **P4 — operação confiável:** scheduler, recuperação, backup e gates de distribuição. P0–P4 entregam produto local operável; não significam publicação pública autorizada. **P5 — autonomia restrita:** política explícita para atualizações factuais de baixo risco, somente após evidência operacional. Multi-host e SaaS ficam como visão futura, condicionados a medição de demanda.

Aceites, blockers e fronteiras de paralelismo: [roadmap](master-evolution/ROADMAP.md). Não executar as fases como refatoração horizontal de todo o repositório.

## Decisões e trade-offs

| Decisão | Tipo | Recomendação / pendência |
|---|---|---|
| Continuar sem LLM interna | Arquitetura | Manter contrato existente; observar handshake com harness |
| Single-writer local | Técnica | Manter; scheduler externo antes de daemon/multi-host |
| Aprovação manual padrão | Segurança/produto | Manter; delegação futura escopada, auditável e revogável |
| Curso sobre ML ou vendido no ML | Produto | Pergunta obrigatória no init; nenhuma inferência automática |
| Preço, garantia e resultados prometidos | Produto | Sem defaults factuais; bloquear publicação correspondente |
| Direitos e privacidade das fontes | Governança | Registro de evidência e revisão do responsável; acesso público não equivale a redistribuição autorizada |
| SLO, hardware e orçamento | Operação | Propostas no plano de qualidade; confirmar em piloto medido |
| Dependências residuais | Segurança | Auditoria nova vinculada ao artefato antes de distribuição; histórico não prova situação atual |

Não são decisões pendentes: criar um chatbot, vender dentro do Mercado Livre, usar Redis/Kubernetes ou contratar um provedor. Esses itens não foram solicitados como implementação e não são necessários para o MVP.

## Entrega para a IA implementadora

Entregar um ticket por vez junto dos documentos indicados no guia TDD. Exigir teste de comportamento falhando antes da implementação, evidência do resultado, diff e handoff. Não aceitar como conclusão apenas arquivo criado, schema válido ou teste com adaptador de memória quando o aceite exige MCP real. Revalidar baseline antes de começar, porque os caminhos de evidência desta auditoria são do SHA registrado.
