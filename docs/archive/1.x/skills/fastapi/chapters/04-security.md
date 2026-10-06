# Capítulo 4 — Segurança (OAuth2/JWT)

Fonte: fastapi-docs/tutorial/security/*.md, advanced/security/*.md

## Fluxo padrão (per doc)

1. `OAuth2PasswordBearer(tokenUrl="token")` → extrai header Authorization.
2. Na criação de usuário: hash de senha (passlib/bcrypt); nunca armazenar plano.
3. Emissão JWT: payload `{sub: username, exp: 7d}` assinado (PyJWT + secret) —
   JWT **não é criptografia**, é assinatura: payload legível; secrets não no payload.
4. `get_current_user` resolve token; 401 com `WWW-Authenticate: Bearer`.

Atenção: `pyjwt[crypto]` para RSA/ECDSA; `OAuth2PasswordRequestForm` espera
form (não JSON) no `/token`.

## Scopes

`OAuth2PasswordBearer(scopes={...})` + `Security(scoped_dep, scopes=["items"])`
descreve permissões no OpenAPI; a autorização é SEMPRE por código (o scope é
contrato/docs). HTTP Basic (`advanced/security/http-basic-auth.md`) com check
manual seguro (constant-time) quando 100% básico.

## Regra de decisão

| Contexto | Ferramenta |
|---|---|
| User + login app (web/mobile) | OAuth2 password + JWT (tutorial security/oauth2-jwt) |
| S2S | HTTP Bearer ou dependencies por service |
| "Só autenticar, sem conta" | Basic via `HTTPBasic` (com comparar constante) |
