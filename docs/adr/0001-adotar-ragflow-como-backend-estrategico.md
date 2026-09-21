# ADR 0001 — Adotar RAGFlow como backend estratégico

## Contexto

O Farol 1.x usa `knowledge-rag==4.8.5` por MCP local. Essa combinação é leve e
portátil, mas a nova direção exige OCR, reconhecimento de layout e tabelas,
parsing profundo, estratégias de chunking e retrieval configurável. O RAGFlow
oferece essas capacidades, ao custo de uma operação mais pesada por Docker e
serviços persistentes.

Referências verificadas em 2026-09-11: [RAGFlow v0.27.2](https://github.com/infiniflow/ragflow/releases/tag/v0.27.2),
[README oficial](https://github.com/infiniflow/ragflow) e
[DeepDoc](https://github.com/infiniflow/ragflow/tree/main/deepdoc).

## Decisão

RAGFlow será o backend estratégico e padrão do Farol 2.0, executado fora do
processo Python do core. `knowledge-rag` será encapsulado como adapter legado
somente durante expand–contract, comparação e rollback; será removido depois dos
gates de paridade.

O Farol não adotará o chat, agente ou seleção de LLM do RAGFlow. A integração
de lifecycle usará a interface autenticada do backend; leitura pode expor MCP
quando isso não reduzir o contrato de citação.

## Motivo

A decisão otimiza fidelidade documental e qualidade de retrieval, que são o
objetivo do produto. Manter `knowledge-rag` para sempre criaria dois backends
com claims e comportamento diferentes; substituição direta impediria paridade e
rollback verificáveis.

## Consequências

- RAGFlow é índice reconstruível; não é fonte de verdade do Farol.
- O core continua instalável sem iniciar RAGFlow, mas não declara pacote factual
  ativo quando o backend obrigatório está indisponível.
- Compose local é fornecido para desenvolvimento; produção nunca é administrada
  implicitamente.
- A remoção do adapter legado exige gates de qualidade e recuperação.

## Alternativas rejeitadas

- Permanecer em `knowledge-rag`: preserva leveza, mas não atende a fidelidade
  escolhida.
- Manter dois backends permanentes: amplia a matriz de compatibilidade e torna
  qualidade dependente da instalação.
- Incorporar RAGFlow ao core Python: acopla o produto à infraestrutura e quebra
  sua neutralidade operacional.
