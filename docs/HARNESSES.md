# Harnesses e contrato de integração

O Farol entrega a cada agente de IA (harness) duas coisas: **Agent Skills**
(`SKILL.md` + capítulos, uma por fonte, mais **um** router do projeto,
`<projeto>-router`, que lista as skills) e o servidor **MCP**
`farol` (stdio, somente leitura). O harness escolhe o modelo e escreve a
resposta final; o Farol nunca chama modelo.

## Conectar

```bash
farol connect claude-code --target ~/meu-repositorio
```

| Harness | Skills | MCP | Verificado em 2026-09-28 |
|---|---|---|---|
| `claude-code` | `.claude/skills/<fonte>/` | `.mcp.json` (`type: stdio`) | listado pelo Claude Code 2.1.283; resposta real com citações `path:linha` via MCP |
| `codex` | `.agents/skills/<fonte>/` | `.codex/config.toml` (bloco gerenciado) | `codex mcp list` lista `farol` como `enabled` |
| `cursor` | via MCP (`get_skill`) + `.cursor/rules/farol.mdc` | `.cursor/mcp.json` | formato conforme documentação oficial |
| `opencode` | `.opencode/skills/<fonte>/` | `opencode.json` (`type: local`) | `opencode mcp list` mostra o servidor como conectado |
| `generic` | pastas indicadas | JSON impresso | qualquer cliente MCP stdio |

Conexões feitas pelo Farol 3.0 instalavam um router por fonte; o próximo
`farol connect` remove esses arquivos e instala o router único.

`--scope user` configura o usuário (`~/.claude/skills`, `~/.codex/config.toml`…)
em vez de um repositório; `--dry-run` mostra as mudanças; `--remove` desfaz.
Arquivos de configuração que você não editou depois do `connect` voltam
byte a byte ao original; nos demais, só a entrada `farol` é removida.

## Ferramentas MCP

| Ferramenta | Uso |
|---|---|
| `list_skills` | skills disponíveis (uma por fonte, mais routers) e capítulos |
| `get_skill` | `SKILL.md` ou um capítulo, para conceitos e decisões |
| `search_knowledge` | fatos literais com `citation` (`path:linha`, página ou `(at HH:MM:SS)`), `block_id` e `risk` |
| `get_context` | blocos vizinhos de um hit (`block_id`, `before`/`after`) ou a seção inteira (`scope: section`), limitado por `max_tokens` |
| `get_document` | blocos de um documento, em ordem; `offset`/`limit` paginam documentos longos (um livro inteiro) |

Sem evidência, `search_knowledge` retorna `insufficient_evidence`; o agente deve
abster-se em vez de adivinhar. Todo texto retornado vem marcado como conteúdo
não confiável; blocos com diretivas para IA (`risk: high`) nunca são retornados.

## Contrato do pacote

`harness.json` de cada pacote declara a geração ativa, as skills e o bloco
`mcp` (`command`, `args`, `tools`), sem caminhos pessoais nem credenciais. O
contrato canônico está em `schemas/harness.schema.json`.

## Backend RAGFlow (opcional)

Com o extra `ragflow` (Python 3.13) e uma instância RAGFlow 0.27.2 própria, a
integração factual pode usar o RAGFlow em vez do índice local. Configure fora do
repositório:

```text
DOCOPS_RAGFLOW_ENDPOINT=https://...
DOCOPS_RAGFLOW_TOKEN=<secret>
DOCOPS_RAGFLOW_IMAGE_DIGEST=<repository>@sha256:<64-hex>
DOCOPS_RAGFLOW_SDK_VERSION=0.27.2
```

O core não inicia o RAGFlow automaticamente; endpoints remotos exigem HTTPS.
A evidência histórica da integração RAGFlow 0.27.2 está em
[specs/farol-2/evidence](https://github.com/VIDORETTO/farol-rag-skill-docs/blob/main/specs/farol-2/evidence/TK-013.md).
