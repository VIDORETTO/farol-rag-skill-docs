# Decisão humana pendente — risco residual ChromaDB

Este arquivo é um gate de publicação, não uma declaração de auditoria limpa.
O perfil RAG usa `chromadb` somente pelo `PersistentClient` local, com MCP
`stdio`, sem `HttpClient`, `trust_remote_code` ou repositório remoto de modelo.

O `pip-audit` cru continua sendo a fonte de verdade para vulnerabilidades. Os
quatro advisories conhecidos precisam permanecer visíveis no relatório:

- `CVE-2026-45829`
- `CVE-2026-45830`
- `CVE-2026-45831`
- `CVE-2026-45833`

## Registro do mantenedor

Antes de qualquer release, um mantenedor deve preencher esta seção com a
decisão `accept`, `mitigate`, `upgrade` ou `remove`, incluindo nome, data,
versão auditada, justificativa e prazo de reavaliação. Enquanto o registro não
estiver preenchido, `scripts/verify_candidate.py --release` deve falhar.

| Campo | Valor obrigatório | Estado atual |
|---|---|---|
| decisão | `accept`, `mitigate`, `upgrade` ou `remove` | `mitigate` |
| responsável | identidade do mantenedor | `VIDORETTO` — administrador autenticado do repositório nesta execução |
| data | ISO-8601 | `2026-09-04` |
| versão | versão efetivamente auditada | `chromadb==1.5.9`; `knowledge-rag==4.8.5` |
| justificativa | motivo verificável da decisão | o produto usa somente `PersistentClient` local e MCP `stdio`; não expõe HTTP Chroma, `HttpClient`, `trust_remote_code` ou repositório remoto de modelos. O candidato mantém a configuração local, não distribui cache/corpus e conserva o audit cru visível. Isso reduz o alcance dos quatro advisories, mas não os remove. |
| reavaliação | data ou condição objetiva | `2026-10-04`, ou imediatamente se HTTP/servidor Chroma, modelo remoto, `trust_remote_code` ou uma correção upstream forem introduzidos |

Esta decisão foi autorizada pelo proprietário do projeto nesta execução. Ela é
uma mitigação delimitada, não uma declaração de auditoria limpa; qualquer
mudança do threat model exige nova revisão e novo candidate.
