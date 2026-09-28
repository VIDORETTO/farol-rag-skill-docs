# Handoff pós-release — template

Preencha este registro fora do candidate antes de anunciar uma publicação.
Não inclua credenciais, corpus, prompts ou logs sem redaction.

## Identidade da release

| Campo | Registro |
|---|---|
| versão | `1.1.0` |
| tag anotada | preencher após criação autorizada; nunca mover |
| commit/SHA | preencher |
| candidate digest | preencher a partir de `candidate-manifest.json` |
| wheel/checksum/SBOM/provenance | URLs e digests públicos |
| GitHub Release | URL e horário UTC |
| registry | nome, URL, trusted publisher e horário; `none` se não houver |

## Canário externo

| Campo | Registro |
|---|---|
| operador sem checkout do autor | identidade/descrição não sensível |
| plataformas/Python | preencher conforme a matriz |
| canal de instalação | URL/versão exata |
| `docops doctor --json` | resultado redigido |
| fluxo fixture | comando, versão e resultado |
| wheel metadata/checksum | resultado |
| RAG/MCP | somente se o perfil foi anunciado e o cache externo é permitido |
| links/documentação | verificados em |

## Observação

Registre eventos em UTC, sem dados de usuário:

| início | fim | canal | instalações/feedback | incidentes | decisão |
|---|---|---|---|---|---|
| preencher | +24 h | controlado | preencher | nenhum/ID | ampliar ou conter |
| preencher | +72 h | ampliado | preencher | nenhum/ID | manter ou corrigir |

## Contenção e rollback

- Não mova a tag nem edite checksums/assets para corrigir divergência.
- Para defeito de pacote, preserve a release afetada, publique uma versão de
  correção e faça yank no registry somente com autorização do proprietário.
- Para segurança, interrompa a divulgação, use `SECURITY.md` e publique só a
  informação necessária até a correção.
- Para candidate divergente, invalide o candidate, gere uma nova versão e
  repita CI, supply chain e canário.

## Aprovações pendentes

Registre nome/identidade, data e escopo do mantenedor para risco Chroma,
settings do GitHub, registry/trusted publishing e cada canal de divulgação.
