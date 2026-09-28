<!-- docs-gate: proposal -->

# Decisões Farol 3.0

Registradas em 2026-09-28 por delegação explícita do mantenedor (“tome as
melhores decisões, as recomendadas para o projeto”). Todas adotam a
recomendação das specs; qualquer uma pode ser revista por nova revisão desta página.

| ID | Decisão | Consequência |
|---|---|---|
| D-01 | **Backend factual local padrão: SQLite FTS5 (BM25), stdlib.** RAGFlow vira backend avançado opt-in. | ADR [0004](../../docs/adr/0004-backend-local-padrao.md) revê a ADR 0001. Desbloqueia TK-103. |
| D-02 | **YouTube/mídia via extra opcional `media`** (`yt-dlp`, `faster-whisper`), só legendas/áudio, `rights` e `purpose` obrigatórios, redistribuição bloqueada. | Desbloqueia TK-107. Nenhuma dependência nova no core. |
| D-03 | **Nome de distribuição `farol-kit`** (PyPI: `farol` já ocupado; `farol-kit` livre em 2026-09-28). Comando principal `farol`; alias `docops` mantido. | Renomear em TK-111; revalidar disponibilidade antes de publicar. |
| D-04 | **Farol 2.0 encerrado como base.** PR #16 já está mergeado em `main` (`90c8229`); 3.0 parte de `main` na branch `farol-3/onda-a`. | TK-020 fica como histórico 2.0; publicação da RC continua dependendo de autorização. |
| D-05 | **Embedding do extra `semantic`: `paraphrase-multilingual-MiniLM-L12-v2` (ONNX, CPU, via fastembed)** — revisado em 2026-09-28: `multilingual-e5-small` não está no fastembed. Vira padrão quando o extra está instalado porque o benchmark AC-124 mostrou ganho (27/31 vs 24/31). | TK-114 implementado. |
| D-06 | **Docs no GitHub Pages do próprio repositório** (MkDocs Material); domínio próprio opcional depois. | Desbloqueia TK-120 (publicação exige autorização). |
| D-07 | **Pacotes demo:** documentação OSS permissiva + 1 livro CC-BY + 1 paper arXiv CC-BY + 1 vídeo CC-BY; cada licença conferida no TK-101 antes do uso. | Desbloqueia TK-120; fontes definidas no manifesto do TK-101. |
| D-08 | **Beta via GitHub Discussions + issues rotuladas `beta`.** | Desbloqueia TK-122 após a release 3.0. |

## Seams de teste

Os seams S1–S9 do [plano](plan.md) ficam confirmados como os únicos pontos de
teste da Onda A em diante; novo seam exige revisão do plano.
