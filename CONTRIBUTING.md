# Contribuindo

1. Leia [AGENTS.md](AGENTS.md) e, para o esforço Farol 2.0, o ticket
   correspondente em [specs/farol-2/tickets/](specs/farol-2/tickets/). Os
   planos em `docs/` são históricos quando a documentação normativa indicar isso.
2. Siga o ciclo TDD: teste vermelho, menor implementação, suíte rápida, lint e
   atualização do manifesto/documentação.
3. Não adicione corpora, índices, caches, segredos ou caminhos absolutos de uma
   máquina local. Use fixtures sintéticas em `documents/fixtures/`.
4. Preserve a fronteira: este repositório fornece protocolo, IR, skills, RAGFlow
   externo e roteamento para um harness; não adicione chamadas a LLMs ou chaves
   de provedor ao core.

Comandos mínimos antes de abrir uma contribuição:

```text
python -m pytest
python -m ruff check docops tests scripts
python scripts/audit_release.py --json
python scripts/check_documentation.py --json
python scripts/check_acceptance_matrix.py --check --json
```

Mudanças que alterem a configuração de embedding precisam de reindex completo
e de uma nota no relatório. Mudanças no transporte HTTP/SSE precisam passar por
`python -m docops config-audit <arquivo>` e nunca podem incluir o token no
repositório.
