# ADR 0003 — Focar o Farol em conhecimento para agentes

## Contexto

Uma evolução anterior incorporou um preset Mercado Livre e contratos genéricos
de curso, página e oferta. Esses artefatos vieram de outro projeto e aumentam
schemas, comandos, testes e lifecycle sem contribuir para o produto confirmado:
fontes transformadas em skills e RAG para agentes.

## Decisão

Farol 2.0 removerá Mercado Livre, curso, página e oferta de seus contratos,
runtime, distribuição, documentação ativa e testes. O histórico continuará no
Git. Infraestrutura realmente genérica de fontes, projetos, políticas, revisões,
presets de conhecimento, candidatas e rollback será preservada.

## Motivo

A remoção reduz conceitos que um agente implementador precisa carregar e
restabelece uma Interface de produto coesa. Manter contratos depreciados por
tempo indefinido perpetuaria o desvio de domínio.

## Consequências

- A mudança é incompatível e será publicada como versão principal 2.0.
- Pacotes 1.x serão migrados por plano, staging e validação; dados editoriais
  excluídos não serão importados silenciosamente.
- Documentos históricos deixam de ser normativos; não haverá reescrita de commits.

## Alternativas rejeitadas

- Manter curso/página como core genérico: mantém complexidade sem consumidor
  confirmado.
- Depreciação indefinida: impede simplificação real da Interface.
- Apagar histórico Git: destrutivo e desnecessário.
