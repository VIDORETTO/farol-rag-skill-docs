# Briefing histórico para estudo e planejamento master

> **Supersedido:** este briefing originou o preset Mercado Livre e os derivados
> curso/página/oferta, que foram excluídos da direção Farol 2.0. Consulte
> [`specs/farol-2/spec.md`](../specs/farol-2/spec.md). O conteúdo abaixo existe
> apenas como registro do escopo 1.x até o ticket de contração TK-017.

## Instrução para a próxima IA

Estude o repositório atual do `agent-knowledge-kit`, sua documentação, testes,
skills e limites operacionais. Produza um planejamento master para evoluir o
sistema. Não implemente código nesta etapa.

Separe claramente:

1. o que já existe e foi comprovado;
2. o que está parcialmente pronto;
3. o que precisa ser criado;
4. o que é decisão de produto e o que é decisão técnica;
5. o que deve ser genérico no `agent-knowledge-kit` e o que deve ser apenas um
   preset ou projeto de Mercado Livre.

Além do planejamento master, produza um segundo documento de diagnóstico e
melhorias, por exemplo `MASTER-IMPROVEMENT-PLAN.md`. Esse documento deve
confirmar cada problema no código ou nos contratos, explicar seu impacto,
propor a menor solução de alto valor, indicar dependências e definir critérios
de aceite. Não trate decisões deliberadas de segurança como bugs sem explicar
o trade-off.

Não proponha um chatbot genérico. O objetivo é um sistema utilizado pelo
próprio agente de IA, através de um harness externo, skills, router e RAG.

## Visão do sistema

Queremos evoluir o `agent-knowledge-kit` para que um agente possa iniciar e
manter projetos de conhecimento por conversa.

O agente deverá:

- executar um `init` conversacional;
- fazer perguntas somente quando faltarem decisões importantes;
- entender o objetivo do projeto, público, entregáveis e restrições;
- estruturar curso, página, skills, fontes e RAG;
- registrar as decisões em documentos e estado versionado;
- continuar o trabalho quando novas fontes forem adicionadas;
- identificar mudanças, remoções, conflitos e impactos;
- preparar candidatas de atualização e avaliar a qualidade antes de publicar;
- responder consultas usando fontes citadas e declarar quando não houver
  evidência suficiente.

O usuário deve precisar de pouca intervenção depois da configuração inicial,
mas o sistema precisa manter governança para licenças, privacidade, conflitos,
regras comerciais, mudanças conceituais e publicação pública.

## Primeiro caso de uso: inteligência para vendedores do Mercado Livre

O domínio Mercado Livre é o primeiro caso de uso, não deve limitar a arquitetura
do sistema. O núcleo precisa continuar reutilizável para outros projetos e
domínios.

O objetivo é reunir documentação oficial, estratégias, dicas, estudos, testes,
vídeos e diferentes visões para que o agente ajude o vendedor a tomar decisões
melhores. O sistema não deve tratar toda fonte como verdade: deve distinguir
regra oficial, dado factual, opinião, experiência, hipótese e recomendação.

O conhecimento deve cobrir, no mínimo:

- escolha e validação de produtos;
- pesquisa de mercado, concorrência e demanda;
- precificação, margem e custos;
- criação de anúncios;
- títulos, palavras-chave e exemplos;
- descrição e argumentos de venda;
- fotos, imagens e vídeos dos produtos;
- ficha técnica e preenchimento correto do catálogo;
- logística, envio, devoluções e operação;
- reputação, métricas e saúde da conta;
- diagnóstico de produtos sem vendas;
- visitas, cliques, conversão e abandono;
- testes A/B e experimentação;
- publicidade, Ads e campanhas;
- cupons, descontos e promoções;
- aumento de conversão por anúncio e da conta como um todo;
- melhoria contínua baseada em dados;
- políticas, termos, limites e boas práticas oficiais do Mercado Livre.

As fontes devem ser pesquisadas com vários termos, sinônimos e perspectivas.
O planejamento deve propor uma taxonomia e uma lista inicial de consultas para
encontrar fontes complementares sem perder as fontes oficiais.

## Curso e página

O projeto pode gerar um curso estruturado e uma página para apresentá-lo, mas
esses dois artefatos devem ser separados do conhecimento operacional do
vendedor.

O `init` deve capturar:

- mapa de módulos e aulas;
- nível do aluno;
- transformação prometida;
- formato do curso;
- exercícios e exemplos;
- dúvidas e objeções do público;
- estrutura, objetivo e tom da página;
- benefícios, provas, oferta, preço, garantia e chamadas para ação;
- restrições de linguagem e conformidade.

O `AGENTS.md` deve conter apenas instruções estáveis de operação. O brief do
projeto, o mapa do curso, a especificação da página, as decisões e o conteúdo
factual devem ficar em artefatos próprios e/ou no RAG.

Há uma ambiguidade que o `init` precisa resolver: “curso para vender no Mercado
Livre” pode significar um curso sobre como vender no Mercado Livre ou um curso
que será comercializado dentro do Mercado Livre. Essas hipóteses devem ser
tratadas separadamente até o usuário confirmar.

## Fontes e RAG

Cada fonte deve possuir um arquivo próprio ou uma representação persistente
equivalente, com metadados suficientes para rastreamento.

Para cada fonte, considerar:

- identificador estável;
- arquivo, URL ou origem;
- tipo de fonte;
- autor, canal ou organização;
- data de publicação e captura;
- idioma e região;
- autoridade e confiabilidade;
- licença, permissão ou restrição de uso;
- versão, vigência e frequência de atualização;
- se a fonte está ativa, arquivada ou revogada.

Vídeos do YouTube podem entrar como transcrições, mas o plano deve tratar
direitos autorais, permissões, timestamps, resumo derivado e rastreabilidade.
Não assumir que qualquer transcrição pode ser redistribuída em um produto
comercial.

O RAG deve:

- consultar todas as fontes ativas do projeto;
- usar busca híbrida lexical e semântica;
- preservar documento, seção, página, timestamp e versão;
- retornar citações próximas à afirmação;
- priorizar fontes oficiais quando a pergunta for normativa;
- mostrar divergências entre fontes;
- considerar atualidade e região;
- recusar ou sinalizar respostas sem evidência;
- permitir filtros por tema, tipo, autoridade e data;
- avaliar recuperação com perguntas reais do vendedor.

“Consultar todos os arquivos” significa pesquisar o índice global e recuperar
os trechos relevantes, não enviar o conteúdo inteiro de todos os arquivos para
a LLM em cada pergunta.

## Atualização e mudanças futuras

O sistema precisa aceitar posteriormente:

- nova fonte;
- fonte atualizada;
- fonte removida ou revogada;
- novo módulo do curso;
- alteração na estrutura da página;
- nova skill;
- mudança de regra comercial;
- correção de uma decisão anterior;
- conflito entre fontes.

Cada mudança deve gerar uma proposta com impacto identificado. Mudanças
factuais podem atualizar o RAG de forma incremental. Mudanças conceituais
devem gerar uma candidata de skill, avaliação e histórico. Remoções devem
revogar documentos e derivados sem apagar evidências históricas.

O sistema deve ter versões de projeto, candidatas, releases, fontes, skills e
especificações de página. A versão ativa nunca deve ser substituída por uma
execução incompleta.

## Problemas e lacunas já identificados para investigar

Use esta lista como hipótese inicial. Confirme cada item no código, nos testes
e na documentação antes de classificá-lo como resolvido ou como defeito:

1. **Inicialização incompleta:** ainda não existe um `init` conversacional que
   transforme respostas do usuário em brief, mapa do curso, especificação de
   página, registro de fontes, políticas e estado versionado.
2. **Estado do projeto espalhado:** o `AGENTS.md`, documentos de projeto, skills,
   fontes e artefatos dinâmicos ainda precisam de uma separação clara e de
   schemas estáveis.
3. **Mudanças futuras sem produto próprio:** adicionar, remover ou alterar
   fontes, tópicos, skills e seções de página precisa de uma interface de
   mudança, análise de impacto, candidata, diff e rollback compreensíveis para
   o agente.
4. **Autonomia contínua incompleta:** adicionar um arquivo sozinho não dispara o
   ciclo; reconcile e worker dependem de scheduler externo, e a CLI atual
   oferece `work --once`, não um serviço contínuo completo.
5. **Atualização conceitual dependente de ferramenta externa:** o enriquecimento
   profundo da skill depende do `book-to-skill` executado pelo harness, em vez de
   existir um fluxo integrado e observável no sistema.
6. **Publicação deliberadamente manual:** candidatos exigem avaliação,
   aprovação e publicação explícitas. O planejamento deve decidir como permitir
   autonomia segura para fontes confiáveis sem remover os gates necessários.
7. **Governança de fontes insuficiente para um produto comercial:** fontes
   oficiais, influencers, opiniões, testes, regras vigentes, conflitos,
   licenças, privacidade e transcrições precisam de autoridade, data, região,
   validade e política de uso explícitas.
8. **Qualidade de RAG ainda dependente do corpus:** o perfil padrão de embedding
   é focado em inglês; conteúdo PT-BR exige perfil multilíngue e rebuild. O
   Golden Set e os testes observados ainda precisam representar o domínio real,
   múltiplos idiomas, fontes conflitantes, frescor e remoções.
9. **Deriva entre documentação e runtime:** há documentação operacional que
   menciona `work --loop`, enquanto a CLI atual expõe apenas `work --once`. A
   análise deve localizar e eliminar esse tipo de contrato divergente.
10. **Operação e escala limitadas:** o desenho atual é forte para execução local,
    single-writer e estado operacional local, mas precisa de uma história clara
    para scheduler, saúde, alertas, backup, filas, concorrência e crescimento.
11. **Riscos de plataforma e dependências:** Python 3.14 é tolerado localmente,
    não é o alvo declarado, há validação manual desigual entre plataformas e
    existem CVEs residuais documentados do Chroma que exigem decisão antes de
    uma publicação definitiva.
12. **Manutenção estrutural:** a análise deve procurar módulos que concentram
    planejamento, aplicação, promoção, validação e integração demais, além de
    interfaces rasas ou duplicadas que dificultem a evolução.

Para cada item, o documento de melhorias deve registrar:

- evidência encontrada e arquivo/contrato relacionado;
- causa raiz;
- risco e impacto para o agente e para o usuário;
- prioridade e dependências;
- solução mínima recomendada;
- alternativa considerada e trade-offs;
- critério de aceite verificável;
- fase do roadmap em que deve ser tratado.

## Perguntas que o planejamento master precisa responder

1. Qual deve ser a interface do `init` e como a conversa pode ser retomada?
2. Quais artefatos e schemas o `init` deve produzir?
3. Como separar o núcleo genérico dos presets de domínio?
4. Como registrar fontes, licenças, autoridade, vigência e conflitos?
5. Como ingerir arquivos, URLs e transcrições com segurança?
6. Como organizar o RAG, os metadados, o roteamento e as citações?
7. Quando uma mudança atualiza somente o RAG, a skill, a página ou todos eles?
8. Como o agente decide entre fontes oficiais e estratégias de influencers?
9. Como avaliar respostas, recomendações, frescor e qualidade das citações?
10. Como permitir autonomia sem publicar informação frágil ou desatualizada?
11. Como operar scheduler, worker, fila, retries, observabilidade e rollback?
12. Como lidar com privacidade, direitos autorais, termos do Mercado Livre e
    promessas comerciais?
13. Como escalar para outros domínios sem copiar a arquitetura?
14. Qual é o menor roadmap que entrega valor sem criar um sistema frágil?

## Formato esperado do planejamento

Entregue um documento master com:

- diagnóstico do estado atual;
- arquitetura alvo e módulos/interfaces principais;
- fluxo conversacional detalhado do `init`;
- modelo de estado, versões e mudanças;
- estratégia de fontes, transcrições e direitos;
- estratégia de RAG, skills, router e citações;
- taxonomia inicial do domínio Mercado Livre;
- estratégia de avaliação e Golden Set;
- riscos, trade-offs e decisões pendentes;
- roadmap priorizado por fases;
- critérios de aceite por fase;
- recomendações de estabilidade, segurança e operação;
- distinção entre MVP, produto pronto e visão futura.

Entregue também o documento de melhorias do estado atual, sem implementar as
alterações. Ele deve priorizar os problemas acima e distinguir correções de
bugs, melhorias de produto, decisões de arquitetura, trabalho operacional e
itens que devem permanecer como gates de segurança.

Antes de sugerir implementação, confronte cada recomendação com o código,
documentação, testes e contratos existentes no repositório.
