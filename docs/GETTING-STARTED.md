# Instalar e começar a usar o Farol

O Farol transforma seus documentos em um pacote de conhecimento para um agente
de IA. Você pode gerar o primeiro pacote localmente, sem conta, chave de API ou
Docker. A busca factual com RAGFlow e o OCR são recursos opcionais.

## Escolha os recursos

| Você precisa de | Instalação | Credenciais |
| --- | --- | --- |
| Gerar skills, router e documentos normalizados | Core + formatos, padrão | Nenhuma |
| Extrair texto de PDF, DOCX, EPUB, HTML e Markdown | Core + formatos | Nenhuma |
| Reconhecer texto em PDFs escaneados | `--ocr`, Python 3.13 | Nenhuma chave; modelos podem precisar de download inicial |
| Indexar e consultar documentos no RAGFlow | `--ragflow`, Python 3.13, serviço RAGFlow 0.27.2 | Token da sua instância |
| Usar o pacote em um agente de IA | Harness compatível com Agent Skills | Login/chaves do próprio harness, quando exigidos |

O suporte do core cobre Python 3.11–3.13 em Windows, Linux e macOS. Para usar
todos os perfis no mesmo ambiente, escolha Python 3.13. Consulte a
[matriz de suporte](SUPPORT-MATRIX.json) para os limites dos perfis opcionais.

## Instalar a partir do código

Baixe e extraia o ZIP do repositório, ou use Git. Abra o terminal na pasta
extraída, onde está `pyproject.toml`:

```text
python scripts/bootstrap.py
```

No macOS/Linux, use `python3` se `python` não existir. No Windows com vários
Pythons, use `py -3.13 scripts/bootstrap.py`.

O instalador cria um ambiente isolado e informa seu caminho no campo `python`.
Ative esse ambiente antes dos próximos comandos:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux/macOS
source .venv/bin/activate
```

Se a ativação do PowerShell estiver bloqueada, execute diretamente
`.\.venv\Scripts\python.exe -m docops doctor --json`. Não é necessário alterar
a política de execução do sistema. Se o instalador informar `.venv-windows`
ou `.venv-posix`, substitua `.venv` pelo diretório informado.

```text
python -m docops doctor --json
```

O resultado esperado é `"ok": true`. RAGFlow `not_configured` é normal quando
você escolheu somente o core. `farol` e `docops` também são comandos disponíveis
no ambiente ativado.

## Instalar uma wheel baixada

Quando uma release publicar a wheel, baixe também `SHA256SUMS` e confira o hash
do arquivo. Não existe instalação pelo nome no PyPI prometida por este guia.
Na pasta que contém a wheel:

```text
python -m venv .venv
```

Ative o ambiente conforme seu sistema e use o nome exato da wheel baixada:

```text
python -m pip install "./consulta_documentacao-2.0.0rc1-py3-none-any.whl[formats]"
python -m docops doctor --json
```

O exemplo corresponde à candidata `2.0.0rc1`, não a uma versão estável. Para
adicionar recursos em Python 3.13, instale a mesma wheel com
`[formats,ragflow,ocr]`. O diagnóstico funciona mesmo fora do código-fonte.

## Gerar o primeiro pacote

Crie uma pasta `minhas-fontes` com um Markdown de sua autoria. Informe a licença
que realmente se aplica ao material; `MIT` abaixo é um exemplo para material
seu disponibilizado sob essa licença. `private-only` mantém o uso privado.

```text
python -m docops resolve ./minhas-fontes --json
python -m docops plan ./minhas-fontes --output ./meu-pacote --slug meu-pacote --license MIT --redistribution private-only --json
python -m docops run ./minhas-fontes --output ./meu-pacote --slug meu-pacote --license MIT --redistribution private-only
python -m docops validate ./meu-pacote --json
```

Ao instalar pelo código, você também pode usar `documents/fixtures/acme-docs`
como fonte de exemplo. O pacote gerado contém `skill/`, `router/`, `rag/`,
`manifest.json` e `harness.json`.

Carregue `skill/` e `router/` no agente que aceita Agent Skills e forneça o
`harness.json` para a integração factual. O Farol prepara o conhecimento; o
agente escolhido por você produz a resposta. Veja [integração com agentes](HARNESSES.md).

## Habilitar OCR ou RAGFlow

No código-fonte, execute com Python 3.13:

```text
python scripts/bootstrap.py --ragflow
python scripts/bootstrap.py --ragflow --ocr
```

Escolha apenas a linha correspondente aos recursos desejados. Esses comandos
usam `.venv-rag`, preservando o ambiente do core. Ative
`.venv-rag/Scripts/Activate.ps1` no Windows ou `.venv-rag/bin/activate` no Bash.
OCR instala dependências grandes; não é necessário para PDFs que já têm texto.
Os perfis não instalam ferramentas de desenvolvimento sem `--dev`.

### Obter as credenciais do RAGFlow

1. Use uma instância RAGFlow 0.27.2 sua ou fornecida pelo administrador.
   Para hospedar localmente, veja o [ambiente Docker fixado](../config/ragflow/README.md).
2. Entre na interface dessa instância e gere sua chave na área de API conforme
   o [guia oficial de chave RAGFlow](https://ragflow.io/docs/dev/acquire_ragflow_api_key).
3. Configure um modelo de embedding na instância para indexar documentos.
   O ambiente de desenvolvimento do Farol inclui TEI local; provedores externos
   podem exigir suas próprias credenciais. Veja o
   [guia oficial de modelos](https://github.com/infiniflow/ragflow/blob/v0.27.2/docs/guides/models/llm_api_key_setup.md).
4. Obtenha do administrador a URL da API e o digest da imagem em execução.
   Para Docker, `docker inspect <container> --format '{{.Config.Image}}'`
   mostra a referência usada. Ela precisa estar fixada em `repository@sha256:...`;
   uma tag isolada não comprova a imagem em execução.

Cada usuário usa sua própria credencial. O download do Farol não contém uma
chave compartilhada. O token do RAGFlow não é uma chave de provedor de LLM.

### Configurar a sessão sem gravar o token no histórico

Substitua a URL e o digest pelos valores da sua instância. PowerShell:

```powershell
$env:DOCOPS_RAGFLOW_ENDPOINT = 'https://ragflow.sua-empresa.example'
$env:DOCOPS_RAGFLOW_IMAGE_DIGEST = 'infiniflow/ragflow@sha256:SEU_DIGEST_REAL'
$env:DOCOPS_RAGFLOW_SDK_VERSION = '0.27.2'
$farolToken = Read-Host 'Token da sua instância RAGFlow' -AsSecureString
$env:DOCOPS_RAGFLOW_TOKEN = [System.Net.NetworkCredential]::new('', $farolToken).Password
Remove-Variable farolToken
python -m docops doctor --require-ragflow --json
```

Bash:

```bash
export DOCOPS_RAGFLOW_ENDPOINT='https://ragflow.sua-empresa.example'
export DOCOPS_RAGFLOW_IMAGE_DIGEST='infiniflow/ragflow@sha256:SEU_DIGEST_REAL'
export DOCOPS_RAGFLOW_SDK_VERSION='0.27.2'
read -r -s -p 'Token da sua instância RAGFlow: ' DOCOPS_RAGFLOW_TOKEN
export DOCOPS_RAGFLOW_TOKEN
python -m docops doctor --require-ragflow --json
```

O diagnóstico confirma autenticação e conectividade sem indexar seus documentos.
Para desenvolvimento local em `http://127.0.0.1:9380`, configure também
`DOCOPS_RAGFLOW_ALLOW_INSECURE_LOCALHOST=1`. Endpoints remotos exigem HTTPS.
As variáveis valem para a sessão atual. Para automação, use o gestor de segredos
do seu ambiente; arquivos `.env` não são carregados automaticamente pelo Farol.

Com o diagnóstico aprovado, acrescente `--index-rag` ao comando `plan` e depois
ao `run` para o pacote que você autorizou a enviar à instância. Mudanças no
modelo de embedding exigem reconstrução completa do índice. Nunca reutilize
um índice de outro perfil como se fosse compatível.

## Resolver problemas

| Sintoma | Próximo passo |
| --- | --- |
| `python` não encontrado | Instale Python 3.11–3.13; tente `py -3.13` no Windows ou `python3` no Linux/macOS. |
| `No module named docops` | Ative o ambiente informado pelo bootstrap ou use o executável do campo `python`. |
| `unsupported_python` | Execute o bootstrap RAGFlow/OCR com Python 3.13. |
| `venv_python_mismatch` | Preserve o ambiente antigo; prepare o perfil em uma nova pasta com Python 3.13. |
| Ambiente criado com `--no-install` | Execute novamente o bootstrap sem essa flag; pip será preparado se estiver ausente. |
| `token_missing` | Gere/recupere sua chave na instância e configure-a nesta sessão. |
| `endpoint_invalid` | Use URL HTTP(S) válida, sem usuário, senha, query ou fragmento; HTTPS remoto. |
| `image_digest_missing_or_unpinned` | Peça ao administrador a referência exata da imagem em execução. |
| RAGFlow indisponível | Confirme que o serviço iniciou, a URL é acessível e o token tem acesso à instância. |
| Fonte sem licença conhecida | Confirme os direitos antes de processar ou distribuir seus derivados. |

## Atualizar e remover

Antes de atualizar, preserve seus pacotes e dados. Para instalação pelo código,
baixe a versão escolhida e execute novamente o bootstrap com os perfis usados.
Para wheel, instale a nova wheel com `python -m pip install --upgrade` e os
mesmos extras; depois execute `doctor` e valide os pacotes existentes.

Para desinstalar o pacote do ambiente ativado, use
`python -m pip uninstall consulta-documentacao`. O comando não apaga seus
documentos nem o RAGFlow. Você pode remover manualmente o ambiente virtual
depois de desativá-lo. Para suporte, informe versão, sistema, comando e saída
redigida conforme a [política de suporte](../community/SUPPORT.md).
