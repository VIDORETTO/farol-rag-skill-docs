<!-- docs-gate: proposal -->

# Decisões Farol 3.1

Estado: **propostas** em 2026-10-06, aguardando confirmação do mantenedor. As
decisões D-301, D-302 e D-305 são **regras de adoção por medição**: o ticket
implementa a opção e a medição decide o padrão; não exigem escolha prévia de
modelo, só a confirmação do critério.

Fatos verificados para estas decisões (fastembed 0.8.1, listas
`TextCrossEncoder.list_supported_models()` e `TextEmbedding.list_supported_models()`
em 2026-10-06):

- Rerankers: `Xenova/ms-marco-MiniLM-L-6-v2` e `-L-12-v2` (Apache-2.0, só inglês,
  0,08–0,12 GB); `BAAI/bge-reranker-base` (MIT, 1,04 GB); `jinaai/jina-reranker-v1-*-en`
  (Apache-2.0, inglês); `jinaai/jina-reranker-v2-base-multilingual`
  (**CC-BY-NC-4.0**, não comercial).
- Embeddings multilíngues: `paraphrase-multilingual-MiniLM-L12-v2` (atual, 384,
  Apache-2.0, 0,22 GB); `paraphrase-multilingual-mpnet-base-v2` (768, Apache-2.0,
  1,0 GB); `intfloat/multilingual-e5-large` (1024, MIT, 2,24 GB);
  `Qwen/Qwen3-Embedding-0.6B-Q` (1024, Apache-2.0, 1,12 GB);
  `minishlab/potion-multilingual-128M` (256, MIT, 0,51 GB, estático e rápido);
  `google/embeddinggemma-300m` (licença Gemma).

| ID | Decisão | Recomendação | Consequência | Bloqueia |
|---|---|---|---|---|
| D-301 | Reranker local: padrão ou opt-in, e qual modelo. | **Opt-in** (`FAROL_RERANKER=<modelo>` ou `farol.json` → `retrieval.reranker`), candidatos com licença permissiva: `BAAI/bge-reranker-base` e `Xenova/ms-marco-MiniLM-L-12-v2`. Vira padrão do extra `semantic` **somente** se cumprir AC-204 inclusive nas perguntas em português. Modelos NC nunca são padrão. | Sem rebuild de índice (rerank é pós-recuperação). | TK-204 |
| D-302 | Modelo de embedding padrão do extra `semantic`. | Benchmark de `paraphrase-multilingual-mpnet-base-v2`, `multilingual-e5-large`, `Qwen3-Embedding-0.6B-Q` e `potion-multilingual-128M` contra o atual. Adotar o melhor **se** recall@5 da validação subir ≥ 0,05 e o build do livro de 500 páginas ficar ≤ 3× o tempo atual em 2 vCPU; senão manter o atual e registrar. | Troca exige rebuild completo e evidência nova (`AGENTS.md`); `farol build` reconstrói sozinho (`docs/COMPATIBILITY.md`). | TK-205 |
| D-303 | Expor o protocolo de tarefas por MCP (escrita) ou só por CLI + skill. | **Manter MCP read-only**; o loop fica em `farol task …` conduzido pela skill `farol-distill`. Preserva o modelo de ameaça do TK-113. | Nada muda no servidor MCP além das tools de leitura. | TK-208 |
| D-304 | Skill composta convive com as skills por fonte ou as substitui. | **Convive**; membros podem optar por `--no-skill`. O pacote composto mora em `packages/@<nome>/` com `manifest.json` de `kind: composite` e não tem índice próprio (a busca continua nos membros). | Chave aditiva `skills[]` em `farol.json` (schema 1). | TK-211 |
| D-305 | Docling para PDF digital (layout/tabelas). | Novo extra `layout` reaproveitando o pin de `docling` do extra `ocr`; usado automaticamente quando instalado **se** a aceitação não regredir (recall@5/MRR@5 do Pro Git e do paper) e os casos novos de tabela passarem; senão fica atrás de `--layout`. | Fidelidade `structured-native` para PDF digital com o extra. | TK-212 |
| D-306 | Escopo de slides de videoaula. | P3, opt-in `--slides`, exige `ffmpeg` no PATH + extra `ocr`; só texto de quadros-chave por mudança de cena, nunca interpretação de imagem. Pode ser adiado sem afetar o 3.1. | Ticket em rascunho. | TK-213 |
| D-307 | Contração do legado 2.0 para o 4.0. | Só depois do relatório de alcance (TK-216) e de um minor com `deprecations` + aviso. Exige autorização explícita (invariante do `AGENTS.md`). | TK-217 permanece `draft`. | TK-217 |
| D-308 | Versão e publicação. | Publicar como **3.1.0** (só adições). PyPI continua decisão separada, como no 3.0. | Tag/release só com autorização. | TK-218 |

## Seams de teste

Os seams S1–S9 de `specs/farol-3/plan.md` continuam válidos; o [plano](plan.md)
propõe S10 (rerank/score global), S11 (aquisição de playlist com cliente falso) e
S12 (conversor de layout falso). Novo seam além desses exige revisão do plano.
