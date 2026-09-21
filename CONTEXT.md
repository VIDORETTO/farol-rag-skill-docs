# Contexto de domínio do Farol

## Projeto de conhecimento

Unidade governada que reúne objetivo, fontes, taxonomia, skills, índice factual,
revisões e políticas. Uma fonte pode alimentar várias skills, e uma skill pode
ser sustentada por várias fontes.

_Evitar:_ pacote de curso, chatbot, base de documentos.

## Fonte

Origem registrada de conhecimento, com identidade, revisão, proveniência,
direitos, vigência e política de uso. Arquivo e documento são representações
possíveis de uma fonte, não seus sinônimos.

_Evitar:_ arquivo, upload, verdade.

## Artefato de fonte

Item adquirido de uma fonte, como arquivo, página web ou objeto de repositório,
identificado por conteúdo e revisão.

_Evitar:_ chunk, documento RAG.

## Representação intermediária canônica (IR)

Representação versionada e independente de backend que preserva estrutura,
conteýo, locators, proveniência e qualidade de extração. É a autoridade comum
para síntese conceitual e indexação factual.

_Evitar:_ Markdown normalizado, chunks do RAGFlow, texto extraído.

## Fidelidade de extração

Capacidade comprovada de uma extração preservar os elementos relevantes do
formato e seus locators. Usa os níveis `structured-native`, `text-fallback`,
`external-converter`, `metadata-only` e `unsupported`.

_Evitar:_ formato suportado, compatível.

## Taxonomia

Mapa hierárquico aprovado de assuntos e capacidades do projeto. Define ownership
conceitual, cobertura obrigatória e dependências entre skills.

_Evitar:_ sumário do livro, árvore de arquivos, categorias do backend.

## Skill temática

Artefato conceitual compacto que ensina modelos mentais, decisões e padrões de
um assunto da taxonomia, com capítulos sob demanda e lineage verificável.

_Evitar:_ resumo de documento, cópia da fonte, resposta factual.

## Lineage conceitual

Relação auditável entre uma afirmação sintetizada e os blocos da IR que a
sustentam, permitindo conflito, atualização e revogação seletivos.

_Evitar:_ bibliografia genérica, link sem locator.

## Candidata

Composição imutável ainda não ativa, contendo revisões coordenadas de IR,
taxonomia, skills, router e índice. Somente uma candidata aprovada e validada
pode substituir a geração ativa.

_Evitar:_ rascunho mutável, índice temporário.

## Router global

Regra do projeto que classifica a intenção da consulta, escolhe skills
temáticas e decide entre orientação conceitual, evidência factual ou ambas.

_Evitar:_ roteador por documento, classificador do RAGFlow.

## Backend de conhecimento

Adapter reconstruível que indexa a revisão autorizada da IR e recupera evidência
factual. Não possui autoridade sobre fontes, direitos, taxonomia ou revisions.

_Evitar:_ autoridade do corpus, banco principal, agente.
