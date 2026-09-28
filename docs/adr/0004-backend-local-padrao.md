# ADR 0004 — Backend factual local como padrão; RAGFlow opt-in

## Contexto

A ADR 0001 tornou o RAGFlow o backend estratégico e padrão do Farol 2.0.
Na prática, um pacote sem RAGFlow fica `corpus-ready` e não é consultável, e
o RAGFlow pede Docker, serviço persistente, token, digest fixado e uma máquina
bem maior que a de um usuário comum. O Farol 3.0 tem como objetivo ser baixado
e usado com qualquer IA, sem serviço externo obrigatório.

## Decisão

- O backend factual padrão passa a ser `local-fts`: SQLite FTS5 (BM25) da
  biblioteca padrão do Python, indexando blocos da IR canônica com locators.
- RAGFlow continua suportado atrás do mesmo `KnowledgeBackend`, como perfil
  avançado opt-in para parsing profundo e retrieval em escala.
- Busca semântica local é um extra opcional (`semantic`), medido antes de virar padrão.

## Consequências

- Um pacote gerado sem serviços externos passa a ser consultável pelo MCP.
- A invariante “sem dois backends com claims diferentes” é substituída por:
  ambos os backends obedecem ao mesmo contrato de citação, elegibilidade e
  revogação, validado por testes de contrato compartilhados.
- A IR continua sendo a autoridade; índices locais e RAGFlow são reconstruíveis.
- Claims de escala do backend local só com benchmark medido (TK-115).

## Alternativas rejeitadas

- Manter RAGFlow obrigatório: inviável como primeira experiência.
- Vector DB embutido como padrão (Chroma, LanceDB): adiciona dependência pesada
  sem ganho medido para fatos literais; reavaliado pelo TK-114.
