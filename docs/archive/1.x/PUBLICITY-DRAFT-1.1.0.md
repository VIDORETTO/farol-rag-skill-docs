# Divulgação 1.1.0 — executada no GitHub Release

> Status: mensagem publicada somente no [GitHub Release v1.1.0](https://github.com/VIDORETTO/agent-knowledge-kit/releases/tag/v1.1.0)
> após verificação do artefato e canário externo. Não foi enviado para contas
> ou canais externos.

## Mensagem curta

O **Farol** 1.1.0 prepara documentação para agentes como uma
skill estruturada, um roteador e, opcionalmente, um índice RAG local via MCP.
O pacote não inclui LLM, provedor, serviço hospedado, corpus adquirido ou
cache de modelo. O fluxo mínimo é resolver a fonte, executar `run`, validar o
pacote e avaliar as consultas revisadas.

## O que apontar

- Release notes: [`docs/RELEASE-NOTES-1.1.0.md`](RELEASE-NOTES-1.1.0.md).
- Instalação e limites: `README.md`, `docs/USE.md` e `docs/PUBLISHING-POLICY.md`.
- Segurança: `SECURITY.md`.
- Suporte: `docs/SUPPORT-MATRIX.json`.
- Evidência de assets: checksums, SBOM e provenance anexados à release
  aprovada.

## O que não afirmar

- Não dizer que o pacote executa LLM, escolhe provedor ou oferece RAG remoto.
- Não prometer suporte fora da matriz verificada.
- Não chamar o raw `pip-audit` de limpo enquanto o residual Chroma existir.
- Não divulgar corpus, consultas, prompts, logs, caches, tokens ou caminhos
  privados.
- Não iniciar divulgação ampla antes da observação controlada de 24 horas.

## Destinos e aprovação

O único destino desta versão é o próprio GitHub Release, com README/changelog
coerentes no repositório. Registry e canais externos ficam explicitamente fora
do escopo; não houve anúncio para contas externas. Publicação registrada em
`2026-09-04T20:18:45Z`; a janela de observação está no
[`POST-RELEASE-HANDOFF-2026-09-04.md`](POST-RELEASE-HANDOFF-2026-09-04.md).
