# Capítulo 6 — Config e deploy

Fonte: fastapi-docs/advanced/settings.md, deployment/*.md, environment-variables.md, advanced/behind-a-proxy.md

## Config: pydantic-settings

`BaseSettings` + env vars (str puro nunca direto no handler). `pydantic-settings`
vem com extra `fastapi[all]`; criar submodel `Settings(BaseSettings)` com
`model_config = SettingsConfigDict(env_file=".env")`.

## Deploy (regras mentais)

| Pergunta | Resposta |
|---|---|
| Como rodar | `fastapi run app/main.py` (FastAPI CLI) ou uvicorn |
| Workers | uma p/ cada CPU core ("multiplicador de CPU") — subir excessivo degrade |
| Proxy | `--proxy-headers`/`--forwarded-allow-ips` quando atrás de proxy |
| HTTPS | terminar TLS no proxy/cloud, app HTTP interno |
| Docker | imagem oficial (uvicorn + build), app no container como 127.0.0.1 |

## Segredo/versionamento

Nunca commit env com secrets; docs via `fastapi-docs/deployment/*` para
conceitos (OS, memory, memory limits).
