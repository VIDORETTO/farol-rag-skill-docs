# RAGFlow de desenvolvimento fixado

Esta pasta contém somente a configuração local, opt-in e fail-closed do
RAGFlow usado pelos gates Farol 2.0. Importar `docops`, planejar um projeto ou
executar o perfil core nunca inicia containers.

- `dev-lock.json` fixa o repositório oficial, tag `v0.27.2`, commit upstream,
  SDK, serviço TEI e modelo de embedding local esperado.
- `compose.dev.override.yaml` é aplicado sobre o Compose oficial desse commit,
  exige imagem em forma `repository@sha256:<digest>` e publica somente a UI e a
  API em loopback.
- `scripts/prepare_ragflow_dev.py` produz um plano sem efeitos por padrão. O
  modo `--apply` recusa diretório existente que não seja o checkout oficial,
  valida o commit antes de iniciar e não cria token de API nem o grava no
  repositório.

Exemplo de planejamento sem efeitos:

```powershell
python scripts/prepare_ragflow_dev.py --workspace C:\farol-runtime\ragflow --json
```

Quando um digest aprovado estiver disponível, o agente operador pode executar
o mesmo comando com `--image-digest repository@sha256:<64-hex> --apply`. O
perfil inclui Elasticsearch, MySQL, MinIO, Redis e TEI CPU com
`BAAI/bge-small-en-v1.5`; todas as portas publicadas permanecem em loopback. O
token gerado pela instância continua sendo fornecido apenas por
`DOCOPS_RAGFLOW_TOKEN` ao perfil de integração.
